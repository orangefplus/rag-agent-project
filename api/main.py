"""
车载智能客服 FastAPI 后端
提供WebSocket流式对话 + REST API + Agent可视化数据
"""
import sys
import os
import json
import asyncio
import uuid
import threading
from datetime import datetime
from typing import Optional

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from rag_agent_project.utils.logger_handler import logger
from rag_agent_project.utils.path_tool import get_abs_path
from rag_agent_project.api import feedback_db


# ============ FastAPI 应用 ============

app = FastAPI(title="车载智能客服API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 会话存储
sessions = {}


# ============ 数据模型 ============

class ChatMessage(BaseModel):
    type: str = "message"
    content: str
    session_id: Optional[str] = None


class FeedbackRequest(BaseModel):
    message_id: str
    rating: str  # "like" or "dislike"
    comment: Optional[str] = None
    session_id: Optional[str] = None
    query: Optional[str] = None
    response: Optional[str] = None


# ============ 懒加载Agent ============

_multi_agent = None
_vector_store = None


def get_multi_agent():
    global _multi_agent
    if _multi_agent is None:
        from rag_agent_project.agent.multi_agent import VehicleMultiAgent
        _multi_agent = VehicleMultiAgent()
        logger.info("[API] 多Agent系统已初始化")
    return _multi_agent


def init_vector_store():
    """初始化向量数据库，加载车载知识库"""
    global _vector_store
    if _vector_store is None:
        from rag_agent_project.rag.vector_store import VectorStoreService
        _vector_store = VectorStoreService()
        _vector_store.load_documents([])
        logger.info("[API] 向量数据库已初始化，车载知识库已加载")


# ============ REST API ============

@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "车载智能客服", "time": datetime.now().isoformat()}


@app.get("/api/agents")
async def get_agents():
    """获取Agent拓扑结构（供前端可视化）"""
    agent = get_multi_agent()
    topology = agent.get_agent_topology()
    return topology


@app.post("/api/session")
async def create_session():
    """创建新会话"""
    session_id = str(uuid.uuid4())[:8]
    sessions[session_id] = {
        "id": session_id,
        "messages": [],
        "created_at": datetime.now().isoformat(),
    }
    return {"session_id": session_id}


@app.get("/api/sessions")
async def list_sessions():
    return {"sessions": list(sessions.values())}


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    if session_id not in sessions:
        return JSONResponse(status_code=404, content={"error": "会话不存在"})
    return sessions[session_id]


# ============ 反馈API ============

@app.post("/api/feedback")
async def submit_feedback(req: FeedbackRequest):
    """提交点赞/踩反馈"""
    result = feedback_db.save_feedback(
        message_id=req.message_id,
        rating=req.rating,
        comment=req.comment,
        session_id=req.session_id,
        query=req.query,
        response=req.response,
    )
    return result


@app.get("/api/feedback/stats")
async def feedback_stats():
    """获取反馈统计数据"""
    return feedback_db.get_feedback_stats()


@app.get("/api/feedback/low-rated")
async def low_rated_responses(limit: int = 20):
    """获取被踩的回答列表（用于优化分析）"""
    return {"items": feedback_db.get_low_rated_responses(limit)}


@app.get("/api/sessions/{session_id}/history")
async def session_history(session_id: str):
    """获取会话消息历史（从数据库）"""
    return {"messages": feedback_db.get_message_history(session_id)}


@app.get("/api/vehicle/status")
async def vehicle_status():
    """获取实时车辆状态"""
    from rag_agent_project.mcp_servers.vehicle_state import vehicle_state
    return vehicle_state.get_status_summary()


@app.post("/api/vehicle/location")
async def update_vehicle_location(payload: dict):
    """
    上报车辆当前位置（前端用浏览器 Geolocation API 定位后调用）
    payload: {lng: 116.xxxx, lat: 39.xxxx, accuracy?: 50, city?: "北京", district?: "海淀区"}
    """
    from rag_agent_project.mcp_servers.vehicle_state import vehicle_state
    lng = float(payload.get("lng", 0))
    lat = float(payload.get("lat", 0))
    if not (lng and lat):
        return {"ok": False, "error": "lng/lat 必填"}
    city = payload.get("city", "")
    district = payload.get("district", "")
    # 调用逆地理编码获取详细地址（如未提供 city/district）
    if not city or not district:
        try:
            from rag_agent_project.mcp_servers.amap_server import _http_get, AMAP_BASE
            data = await _http_get(
                f"{AMAP_BASE}/geocode/regeo",
                {"location": f"{lng},{lat}", "extensions": "base", "batch": "false"}
            )
            a = data.get("regeocode", {}).get("addressComponent", {})
            city = city or a.get("city", "") or a.get("province", "")
            district = district or a.get("district", "")
        except Exception as e:
            logger.warning(f"[API] 逆地理编码失败: {e}")
    vehicle_state.location = {
        "lng": lng,
        "lat": lat,
        "city": city or "",
        "district": district or "",
    }
    vehicle_state._save_to_disk()
    logger.info(f"[API] 已更新车辆位置: {city}{district} ({lng},{lat})")
    return {
        "ok": True,
        "location": vehicle_state.location,
    }


@app.post("/api/vehicle/location-by-ip")
async def location_by_ip():
    """
    降级方案：通过客户端 IP 定位（浏览器定位失败时使用）
    多级降级：
    1. 高德 IP 定位（需有效 Key）
    2. ip-api.com（免费，无需 Key）
    3. ipapi.co（免费，无需 Key）
    """
    from rag_agent_project.mcp_servers.vehicle_state import vehicle_state
    import httpx

    # ========== 第1级：高德 IP 定位 ==========
    try:
        from rag_agent_project.mcp_servers.amap_server import _http_get, AMAP_BASE
        data = await _http_get(f"{AMAP_BASE}/ip", {"ip": ""})
        if data.get("status") == "1" and data.get("province"):
            province = data.get("province", "")
            city = data.get("city", "")
            if province and city:
                geo_data = await _http_get(
                    f"{AMAP_BASE}/geocode/geo",
                    {"address": f"{province}{city}", "city": city}
                )
                if geo_data.get("geocodes"):
                    loc = geo_data["geocodes"][0]["location"]
                    lng, lat = loc.split(",")
                    vehicle_state.location = {
                        "lng": float(lng),
                        "lat": float(lat),
                        "city": city,
                        "district": "（IP定位，精度较低）",
                    }
                    vehicle_state._save_to_disk()
                    logger.info(f"[API] 高德IP定位成功: {city} ({lng},{lat})")
                    return {"ok": True, "location": vehicle_state.location, "source": "amap_ip"}
        logger.warning(f"[API] 高德IP定位失败: {data.get('info')}, 尝试 ip-api.com")
    except Exception as e:
        logger.warning(f"[API] 高德IP定位异常: {e}, 尝试 ip-api.com")

    # ========== 第2级：ip-api.com（免费，无需 Key） ==========
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                "http://ip-api.com/json/?lang=zh-CN",
                params={"fields": "status,country,regionName,city,lat,lon"},
                timeout=8.0,
            )
            data = r.json()
            if data.get("status") == "success":
                city = data.get("city", "")
                lat = data.get("lat")
                lon = data.get("lon")
                if lat and lon:
                    vehicle_state.location = {
                        "lng": float(lon),
                        "lat": float(lat),
                        "city": city or data.get("regionName", ""),
                        "district": "（IP定位，精度较低）",
                    }
                    vehicle_state._save_to_disk()
                    logger.info(f"[API] ip-api.com定位成功: {city} ({lon},{lat})")
                    return {"ok": True, "location": vehicle_state.location, "source": "ip-api.com"}
            logger.warning(f"[API] ip-api.com失败: {data}, 尝试 ipapi.co")
    except Exception as e:
        logger.warning(f"[API] ip-api.com异常: {e}, 尝试 ipapi.co")

    # ========== 第3级：ipapi.co（免费，无需 Key） ==========
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                "https://ipapi.co/json/",
                timeout=8.0,
            )
            data = r.json()
            lat = data.get("latitude")
            lon = data.get("longitude")
            if lat and lon:
                vehicle_state.location = {
                    "lng": float(lon),
                    "lat": float(lat),
                    "city": data.get("city", ""),
                    "district": "（IP定位，精度较低）",
                }
                vehicle_state._save_to_disk()
                logger.info(f"[API] ipapi.co定位成功: {data.get('city')} ({lon},{lat})")
                return {"ok": True, "location": vehicle_state.location, "source": "ipapi.co"}
    except Exception as e:
        logger.error(f"[API] ipapi.co也失败: {e}")

    return {"ok": False, "error": "所有IP定位服务都失败，请手动输入位置"}


# ============ WebSocket 流式对话 ============

@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """
    WebSocket流式对话端点。
    协议：
    - 客户端发送: {"type": "message", "content": "...", "session_id": "..."}
    - 服务端返回事件:
      {"type": "start", "query": "..."}
      {"type": "thinking", "content": "..."}
      {"type": "route", "from_agent": "...", "to_agent": "...", "to_agent_name": "...", "reason": "..."}
      {"type": "tool_call", "agent": "...", "tool": "...", "args": {...}}
      {"type": "tool_result", "agent": "...", "tool": "...", "result": "..."}
      {"type": "token", "content": "...", "agent": "..."}
      {"type": "end", "agent": "..."}
      {"type": "error", "message": "..."}
    """
    await websocket.accept()
    logger.info("[WS] WebSocket连接已建立")

    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({"type": "error", "message": "无效的JSON格式"}))
                continue

            if msg.get("type") != "message":
                continue

            content = msg.get("content", "").strip()
            if not content:
                continue

            session_id = msg.get("session_id") or str(uuid.uuid4())[:8]
            if session_id not in sessions:
                sessions[session_id] = {"id": session_id, "messages": [], "created_at": datetime.now().isoformat()}

            # 生成消息ID用于反馈追踪
            msg_id = f"msg_{uuid.uuid4().hex[:12]}"

            sessions[session_id]["messages"].append({
                "role": "user", "content": content, "time": datetime.now().isoformat()
            })

            # 保存用户消息到数据库
            feedback_db.save_message(msg_id, session_id, "user", content)

            # 在后台线程执行Agent，通过队列传递事件
            from rag_agent_project.agent.multi_agent import EventEmitter

            emitter = EventEmitter()
            full_response = []
            tools_called = []
            intent_captured = ""

            def run_agent():
                try:
                    agent = get_multi_agent()
                    # 关键修复：必须传 session_id，否则子Agent无法读取历史消息
                    # 之前这里没传，导致多轮对话完全失去上下文
                    for chunk in agent.execute_stream(content, emitter, session_id=session_id):
                        full_response.append(chunk)
                except Exception as e:
                    logger.error(f"[WS] Agent执行异常: {e}", exc_info=True)
                    emitter.emit("error", message=str(e))
                    emitter.emit("end")

            agent_thread = threading.Thread(target=run_agent, daemon=True)
            agent_thread.start()

            # 从事件队列中读取事件并发送给客户端（非阻塞轮询，避免WebSocket ping超时）
            idle_count = 0
            max_idle = 240  # 240次 * 0.5秒 = 120秒超时
            while True:
                event = emitter.get(timeout=0.1)
                if event is None:
                    # 没有事件，短暂让出控制权让WebSocket能响应ping
                    idle_count += 1
                    if idle_count > max_idle:
                        await websocket.send_text(json.dumps({"type": "error", "message": "响应超时"}))
                        break
                    await asyncio.sleep(0.1)
                    continue

                idle_count = 0  # 收到事件，重置计数器

                # 捕获意图和工具调用信息
                if event.type == "route":
                    intent_captured = getattr(event, "to_agent", "")
                elif event.type == "tool_call":
                    tool_name = getattr(event, "tool", "")
                    if tool_name:
                        tools_called.append(tool_name)

                # 在end事件中附加message_id和完整回复
                if event.type == "end":
                    event.message_id = msg_id
                    event.response = "".join(full_response)
                    event.tools = tools_called

                await websocket.send_text(event.to_json())

                if event.type == "end":
                    break
                if event.type == "error":
                    break

            agent_thread.join(timeout=5)

            response_text = "".join(full_response) or "抱歉，我无法处理您的请求。"
            sessions[session_id]["messages"].append({
                "role": "assistant", "content": response_text, "time": datetime.now().isoformat(),
                "message_id": msg_id,
            })

            # 保存AI回复到数据库
            ai_msg_id = f"msg_{uuid.uuid4().hex[:12]}"
            feedback_db.save_message(
                ai_msg_id, session_id, "assistant", response_text,
                agent=intent_captured, intent=intent_captured, tools_called=tools_called
            )

    except WebSocketDisconnect:
        logger.info("[WS] WebSocket连接已断开")
    except Exception as e:
        logger.error(f"[WS] WebSocket异常: {e}", exc_info=True)


# ============ 启动事件 ============

@app.on_event("startup")
async def startup():
    logger.info("[API] 车载智能客服API启动中...")
    # 初始化反馈数据库
    feedback_db.init_db()
    # 在后台线程初始化向量数据库
    def init_rag():
        try:
            init_vector_store()
        except Exception as e:
            logger.error(f"[API] 向量数据库初始化失败: {e}")
    threading.Thread(target=init_rag, daemon=True).start()


# ============ 静态文件（前端构建产物） ============
# 注意：必须用具体子目录挂载，不要用根目录（否则会拦截 WebSocket 升级）
frontend_dist = get_abs_path("frontend/dist")
if os.path.exists(frontend_dist):
    # 挂载静态资源（JS/CSS/图片等）
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")

    # 根路径与 SPA 路由返回 index.html（避免拦截 WebSocket）
    from fastapi.responses import FileResponse

    @app.get("/")
    async def serve_index():
        return FileResponse(os.path.join(frontend_dist, "index.html"))

    @app.get("/{path:path}")
    async def serve_spa(path: str):
        # 优先返回实际静态文件
        file_path = os.path.join(frontend_dist, path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        # 否则返回 index.html（SPA 路由）
        return FileResponse(os.path.join(frontend_dist, "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "rag_agent_project.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        ws_ping_interval=30,  # 30秒发送一次ping
        ws_ping_timeout=90,   # 90秒超时，给Agent足够时间处理
        timeout_keep_alive=120,
    )
