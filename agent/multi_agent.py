"""
车载智能客服多Agent系统
主控编排器 + 6个子Agent，支持事件发射用于可视化。

架构：
  Orchestrator (主控) → 意图识别 → 路由到子Agent
    ├── VehicleStatusAgent   车况查询
    ├── VehicleControlAgent  车控操作
    ├── NavigationAgent      导航服务
    ├── DiagnosisAgent       故障诊断
    ├── AppointmentAgent     预约服务
    └── CustomerServiceAgent 售后咨询
"""
import sys
import os
import re
import time
import json
import queue
import threading
import asyncio
from typing import Optional, Generator, Any

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
if package_root not in sys.path:
    sys.path.insert(0, package_root)

from langchain.agents import create_agent, AgentState
from langchain.agents.middleware import AgentMiddleware, wrap_tool_call
from langchain.tools.tool_node import ToolCallRequest
from langchain_core.messages import ToolMessage, HumanMessage, AIMessage
from langchain_core.tools import BaseTool
from langgraph.runtime import Runtime
from langgraph.types import Command

from model.factory import chat_model
from utils.prompt_loader import load_system_prompt
from utils.logger_handler import logger
from agent.tools.agent_tools import rag_summarize
from rag_agent_project.mcp_servers.mcp_client import get_mcp_tools, set_current_query, get_args_for_call, set_current_call_id


# ============ 事件系统（用于可视化） ============

class AgentEvent:
    """Agent执行事件，用于前端可视化"""
    def __init__(self, event_type: str, **kwargs):
        self.type = event_type
        self.timestamp = time.time()
        for k, v in kwargs.items():
            setattr(self, k, v)

    def to_dict(self) -> dict:
        d = {"type": self.type, "timestamp": self.timestamp}
        for k, v in self.__dict__.items():
            if k not in ("type", "timestamp"):
                if isinstance(v, (str, int, float, bool, type(None), dict, list)):
                    d[k] = v
                else:
                    d[k] = str(v)
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


class EventEmitter:
    """事件发射器，线程安全队列"""
    def __init__(self):
        self._queue = queue.Queue()

    def emit(self, event_type: str, **kwargs):
        event = AgentEvent(event_type, **kwargs)
        self._queue.put(event)
        logger.debug(f"[Event] {event_type}: {kwargs}")

    def get(self, timeout: float = None) -> Optional[AgentEvent]:
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def events(self) -> Generator[AgentEvent, None, None]:
        """生成器：持续产出事件直到收到end/error"""
        while True:
            event = self._queue.get()
            yield event
            if event.type in ("end", "error"):
                break


# ============ 事件感知中间件 ============

class EventMiddleware(AgentMiddleware):
    """拦截工具调用，发射tool_call/tool_result事件"""
    def __init__(self, emitter: EventEmitter, agent_name: str = ""):
        self._emitter = emitter
        self._agent_name = agent_name

    @wrap_tool_call
    def _monitor(self, request: ToolCallRequest, handler):
        tool_name = request.tool_call.get("name", "")
        tool_args = request.tool_call.get("args", {}) or {}
        # 过滤无效的tool_call
        if not tool_name:
            logger.warning(f"[EventMiddleware] 跳过无效工具调用: {request.tool_call}")
            return handler(request)
        tool_call_id = request.tool_call.get("id", "")
        # 在调用工具前设置当前 call_id（供 MCP caller 写入实际参数时使用）
        set_current_call_id(tool_call_id)
        self._emitter.emit(
            "tool_call",
            agent=self._agent_name,
            tool=tool_name,
            args=tool_args,
            call_id=tool_call_id,
        )
        try:
            result = handler(request)
            result_str = ""
            if isinstance(result, ToolMessage):
                result_str = result.content if isinstance(result.content, str) else str(result.content)
            elif isinstance(result, Command):
                result_str = "命令执行"
            # 获取实际参数
            actual_args = get_args_for_call(tool_call_id)
            self._emitter.emit(
                "tool_result",
                agent=self._agent_name,
                tool=tool_name,
                result=result_str[:500] if len(result_str) > 500 else result_str,
                call_id=tool_call_id,
                actual_args=actual_args,
            )
            return result
        except Exception as e:
            self._emitter.emit(
                "tool_result",
                agent=self._agent_name,
                tool=tool_name,
                result=f"执行失败: {str(e)}",
                call_id=tool_call_id,
            )
            raise


# ============ 子Agent定义 ============

# MCP工具名 -> 子Agent映射
SUB_AGENT_TOOL_MAP = {
    "vehicle_status": [
        "get_vehicle_status", "get_battery_status", "get_mileage_info",
        "get_tire_pressure", "get_fault_codes", "get_location",
    ],
    "vehicle_control": [
        "control_air_conditioner", "control_window", "control_sunroof",
        "control_seat", "control_ambient_light", "set_driving_mode",
    ],
    "navigation": [
        # 模拟工具
        "get_common_addresses", "navigate_to", "get_traffic_info",
        # 高德真实API工具（优先使用）
        "search_poi", "geocode", "plan_route", "get_weather", "get_weather_forecast",
        "search_around", "get_location_info",
        # 接入高德skill知识库（RAG）：遇到"高德安全密钥怎么配"、"驾车策略怎么选"等API/平台问题时可检索
        "_rag_summarize",
    ],
    "appointment": [
        "query_service_centers", "get_available_slots", "book_maintenance",
        "book_test_drive", "request_road_rescue", "get_appointment_status",
        "cancel_appointment",
    ],
    "diagnosis": ["_rag_summarize", "get_fault_codes", "get_battery_status", "get_tire_pressure"],
    "customer_service": ["_rag_summarize"],
}

SUB_AGENT_INFO = {
    "vehicle_status": {"name": "车况查询Agent", "desc": "查询电量、续航、里程、胎压、故障码等车辆状态"},
    "vehicle_control": {"name": "车控操作Agent", "desc": "控制空调、车窗、天窗、座椅、氛围灯、驾驶模式"},
    "navigation": {"name": "导航服务Agent", "desc": "路线规划、POI搜索、天气查询、常用地址"},
    "diagnosis": {"name": "故障诊断Agent", "desc": "故障码解读、故障排查建议、紧急处理"},
    "appointment": {"name": "预约服务Agent", "desc": "保养预约、试驾预约、道路救援、网点查询"},
    "customer_service": {"name": "售后咨询Agent", "desc": "质保政策、保养周期、车主权益咨询"},
}


def _build_tool_registry() -> dict:
    """构建工具名->工具对象的注册表（RAG + MCP）"""
    registry = {"_rag_summarize": rag_summarize}
    try:
        mcp_tools = get_mcp_tools()
        for t in mcp_tools:
            registry[t.name] = t
        logger.info(f"[MultiAgent] 工具注册表构建完成，共{len(registry)}个工具")
    except Exception as e:
        logger.error(f"[MultiAgent] 加载MCP工具失败: {e}，将仅使用RAG工具")
    return registry


def _get_sub_agent_tools(sub_agent_key: str, registry: dict) -> list:
    """获取子Agent的工具列表"""
    tool_names = SUB_AGENT_TOOL_MAP.get(sub_agent_key, [])
    tools = []
    for name in tool_names:
        if name in registry:
            tools.append(registry[name])
    return tools


# ============ 主控编排器 ============

ROUTER_PROMPT = """你是一个意图识别路由器。请分析用户的问题，判断属于以下哪个领域，只返回领域标识符（一个单词），不要其他内容。

领域标识符：
- vehicle_status: 查询车辆状态，如电量、续航、里程、胎压、故障码、位置
- vehicle_control: 控制车辆设备，如空调、车窗、天窗、座椅、氛围灯、驾驶模式
- navigation: 导航、路线规划、POI搜索（加油站/充电桩/停车场/餐厅）、天气、常用地址、路况
- diagnosis: 故障诊断、故障码含义、故障排查、异常现象分析、紧急情况
- appointment: 预约保养、预约试驾、道路救援、查询服务网点、查询/取消预约
- customer_service: 售后政策、质保、保养周期、车主权益、退换车、保险理赔等咨询

用户问题：{query}

请只返回领域标识符："""


class VehicleMultiAgent:
    """车载智能客服多Agent系统"""

    def __init__(self):
        self.model = chat_model
        self.system_prompt = load_system_prompt()
        self._tool_registry = None
        self._sub_agents = {}  # sub_agent_key -> agent instance
        self._emitters = {}  # thread-local emitters

    def _ensure_initialized(self):
        """懒加载初始化工具和子Agent"""
        if self._tool_registry is None:
            self._tool_registry = _build_tool_registry()
            self._build_sub_agents()

    def _build_sub_agents(self):
        """构建所有子Agent"""
        for key, info in SUB_AGENT_INFO.items():
            try:
                tools = _get_sub_agent_tools(key, self._tool_registry)
                if not tools:
                    logger.warning(f"[MultiAgent] 子Agent {key} 无可用工具，跳过")
                    continue
                agent = create_agent(
                    model=self.model,
                    system_prompt=self.system_prompt,
                    tools=tools,
                )
                self._sub_agents[key] = agent
                logger.info(f"[MultiAgent] 子Agent已创建: {key} ({info['name']}), 工具数: {len(tools)}")
            except Exception as e:
                logger.error(f"[MultiAgent] 创建子Agent {key} 失败: {e}")

    # 关键词路由表：领域 -> 关键词列表
    KEYWORD_ROUTES = {
        "vehicle_status": ["电量", "续航", "里程", "胎压", "故障码", "车况", "多少电",
                           "剩余", "车在哪", "位置", "电池", "健康度", "还能跑"],
        "vehicle_control": ["打开", "关闭", "调节", "设置", "空调", "车窗", "天窗",
                            "座椅", "氛围灯", "驾驶模式", "温度调", "风量", "加热",
                            "通风", "遮阳帘", "切换模式", "开空调", "关空调", "升窗", "降窗"],
        "navigation": ["导航", "路线", "加油站", "充电桩", "停车场", "餐厅", "天气",
                       "回家", "去公司", "常用地址", "路况", "附近", "洗手间", "医院",
                       "4s店", "怎么走", "去哪", "规划路线", "poi", "兴趣点"],
        "diagnosis": ["故障", "异常", "报警", "警告灯", "不制冷", "不亮", "异响",
                      "失效", "怎么办", "排除", "亮了", "报错", "error", "故障码",
                      "打不着", "启动不了", "刹车", "制动"],
        "appointment": ["预约", "保养", "试驾", "救援", "网点", "维修", "钣喷",
                        "取消预约", "查预约", "服务网点", "到店"],
        "customer_service": ["质保", "保修", "政策", "权益", "退换", "保险", "理赔",
                             "三包", "过户", "积分", "套餐", "终身质保"],
    }

    def _keyword_classify(self, query: str) -> str:
        """关键词预路由：返回得分最高的领域，无匹配返回None"""
        scores = {}
        for domain, keywords in self.KEYWORD_ROUTES.items():
            score = sum(1 for kw in keywords if kw in query)
            if score > 0:
                scores[domain] = score
        if not scores:
            return None
        # 返回得分最高的
        return max(scores, key=scores.get)

    def _classify_intent(self, query: str) -> str:
        """意图分类：先关键词预路由，无匹配再用LLM分类"""
        # 1. 关键词预路由
        kw_result = self._keyword_classify(query)
        if kw_result:
            logger.info(f"[MultiAgent] 关键词路由: {kw_result}")
            return kw_result
        # 2. LLM分类
        prompt = ROUTER_PROMPT.format(query=query)
        try:
            response = self.model.invoke(prompt)
            intent = response.content.strip().lower()
            valid_intents = set(SUB_AGENT_INFO.keys())
            for vi in valid_intents:
                if vi in intent:
                    return vi
            return "customer_service"
        except Exception as e:
            logger.error(f"[MultiAgent] 意图分类失败: {e}")
            return "customer_service"

    # ============ 会话记忆管理 ============
    def _get_session_history(self, session_id: str, max_turns: int = 5) -> list:
        """从反馈数据库读取会话历史（最近N轮）"""
        if not session_id:
            return []
        try:
            from rag_agent_project.api.feedback_db import feedback_db
            history = feedback_db.get_message_history(session_id, limit=max_turns * 2)
            return history
        except Exception as e:
            logger.warning(f"[MultiAgent] 读取会话历史失败: {e}")
            return []

    def _resolve_anaphora(self, query: str, session_id: str) -> str:
        """
        指代消解：处理"第四个"、"第一个"、"它"、"那家"等代词
        将查询改写为包含具体实体引用的版本
        """
        # 检测指代关键词
        anaphora_patterns = [
            r'第([一二三四五六七八九十\d]+)个',
            r'第一个', r'第二个', r'第三个', r'第四个', r'第五个',
            r'去那[个家里地方]', r'就那[个家]',
            r'选[它这那]', r'这[个家]', r'那[个家]',
        ]
        is_anaphora = any(re.search(p, query) for p in anaphora_patterns)
        if not is_anaphora:
            return query

        # 从会话历史中查找最近一次的POI列表
        try:
            from rag_agent_project.api.feedback_db import feedback_db
            history = feedback_db.get_message_history(session_id, limit=10)
            # 反向遍历找到最近的POI列表
            for msg in reversed(history):
                if msg.get("role") != "assistant":
                    continue
                content = msg.get("content", "")
                # 解析POI列表
                pois = self._parse_poi_list(content)
                if pois:
                    # 解析"第N个"
                    cn_map = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
                              "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
                    m = re.search(r'第([一二三四五六七八九十\d]+)个', query)
                    if m:
                        idx_str = m.group(1)
                        idx = int(idx_str) if idx_str.isdigit() else cn_map.get(idx_str, 0)
                        if 1 <= idx <= len(pois):
                            target = pois[idx - 1]
                            # 改写查询
                            new_query = f"导航到{target['name']}（{target['address']}，坐标{target['location']}）"
                            logger.info(f"[MultiAgent] 指代消解: '{query}' → '{new_query}'")
                            return new_query
                    # 通用指代"那个" → 默认第一个
                    if pois:
                        target = pois[0]
                        new_query = f"导航到{target['name']}（{target['address']}，坐标{target['location']}）"
                        logger.info(f"[MultiAgent] 指代消解: '{query}' → '{new_query}'")
                        return new_query
        except Exception as e:
            logger.warning(f"[MultiAgent] 指代消解失败: {e}")
        return query

    def _parse_poi_list(self, content: str) -> list:
        """从助手回复中解析POI列表"""
        pois = []
        # 匹配 "1. 名称 - 地址 (坐标: lng,lat)" 格式
        for line in content.split("\n"):
            m = re.match(r'(\d+)\.\s+\*?\*?(.+?)\*?\*?\s+-\s+(.+?)\s*[（(]坐标[:\s]*([\d.]+)[,，]\s*([\d.]+)[)）]', line)
            if m:
                pois.append({
                    "name": m.group(2).strip(),
                    "address": m.group(3).strip(),
                    "location": f"{m.group(4)},{m.group(5)}",
                })
            else:
                # 兜底：宽松匹配
                m2 = re.match(r'(\d+)\.\s+(.+?)\s+-\s+(.+?)\s+\(([\d.]+),([\d.]+)\)', line)
                if m2:
                    pois.append({
                        "name": m2.group(2).strip(),
                        "address": m2.group(3).strip(),
                        "location": f"{m2.group(4)},{m2.group(5)}",
                    })
        return pois

    # 导航类目词：当用户用类目词做目的地时，应自动改写为"最近的X"
    _NAV_CATEGORIES = [
        "充电桩", "充电站", "充电",
        "加油站", "加气站",
        "停车场", "停车",
        "餐厅", "吃饭", "美食", "饭店",
        "咖啡店", "咖啡",
        "洗手间", "厕所", "卫生间",
        "医院", "诊所",
        "4s店", "4S店", "服务站", "维修站",
    ]
    # 导航动作关键词
    _NAV_VERBS = ["导航", "去", "带我去", "我要去", "想去", "出发", "开车去", "驶向", "前往", "过去"]

    def _preprocess_navigation_intent(self, query: str) -> str:
        """
        导航意图预处理。

        场景1: 用户说"导航到充电桩"（类目词做目的地）
          → 改写为"导航到最近的充电桩"，让 plan_route 一步完成 POI 搜索+路径规划

        场景2: 用户说"导航到北京西站"（具体地名）
          → 不改写，仍走 plan_route 关键词规划

        场景3: 用户说"去吃饭"（"去+类目"组合）
          → 改写为"导航到最近的餐厅"

        场景4: 用户说"导航回家"
          → 不改写
        """
        q = query.strip()
        if not q:
            return q

        # 快速过滤：必须是导航场景
        has_nav_verb = any(v in q for v in self._NAV_VERBS)
        if not has_nav_verb:
            return q

        # 提取"去X / 导航到X / 带我去X"中的目的地
        # 正则：动词 + （的）? + 目的地
        m = re.search(
            r'(?:导航|带我去|我要去|想去|出发|开车去|驶向|前往|过去|去)(?:到|往|去)?\s*[的了]?\s*(.+)',
            q
        )
        target = m.group(1).strip() if m else ""
        # 兜底：如果没匹配到，尝试整句作为目的地
        if not target:
            return q

        # 去掉末尾的标点和语气词
        target = re.sub(r'[吧啊呢嘛呀哈哦哇嘞呀]+$', '', target)
        target = target.rstrip("？?！!，,。.").strip()
        if not target:
            return q

        # 已经是"最近的X"则不重复改写
        if target.startswith("最近"):
            return q

        # 检查target是否是类目词
        for cat in self._NAV_CATEGORIES:
            if target == cat or target == f"最近的{cat}":
                # 改写为"导航到最近的X"
                new_query = f"导航到最近的{cat}"
                return new_query
            # 包含类目词且没有具体地点（避免误改写"导航到中关村充电桩"）
            if cat in target and len(target) <= len(cat) + 2:
                new_query = f"导航到最近的{cat}"
                return new_query

        return q

    def execute_stream(self, query: str, emitter: EventEmitter = None, session_id: str = "") -> Generator[str, None, None]:
        """
        执行用户查询，流式返回结果。
        同时通过emitter发射可视化事件。
        支持多轮对话记忆：指代消解 + 会话历史传递 + 导航意图预处理。
        """
        self._ensure_initialized()

        if emitter is None:
            emitter = EventEmitter()

        # 0. 导航意图预处理：用户说"导航到充电桩"时，
        # 智能改写为"导航到最近的充电桩"，让 plan_route 一步完成 POI 搜索+路径规划，
        # 直接在中间地图视图出路线，而不是列出 POI 列表让用户二次选择
        preprocessed_query = self._preprocess_navigation_intent(query)
        if preprocessed_query != query:
            emitter.emit(
                "query_preprocessed",
                original=query,
                processed=preprocessed_query,
                reason="导航到类目词时自动改写为'最近的X'，由 plan_route 一步完成规划",
            )
            logger.info(f"[MultiAgent] 导航预处理: '{query}' → '{preprocessed_query}'")
            query = preprocessed_query

        # 1. 指代消解（将"第四个"等改为具体POI名称）
        resolved_query = self._resolve_anaphora(query, session_id) if session_id else query
        if resolved_query != query:
            emitter.emit(
                "anaphora_resolved",
                original=query,
                resolved=resolved_query,
            )

        # 发射开始事件
        emitter.emit("start", query=resolved_query, original_query=query, agent="orchestrator")

        # 1. 意图识别
        emitter.emit("thinking", content="正在分析您的需求...", agent="orchestrator")
        intent = self._classify_intent(resolved_query)
        agent_info = SUB_AGENT_INFO.get(intent, SUB_AGENT_INFO["customer_service"])
        emitter.emit(
            "route",
            from_agent="orchestrator",
            to_agent=intent,
            to_agent_name=agent_info["name"],
            reason=f"识别为{agent_info['desc']}",
        )
        logger.info(f"[MultiAgent] 意图: {intent}, 路由到: {agent_info['name']}")

        # 2. 获取子Agent
        sub_agent = self._sub_agents.get(intent)
        if sub_agent is None:
            # 回退到售后咨询Agent
            sub_agent = self._sub_agents.get("customer_service")
            if sub_agent is None:
                emitter.emit("error", message="无可用Agent处理该请求")
                emitter.emit("end")
                yield "抱歉，我暂时无法处理您的请求。"
                return

        # 3. 构建消息列表（含会话历史）
        messages = []
        # 注入历史消息（最近3轮，6条）
        if session_id:
            history = self._get_session_history(session_id, max_turns=3)
            for h in history:
                role = h.get("role", "user")
                content = h.get("content", "")
                if not content:
                    continue
                if role == "user":
                    messages.append(HumanMessage(content=content))
                elif role == "assistant":
                    messages.append(AIMessage(content=content))
        # 当前用户查询
        messages.append(HumanMessage(content=resolved_query))

        # 设置当前用户查询上下文，供MCP工具参数推断使用
        set_current_query(resolved_query)

        input_dict = {
            "messages": messages,
        }

        full_response = ""
        # 工具调用ID追踪：tool_call_id -> {tool_name, original_args}
        _tool_call_tracker = {}
        _call_counter = 0
        try:
            # 添加递归限制防止无限循环（最多8轮工具调用）
            for msg, metadata in sub_agent.stream(input_dict, stream_mode="messages", recursion_limit=16):
                # 处理工具调用消息
                if isinstance(msg, AIMessage):
                    # 检测工具调用（过滤无效的空调用）
                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                        for tc in msg.tool_calls:
                            # 过滤无效的tool_call（无name或无id）
                            tool_name = tc.get("name", "")
                            tc_id = tc.get("id", "")
                            if not tool_name and not tc_id:
                                continue
                            _call_counter += 1
                            call_id = tc_id if tc_id else f"call_{_call_counter}"
                            original_args = tc.get("args", {}) or {}
                            _tool_call_tracker[call_id] = {
                                "tool": tool_name,
                                "args": original_args,
                            }
                            # 在工具调用事件前设置 call_id（供后续 tool_result 读取实际参数）
                            set_current_call_id(call_id)
                            emitter.emit(
                                "tool_call",
                                agent=intent,
                                tool=tool_name,
                                args=original_args,
                                call_id=call_id,
                            )
                            logger.info(f"[MultiAgent] 工具调用: {tool_name}, call_id={call_id}, 原始参数: {original_args}")
                    # 流式输出文本内容
                    if msg.content:
                        full_response += msg.content
                        emitter.emit("token", content=msg.content, agent=intent)
                        yield msg.content
                # 处理工具返回结果
                elif isinstance(msg, ToolMessage):
                    result_str = msg.content if isinstance(msg.content, str) else str(msg.content)
                    tool_name = msg.name or ""
                    tool_call_id = getattr(msg, "tool_call_id", "")
                    # 根据 call_id 获取实际参数
                    actual_args = get_args_for_call(tool_call_id)
                    emitter.emit(
                        "tool_result",
                        agent=intent,
                        tool=tool_name,
                        result=result_str[:500] if len(result_str) > 500 else result_str,
                        call_id=tool_call_id,
                        actual_args=actual_args,
                    )
                    logger.info(f"[MultiAgent] 工具结果: {tool_name}, call_id={tool_call_id}, 实际参数: {actual_args}, 返回: {result_str[:100]}")

                    # 如果是车控操作，推送车辆状态更新
                    if tool_name and (tool_name.startswith("control_") or tool_name == "set_driving_mode"):
                        try:
                            from rag_agent_project.mcp_servers.vehicle_state import vehicle_state
                            status = vehicle_state.get_status_summary()
                            emitter.emit("vehicle_status_update", status=status)
                        except Exception as e:
                            logger.warning(f"[MultiAgent] 推送车辆状态更新失败: {e}")

                    # 关键修复：navigate_to / plan_route(mcp) 返回的是纯文本 mock
                    # 必须再调一次高德 amap.plan_route 拿真实 polyline 推给前端画线
                    if tool_name in ("navigate_to", "plan_route") and actual_args.get("destination"):
                        try:
                            from rag_agent_project.mcp_servers.amap_server import plan_route as _amap_plan
                            from rag_agent_project.rag.amap_route import parse_amap_route
                            dest = actual_args.get("destination", "")
                            origin = actual_args.get("origin", "") or ""
                            mode = actual_args.get("mode", "driving")

                            # execute_stream 是同步生成器（运行在子线程里），
                            # 在新事件循环中跑 async plan_route
                            loop = asyncio.new_event_loop()
                            try:
                                route_result = loop.run_until_complete(
                                    _amap_plan(origin=origin, destination=dest, mode=mode)
                                )
                            finally:
                                loop.close()

                            parsed = parse_amap_route(route_result)
                            if parsed and parsed.get("polyline"):
                                # 显示名优先用用户输入（高德模糊匹配可能返回不同 POI 名），
                                # 坐标用高德实际解算的（更准）
                                emitter.emit(
                                    "route_update",
                                    points=parsed["polyline"],
                                    distance=parsed.get("distance"),
                                    duration=parsed.get("duration"),
                                    destination=dest,  # 用户输入的原始目的地
                                )
                                logger.info(
                                    f"[MultiAgent] 推路线: {len(parsed['polyline'])} 个点, "
                                    f"距离={parsed.get('distance')}, 耗时={parsed.get('duration')}"
                                )
                        except Exception as e:
                            logger.warning(f"[MultiAgent] 真实路线规划失败: {e}")
        except Exception as e:
            logger.error(f"[MultiAgent] 子Agent执行失败: {e}", exc_info=True)
            emitter.emit("error", message=str(e))
            yield f"处理过程中出现错误: {str(e)}"

        # 4. 发射结束事件
        emitter.emit("end", agent=intent)
        logger.info(f"[MultiAgent] 执行完成, 意图: {intent}")

    def get_agent_topology(self) -> dict:
        """获取Agent拓扑结构（供前端可视化）"""
        self._ensure_initialized()
        nodes = [
            {"id": "orchestrator", "name": "主控编排器", "type": "orchestrator", "desc": "意图识别与路由分发"},
        ]
        edges = []
        for key, info in SUB_AGENT_INFO.items():
            tool_names = SUB_AGENT_TOOL_MAP.get(key, [])
            tools = [t for t in tool_names if t != "_rag_summarize"]
            has_rag = "_rag_summarize" in tool_names
            nodes.append({
                "id": key,
                "name": info["name"],
                "type": "sub_agent",
                "desc": info["desc"],
                "tools": tools,
                "has_rag": has_rag,
                "available": key in self._sub_agents,
            })
            edges.append({"from": "orchestrator", "to": key})
        return {"nodes": nodes, "edges": edges}


# 全局单例
_multi_agent = None


def get_multi_agent() -> VehicleMultiAgent:
    global _multi_agent
    if _multi_agent is None:
        _multi_agent = VehicleMultiAgent()
    return _multi_agent


if __name__ == "__main__":
    # 测试
    agent = get_multi_agent()
    emitter = EventEmitter()

    def run():
        for chunk in agent.execute_stream("我的车还有多少电？", emitter):
            print(chunk, end="", flush=True)
        print()

    t = threading.Thread(target=run)
    t.start()

    # 打印事件
    for event in emitter.events():
        print(f"[EVENT] {event.to_json()}")

    t.join()
