import requests
from typing import Dict, Optional, Literal, Union, Any
import json
from requests import RequestException
import os
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3 import Retry
from dataclasses import dataclass
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 加载环境变量
load_dotenv()

# 类型定义
PathMode = Literal["walking", "bicycling", "driving"]
PathModeInput = Literal["1", "2", "3"]  # 外部输入的路径模式


# 配置管理
@dataclass
class Config:
    API_KEY: str = os.getenv("AMAP_API_KEY")
    MERCHANT_LONGITUDE: str = os.getenv("MERCHANT_LONGITUDE", "114.401934")
    MERCHANT_LATITUDE: str = os.getenv("MERCHANT_LATITUDE", "30.465295")
    DELIVERY_RADIUS: int = int(os.getenv("DELIVERY_RADIUS", "2500"))
    DEFAULT_PATH_MODE: PathModeInput = os.getenv("DEFAULT_PATH_MODE", "2")  # 默认使用2(bicycling)

    def __post_init__(self):
        if not self.API_KEY:
            raise ValueError("AMAP_API_KEY 环境变量未设置")


config = Config()


# 路径模式转换工具
class PathModeConverter:
    """路径模式转换工具类"""

    # 映射关系  外部输入的路径模式 -> 内部使用的路径模式
    MODE_MAPPING = {
        "1": "walking",
        "2": "electrobike",
        "3": "driving",

    }

    @classmethod
    def to_mode(cls, mode_input: PathModeInput) -> PathMode:
        """将输入的模式转换为内部使用的模式"""

        if mode_input in cls.MODE_MAPPING:
            return cls.MODE_MAPPING[mode_input]
        else:
            raise ValueError(f"不支持的路径模式: {mode_input}，支持的模式: {list(cls.MODE_MAPPING.keys())}")


def create_session_with_retries():
    """创建带重试机制的requests会话"""
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def safe_request(base_url: str, params: dict) -> Optional[Dict]:
    """安全的HTTP请求，处理重试和SSL降级"""
    session = create_session_with_retries()
    try:
        response = session.get(base_url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.SSLError:
        try:
            http_url = base_url.replace("https://", "http://")
            response = session.get(http_url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise RequestException(f"HTTP请求失败: {e}")
    except requests.exceptions.RequestException as e:
        raise RequestException(f"HTTPS请求失败: {e}")
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(f"JSON解析错误: {e}") from e


def geocode_address(address: str) -> Dict[str, Any]:
    """
    地理编码功能 将地址转换为坐标

    Args:
       address: 用户输入要查询的地址

    Returns:
        Dict: 地理编码结果 包含格式化后的地址、经纬度

   """
    try:
        if not config.API_KEY:
            raise ValueError("API_KEY不存在")

        # 1. 构建请求URL
        base_url = "https://restapi.amap.com/v3/geocode/geo"

        #  2. 构建请求参数
        params = {
            "key": config.API_KEY,
            "address": address,
            "output": "JSON"
        }

        # 3. 发送请求并处理响应
        response_data = safe_request(base_url, params)
        if response_data["status"] == "1" and int(response_data["count"]) > 0:
            geocodes = response_data["geocodes"]
            if geocodes and len(geocodes) > 0:
                return {
                    "formatted_address": geocodes[0]["formatted_address"],
                    "location": geocodes[0]["location"], # “经度,纬度”
                    "status": "success"
                }

        return {
            "status": "fail",
            "message": "高德地图地理坐标解析失败"
        }
    except Exception as e:
        logger.error(f"高德地图地理坐标解析失败,原因:{e}")
        raise


def calculate_distance(origin_location: str, destination_location: str,
                       path_mode_input: PathModeInput = "2") -> Dict[str, Any]:
    """
    不同的路径模式计算两个地点之间的距离和预计时间

    Args:
        origin_location: 起点经纬度
        destination_location:  终点经纬度
        path_mode_input:  路径模式，1:步行，2:骑行，3:驾车

    Returns:
        Dict: 路径结果，包含路径模式、距离、预计时间等

    """
    try:

        if not config.API_KEY:
            raise ValueError("AMAP_API_KEY不存在")
        # 1. 转换外部输入路径模式为内部使用的路径模式
        path_mode = PathModeConverter.to_mode(path_mode_input)

        # 2. 根据路径模式构建不同的请求URL
        endpoints = {
            "walking": "https://restapi.amap.com/v5/direction/walking",
            "electrobike": "https://restapi.amap.com/v5/direction/electrobike",
            "driving": "https://restapi.amap.com/v5/direction/driving"
        }

        # 3. 构建请求参数
        params = {
            "key": config.API_KEY,
            "origin": origin_location,
            "destination": destination_location,
        }

        # 4. 根据路径模式添加不同的参数
        if path_mode == "driving":
            params["show_fields"] = "cost"

        # 5. 发送请求并处理响应
        response = safe_request(endpoints[path_mode], params)
        if response.get("status") == "1":
            path = response["route"]["paths"][0]
            duration = int(path["duration"]) if path_mode == "electrobike" else int(path["cost"]["duration"])
            return {
                "distance": int(path["distance"]),
                "duration": duration,
                "status": "success"
            }

        return {
            "status": "success",
            "message": "高德地图距离解析失败"

        }
    except Exception as e:
        logger.error(f"高德地图距离解析失败,原因:{e}")
        raise


def check_delivery_range(address: str, path_mode_input: PathModeInput = None) -> Dict[str, Any]:
    """检查地址是否在配送范围内

    Args:
        address: 用户输入的地址

        path_mode_input: 路径模式，支持 "1"(walking), "2"(bicycling), "3"(driving)。如果为None则使用配置的默认模式

    Returns:
          包含检查结果的 Dict 对象
    """

    try:
        # 1. 使用传入的模式或默认模式
        if path_mode_input is None:
            path_mode_input = config.DEFAULT_PATH_MODE

        # 2. 地理编码获取经纬度
        geocode_result = geocode_address(address)
        if geocode_result['status'] != "success":
            logger.error("地理位置编码失败")
            return geocode_result

        # 3. 计算距离
        origin_location = f"{config.MERCHANT_LONGITUDE},{config.MERCHANT_LATITUDE}"
        distance_result = calculate_distance(origin_location, geocode_result['location'], path_mode_input)
        if distance_result['status'] != "success":
            return distance_result

        # 4. 检查是否在配送范围内 并返回结果
        in_range = distance_result['distance'] <= config.DELIVERY_RADIUS
        distance_km = round(distance_result['distance'] / 1000, 2)
        return {
            "status": "success",
            "in_range": in_range,
            "distance": distance_km,
            "duration": distance_result['duration'],
            "formatted_address": geocode_result['formatted_address'],
            "message": (
                f"配送地址：{geocode_result['formatted_address']}\n"
                f"配送距离：{distance_km:.2f}公里\n"
                f"配送状态：{'在配送范围内' if in_range else '超出配送范围'}"
            )
        }
    except Exception as e:
        raise


# 使用示例
if __name__ == "__main__":
    # 不同模式的使用
    pass
    test_address = "武汉市洪山区光谷天地"  # 测试地址
    print("\n=== 测试不同路径模式 ===")
    # 测试步行模式 (1)
    print("\n1. 步行模式测试:")
    result1 = check_delivery_range(test_address, "1")
    minutes = result1['duration'] // 60
    seconds = result1['duration'] % 60
    print(f"步行模式距离: {result1['distance']}公里 时间: {result1['duration']}秒 ({minutes}分{round(seconds, 2)}秒)")
    print(f"是否在配送范围内: {result1['message']}")

    # 测试骑行模式 (2)
    print("\n2. 骑电动车模式测试:")
    result2 = check_delivery_range(test_address, "2")
    minutes = result2['duration'] // 60
    seconds = result2['duration'] % 60
    print(f"骑电动车模式距离: {result2['distance']}公里 时间: {result2['duration']}秒 ({minutes}分{round(seconds, 2)}秒)")
    print(f"是否在配送范围内: {result2['message']}")

    # 测试驾车模式 (3)
    print("\n3. 驾车模式测试:")
    result3 = check_delivery_range(test_address, "3")
    minutes = result3['duration'] // 60
    seconds = result3['duration'] % 60
    print(f"驾车模式距离: {result3['distance']}公里 时间: {result3['duration']}秒 ({minutes}分{round(seconds, 2)}秒)")
    print(f"是否在配送范围内: {result3['message']}")