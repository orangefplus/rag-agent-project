"""
MCP Client 管理器
连接MCP Server，发现工具，并将MCP工具封装为LangChain工具。
通过后台事件循环处理异步MCP通信，对上层提供同步接口。
使用AsyncExitStack正确管理MCP连接的异步上下文生命周期。
"""
import sys
import os
import asyncio
import threading
import json
import contextlib
import re
from typing import Any

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from langchain_core.tools import StructuredTool, tool
from pydantic import BaseModel, create_model, Field
from rag_agent_project.utils.logger_handler import logger
from rag_agent_project.utils.path_tool import get_abs_path


# 线程局部存储：保存当前用户查询，用于参数推断
_query_context = threading.local()
# 全局查询存储（作为线程局部的备份，用于跨线程场景）
_global_query = ""
# 最近一次工具调用的实际参数（按 call_id 索引的全局字典，避免跨线程问题）
_last_args_by_call_id = {}
# 当前正在执行的 tool_call_id（由 event_middleware 设置，caller 读取）
_current_call_id = {"value": ""}


def set_current_query(query: str):
    """设置当前线程的用户查询上下文"""
    global _global_query
    _query_context.query = query
    _global_query = query  # 全局备份


def get_current_query() -> str:
    """获取当前线程的用户查询上下文"""
    q = getattr(_query_context, "query", "")
    if not q:
        q = _global_query  # 回退到全局
    return q


def get_last_tool_args() -> dict:
    """获取最近一次工具调用的实际参数（推断后）
    优先按 call_id 查表，回退到最近一次全局记录。
    """
    if _last_args_by_call_id:
        latest_key = max(_last_args_by_call_id.keys(), key=lambda k: _last_args_by_call_id[k].get("ts", 0))
        return _last_args_by_call_id[latest_key].get("args", {})
    return {}


def _set_last_tool_args(args: dict, call_id: str = ""):
    """设置最近一次工具调用的实际参数（写入全局字典，跨线程可见）"""
    import time
    args_copy = dict(args)
    if call_id:
        _last_args_by_call_id[call_id] = {"args": args_copy, "ts": time.time()}
    else:
        # 没有call_id时，使用特殊key
        _last_args_by_call_id["__last__"] = {"args": args_copy, "ts": time.time()}


def get_args_for_call(call_id: str) -> dict:
    """根据call_id获取实际参数（fallback到最近一次）"""
    if call_id and call_id in _last_args_by_call_id:
        return _last_args_by_call_id[call_id].get("args", {})
    if call_id and call_id == "__last__":
        return _last_args_by_call_id.get("__last__", {}).get("args", {})
    return get_last_tool_args()


def set_current_call_id(call_id: str):
    """由 event_middleware 在调用工具前设置当前 call_id"""
    _current_call_id["value"] = call_id


def get_current_call_id() -> str:
    """获取当前正在执行的 call_id（caller 使用）"""
    return _current_call_id.get("value", "")


# MCP Server 配置：服务名 -> 启动命令
MCP_SERVERS = {
    "vehicle-server": {
        "module": "rag_agent_project.mcp_servers.vehicle_server",
        "description": "车辆控制与车况查询",
    },
    "navigation-server": {
        "module": "rag_agent_project.mcp_servers.navigation_server",
        "description": "导航与位置服务（模拟）",
    },
    "amap-server": {
        "module": "rag_agent_project.mcp_servers.amap_server",
        "description": "高德地图真实API（POI/路线/天气/地理编码）",
    },
    "appointment-server": {
        "module": "rag_agent_project.mcp_servers.appointment_server",
        "description": "预约与服务",
    },
}


class MCPClientManager:
    """MCP客户端管理器：管理多个MCP Server连接，提供工具发现和调用"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._loop = None
        self._loop_thread = None
        self._sessions = {}  # server_name -> ClientSession
        self._exit_stacks = {}  # server_name -> AsyncExitStack
        self._tool_specs = {}  # tool_name -> {server, spec}
        self._started = False
        self._start_event_loop()

    def _start_event_loop(self):
        """启动后台事件循环线程"""
        self._loop = asyncio.new_event_loop()
        self._loop_thread = threading.Thread(target=self._run_loop, daemon=True)
        self._loop_thread.start()
        logger.info("[MCP Client] 后台事件循环已启动")

    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def _run_async(self, coro):
        """在后台事件循环中运行协程并同步等待结果"""
        if not self._loop or not self._loop.is_running():
            raise RuntimeError("MCP事件循环未运行")
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=60)

    async def _connect_server(self, server_name: str, module: str):
        """连接单个MCP Server，使用AsyncExitStack管理上下文"""
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", module],
            env={**os.environ, "PYTHONPATH": project_root},
        )

        # 使用AsyncExitStack管理异步上下文，确保在同一task中enter/exit
        stack = contextlib.AsyncExitStack()
        try:
            read, write = await stack.enter_async_context(stdio_client(params))
            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()

            self._sessions[server_name] = session
            self._exit_stacks[server_name] = stack
            logger.info(f"[MCP Client] 已连接MCP Server: {server_name}")

            # 发现工具
            tools_result = await session.list_tools()
            for tool_spec in tools_result.tools:
                self._tool_specs[tool_spec.name] = {
                    "server": server_name,
                    "spec": tool_spec,
                }
                logger.info(f"[MCP Client] 发现工具: {tool_spec.name} (来自{server_name})")
        except Exception as e:
            await stack.aclose()
            raise e

    async def _call_tool_async(self, tool_name: str, arguments: dict) -> str:
        """异步调用MCP工具"""
        if tool_name not in self._tool_specs:
            raise ValueError(f"未找到工具: {tool_name}")
        spec_info = self._tool_specs[tool_name]
        session = self._sessions[spec_info["server"]]
        result = await session.call_tool(tool_name, arguments=arguments)
        if result.content:
            texts = []
            for item in result.content:
                if hasattr(item, "text"):
                    texts.append(item.text)
                else:
                    texts.append(str(item))
            return "\n".join(texts)
        return "工具执行完成，无返回内容。"

    def start(self):
        """启动并连接所有MCP Server"""
        if self._started:
            return
        self._started = True
        for server_name, config in MCP_SERVERS.items():
            try:
                self._run_async(self._connect_server(server_name, config["module"]))
            except Exception as e:
                logger.error(f"[MCP Client] 连接{server_name}失败: {e}")
        logger.info(f"[MCP Client] 启动完成，共发现{len(self._tool_specs)}个工具")

    def call_tool(self, tool_name: str, arguments: dict) -> str:
        """同步调用MCP工具"""
        return self._run_async(self._call_tool_async(tool_name, arguments))

    def get_available_tools(self) -> dict:
        """获取所有可用工具的规格"""
        return self._tool_specs

    def _build_pydantic_model(self, tool_spec) -> type:
        """根据MCP工具的inputSchema构建Pydantic模型"""
        schema = tool_spec.inputSchema or {}
        properties = schema.get("properties", {})
        required = schema.get("required", [])

        fields = {}
        type_map = {
            "string": str,
            "integer": int,
            "number": float,
            "boolean": bool,
            "array": list,
            "object": dict,
        }
        for prop_name, prop_info in properties.items():
            py_type = type_map.get(prop_info.get("type", "string"), str)
            desc = prop_info.get("description", "")
            if prop_name in required:
                fields[prop_name] = (py_type, Field(..., description=desc))
            else:
                fields[prop_name] = (py_type, Field(None, description=desc))

        if not fields:
            fields["placeholder"] = (str, Field(None, description="占位符"))

        return create_model(f"{tool_spec.name}_Args", **fields)

    def _infer_missing_params(self, tool_name: str, arguments: dict):
        """
        智能推断缺失的必需参数。
        当LLM调用工具时传入空参数或缺少必需参数时，从用户查询中推断参数。
        返回 (推断后的参数, 错误消息或None)
        """
        inferred = dict(arguments)
        spec_info = self._tool_specs.get(tool_name)
        if spec_info is None:
            return inferred, None
        schema = spec_info["spec"].inputSchema or {}
        required = schema.get("required", [])
        properties = schema.get("properties", {})

        # 检查缺失的必需参数（空字符串、None、{}、[] 视为缺失）
        def _is_missing(v):
            if v is None:
                return True
            if isinstance(v, str) and not v.strip():
                return True
            if isinstance(v, (dict, list)) and len(v) == 0:
                return True
            return False

        missing = [r for r in required if r not in inferred or _is_missing(inferred[r])]
        if not missing:
            return inferred, None

        # 从用户查询中推断参数
        user_query = get_current_query()
        if user_query:
            logger.info(f"[MCP Client] 工具{tool_name}缺少参数{missing}，从查询推断: {user_query[:50]}")
            inferred_params = self._extract_params_from_query(tool_name, missing, user_query)
            for k, v in inferred_params.items():
                if v is not None and not (isinstance(v, str) and not v.strip()):
                    inferred[k] = v
                    logger.info(f"[MCP Client] 推断参数: {k}={v}")

        # 重新检查是否还有缺失（用_is_missing判定空字符串也算缺失）
        still_missing = [r for r in required if r not in inferred or _is_missing(inferred[r])]
        if not still_missing:
            return inferred, None

        # 清空字符串型空值（避免把""传给工具）
        for r in still_missing:
            if isinstance(inferred.get(r), str) and not inferred[r].strip():
                inferred.pop(r, None)

        logger.warning(f"[MCP Client] 工具{tool_name}仍缺少参数: {still_missing}")

        # 构建详细的错误提示
        param_hints = []
        for param_name in still_missing:
            prop_info = properties.get(param_name, {})
            prop_type = prop_info.get("type", "string")
            param_hints.append(f"{param_name}({prop_type})")

        error_msg = (
            f"参数缺失：调用{tool_name}需要参数 {', '.join(param_hints)}。"
            f"用户查询：{user_query}"
        )
        return inferred, error_msg

    def _extract_params_from_query(self, tool_name: str, missing: list, query: str) -> dict:
        """根据工具名和用户查询推断参数（包括必需和可选参数）"""
        params = {}
        q = query.lower()

        if tool_name == "control_air_conditioner":
            # 推断action（必需）- 优先级：检查是否指定了具体温度或风量
            temp_match = re.search(r'(\d+)\s*度', query)
            fan_match = re.search(r'(\d+)\s*档', query)
            has_temp = temp_match is not None
            has_fan = fan_match is not None

            if "action" in missing or "action" not in params:
                # 如果用户指定了具体温度或风量，使用 set
                if has_temp or has_fan or any(kw in query for kw in ["设置", "调到", "调为", "调成", "调低", "调高", "调到", "改为", "设置成"]):
                    params["action"] = "set"
                elif any(kw in query for kw in ["关闭", "关空调", "关掉", "关一下"]):
                    params["action"] = "off"
                elif any(kw in query for kw in ["打开", "开启", "开空调", "制冷", "制热", "开一下"]):
                    params["action"] = "on"
                elif any(kw in query for kw in ["空调"]):
                    params["action"] = "on"  # 默认开启

            # 推断温度（即使action已设置也要推断，因为这是最常见场景）
            if has_temp:
                params["temperature"] = int(temp_match.group(1))

            # 推断风量
            if has_fan:
                params["fan_speed"] = int(fan_match.group(1))

        elif tool_name == "control_window":
            # 推断position（必需）
            if "position" in missing or "position" not in params:
                if any(kw in query for kw in ["主驾", "驾驶", "左边"]):
                    params["position"] = "main"
                elif any(kw in query for kw in ["副驾", "右边"]):
                    params["position"] = "passenger"
                elif any(kw in query for kw in ["左后", "后排左"]):
                    params["position"] = "rear_left"
                elif any(kw in query for kw in ["右后", "后排右"]):
                    params["position"] = "rear_right"
                elif any(kw in query for kw in ["全部", "所有", "车窗"]):
                    params["position"] = "all"

            # 推断open_percent（必需）
            if "open_percent" in missing or "open_percent" not in params:
                if "一半" in query or "半" in query:
                    params["open_percent"] = 50
                elif "一点" in query or "稍微" in query:
                    params["open_percent"] = 30
                elif any(kw in query for kw in ["打开", "开一点", "升起"]):
                    if "全开" in query:
                        params["open_percent"] = 100
                    else:
                        params["open_percent"] = 100
                elif any(kw in query for kw in ["关闭", "关上", "关掉"]):
                    params["open_percent"] = 0
                else:
                    percent_match = re.search(r'(\d+)\s*%?', query)
                    if percent_match:
                        params["open_percent"] = int(percent_match.group(1))

        elif tool_name == "control_sunroof" and "open_percent" in missing:
            if "一半" in query:
                params["open_percent"] = 50
            elif any(kw in query for kw in ["打开", "开一点"]):
                params["open_percent"] = 100
            elif any(kw in query for kw in ["关闭", "关上"]):
                params["open_percent"] = 0

        elif tool_name == "control_seat":
            # 推断position（必需）
            if "position" in missing or "position" not in params:
                if any(kw in query for kw in ["副驾", "副驾驶"]):
                    params["position"] = "passenger"
                else:
                    params["position"] = "main"

            # 推断heating（可选）
            if "加热" in query:
                heat_match = re.search(r'加热\s*(\d+)\s*档?', query)
                if heat_match:
                    params["heating"] = int(heat_match.group(1))
                elif "加热" in query:
                    params["heating"] = 2  # 默认2档

            # 推断ventilation（可选）
            if "通风" in query:
                vent_match = re.search(r'通风\s*(\d+)\s*档?', query)
                if vent_match:
                    params["ventilation"] = int(vent_match.group(1))
                elif "通风" in query:
                    params["ventilation"] = 2  # 默认2档

        elif tool_name == "control_ambient_light":
            # 推断action（必需）
            if "action" in missing or "action" not in params:
                if any(kw in query for kw in ["关闭", "关掉"]):
                    params["action"] = "off"
                elif any(kw in query for kw in ["设置", "调", "颜色", "模式"]):
                    params["action"] = "set"
                elif any(kw in query for kw in ["氛围灯"]):
                    params["action"] = "on"

            # 推断color（可选）
            for color in ["红色", "蓝色", "绿色", "紫色", "白色", "黄色", "橙色", "粉色"]:
                if color in query:
                    params["color"] = color
                    break

            # 推断mode（可选）
            for mode in ["单色", "渐变", "呼吸", "律动"]:
                if mode in query:
                    params["mode"] = mode
                    break

        elif tool_name == "set_driving_mode" and "mode" in missing:
            for mode in ["经济", "舒适", "运动", "雪地", "越野"]:
                if mode in query:
                    params["mode"] = mode
                    break

        elif tool_name == "search_poi" and "keyword" in missing:
            for kw in ["加油站", "充电桩", "停车场", "餐厅", "洗手间", "4s店", "4S店", "医院"]:
                if kw in query:
                    params["keyword"] = kw
                    break
            if "keyword" not in params:
                kw_map = {"吃饭": "餐厅", "美食": "餐厅", "充电": "充电桩",
                          "加油": "加油站", "停车": "停车场", "厕所": "洗手间"}
                for kw, mapped in kw_map.items():
                    if kw in query:
                        params["keyword"] = mapped
                        break

        elif tool_name == "search_around" and "keyword" in missing:
            # 优先匹配明确的POI类型
            for kw in ["加油站", "充电桩", "停车场", "餐厅", "洗手间", "4s店", "4S店", "医院",
                       "咖啡店", "奶茶店", "便利店", "超市", "酒店"]:
                if kw in query:
                    params["keyword"] = kw
                    break
            # 兜底：模糊匹配
            if "keyword" not in params:
                for keyword, category in {
                    "加油": "加油站", "电": "充电桩", "充电": "充电桩",
                    "停车": "停车场", "吃饭": "餐厅", "美食": "餐厅",
                    "喝": "咖啡店", "咖啡": "咖啡店", "奶茶": "奶茶店",
                    "厕": "洗手间", "医院": "医院", "急救": "医院",
                }.items():
                    if keyword in query:
                        params["keyword"] = category
                        break
            # 终极兜底：从查询中提取"附近有什么X"中的X
            if "keyword" not in params:
                m = re.search(r'(?:附近|旁边|周边).*?(?:有什么|有哪些|找|搜|看看)?(.+?)[?？。.,，]?$', query)
                if m and m.group(1).strip():
                    params["keyword"] = m.group(1).strip()[:10]  # 截短避免太长

        elif tool_name == "get_weather":
            for city in ["北京", "上海", "广州", "深圳"]:
                if city in query:
                    params["city"] = city
                    break

        elif tool_name == "navigate_to" and "destination" in missing:
            dest_patterns = [
                r'导航到(.+?)[?？。.,，]',
                r'去(.+?)[?？。.,，]',
                r'到(.+?)[?？。.,，]',
                r'回(.+?)[?？。.,，]',
            ]
            for pattern in dest_patterns:
                match = re.search(pattern, query)
                if match:
                    params["destination"] = match.group(1).strip()
                    break
            if "destination" not in params:
                if "回家" in query:
                    params["destination"] = "家"
                elif "公司" in query or "上班" in query:
                    params["destination"] = "公司"

        elif tool_name == "plan_route":
            if "origin" in missing:
                origin_match = re.search(r'从(.+?)[到去]', query)
                if origin_match:
                    params["origin"] = origin_match.group(1).strip()
            if "destination" in missing:
                # 模式0: 优先匹配"最近的X"格式（如"最近的充电桩"）
                nearest_match = re.search(r'最近[的的]?(.+?)[?？。.,，]?$', query)
                if nearest_match:
                    candidate = nearest_match.group(1).strip().rstrip("吗？?")
                    if candidate:
                        params["destination"] = f"最近的{candidate}"
                # 模式1: "导航到X" / "去X" / "到X" 形式
                if "destination" not in params:
                    nav_match = re.search(r'(?:导航到|去|到)(.+?)[?？。.,，]?$', query)
                    if nav_match:
                        candidate = nav_match.group(1).strip()
                        # 如果候选词包含类别关键词，转为"最近的X"格式
                        if any(kw in candidate for kw in ["充电桩", "加油站", "咖啡店", "餐厅", "医院", "停车场", "酒店", "厕所", "洗手间"]):
                            params["destination"] = f"最近的{candidate}"
                        else:
                            params["destination"] = candidate

        return params

    def get_langchain_tools(self) -> list:
        """将所有MCP工具封装为LangChain StructuredTool"""
        tools = []
        for tool_name, spec_info in self._tool_specs.items():
            tool_spec = spec_info["spec"]
            server_name = spec_info["server"]
            description = tool_spec.description or f"MCP工具: {tool_name}"

            try:
                args_model = self._build_pydantic_model(tool_spec)
            except Exception as e:
                logger.warning(f"[MCP Client] 构建{tool_name}参数模型失败: {e}")
                args_model = create_model(f"{tool_name}_Args")

            def make_caller(t_name):
                def caller(**kwargs):
                    clean_args = {k: v for k, v in kwargs.items() if v is not None and k != "placeholder"}
                    # 智能推断缺失的必需参数
                    clean_args, error_msg = self._infer_missing_params(t_name, clean_args)
                    if error_msg:
                        logger.warning(f"[MCP工具调用] {t_name} 参数仍缺失: {error_msg[:100]}")
                        # 即使有错误，也尝试用推断的参数调用
                        if not clean_args:
                            return error_msg
                    # 保存实际使用的参数（供事件系统读取）
                    # 优先从kwargs中取call_id，否则从全局_current_call_id取
                    call_id = clean_args.get("__call_id__", "") or get_current_call_id()
                    if "__call_id__" in clean_args:
                        clean_args.pop("__call_id__", None)
                    _set_last_tool_args(dict(clean_args), call_id=call_id)
                    logger.info(f"[MCP工具调用] {t_name}, 参数: {clean_args}, call_id={call_id}")
                    try:
                        result = self.call_tool(t_name, clean_args)
                        logger.info(f"[MCP工具调用] {t_name} 返回: {result[:200]}")
                        return result
                    except Exception as e:
                        logger.error(f"[MCP工具调用] {t_name} 异常: {e}")
                        return f"工具执行失败: {str(e)}"
                return caller

            lc_tool = StructuredTool.from_function(
                func=make_caller(tool_name),
                name=tool_name,
                description=description,
                args_schema=args_model,
            )
            tools.append(lc_tool)
            logger.info(f"[MCP Client] 封装LangChain工具: {tool_name}")
        return tools

    def stop(self):
        """关闭所有MCP连接"""
        async def _close_all():
            for name, stack in list(self._exit_stacks.items()):
                try:
                    await stack.aclose()
                    logger.info(f"[MCP Client] 已关闭连接: {name}")
                except Exception as e:
                    logger.warning(f"[MCP Client] 关闭{name}异常: {e}")
            self._exit_stacks.clear()
            self._sessions.clear()
        try:
            self._run_async(_close_all())
        except Exception as e:
            logger.warning(f"[MCP Client] 关闭连接异常: {e}")
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)
        logger.info("[MCP Client] 已关闭所有连接")


# 全局单例
mcp_manager = MCPClientManager()


def get_mcp_tools() -> list:
    """获取所有MCP工具（LangChain格式），首次调用时自动启动连接"""
    mcp_manager.start()
    return mcp_manager.get_langchain_tools()


def get_mcp_tool_names() -> list:
    """获取所有MCP工具名称"""
    return list(mcp_manager.get_available_tools().keys())


if __name__ == "__main__":
    # 测试MCP客户端
    manager = MCPClientManager()
    manager.start()
    print(f"发现工具: {get_mcp_tool_names()}")
    # 测试调用
    result = manager.call_tool("get_battery_status", {})
    print(f"电池状态: {result}")
    result = manager.call_tool("get_weather", {"city": "北京"})
    print(f"天气: {result}")
    manager.stop()
