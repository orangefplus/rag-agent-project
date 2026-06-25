"""完整功能测试：工具调用+流式+反馈"""
import asyncio
import json
import websockets
import requests


async def test_chat(query: str, label: str):
    uri = "ws://localhost:8000/ws/chat"
    async with websockets.connect(uri) as ws:
        await ws.send(json.dumps({"type": "message", "content": query, "session_id": "test"}))
        print(f"\n{'='*60}")
        print(f"测试: {label}")
        print(f"查询: {query}")
        print(f"{'='*60}")
        tokens = []
        tools = []
        msg_id = None
        while True:
            try:
                resp = await asyncio.wait_for(ws.recv(), timeout=90)
                data = json.loads(resp)
                etype = data.get("type", "")
                if etype == "token":
                    t = data.get("content", "")
                    tokens.append(t)
                    print(t, end="", flush=True)
                elif etype == "tool_call":
                    tools.append(data.get("tool"))
                    print(f"\n  >>> [工具调用] {data.get('tool')} 参数: {data.get('args')}")
                elif etype == "tool_result":
                    print(f"\n  <<< [工具结果] {data.get('result', '')[:120]}")
                elif etype == "route":
                    print(f"\n[路由] -> {data.get('to_agent_name')}")
                elif etype == "thinking":
                    print(f"[思考] {data.get('content')}")
                elif etype == "start":
                    print(f"[开始] {data.get('query')}")
                elif etype == "end":
                    msg_id = data.get("message_id")
                    print(f"\n[结束] message_id={msg_id}, tools={data.get('tools')}")
                    break
                elif etype == "error":
                    print(f"\n[错误] {data.get('message')}")
                    break
            except asyncio.TimeoutError:
                print("\n[超时]")
                break
        full = "".join(tokens)
        print(f"\n--- 回复({len(full)}字): {full[:150]}")
        print(f"--- 工具调用: {tools}")
        return msg_id, full, tools


def test_feedback(msg_id: str, query: str, response: str):
    """测试反馈API"""
    if not msg_id:
        print("无message_id，跳过反馈测试")
        return
    r = requests.post("http://localhost:8000/api/feedback", json={
        "message_id": msg_id,
        "rating": "like",
        "session_id": "test",
        "query": query,
        "response": response,
    })
    print(f"\n[反馈提交] 状态码={r.status_code}, 响应={r.json()}")

    r2 = requests.get("http://localhost:8000/api/feedback/stats")
    print(f"[反馈统计] {r2.json()}")


async def main():
    # 测试1: 车况查询（应调用MCP工具）
    msg_id, response, tools = await test_chat("我的车还有多少电？续航多少？", "车况查询+工具调用")
    test_feedback(msg_id, "我的车还有多少电？续航多少？", response)

    # 测试2: 车控操作（应调用MCP工具）
    await test_chat("帮我把空调调到26度，风量开到4档", "车控操作+工具调用")

    # 测试3: 导航（应调用MCP工具）
    await test_chat("附近有什么充电桩？", "导航POI+工具调用")

    # 测试4: 知识问答（应调用RAG工具）
    await test_chat("发动机无法启动怎么排查？", "维修知识+RAG工具")


if __name__ == "__main__":
    asyncio.run(main())
