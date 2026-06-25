"""
后端版高德路线文本解析器
解析 plan_route 工具返回的文本，提取 polyline / 起点 / 终点 / 距离 / 耗时
"""
import re
from typing import Optional, Dict, List, Tuple


def parse_amap_route(text: str) -> Optional[Dict]:
    """
    解析高德 plan_route 工具返回的路线文本。
    返回字典，包含 polyline/origin/destination/distance/duration。
    """
    if not text:
        return None

    # 起点坐标：116.3076,39.9847
    o_match = re.search(r"起点坐标[：:]\s*([\d.]+)[,，]\s*([\d.]+)", text)
    # 终点坐标：116.3151,39.9828
    d_match = re.search(r"终点坐标[：:]\s*([\d.]+)[,，]\s*([\d.]+)", text)
    # 路线坐标：lng,lat;lng,lat;...
    p_match = re.search(r"路线坐标[：:]\s*([\d.,;\s]+)", text)
    # 距离：12.5公里（12500米）
    dist_match = re.search(r"距离[：:]\s*([\d.]+)\s*公里[（(]?(\d+)?[米)）]?", text)
    # 耗时：1小时30分钟 / 30分钟
    hour_match = re.search(r"(\d+)\s*小时", text)
    min_match = re.search(r"(\d+)\s*分钟", text)

    if not o_match and not d_match and not p_match:
        return None

    # 解析 polyline
    polyline: List[Tuple[float, float]] = []  # [lat, lng] 与 Leaflet 一致
    if p_match:
        for coord in p_match.group(1).split(";"):
            coord = coord.strip()
            if not coord:
                continue
            parts = coord.split(",")
            if len(parts) == 2:
                try:
                    lng = float(parts[0])
                    lat = float(parts[1])
                    polyline.append((lat, lng))
                except ValueError:
                    continue

    # 起点/终点名称
    o_name_match = re.search(r"起点[：:]\s*([^\n]+)", text)
    d_name_match = re.search(r"终点[：:]\s*([^\n]+)", text)

    # 距离（米）
    distance = None
    if dist_match:
        km = float(dist_match.group(1))
        distance = int(km * 1000)

    # 耗时（秒）
    duration = None
    if hour_match or min_match:
        h = int(hour_match.group(1)) if hour_match else 0
        m = int(min_match.group(1)) if min_match else 0
        duration = h * 3600 + m * 60

    return {
        "origin": {
            "lng": float(o_match.group(1)),
            "lat": float(o_match.group(2)),
            "name": o_name_match.group(1).strip() if o_name_match else None,
        } if o_match else None,
        "destination": {
            "lng": float(d_match.group(1)),
            "lat": float(d_match.group(2)),
            "name": d_name_match.group(1).strip() if d_name_match else None,
        } if d_match else None,
        "polyline": polyline,
        "distance": distance,
        "duration": duration,
    }
