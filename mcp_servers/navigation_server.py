"""
导航与位置服务 MCP Server
提供导航规划、POI搜索、天气查询、常用地址管理工具。
启动方式：python -m rag_agent_project.mcp_servers.navigation_server
"""
import sys
import os
import json

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from mcp.server.fastmcp import FastMCP
from rag_agent_project.mcp_servers.vehicle_state import vehicle_state

mcp = FastMCP("navigation-server")

# 模拟POI数据库
POI_DATABASE = {
    "加油站": [
        {"name": "中石化中关村加油站", "address": "海淀区中关村大街58号", "distance": 1.2, "price": "92#7.89元/升"},
        {"name": "中石油海淀路加油站", "address": "海淀区海淀路12号", "distance": 2.1, "price": "92#7.85元/升"},
    ],
    "充电桩": [
        {"name": "特来电中关村超充站", "address": "海淀区中关村大街1号", "distance": 0.8, "power": "120kW快充", "available": 4, "total": 8},
        {"name": "星星充电五道口充电站", "address": "海淀区五道口华联", "distance": 1.5, "power": "60kW快充", "available": 2, "total": 6},
        {"name": "国家电网上地充电站", "address": "海淀区上地信息路", "distance": 3.2, "power": "60kW快充", "available": 6, "total": 10},
    ],
    "停车场": [
        {"name": "中关村地下停车场", "address": "海淀区中关村大街", "distance": 0.5, "price": "6元/小时", "available": 120},
        {"name": "海淀图书城停车场", "address": "海淀区海淀大街", "distance": 0.9, "price": "5元/小时", "available": 45},
    ],
    "餐厅": [
        {"name": "海底捞中关村店", "address": "海淀区中关村大街27号", "distance": 0.6, "type": "火锅", "rating": 4.8},
        {"name": "西贝莜面村五道口店", "address": "海淀区五道口华联", "distance": 1.5, "type": "西北菜", "rating": 4.6},
        {"name": "外婆大悦城店", "address": "海淀区大悦城5楼", "distance": 2.3, "type": "江浙菜", "rating": 4.7},
    ],
    "洗手间": [
        {"name": "中关村广场洗手间", "address": "海淀区中关村广场", "distance": 0.3, "available": True},
        {"name": "海淀公园洗手间", "address": "海淀区海淀公园", "distance": 0.7, "available": True},
    ],
    "4S店": [
        {"name": "智行汽车海淀服务中心", "address": "海淀区上地十街10号", "distance": 4.5, "phone": "010-88888001", "service": "保养/维修/钣喷"},
        {"name": "智行汽车朝阳体验中心", "address": "朝阳区国贸大厦1层", "distance": 12.3, "phone": "010-88888002", "service": "体验/销售"},
    ],
    "医院": [
        {"name": "北医三院", "address": "海淀区花园北路49号", "distance": 3.5, "phone": "010-62017691"},
        {"name": "海淀医院", "address": "海淀区中关村大街29号", "distance": 1.8, "phone": "010-62583000"},
    ],
}

# 模拟天气数据
WEATHER_DATA = {
    "北京": {"weather": "晴转多云", "temp": 28, "humidity": 55, "wind": "东南风2级", "aqi": 75, "uv": "中等", "tomorrow": "多云转小雨，22-29℃"},
    "上海": {"weather": "小雨", "temp": 25, "humidity": 80, "wind": "东风3级", "aqi": 60, "uv": "弱", "tomorrow": "阴，23-27℃"},
    "广州": {"weather": "雷阵雨", "temp": 31, "humidity": 85, "wind": "南风2级", "aqi": 50, "uv": "弱", "tomorrow": "阵雨，26-32℃"},
    "深圳": {"weather": "多云", "temp": 30, "humidity": 75, "wind": "东南风2级", "aqi": 45, "uv": "强", "tomorrow": "晴，27-33℃"},
}


@mcp.tool()
def search_poi(keyword: str, count: int = 3) -> str:
    """
    搜索附近的兴趣点(POI)。
    参数：
    - keyword: 搜索关键词，如"加油站"/"充电桩"/"停车场"/"餐厅"/"洗手间"/"4S店"/"医院"
    - count: 返回结果数量，默认3
    返回字符串，包含匹配的POI列表。
    """
    results = []
    for category, pois in POI_DATABASE.items():
        if keyword in category or category in keyword:
            results.extend(pois[:count])
    if not results:
        return f"未找到与'{keyword}'相关的地点。可搜索的类型：加油站、充电桩、停车场、餐厅、洗手间、4S店、医院。"
    output = [f"为您找到{len(results[:count])}个相关地点："]
    for i, poi in enumerate(results[:count], 1):
        line = f"{i}. {poi['name']}，地址：{poi['address']}，距离{poi.get('distance', '未知')}km"
        if "price" in poi:
            line += f"，{poi['price']}"
        if "available" in poi and "total" in poi:
            line += f"，可用{poi['available']}/{poi['total']}"
        if "rating" in poi:
            line += f"，评分{poi['rating']}"
        if "power" in poi:
            line += f"，{poi['power']}"
        output.append(line)
    return "。".join(output) + "。"


@mcp.tool()
def get_weather(city: str = None) -> str:
    """
    获取指定城市的天气信息。
    参数：
    - city: 城市名称，不传则获取车辆所在城市的天气
    返回字符串，包含天气、温度、湿度、风力、空气质量等信息。
    """
    if city is None:
        city = vehicle_state.location["city"]
    if city in WEATHER_DATA:
        w = WEATHER_DATA[city]
        return (f"{city}天气：{w['weather']}，当前温度{w['temp']}℃，湿度{w['humidity']}%，"
                f"{w['wind']}，空气质量指数AQI {w['aqi']}，紫外线{w['uv']}。"
                f"明日天气：{w['tomorrow']}。")
    return f"暂未获取到{city}的天气信息，支持查询的城市：北京、上海、广州、深圳。"


@mcp.tool()
def get_common_addresses() -> str:
    """
    获取用户常用地址列表（家、公司、学校等）。
    无入参，返回字符串，包含所有常用地址。
    """
    if not vehicle_state.common_addresses:
        return "暂无常用地址，您可以说'添加常用地址'来设置。"
    lines = ["您的常用地址："]
    for i, addr in enumerate(vehicle_state.common_addresses, 1):
        lines.append(f"{i}. {addr['name']}：{addr['address']}")
    return "\n".join(lines)


@mcp.tool()
def navigate_to(destination: str) -> str:
    """
    开始导航到指定目的地。
    参数：
    - destination: 目的地名称或地址，如"天安门广场"/"回家"/"去公司"
    返回字符串，包含导航规划结果。
    """
    # 检查是否是常用地址
    for addr in vehicle_state.common_addresses:
        if destination in addr["name"] or addr["name"] in destination:
            distance = round(abs(addr["lat"] - vehicle_state.location["lat"]) * 111, 1)
            duration = int(distance / 35 * 60)  # 估算
            return (f"已为您规划到「{addr['name']}」的导航路线：{addr['address']}。"
                    f"距离约{distance}km，预计用时{duration}分钟，当前路况畅通。导航已开始。")
    # 普通目的地
    distance = round(abs(hash(destination) % 30) + 1, 1)
    duration = int(distance / 35 * 60)
    return (f"已为您规划到「{destination}」的导航路线。"
            f"距离约{distance}km，预计用时{duration}分钟，当前路况轻度拥堵。导航已开始。")


@mcp.tool()
def plan_route(origin: str, destination: str, via: str = None) -> str:
    """
    规划多途经点路线。
    参数：
    - origin: 出发地
    - destination: 目的地
    - via: 途经点（可选），多个途经点用逗号分隔
    返回字符串，包含路线规划结果。
    """
    distance = round(abs(hash(origin + destination) % 50) + 5, 1)
    duration = int(distance / 40 * 60)
    result = f"路线规划：{origin} → "
    if via:
        via_points = [v.strip() for v in via.split(",")]
        result += " → ".join(via_points) + " → "
    result += f"{destination}。总距离约{distance}km，预计用时{duration}分钟。"
    return result


@mcp.tool()
def get_traffic_info(road: str = None) -> str:
    """
    获取实时路况信息。
    参数：
    - road: 道路名称，不传则获取当前位置周边路况
    返回字符串，包含路况信息。
    """
    if road:
        return f"{road}当前路况：轻度拥堵，平均车速35km/h，预计比平时多花5分钟。建议绕行。"
    return ("周边路况：中关村大街畅通，海淀路轻度拥堵，"
            "北四环中度拥堵（事故），建议走中关村大街。")


if __name__ == "__main__":
    mcp.run(transport="stdio")
