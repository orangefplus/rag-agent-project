"""
高德地图 MCP Server
封装高德 Web API（POI搜索、路线规划、天气查询、地理编码）。
免费 tier：每日 5000 次调用。
API 文档：
  - 基础 API:    https://lbs.amap.com/api/webservice/guide/api/overview
  - 路径规划 2.0: https://lbs.amap.com/api/webservice/guide/api/newroute
  - POI 搜索:    https://lbs.amap.com/api/webservice/guide/api/search
  - 天气:        https://lbs.amap.com/api/webservice/guide/api/weatherinfo
2021.12.01 后高德 Web 服务 API 需要数字签名（sig参数）才能调用。
"""
import os
import re
import json
import hashlib
import logging
import asyncio
import httpx
from mcp.server.fastmcp import FastMCP

# 从环境变量或配置文件读取高德Key
# 优先级: 环境变量 AMAP_KEY > config/amap.yml DEFAULT_AMAP_KEY > 内置默认 key
try:
    import yaml as _yaml
    _amap_cfg_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "config", "amap.yml"
    )
    if os.path.exists(_amap_cfg_path):
        with open(_amap_cfg_path, "r", encoding="utf-8") as _f:
            _amap_cfg = _yaml.safe_load(_f) or {}
        _config_key = _amap_cfg.get("DEFAULT_AMAP_KEY", "") or ""
    else:
        _config_key = ""
except Exception:
    _config_key = ""

AMAP_KEY = (
    os.getenv("AMAP_KEY")
    or _config_key
    or "d5e043b73771f7d9a2607303f1bf4941"  # 内置默认（Web服务 Key）
)
AMAP_BASE = "https://restapi.amap.com/v3"
# 路径规划 2.0 用 v5 版本（v3 是旧版，无 polyline 返回）
AMAP_V5 = "https://restapi.amap.com/v5"

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("amap-server")

# 启动时输出当前 Key 状态（脱敏）
_masked_key = (AMAP_KEY[:8] + "***" + AMAP_KEY[-4:]) if AMAP_KEY and len(AMAP_KEY) > 12 else "(empty)"
logger.info(f"[AMAP] 当前 Key: {_masked_key} (可通过环境变量 AMAP_KEY 覆盖)")

mcp = FastMCP("amap-navigation")


# ============ 降级数据（API不可用时使用，必须在工具函数前定义） ============

_FALLBACK_POIS = {
    "北京": {
        "加油站": [
            {"name": "中石化加油站(中关村店)", "address": "北京市海淀区中关村大街1号", "location": "116.3126,39.9847"},
            {"name": "中石油加油站(海淀大街)", "address": "北京市海淀区海淀大街38号", "location": "116.3104,39.9828"},
            {"name": "壳牌加油站(知春路店)", "address": "北京市海淀区知春路82号", "location": "116.3436,39.9785"},
            {"name": "中石化加油站(上地店)", "address": "北京市海淀区上地信息路", "location": "116.3056,40.0421"},
        ],
        "充电桩": [
            {"name": "特来电充电站(中关村)", "address": "北京市海淀区中关村大街5号", "location": "116.3141,39.9854"},
            {"name": "国家电网充电站(海淀)", "address": "北京市海淀区中关村南大街", "location": "116.3186,39.9622"},
            {"name": "星星充电(清华科技园)", "address": "北京市海淀区清华科技园", "location": "116.3225,40.0033"},
            {"name": "特来电(上地信息产业基地)", "address": "北京市海淀区上地信息路2号", "location": "116.3078,40.0456"},
        ],
        "停车场": [
            {"name": "中关村广场停车场", "address": "北京市海淀区中关村广场", "location": "116.3126,39.9847"},
            {"name": "新中关购物中心停车场", "address": "北京市海淀区中关村大街19号", "location": "116.3151,39.9828"},
            {"name": "海淀剧院停车场", "address": "北京市海淀区中关村大街28号", "location": "116.3166,39.9833"},
        ],
        "餐厅": [
            {"name": "海底捞火锅(中关村店)", "address": "北京市海淀区中关村大街15号", "location": "116.3136,39.9842"},
            {"name": "西少爷肉夹馍(中关村)", "address": "北京市海淀区中关村大街", "location": "116.3126,39.9847"},
            {"name": "星巴克(新中关店)", "address": "北京市海淀区中关村大街19号", "location": "116.3151,39.9828"},
            {"name": "麦当劳(海淀大街)", "address": "北京市海淀区海淀大街2号", "location": "116.3111,39.9830"},
        ],
        "咖啡店": [
            {"name": "星巴克(中关村店)", "address": "北京市海淀区中关村大街15号", "location": "116.3136,39.9842"},
            {"name": "Costa Coffee(新中关)", "address": "北京市海淀区中关村大街19号", "location": "116.3151,39.9828"},
            {"name": "瑞幸咖啡(海淀大街)", "address": "北京市海淀区海淀大街38号", "location": "116.3104,39.9828"},
        ],
        "医院": [
            {"name": "北京大学第三医院", "address": "北京市海淀区花园北路49号", "location": "116.3621,39.9872"},
            {"name": "海淀医院", "address": "北京市海淀区中关村大街29号", "location": "116.3176,39.9842"},
            {"name": "北京协和医院(西院)", "address": "北京市西城区大木仓胡同41号", "location": "116.3586,39.9132"},
        ],
        "4s店": [
            {"name": "一汽丰田4S店(海淀)", "address": "北京市海淀区杏石口路", "location": "116.2564,39.9785"},
            {"name": "比亚迪汽车4S店", "address": "北京市朝阳区花虎沟", "location": "116.4325,40.0156"},
        ],
    }
}


def _fallback_search_poi(keyword: str, city: str = "北京") -> str:
    """降级POI搜索（高德API不可用时）"""
    city_data = _FALLBACK_POIS.get(city, _FALLBACK_POIS["北京"])
    matched = []
    for k, pois in city_data.items():
        if keyword in k or k in keyword:
            matched.extend(pois)
    if not matched:
        # 兜底：找最近的类别
        for k, pois in city_data.items():
            if any(t in keyword for t in ["吃", "饭", "餐", "喝", "咖啡", "奶茶"]):
                if k in ("餐厅", "咖啡店"):
                    matched.extend(pois)
                    break
            if any(t in keyword for t in ["车", "油", "电", "充电", "停车"]):
                if k in ("加油站", "充电桩", "停车场", "4s店"):
                    matched.extend(pois[:2])
            if any(t in keyword for t in ["医", "院"]):
                if k == "医院":
                    matched.extend(pois)
                    break
    if not matched:
        matched = city_data.get("餐厅", [])[:3]

    lines = [f"[降级模式] 找到{len(matched[:5])}个{keyword}相关地点（高德API当前不可用）："]
    for i, p in enumerate(matched[:5], 1):
        lines.append(f"{i}. {p['name']} - {p['address']} (坐标: {p['location']})")
    return "\n".join(lines)


def _fallback_search_around(keyword: str, location: str = "116.3076,39.9847", radius: int = 3000) -> str:
    """降级周边搜索"""
    city_data = _FALLBACK_POIS.get("北京", {})
    matched = []
    for k, pois in city_data.items():
        if keyword in k or k in keyword:
            matched.extend(pois[:4])
    if not matched:
        # 兜底：基于位置
        matched = city_data.get("餐厅", [])[:3]

    lines = [f"附近{radius}米内找到{len(matched)}个{keyword}（降级数据）："]
    for i, p in enumerate(matched, 1):
        # 简单计算距离（基于坐标差的伪距离）
        try:
            p_lng, p_lat = p["location"].split(",")
            my_lng, my_lat = location.split(",")
            dist_m = int(((float(p_lng) - float(my_lng))**2 + (float(p_lat) - float(my_lat))**2)**0.5 * 111000)
            dist_str = f"，约{dist_m}米"
        except Exception:
            dist_str = ""
        lines.append(f"{i}. {p['name']} - {p['address']}{dist_str} (坐标: {p['location']})")
    return "\n".join(lines)


def _fallback_weather(city: str = "北京") -> str:
    """降级天气查询"""
    return (
        f"📍 {city}实时天气（降级数据）\n"
        f"天气：晴\n"
        f"温度：22℃\n"
        f"风向：东南风\n"
        f"风力：2级\n"
        f"湿度：45%\n"
        f"提示：高德天气API当前不可用，已返回模拟数据。"
    )


def _fallback_route(origin: str, destination: str) -> str:
    """降级路线规划（无 polyline，因为是模拟数据）"""
    h = hashlib.md5(f"{origin}{destination}".encode()).hexdigest()
    distance = 5000 + (int(h[:4], 16) % 30000)
    duration = distance * 1.5 // 100
    return (
        f"=== 路线规划（降级数据）===\n"
        f"起点：{origin}\n"
        f"终点：{destination}\n"
        f"距离：{distance/1000:.1f}公里\n"
        f"预计耗时：{duration//60}小时{duration%60}分钟\n"
        f"主要道路：建议使用主干道\n"
        f"起点坐标：116.3076,39.9847\n"
        f"终点坐标：116.3151,39.9828\n"
        f"路线坐标：116.3076,39.9847;116.3100,39.9835;116.3120,39.9828;116.3151,39.9828\n"
        f"提示：高德路径规划API当前不可用，已返回估算数据。"
    )


def _sign_params(params: dict) -> dict:
    """为高德API生成数字签名（sig参数）
    高德签名规则：
    1. 将除 key 和 sig 外的所有参数按 key 字母序升序排列
    2. 拼接为 key1value1key2value2... 格式
    3. 在末尾拼接上 Key
    4. MD5 加密后转大写
    """
    # 过滤 None 和空值
    filtered = {k: v for k, v in params.items() if v is not None and v != "" and k not in ("key", "sig")}
    # 按key排序
    sorted_keys = sorted(filtered.keys())
    # 拼接
    sign_str = "".join(f"{k}{filtered[k]}" for k in sorted_keys) + AMAP_KEY
    sig = hashlib.md5(sign_str.encode("utf-8")).hexdigest().upper()
    params["sig"] = sig
    return params


async def _http_get(url: str, params: dict, timeout: int = 10, retries: int = 2) -> dict:
    """统一的高德 API GET 请求封装（带数字签名 + 重试机制）

    Args:
        url: API 地址
        params: 请求参数
        timeout: 单次超时时间（秒）
        retries: 失败后重试次数（默认 2 次，即最多 3 次调用）
    """
    params = {k: v for k, v in params.items() if v is not None and v != ""}
    params["key"] = AMAP_KEY
    # 生成签名
    params = _sign_params(params)
    # 调试日志：打印实际发送的URL
    import urllib.parse
    debug_url = url + "?" + urllib.parse.urlencode(params)
    logger.info(f"[AMAP] 请求URL: {debug_url[:400]}")
    last_err = ""
    for attempt in range(retries + 1):
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(url, params=params, timeout=timeout)
                r.raise_for_status()
                logger.info(f"[AMAP] 实际请求URL: {str(r.request.url)[:400]}")
                data = r.json()
                if str(data.get("status")) != "1":
                    err_info = f"{data.get('info')}, infocode={data.get('infocode')}"
                    logger.error(f"[AMAP] API错误 (尝试 {attempt+1}/{retries+1}): {err_info}, url={url}, 完整响应={data}")
                    last_err = err_info
                    # Key 鉴权类错误不重试，节约时间
                    # 10001=INVALID_USER_KEY, 10003=DAILY_QUERY_OVER_LIMIT, 10004=ACCESS_TOO_FREQ
                    if str(data.get("infocode")) in ("10001", "10003", "10004", "10005", "10007", "10008", "10009", "10010", "10011", "10012", "10016", "10017", "10018", "10019", "10020", "10021", "10022", "10026"):
                        return data
                    # 其它错误（如网络临时问题）重试
                    if attempt < retries:
                        await asyncio.sleep(1.0 * (attempt + 1))
                        continue
                    return data
                # 成功
                if attempt > 0:
                    logger.info(f"[AMAP] 重试成功 (第 {attempt+1} 次)")
                return data
        except httpx.TimeoutException:
            last_err = "请求超时"
            logger.error(f"[AMAP] 请求超时 (尝试 {attempt+1}/{retries+1}): {url}")
            if attempt < retries:
                await asyncio.sleep(1.0 * (attempt + 1))
                continue
            return {"status": "0", "info": "请求超时", "pois": [], "lives": [], "geocodes": [], "route": {}}
        except Exception as e:
            last_err = str(e)
            logger.error(f"[AMAP] 请求异常 (尝试 {attempt+1}/{retries+1}): {e}")
            if attempt < retries:
                await asyncio.sleep(1.0 * (attempt + 1))
                continue
            return {"status": "0", "info": str(e), "pois": [], "lives": [], "geocodes": [], "route": {}}
    return {"status": "0", "info": last_err, "pois": [], "lives": [], "geocodes": [], "route": {}}


@mcp.tool()
async def search_poi(keyword: str, city: str = "北京", poi_type: str = "") -> str:
    """
    真实POI搜索（高德API）。支持搜索餐馆、加油站、充电桩、停车场、医院、4S店等。
    【必填参数】keyword: 搜索关键词，如"加油站"、"充电桩"、"星巴克"
    【可选参数】city: 城市名称，默认"北京"
    【可选参数】poi_type: POI类型编码（可选），如"010000"（汽车服务）、"050000"（餐饮）
    返回: POI名称、地址、坐标（GCJ-02火星坐标）
    """
    data = await _http_get(
        f"{AMAP_BASE}/place/text",
        {
            "keywords": keyword,
            "city": city,
            "citylimit": "true",
            "extensions": "base",
            "types": poi_type,
            "offset": 8,
        }
    )
    pois = data.get("pois", [])
    # 降级：如果API失败（INVALID_USER_KEY/超时），使用模拟数据
    if not pois and str(data.get("status")) != "1":
        return _fallback_search_poi(keyword, city)

    lines = [f"找到{len(pois)}个{keyword}相关地点："]
    for i, p in enumerate(pois, 1):
        name = p.get("name", "")
        address = p.get("address", "")
        location = p.get("location", "")
        distance = p.get("distance", "")
        dist_str = f"，距离{distance}米" if distance else ""
        lines.append(f"{i}. {name} - {address}{dist_str} (坐标: {location})")
    return "\n".join(lines)


@mcp.tool()
async def geocode(address: str, city: str = "北京") -> str:
    """
    真实地理编码（高德API）。将地址转换为经纬度坐标。
    【必填参数】address: 详细地址，如"北京市朝阳区国贸大厦"、"中关村大街1号"
    【可选参数】city: 城市名称，默认"北京"，限定搜索范围
    返回: 坐标、匹配的行政区、格式化地址
    """
    data = await _http_get(
        f"{AMAP_BASE}/geocode/geo",
        {"address": address, "city": city}
    )
    geocodes = data.get("geocodes", [])
    if not geocodes:
        return f"未找到\"{address}\"对应的地理位置。请尝试更详细的地址。"

    g = geocodes[0]
    return (
        f"地址：{g.get('formatted_address', '')}\n"
        f"坐标：{g.get('location', '')} (经度,纬度)\n"
        f"所在区域：{g.get('district', '')} {g.get('street', '')}\n"
        f"城市：{g.get('city', '')}\n"
        f"匹配级别：{g.get('level', '')}"
    )


@mcp.tool()
async def plan_route(origin: str = "", destination: str = "", mode: str = "driving", city: str = "北京") -> str:
    """
    智能路线规划（高德API）。驾车、步行、骑行路径规划。
    【可选参数】origin: 起点名称或坐标（"lng,lat"格式）。留空时使用车辆当前位置。
    【必填参数】destination: 终点名称、坐标，或"最近的X"格式（如"最近的充电桩"、"最近的咖啡店"）
    【可选参数】mode: 交通方式，driving(驾车)/walking(步行)/riding(骑行)/transit(公交)
    【可选参数】city: 城市名称，默认"北京"
    返回: 距离、预计耗时、途经道路

    特殊语法：
    - destination="最近的充电桩"：自动查找最近一个充电桩并规划路线
    - destination="最近的咖啡店"：自动查找最近一个咖啡店
    """
    # ============ 智能解析：处理"最近的X"格式 ============
    is_nearest = "最近" in destination

    # 默认从车辆状态读取实际城市（英文转中文）
    _city_en2cn = {
        "Beijing": "北京", "Shanghai": "上海", "Guangzhou": "广州",
        "Shenzhen": "深圳", "Chengdu": "成都", "Hangzhou": "杭州",
        "Nanjing": "南京", "Wuhan": "武汉", "Xi'an": "西安", "Xian": "西安",
        "Tianjin": "天津", "Chongqing": "重庆", "Suzhou": "苏州",
        "Qingdao": "青岛", "Dalian": "大连", "Shenyang": "沈阳",
        "Harbin": "哈尔滨", "Changsha": "长沙", "Zhengzhou": "郑州",
        "Jinan": "济南", "Fuzhou": "福州", "Xiamen": "厦门",
        "Hefei": "合肥", "Nanchang": "南昌", "Kunming": "昆明",
        "Nanning": "南宁", "Ningbo": "宁波", "Wenzhou": "温州",
        "Foshan": "佛山", "Dongguan": "东莞", "Zhuhai": "珠海",
    }
    try:
        from rag_agent_project.mcp_servers.vehicle_state import vehicle_state
        vehicle_state._refresh_from_disk()
        _raw_city = vehicle_state.location.get("city", "") or ""
        actual_city = _city_en2cn.get(_raw_city, _raw_city) or city
    except Exception:
        actual_city = city

    if is_nearest:
        # 提取"最近的"后面的类别
        m = re.search(r'最近[的的]?(.+?)$', destination)
        if m:
            category = m.group(1).strip().rstrip("吗？?")
        else:
            category = "充电桩"  # 默认

        # 从 vehicle_state 读取当前真实位置
        try:
            from rag_agent_project.mcp_servers.vehicle_state import vehicle_state
            # 每次都从磁盘同步，确保拿到前端刚更新的位置
            vehicle_state._refresh_from_disk()
            cur_loc = vehicle_state.location
            center = f"{cur_loc['lng']},{cur_loc['lat']}"
            # 用车辆实际所在城市，而不是传参city
            # vehicle_state.city 可能是英文（如"Chengdu"），需转换为中文
            _city_en2cn_local = {
                "Beijing": "北京", "Shanghai": "上海", "Guangzhou": "广州",
                "Shenzhen": "深圳", "Chengdu": "成都", "Hangzhou": "杭州",
                "Nanjing": "南京", "Wuhan": "武汉", "Xi'an": "西安", "Xian": "西安",
                "Tianjin": "天津", "Chongqing": "重庆", "Suzhou": "苏州",
                "Qingdao": "青岛", "Dalian": "大连", "Shenyang": "沈阳",
                "Harbin": "哈尔滨", "Changsha": "长沙", "Zhengzhou": "郑州",
                "Jinan": "济南", "Fuzhou": "福州", "Xiamen": "厦门",
                "Hefei": "合肥", "Nanchang": "南昌", "Kunming": "昆明",
                "Nanning": "南宁", "Ningbo": "宁波", "Wenzhou": "温州",
                "Foshan": "佛山", "Dongguan": "东莞", "Zhuhai": "珠海",
            }
            raw_city = cur_loc.get("city", "") or ""
            actual_city = _city_en2cn_local.get(raw_city, raw_city) or actual_city
        except Exception as e:
            logger.warning(f"[AMAP] 读取车辆位置失败: {e}，请确保前端已通过 /api/vehicle/location 上报位置")
            return "无法获取车辆当前位置。请允许浏览器定位权限后重试。"

        # 用 search_around 找最近POI
        data = await _http_get(
            f"{AMAP_BASE}/place/around",
            {
                "keywords": category,
                "location": center,
                "radius": "10000",
                "city": actual_city,
                "citylimit": "true",
                "extensions": "base",
                "offset": 5,
                "sortrule": "distance",
            }
        )
        pois = data.get("pois", [])
        if not pois and str(data.get("status")) != "1":
            # 降级
            fallback = _fallback_search_around(category, center, 10000)
            return f"已为您查找最近的{category}，但当前高德API不可用：\n{fallback}\n\n请您选择一个具体地点后再次查询。"

        if pois:
            # 选第一个（最近的）
            nearest = pois[0]
            d_name = nearest.get("name", category)
            d_coords = nearest.get("location", "")
            target_address = nearest.get("address", "")
            # 列出所有选项供用户参考
            options = "\n".join([
                f"  {i+1}. {p.get('name', '')} - {p.get('address', '')} (距离{p.get('distance', '?')}米)"
                for i, p in enumerate(pois[:5])
            ])
        else:
            return f"附近未找到{category}，请尝试其他关键词。"
    else:
        d_name = destination
        d_coords = None
        target_address = ""
        options = ""

    # ============ 起点处理：留空时用车辆当前位置 ============
    o_coords = None
    if origin:
        # 检测是否是坐标
        if "," in origin and all(c.replace(".", "").replace("-", "").isdigit() for c in origin.split(",")):
            o_coords = origin
            o_name = "指定位置"
        else:
            geo_data = await _http_get(f"{AMAP_BASE}/geocode/geo", {"address": origin, "city": actual_city})
            if geo_data.get("geocodes"):
                o_coords = geo_data["geocodes"][0]["location"]
                o_name = geo_data["geocodes"][0].get("formatted_address", origin)
            else:
                return f"无法解析起点：{origin}"

    if not o_coords:
        # 从 vehicle_state 读取真实位置
        try:
            from rag_agent_project.mcp_servers.vehicle_state import vehicle_state
            vehicle_state._refresh_from_disk()
            cur_loc = vehicle_state.location
            o_coords = f"{cur_loc['lng']},{cur_loc['lat']}"
            o_name = f"车辆当前位置（{cur_loc.get('city', '')}{cur_loc.get('district', '')}）"
        except Exception as e:
            logger.warning(f"[AMAP] 读取车辆位置失败: {e}")
            return "无法获取车辆当前位置。请允许浏览器定位权限后重试。"

    # ============ 终点坐标处理（POI 优先，地理编码兜底）============
    if not d_coords:
        # 优先用 POI 搜索（place/text），能精确匹配"成都东站"这类有具体名称的地点
        # 因为 geocode/geo 对某些地标只返回城市中心
        poi_data = await _http_get(
            f"{AMAP_BASE}/place/text",
            {
                "keywords": destination,
                "city": actual_city,
                "citylimit": "true",
                "extensions": "base",
                "offset": 5,
            }
        )
        poi_list = poi_data.get("pois", [])
        if poi_list:
            # 优先选 level 不是 "市/省" 的精确地点
            precise = [p for p in poi_list if p.get("type", "") and "市" not in p.get("type", "").split(";")[0]]
            chosen = (precise or poi_list)[0]
            d_coords = chosen.get("location", "")
            d_name = chosen.get("name", destination)
            target_address = chosen.get("address", "") or chosen.get("cityname", "")
            logger.info(f"[AMAP] POI命中 '{destination}': {d_name} @ {d_coords} ({chosen.get('type', '')})")
            # 列出候选供用户参考
            options = "\n".join([
                f"  {i+1}. {p.get('name', '')} - {p.get('address', '')} ({p.get('location', '')})"
                for i, p in enumerate(poi_list[:5])
            ])
        else:
            # 兜底用地理编码
            geo_data = await _http_get(f"{AMAP_BASE}/geocode/geo", {"address": destination, "city": actual_city})
            geocodes = geo_data.get("geocodes", [])
            if not geocodes:
                return f"无法解析终点：{destination}。请提供更详细地址（如「成都东站北广场」「北京市朝阳区国贸大厦」）。"
            # 优先选非市/省级的精确结果
            precise_g = [g for g in geocodes if g.get("level") not in ("市", "省", "区县")]
            best = (precise_g or geocodes)[0]
            d_coords = best.get("location", "")
            d_name = best.get("formatted_address", destination)
            target_address = best.get("district", "")
            logger.info(f"[AMAP] 地理编码命中 '{destination}': {d_name} @ {d_coords} (level={best.get('level')})")

    # ============ 路径规划（高德 v5.0 路径规划 2.0）============
    # 文档：https://lbs.amap.com/api/webservice/guide/api/newroute
    # 重要：必须传 show_fields=polyline,cost，否则不返回 polyline 和 duration
    if mode not in ("driving", "walking", "riding", "bicycling", "electrobike", "transit"):
        mode = "driving"
    # v5 路径规划 2.0 支持的模式：driving / walking / bicycling / electrobike
    # riding/transit 在 v3 旧版才完整支持，简单映射
    v5_mode_map = {
        "driving": "driving",
        "walking": "walking",
        "riding": "bicycling",  # 骑行 → bicycling
        "bicycling": "bicycling",
        "electrobike": "electrobike",
    }
    actual_mode = v5_mode_map.get(mode, "driving")

    data = await _http_get(
        f"{AMAP_V5}/direction/{actual_mode}",
        {
            "origin": o_coords,
            "destination": d_coords,
            "show_fields": "polyline,cost",  # 关键：传此参数才返回 polyline 和 duration
            "strategy": "32",  # 默认高德推荐
        }
    )
    if str(data.get("status")) != "1" or not data.get("route"):
        return _fallback_route(o_name, d_name)

    path = data["route"]["paths"][0]
    distance_m = int(path.get("distance", 0))
    # duration 在 cost 字段中
    duration_s = 0
    cost = path.get("cost", {})
    if cost and "duration" in cost:
        duration_s = int(cost.get("duration", 0))
    else:
        duration_s = int(path.get("duration", 0))
    strategy = path.get("strategy", "")
    road = path.get("road", "")[:200]

    # ============ 提取 polyline 坐标 ============
    # v5 polyline 格式: steps[].polyline = "lng,lat;lng,lat;..."
    # （也可能是 path.polyline，取决于 show_fields）
    polyline_points = []
    # 优先用 path.polyline（show_fields=polyline 时整体返回）
    if path.get("polyline"):
        for coord in path["polyline"].split(";"):
            if "," in coord:
                try:
                    lng, lat = coord.split(",")
                    polyline_points.append(f"{float(lng):.6f},{float(lat):.6f}")
                except (ValueError, IndexError):
                    continue
    else:
        # 回退：从 steps 拼接
        for step in path.get("steps", []):
            step_poly = step.get("polyline", "")
            if step_poly:
                for coord in step_poly.split(";"):
                    if "," in coord:
                        try:
                            lng, lat = coord.split(",")
                            polyline_points.append(f"{float(lng):.6f},{float(lat):.6f}")
                        except (ValueError, IndexError):
                            continue
    polyline_str = ";".join(polyline_points) if polyline_points else ""

    nearest_intro = ""
    if is_nearest and options:
        nearest_intro = f"\n附近找到{len(pois)}个候选地点：\n{options}\n\n已为您规划到最近的【{d_name}】的路线：\n"

    return (
        f"=== 路线规划成功 ==={nearest_intro}"
        f"起点：{o_name}\n"
        f"终点：{d_name}\n"
        f"地址：{target_address}\n"
        f"距离：{distance_m/1000:.1f}公里（{distance_m}米）\n"
        f"预计耗时：{duration_s//3600}小时{duration_s%3600//60}分钟（{duration_s}秒）\n"
        f"推荐策略：{strategy}\n"
        f"主要道路：{road or '无'}\n"
        f"起点坐标：{o_coords}\n"
        f"终点坐标：{d_coords}\n"
        f"路线坐标：{polyline_str}"  # 用于前端绘制 polyline
    )


@mcp.tool()
async def get_weather(city: str = "北京") -> str:
    """
    真实天气查询（高德API）。实时天气信息。
    【必填参数】city: 城市名称（支持 adcode 区县级），如"北京"、"海淀"
    返回: 天气状况、温度、风向、风力、湿度、发布时间
    """
    # 先获取城市的adcode
    if not city.isdigit():
        # 尝试地理编码获取adcode
        geo = await _http_get(f"{AMAP_BASE}/geocode/geo", {"address": city + "市"})
        if geo.get("geocodes"):
            adcode = geo["geocodes"][0].get("adcode", "")
        else:
            adcode = "110000"  # 默认北京
    else:
        adcode = city

    data = await _http_get(
        f"{AMAP_BASE}/weather/weatherInfo",
        {"city": adcode, "extensions": "base"}
    )
    lives = data.get("lives", [])
    if not lives:
        return _fallback_weather(city)

    w = lives[0]
    return (
        f"📍 {w.get('province', '')} {w.get('city', '')} 实时天气\n"
        f"天气：{w.get('weather', '未知')}\n"
        f"温度：{w.get('temperature', '?')}℃\n"
        f"风向：{w.get('winddirection', '?')}风\n"
        f"风力：{w.get('windpower', '?')}级\n"
        f"湿度：{w.get('humidity', '?')}%\n"
        f"发布时间：{w.get('reporttime', '?')}"
    )


@mcp.tool()
async def get_weather_forecast(city: str = "北京") -> str:
    """
    天气预报（高德API），未来3-4天天气。
    【必填参数】city: 城市名称
    返回: 未来3-4天天气预报
    """
    if not city.isdigit():
        geo = await _http_get(f"{AMAP_BASE}/geocode/geo", {"address": city + "市"})
        adcode = geo.get("geocodes", [{}])[0].get("adcode", "110000")
    else:
        adcode = city

    data = await _http_get(
        f"{AMAP_BASE}/weather/weatherInfo",
        {"city": adcode, "extensions": "all"}
    )
    forecasts = data.get("forecasts", [{}])[0].get("casts", [])
    if not forecasts:
        return f"未获取到{city}的天气预报"

    lines = [f"📍 {city}未来{len(forecasts)}天天气预报："]
    for f in forecasts:
        lines.append(
            f"- {f.get('date', '')}: {f.get('dayweather', '?')}, "
            f"{f.get('daytemp', '?')}℃/{f.get('nighttemp', '?')}℃, "
            f"{f.get('daywind', '?')}风{f.get('daypower', '?')}级"
        )
    return "\n".join(lines)


@mcp.tool()
async def search_around(keyword: str, location: str = "116.3076,39.9847", radius: int = 3000, city: str = "北京") -> str:
    """
    周边搜索（高德API）。搜索指定坐标附近的POI。
    【必填参数】keyword: 搜索关键词
    【可选参数】location: 中心坐标 "lng,lat"（GCJ-02火星坐标），默认天安门
    【可选参数】radius: 搜索半径，单位米，默认3000米
    【可选参数】city: 城市名称
    返回: 附近POI列表（名称、地址、距离、坐标）
    """
    if not keyword:
        return "调用search_around必须提供keyword参数（搜索关键词，如'加油站'、'餐厅'）"

    data = await _http_get(
        f"{AMAP_BASE}/place/around",
        {
            "keywords": keyword,
            "location": location,
            "radius": str(radius),
            "city": city,
            "citylimit": "true",
            "extensions": "base",
            "offset": 8,
        }
    )
    pois = data.get("pois", [])
    if not pois and str(data.get("status")) != "1":
        return _fallback_search_around(keyword, location, radius)

    lines = [f"附近{len(pois)}个{keyword}："]
    for i, p in enumerate(pois, 1):
        name = p.get("name", "")
        address = p.get("address", "")
        loc = p.get("location", "")
        distance = p.get("distance", "")
        dist_str = f"，距离{distance}米" if distance else ""
        lines.append(f"{i}. {name} - {address}{dist_str} ({loc})")
    return "\n".join(lines)


@mcp.tool()
async def get_location_info(location: str) -> str:
    """
    逆地理编码（高德API）。根据经纬度获取详细地址。
    【必填参数】location: 坐标 "lng,lat" 格式
    返回: 详细地址、所在区域
    """
    data = await _http_get(
        f"{AMAP_BASE}/geocode/regeo",
        {"location": location, "extensions": "base", "batch": "false"}
    )
    regeocode = data.get("regeocode", {})
    if not regeocode:
        return f"未找到坐标{location}对应的地址"

    a = regeocode.get("addressComponent", {})
    return (
        f"详细地址：{regeocode.get('formatted_address', '')}\n"
        f"省份：{a.get('province', '')}\n"
        f"城市：{a.get('city', '')}\n"
        f"区县：{a.get('district', '')}\n"
        f"街道：{a.get('streetNumber', {}).get('street', '')} {a.get('streetNumber', {}).get('number', '')}\n"
        f"兴趣点：{', '.join([p.get('name', '') for p in regeocode.get('pois', [])[:3]])}"
    )


if __name__ == "__main__":
    mcp.run(transport='stdio')
