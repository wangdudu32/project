import pytest

import config
from LangChain.mcp import load_prompt


def test_local_chat_and_followup(client):
    first = client.post('/chat', json={'query': '推荐不辣的素菜'}).json()
    assert first['mode'] == 'local'
    assert set(first['menu_ids']) == {'3', '5'}
    followup = client.post('/chat', json={'query': '还有 13 元以内的吗', 'history': [
        {'role': 'user', 'content': '推荐不辣的素菜'},
        {'role': 'assistant', 'content': first['recommendation']},
    ]}).json()
    assert followup['menu_ids'] == ['5']
    assert client.post('/chat', json={'query': '推荐 1 元以内的菜'}).json()['menu_ids'] == []


def test_prompt_path_and_general_info(client, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    assert '客服' in load_prompt('general_inquiry')
    monkeypatch.setenv('RESTAURANT_HOURS', '每天 10:00-20:00')
    assert '10:00-20:00' in client.post('/chat', json={'query': '几点营业'}).json()['response']


def test_model_failure_falls_back(client, monkeypatch):
    monkeypatch.setattr(config, 'AI_ENABLED', True)
    def fail(*args, **kwargs):
        raise TimeoutError('do not expose credentials')
    monkeypatch.setattr('LangChain.main.call_llm', fail)
    result = client.post('/chat', json={'query': '推荐不辣的素菜'}).json()
    assert result['mode'] == 'local'
    assert result['menu_ids']
    assert '暂时不可用' in result['notice']
    assert 'credentials' not in str(result)


def test_ai_history_and_current_menu(client, monkeypatch):
    monkeypatch.setattr(config, 'AI_ENABLED', True)
    history = [{'role': 'user', 'content': '我不吃辣'}]
    seen = []
    def intent(query, instruction, messages):
        seen.append(messages)
        return '```json\n{"tool_name":"menu_inquiry","format_query":"推荐不辣的素菜"}\n```'
    def recommend(query, instruction, messages):
        seen.append(messages)
        assert '清炒时蔬' in instruction
        assert '麻婆豆腐' not in instruction
        return '推荐清炒时蔬和蒜蓉西兰花。'
    monkeypatch.setattr('LangChain.main.call_llm', intent)
    monkeypatch.setattr('LangChain.mcp.call_llm', recommend)
    result = client.post('/chat', json={'query': '推荐不辣的素菜', 'history': history}).json()
    assert result['mode'] == 'ai'
    assert seen == [history, history]


def test_chat_validation(client):
    assert client.post('/chat', json={'query': '   '}).status_code == 422
    assert client.post('/chat', json={'query': 'test', 'history': [{'role': 'system', 'content': 'hello'}]}).status_code == 422


def test_followup_preserves_diet_and_unavailable_cuisine(client):
    result = client.post('/chat', json={'query': '推荐几道菜', 'history': [
        {'role': 'user', 'content': '我不吃辣，只吃素食'}
    ]}).json()
    assert set(result['menu_ids']) == {'3', '5'}
    assert client.post('/chat', json={'query': '推荐粤菜'}).json()['menu_ids'] == []


def test_delivery_disabled(client):
    result = client.post('/delivery', json={'address': '北京市中关村'}).json()
    assert result['success'] is False
    assert result['distance'] is None
    assert '暂未启用' in result['message']
    assert client.post('/delivery', json={'address': '北京市中关村', 'travel_mode': 2}).status_code == 422


@pytest.mark.parametrize('mode', ['1', '2', '3'])
def test_delivery_routes(client, monkeypatch, mode):
    monkeypatch.setattr(config, 'AMAP_ENABLED', True)
    monkeypatch.setenv('AMAP_API_KEY', 'fake-test-key')
    monkeypatch.setenv('MERCHANT_LONGITUDE', '116.3')
    monkeypatch.setenv('MERCHANT_LATITUDE', '39.9')
    monkeypatch.setenv('DELIVERY_RADIUS', '2500')
    def fake_request(url, params):
        if 'geocode' in url:
            return {'geocodes': [{'formatted_address': '测试地址', 'location': '116.31,39.91'}]}
        assert params['show_fields'] == 'cost'
        path = {'distance': '2500', 'duration': '600'} if mode == '2' else {'distance': '2500', 'cost': {'duration': '600'}}
        return {'route': {'paths': [path]}}
    monkeypatch.setattr('tools.amap_tool.safe_request', fake_request)
    result = client.post('/delivery', json={'address': '测试地址', 'travel_mode': mode}).json()
    assert result['success'] is True
    assert result['in_range'] is True
    assert result['distance'] == 2.5
    assert result['duration'] == 600


def test_delivery_error_has_clear_message(client, monkeypatch):
    monkeypatch.setattr(config, 'AMAP_ENABLED', True)
    monkeypatch.setenv('AMAP_API_KEY', 'fake-test-key')
    def fail(*args):
        raise ValueError('secret fake-test-key')
    monkeypatch.setattr('tools.amap_tool.safe_request', fail)
    result = client.post('/delivery', json={'address': '测试地址'}).json()
    assert result['success'] is False
    assert 'secret' not in result['message']
