"""
预约与服务 MCP Server
提供保养预约、试驾预约、道路救援、服务网点查询工具。
启动方式：python -m rag_agent_project.mcp_servers.appointment_server
"""
import sys
import os
import json
from datetime import datetime, timedelta

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from mcp.server.fastmcp import FastMCP
from rag_agent_project.mcp_servers.vehicle_state import vehicle_state

mcp = FastMCP("appointment-server")

# 服务网点数据
SERVICE_CENTERS = [
    {"name": "智行汽车海淀服务中心", "address": "海淀区上地十街10号", "phone": "010-88888001", "distance": 4.5, "services": ["保养", "维修", "钣喷", "充电"], "rating": 4.8, "slots": ["2026-06-20 09:00", "2026-06-20 14:00", "2026-06-21 10:00"]},
    {"name": "智行汽车朝阳服务中心", "address": "朝阳区建国路88号", "phone": "010-88888002", "distance": 15.2, "services": ["保养", "维修", "充电"], "rating": 4.7, "slots": ["2026-06-20 11:00", "2026-06-21 09:00", "2026-06-21 15:00"]},
    {"name": "智行汽车丰台维修中心", "address": "丰台区南三环西路6号", "phone": "010-88888003", "distance": 18.6, "services": ["维修", "钣喷"], "rating": 4.6, "slots": ["2026-06-20 13:00", "2026-06-22 10:00"]},
]


@mcp.tool()
def query_service_centers(service_type: str = None) -> str:
    """
    查询附近的服务网点。
    参数：
    - service_type: 服务类型，如"保养"/"维修"/"钣喷"/"充电"，不传则查询全部
    返回字符串，包含网点列表。
    """
    results = []
    for center in SERVICE_CENTERS:
        if service_type is None or service_type in center["services"]:
            results.append(center)
    if not results:
        return f"未找到提供{service_type}服务的网点。"
    lines = [f"为您找到{len(results)}个服务网点："]
    for i, c in enumerate(results, 1):
        line = (f"{i}. {c['name']}，地址：{c['address']}，距离{c['distance']}km，"
                f"电话：{c['phone']}，服务：{'/'.join(c['services'])}，评分{c['rating']}。")
        lines.append(line)
    return "\n".join(lines)


@mcp.tool()
def get_available_slots(center_name: str) -> str:
    """
    查询指定服务网点的可预约时间段。
    参数：
    - center_name: 网点名称
    返回字符串，包含可预约时间段列表。
    """
    for center in SERVICE_CENTERS:
        if center_name in center["name"]:
            slots = "、".join(center["slots"])
            return f"{center['name']}可预约时间段：{slots}。请选择合适的时间进行预约。"
    return f"未找到网点：{center_name}。"


@mcp.tool()
def book_maintenance(center_name: str, appointment_time: str, maintenance_type: str = "常规保养") -> str:
    """
    预约保养服务。
    参数：
    - center_name: 服务网点名称
    - appointment_time: 预约时间，如"2026-06-20 09:00"
    - maintenance_type: 保养类型，"常规保养"/"大保养"/"专项检查"，默认常规保养
    返回字符串，包含预约结果。
    """
    # 验证网点
    target = None
    for center in SERVICE_CENTERS:
        if center_name in center["name"]:
            target = center
            break
    if not target:
        return f"未找到网点：{center_name}。请先查询可用网点。"
    # 验证时间段
    if appointment_time not in target["slots"]:
        return f"该时间段不可预约，{center_name}可预约时间段：{'、'.join(target['slots'])}。"
    # 创建预约
    appointment = {
        "id": f"MT{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "type": "保养",
        "subtype": maintenance_type,
        "center": target["name"],
        "time": appointment_time,
        "status": "已预约",
        "vehicle_mileage": vehicle_state.total_mileage,
    }
    vehicle_state.add_appointment(appointment)
    # 移除已预约时段
    target["slots"].remove(appointment_time)
    return (f"保养预约成功！预约单号：{appointment['id']}。"
            f"网点：{target['name']}，时间：{appointment_time}，"
            f"类型：{maintenance_type}，当前里程：{vehicle_state.total_mileage}km。"
            f"预约到店免等待，工时费9折，赠送洗车。请提前10分钟到店。")


@mcp.tool()
def book_test_drive(center_name: str, appointment_time: str, car_model: str = "智行X9") -> str:
    """
    预约试驾。
    参数：
    - center_name: 体验中心名称
    - appointment_time: 预约时间
    - car_model: 试驾车型，默认智行X9
    返回字符串，包含预约结果。
    """
    appointment = {
        "id": f"TD{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "type": "试驾",
        "center": center_name,
        "time": appointment_time,
        "car_model": car_model,
        "status": "已预约",
    }
    vehicle_state.add_appointment(appointment)
    return (f"试驾预约成功！预约单号：{appointment['id']}。"
            f"体验中心：{center_name}，时间：{appointment_time}，"
            f"试驾车型：{car_model}。请携带驾驶证到店，试驾时长约30分钟。")


@mcp.tool()
def request_road_rescue(rescue_type: str, description: str = "") -> str:
    """
    请求道路救援。
    参数：
    - rescue_type: 救援类型，"搭电"/"换胎"/"拖车"/"送油"/"困境救援"
    - description: 故障描述（可选）
    返回字符串，包含救援安排信息。
    """
    loc = vehicle_state.location
    case_id = f"RS{datetime.now().strftime('%Y%m%d%H%M%S')}"
    response_time = "30分钟" if rescue_type in ["搭电", "换胎"] else "45分钟"
    appointment = {
        "id": case_id,
        "type": "道路救援",
        "subtype": rescue_type,
        "location": f"{loc['city']}{loc['district']}",
        "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "status": "救援中",
        "description": description,
    }
    vehicle_state.add_appointment(appointment)
    return (f"道路救援已受理！救援单号：{case_id}。"
            f"救援类型：{rescue_type}，救援位置：{loc['city']}{loc['district']}，"
            f"预计{response_time}内到达。救援人员将电话联系您，请保持电话畅通。"
            f"质保期内免费救援，拖车100公里内免费。")


@mcp.tool()
def get_appointment_status() -> str:
    """
    查询当前用户的预约记录。
    无入参，返回字符串，包含所有预约记录。
    """
    if not vehicle_state.appointments:
        return "您当前没有预约记录。"
    lines = [f"您共有{len(vehicle_state.appointments)}条预约记录："]
    for apt in vehicle_state.appointments:
        line = (f"- 单号{apt['id']}：{apt.get('subtype', apt['type'])}，"
                f"{apt.get('center', apt.get('location', ''))}，"
                f"时间{apt.get('time', '')}，状态：{apt['status']}。")
        lines.append(line)
    return "\n".join(lines)


@mcp.tool()
def cancel_appointment(appointment_id: str) -> str:
    """
    取消预约。
    参数：
    - appointment_id: 预约单号
    返回字符串，包含取消结果。
    """
    for apt in vehicle_state.appointments:
        if apt["id"] == appointment_id:
            apt["status"] = "已取消"
            return f"预约{appointment_id}已取消。如需重新预约请再次申请。"
    return f"未找到预约单号：{appointment_id}。"


if __name__ == "__main__":
    mcp.run(transport="stdio")
