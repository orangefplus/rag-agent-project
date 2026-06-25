"""
车辆控制与车况查询 MCP Server
提供车辆状态查询和车控操作工具，通过MCP协议对外暴露。
启动方式：python -m rag_agent_project.mcp_servers.vehicle_server
"""
import sys
import os
import json

# 确保项目根目录在路径中
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from mcp.server.fastmcp import FastMCP
from rag_agent_project.mcp_servers.vehicle_state import vehicle_state

mcp = FastMCP("vehicle-server")


# ============ 车况查询工具 ============

@mcp.tool()
def get_vehicle_status() -> str:
    """获取车辆完整状态信息，包括电量、续航、里程、胎压、温度、空调、车窗、驾驶模式等。无入参，返回JSON格式字符串。"""
    summary = vehicle_state.get_status_summary()
    return json.dumps(summary, ensure_ascii=False)


@mcp.tool()
def get_battery_status() -> str:
    """获取动力电池状态，包括电量百分比、电池健康度SOH、续航里程、充电状态。无入参，返回字符串。"""
    vehicle_state._refresh_from_disk()  # 跨进程同步：让主进程能读到子进程的修改
    charging = "正在充电" if vehicle_state.charging else "未充电"
    return (f"电池电量：{vehicle_state.battery_percent}%，电池健康度SOH：{vehicle_state.battery_health}%，"
            f"预估续航里程：{vehicle_state.range_km}km，充电状态：{charging}，"
            f"充电限值：{vehicle_state.charge_limit}%。"
            f"建议：电量低于20%请及时充电，日常使用建议保持在20%-80%以延长电池寿命。")


@mcp.tool()
def get_mileage_info() -> str:
    """获取车辆里程信息，包括总里程、上次保养里程、下次保养里程。无入参，返回字符串。"""
    vehicle_state._refresh_from_disk()
    remaining = vehicle_state.next_maintenance_mileage - vehicle_state.total_mileage
    return (f"总里程：{vehicle_state.total_mileage}km，"
            f"上次保养里程：{vehicle_state.last_maintenance_mileage}km，"
            f"下次保养里程：{vehicle_state.next_maintenance_mileage}km，"
            f"距离下次保养还有{remaining}km。"
            f"{'已超过保养里程，建议尽快预约保养。' if remaining < 0 else '保养周期正常。'}")


@mcp.tool()
def get_tire_pressure() -> str:
    """获取四轮胎压信息。无入参，返回字符串，包含四个轮胎的胎压值。"""
    vehicle_state._refresh_from_disk()
    tp = vehicle_state.tire_pressure
    abnormal = []
    for i, name in enumerate(["前左", "前右", "后左", "后右"]):
        if tp[i] < 2.3 or tp[i] > 2.9:
            abnormal.append(f"{name}胎压异常({tp[i]}bar)")
    result = f"胎压信息：前左{tp[0]}bar，前右{tp[1]}bar，后左{tp[2]}bar，后右{tp[3]}bar。标准胎压2.5bar(满载2.7bar)。"
    if abnormal:
        result += "警告：" + "、".join(abnormal) + "，请及时检查。"
    else:
        result += "四轮胎压正常。"
    return result


@mcp.tool()
def get_fault_codes() -> str:
    """获取当前车辆故障码。无入参，返回字符串，无故障时返回无故障信息。"""
    vehicle_state._refresh_from_disk()
    if not vehicle_state.fault_codes:
        return "当前无故障码，车辆各系统运行正常。"
    return f"当前故障码：{', '.join(vehicle_state.fault_codes)}。建议尽快到店检查或联系售后。"


# ============ 车控操作工具 ============

@mcp.tool()
def control_air_conditioner(action: str, temperature: int = None, fan_speed: int = None) -> str:
    """
    控制车辆空调系统。必须传入action参数。
    【必填参数】action: 操作类型，必须为 "on"(开启) 或 "off"(关闭) 或 "set"(设置)
    【可选参数】temperature: 目标温度16-32，仅action=set时有效
    【可选参数】fan_speed: 风量0-7档，仅action=set时有效
    调用示例：开启空调 action="on"；关闭空调 action="off"；设置24度2档 action="set" temperature=24 fan_speed=2
    """
    if action == "off":
        vehicle_state.ac_on = False
        vehicle_state._save_to_disk()
        return "空调已关闭。"
    if action == "on":
        vehicle_state.ac_on = True
        vehicle_state._save_to_disk()
        return f"空调已开启，当前温度{vehicle_state.ac_temp}℃，{vehicle_state.ac_fan_speed}档风。"
    if action == "set":
        vehicle_state.ac_on = True
        if temperature is not None:
            if 16 <= temperature <= 32:
                vehicle_state.ac_temp = temperature
            else:
                return f"温度设置无效，温度范围应为16-32摄氏度。"
        if fan_speed is not None:
            if 0 <= fan_speed <= 7:
                vehicle_state.ac_fan_speed = fan_speed
            else:
                return f"风量设置无效，风量范围应为0-7档。"
        vehicle_state._save_to_disk()
        return f"空调设置成功：温度{vehicle_state.ac_temp}℃，{vehicle_state.ac_fan_speed}档风。"
    return f"未知操作：{action}，支持的操作为on/off/set。"


@mcp.tool()
def control_window(position: str, open_percent: int) -> str:
    """
    控制车窗开合。必须传入position和open_percent两个参数。
    【必填参数】position: 车窗位置，必须为 "main"(主驾)/"passenger"(副驾)/"rear_left"(左后)/"rear_right"(右后)/"all"(全部)
    【必填参数】open_percent: 开度百分比0-100，0为关闭，100为全开
    调用示例：打开主驾车窗一半 position="main" open_percent=50；关闭所有车窗 position="all" open_percent=0
    """
    if not 0 <= open_percent <= 100:
        return "开度设置无效，范围应为0-100。"
    pos_map = {"main": 0, "passenger": 1, "rear_left": 2, "rear_right": 3}
    pos_name = {"main": "主驾", "passenger": "副驾", "rear_left": "左后", "rear_right": "右后"}
    if position == "all":
        vehicle_state.windows = [open_percent] * 4
        vehicle_state._save_to_disk()
        return f"全部车窗已设置开度{open_percent}%。"
    if position in pos_map:
        idx = pos_map[position]
        vehicle_state.windows[idx] = open_percent
        vehicle_state._save_to_disk()
        return f"{pos_name[position]}车窗已设置开度{open_percent}%。"
    return f"未知车窗位置：{position}，支持main/passenger/rear_left/rear_right/all。"


@mcp.tool()
def control_sunroof(open_percent: int) -> str:
    """
    控制全景天窗开合。必须传入open_percent参数。
    【必填参数】open_percent: 开度百分比0-100，0为关闭，100为全开
    调用示例：打开天窗一半 open_percent=50；关闭天窗 open_percent=0
    """
    if not 0 <= open_percent <= 100:
        return "开度设置无效，范围应为0-100。"
    vehicle_state.sunroof = open_percent
    vehicle_state._save_to_disk()
    return f"天窗已设置开度{open_percent}%。"


@mcp.tool()
def control_seat(position: str, heating: int = None, ventilation: int = None) -> str:
    """
    控制座椅加热和通风。必须传入position参数。
    【必填参数】position: 座椅位置，必须为 "main"(主驾) 或 "passenger"(副驾)
    【可选参数】heating: 加热档位0-3，0为关闭
    【可选参数】ventilation: 通风档位0-3，0为关闭
    调用示例：主驾座椅加热2档 position="main" heating=2；副驾通风1档 position="passenger" ventilation=1
    """
    pos_map = {"main": 0, "passenger": 1}
    pos_name = {"main": "主驾", "passenger": "副驾"}
    if position not in pos_map:
        return f"未知座椅位置：{position}，支持main/passenger。"
    idx = pos_map[position]
    parts = []
    if heating is not None:
        if 0 <= heating <= 3:
            vehicle_state.seat_heating[idx] = heating
            parts.append(f"加热{heating}档" if heating > 0 else "加热已关闭")
        else:
            return "加热档位无效，范围0-3。"
    if ventilation is not None:
        if 0 <= ventilation <= 3:
            vehicle_state.seat_ventilation[idx] = ventilation
            parts.append(f"通风{ventilation}档" if ventilation > 0 else "通风已关闭")
        else:
            return "通风档位无效，范围0-3。"
    vehicle_state._save_to_disk()
    return f"{pos_name[position]}座椅" + "，".join(parts) + "。"


@mcp.tool()
def control_ambient_light(action: str, color: str = None, mode: str = None) -> str:
    """
    控制氛围灯。必须传入action参数。
    【必填参数】action: 操作类型，必须为 "on"(开启) 或 "off"(关闭) 或 "set"(设置)
    【可选参数】color: 颜色，如"红色"/"蓝色"/"紫色"等，仅action=set时有效
    【可选参数】mode: 模式，"单色"/"渐变"/"呼吸"/"律动"，仅action=set时有效
    调用示例：开启氛围灯 action="on"；设置为蓝色呼吸 mode action="set" color="蓝色" mode="呼吸"
    """
    if action == "off":
        vehicle_state.ambient_light_on = False
        vehicle_state._save_to_disk()
        return "氛围灯已关闭。"
    if action == "on":
        vehicle_state.ambient_light_on = True
        vehicle_state._save_to_disk()
        return f"氛围灯已开启，{vehicle_state.ambient_light_color}，{vehicle_state.ambient_light_mode}模式。"
    if action == "set":
        vehicle_state.ambient_light_on = True
        if color:
            vehicle_state.ambient_light_color = color
        if mode:
            valid_modes = ["单色", "渐变", "呼吸", "律动"]
            if mode in valid_modes:
                vehicle_state.ambient_light_mode = mode
            else:
                return f"模式无效，支持：{'/'.join(valid_modes)}。"
        vehicle_state._save_to_disk()
        return f"氛围灯设置成功：{vehicle_state.ambient_light_color}，{vehicle_state.ambient_light_mode}模式。"
    return f"未知操作：{action}，支持on/off/set。"


@mcp.tool()
def set_driving_mode(mode: str) -> str:
    """
    切换驾驶模式。必须传入mode参数。
    【必填参数】mode: 驾驶模式，必须为 "经济"/"舒适"/"运动"/"雪地"/"越野" 之一
    调用示例：切换到运动模式 mode="运动"；切换到经济模式 mode="经济"
    """
    valid_modes = ["经济", "舒适", "运动", "雪地", "越野"]
    if mode not in valid_modes:
        return f"驾驶模式无效，支持：{'/'.join(valid_modes)}。"
    vehicle_state.driving_mode = mode
    vehicle_state._save_to_disk()
    mode_desc = {
        "经济": "动力响应平缓，能量回收增强，最大化续航",
        "舒适": "动力与能耗平衡，适合日常驾驶",
        "运动": "动力响应敏捷，悬挂变硬，适合高速和超车",
        "雪地": "动力输出平缓，防止打滑，适合冰雪路面",
        "越野": "提升离地间隙，关闭部分辅助功能，适合非铺装路面",
    }
    return f"驾驶模式已切换为{mode}。{mode_desc[mode]}。"


@mcp.tool()
def get_location() -> str:
    """获取车辆当前位置信息。无入参，返回字符串，包含城市、区域和经纬度。"""
    # 关键：每次读取前都从磁盘同步最新状态，否则IP上报/手动设置的位置永远不生效
    vehicle_state._refresh_from_disk()
    loc = vehicle_state.location
    return f"当前位置：{loc['city']}{loc['district']}，经纬度：{loc['lat']},{loc['lng']}。"


if __name__ == "__main__":
    mcp.run(transport="stdio")
