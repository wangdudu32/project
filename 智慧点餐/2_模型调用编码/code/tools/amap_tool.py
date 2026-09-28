import os
from typing import Literal

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import config

PathModeInput = Literal['1', '2', '3']
MODE_MAPPING = {'1': 'walking', '2': 'electrobike', '3': 'driving'}


def safe_request(url, params):
    with requests.Session() as session:
        retry = Retry(total=1, backoff_factor=0.3, status_forcelist=[429, 502, 503, 504])
        session.mount('https://', HTTPAdapter(max_retries=retry))
        response = session.get(url, params=params, timeout=(3, 8))
        response.raise_for_status()
        data = response.json()
        if data.get('status') != '1':
            raise ValueError('地图服务未返回有效结果，请检查地址和地图配置')
        return data


def geocode_address(address):
    data = safe_request('https://restapi.amap.com/v3/geocode/geo',
                        {'key': os.environ['AMAP_API_KEY'], 'address': address})
    if not data.get('geocodes'):
        raise ValueError('没有找到该地址，请补充城市、街道等信息')
    item = data['geocodes'][0]
    return {'formatted_address': item['formatted_address'], 'location': item['location']}


def calculate_distance(origin_location, destination_location, path_mode_input='2'):
    mode = MODE_MAPPING.get(path_mode_input)
    if mode is None:
        raise ValueError('不支持的出行方式')
    data = safe_request(f'https://restapi.amap.com/v5/direction/{mode}',
                        {'key': os.environ['AMAP_API_KEY'], 'origin': origin_location,
                         'destination': destination_location, 'show_fields': 'cost'})
    paths = data.get('route', {}).get('paths') or []
    if not paths:
        raise ValueError('没有找到可用路线')
    path = paths[0]
    duration = path.get('duration', path.get('cost', {}).get('duration'))
    if duration is None:
        raise ValueError('地图服务未返回预计时间')
    return {'distance': int(path['distance']), 'duration': int(duration)}


def check_delivery_range(address, path_mode_input='2'):
    failure = {'status': 'fail', 'in_range': False, 'distance': None, 'duration': None,
               'formatted_address': address}
    if not config.AMAP_ENABLED or not os.getenv('AMAP_API_KEY'):
        return {**failure, 'message': '配送查询暂未启用，请联系商家确认配送范围。'}
    try:
        geo = geocode_address(address)
        longitude = os.environ['MERCHANT_LONGITUDE']
        latitude = os.environ['MERCHANT_LATITUDE']
        route = calculate_distance(f'{longitude},{latitude}', geo['location'], path_mode_input)
        in_range = route['distance'] <= int(os.getenv('DELIVERY_RADIUS', '2500'))
        return {'status': 'success', 'in_range': in_range, 'distance': round(route['distance'] / 1000, 2),
                'duration': route['duration'], 'formatted_address': geo['formatted_address'],
                'message': '该地址在配送范围内' if in_range else '该地址超出配送范围'}
    except ValueError:
        return {**failure, 'message': '未能查询到路线，请检查地址，或联系商家确认配送。'}
    except (requests.RequestException, KeyError, TypeError, IndexError):
        return {**failure, 'message': '配送查询暂时不可用，请稍后重试或联系商家。'}
