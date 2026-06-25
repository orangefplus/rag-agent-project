"""
车辆状态模拟器
模拟真实车辆的状态数据，供MCP Server读写，实现车控操作的状态持久化。
使用本地文件持久化来跨进程同步（MCP Server在子进程中运行）。
"""
import os
import json
import time
import random
from datetime import datetime, timedelta


# 状态持久化文件路径（项目data目录下）
_STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "vehicle_state.json")


def _load_persisted_state() -> dict:
    """从文件加载已持久化的状态"""
    if not os.path.exists(_STATE_FILE):
        return {}
    try:
        with open(_STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _persist_state(state_dict: dict):
    """将状态持久化到文件"""
    try:
        os.makedirs(os.path.dirname(_STATE_FILE), exist_ok=True)
        with open(_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state_dict, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


class VehicleState:
    """车辆状态单例，模拟真实车辆数据。
    每次读取状态时会先尝试从文件加载最新持久化的状态。"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_state()
        return cls._instance

    def _init_state(self):
        now = datetime.now()
        # 基本车况
        self.battery_percent = 78  # 电池电量 %
        self.battery_health = 96  # 电池健康度 SOH %
        self.range_km = 412  # 续航里程 km
        self.total_mileage = 15680  # 总里程 km
        self.speed = 0  # 当前车速 km/h
        self.vin = "LSGAB52L9DF012345"  # 车架号
        self.car_model = "智行X9 纯电版"  # 车型
        self.location = {"city": "北京", "district": "海淀区", "lat": 39.9847, "lng": 116.3076}

        # 胎压 (前左、前右、后左、后右) bar
        self.tire_pressure = [2.5, 2.5, 2.5, 2.6]

        # 温度
        self.outdoor_temp = 28  # 室外温度
        self.indoor_temp = 32  # 室内温度

        # 空调状态
        self.ac_on = True
        self.ac_temp = 24
        self.ac_fan_speed = 3  # 0-7
        self.ac_mode = "auto"  # auto/face/foot/defrost

        # 车窗 (主驾、副驾、左后、右后) 开度 0-100
        self.windows = [0, 0, 0, 0]

        # 天窗 0-100
        self.sunroof = 0
        self.sunshade = 100  # 遮阳帘 0关 100开

        # 座椅 (主驾加热0-3, 通风0-3, 副驾加热0-3, 通风0-3)
        self.seat_heating = [0, 0]
        self.seat_ventilation = [0, 0]
        self.steering_heating = 0  # 方向盘加热 0-2

        # 氛围灯
        self.ambient_light_on = True
        self.ambient_light_color = "蓝色"
        self.ambient_light_mode = "呼吸"  # 单色/渐变/呼吸/律动

        # 驾驶模式
        self.driving_mode = "舒适"  # 经济/舒适/运动/雪地/越野
        self.energy_recovery = "中"  # 单踏板/弱/中/强

        # 故障码
        self.fault_codes = []  # 当前无故障

        # 保养
        self.last_maintenance_mileage = 10000
        self.next_maintenance_mileage = 20000

        # 充电状态
        self.charging = False
        self.charge_limit = 80  # 充电限值

        # 常用地址
        self.common_addresses = [
            {"name": "家", "address": "北京市海淀区中关村大街1号", "lat": 39.9847, "lng": 116.3076, "tag": "home"},
            {"name": "公司", "address": "北京市朝阳区国贸大厦", "lat": 39.9089, "lng": 116.4574, "tag": "work"},
            {"name": "孩子学校", "address": "北京市海淀区清华附小", "lat": 40.0084, "lng": 116.3225, "tag": "school"},
            {"name": "常去健身房", "address": "北京市海淀区五道口华联商场", "lat": 39.9928, "lng": 116.3380, "tag": "gym"},
        ]

        # 预约记录
        self.appointments = []

        # 行程记录
        self.trips = [
            {"date": (now - timedelta(days=1)).strftime("%Y-%m-%d"), "from": "公司", "to": "家", "distance": 18.5, "duration": 42},
            {"date": (now - timedelta(days=2)).strftime("%Y-%m-%d"), "from": "家", "to": "孩子学校", "distance": 6.2, "duration": 18},
        ]

    def _refresh_from_disk(self):
        """从持久化文件加载最新状态（如果存在）"""
        persisted = _load_persisted_state()
        if not persisted:
            return
        # 同步需要持久化的字段
        for key in ["ac_on", "ac_temp", "ac_fan_speed", "ac_mode",
                    "windows", "sunroof", "sunshade",
                    "seat_heating", "seat_ventilation", "steering_heating",
                    "ambient_light_on", "ambient_light_color", "ambient_light_mode",
                    "driving_mode", "energy_recovery", "fault_codes",
                    "battery_percent", "battery_health", "range_km", "total_mileage",
                    "indoor_temp", "outdoor_temp", "tire_pressure", "location",
                    "charging", "charge_limit"]:
            if key in persisted:
                setattr(self, key, persisted[key])

    def _save_to_disk(self):
        """将可变状态持久化到文件"""
        state_to_save = {
            "ac_on": self.ac_on,
            "ac_temp": self.ac_temp,
            "ac_fan_speed": self.ac_fan_speed,
            "ac_mode": self.ac_mode,
            "windows": self.windows,
            "sunroof": self.sunroof,
            "sunshade": self.sunshade,
            "seat_heating": self.seat_heating,
            "seat_ventilation": self.seat_ventilation,
            "steering_heating": self.steering_heating,
            "ambient_light_on": self.ambient_light_on,
            "ambient_light_color": self.ambient_light_color,
            "ambient_light_mode": self.ambient_light_mode,
            "driving_mode": self.driving_mode,
            "energy_recovery": self.energy_recovery,
            "fault_codes": self.fault_codes,
            "battery_percent": self.battery_percent,
            "battery_health": self.battery_health,
            "range_km": self.range_km,
            "total_mileage": self.total_mileage,
            "indoor_temp": self.indoor_temp,
            "outdoor_temp": self.outdoor_temp,
            "tire_pressure": self.tire_pressure,
            "location": self.location,
            "charging": self.charging,
            "charge_limit": self.charge_limit,
            "updated_at": time.time(),
        }
        _persist_state(state_to_save)

    def add_appointment(self, appointment):
        self.appointments.append(appointment)
        self._save_to_disk()

    def get_status_summary(self) -> dict:
        # 每次返回前先从磁盘同步最新状态（让主进程能读到子进程的修改）
        self._refresh_from_disk()
        return {
            "车型": self.car_model,
            "车架号": self.vin,
            "电池电量": f"{self.battery_percent}%",
            "电池健康度": f"{self.battery_health}%",
            "续航里程": f"{self.range_km}km",
            "总里程": f"{self.total_mileage}km",
            "当前位置": f"{self.location['city']}{self.location['district']}",
            # 结构化胎压数据（供前端直接使用）
            "胎压": {
                "fl": self.tire_pressure[0],
                "fr": self.tire_pressure[1],
                "rl": self.tire_pressure[2],
                "rr": self.tire_pressure[3],
            },
            "胎压_文本": f"前左{self.tire_pressure[0]}bar/前右{self.tire_pressure[1]}bar/后左{self.tire_pressure[2]}bar/后右{self.tire_pressure[3]}bar",
            "室外温度": f"{self.outdoor_temp}℃",
            "车内温度": f"{self.indoor_temp}℃",
            "空调": f"{'开启' if self.ac_on else '关闭'}, {self.ac_temp}℃, {self.ac_fan_speed}档风",
            "车窗": f"主驾{self.windows[0]}%/副驾{self.windows[1]}%/左后{self.windows[2]}%/右后{self.windows[3]}%",
            "天窗": f"开度{self.sunroof}%",
            "氛围灯": f"{'开启' if self.ambient_light_on else '关闭'}, {self.ambient_light_color}, {self.ambient_light_mode}模式",
            "驾驶模式": self.driving_mode,
            "能量回收": self.energy_recovery,
            "故障码": "无" if not self.fault_codes else ",".join(self.fault_codes),
            "充电状态": "充电中" if self.charging else "未充电",
            "下次保养": f"{self.next_maintenance_mileage}km",
        }


# 全局单例
vehicle_state = VehicleState()
