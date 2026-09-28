from types import SimpleNamespace

import pytest

from tools import pine_cone_tool as vectors


def fake_pinecone(monkeypatch, target):
    import sys
    monkeypatch.setitem(sys.modules, 'pinecone', SimpleNamespace(ServerlessSpec=lambda **kwargs: kwargs))
    monkeypatch.setattr(vectors, 'client', lambda: SimpleNamespace(
        has_index=lambda name: True,
        describe_index=lambda name: SimpleNamespace(status={'ready': True}),
        Index=lambda name: target,
    ))


def test_sync_uses_real_ids_and_only_cleans_own_namespace(monkeypatch):
    events = []
    target = SimpleNamespace(
        upsert=lambda **kwargs: events.append(('upsert', kwargs)),
        list=lambda **kwargs: [['42', '99']],
        delete=lambda **kwargs: events.append(('delete', kwargs)),
    )
    fake_pinecone(monkeypatch, target)
    monkeypatch.setattr(vectors, 'get_menu_item_list', lambda: [{'id': 42}])
    monkeypatch.setattr(vectors, 'menu_text', lambda item: '真实菜品42')
    monkeypatch.setattr(vectors, 'embedding', lambda text: [0.0] * 1536)
    assert vectors.sync_menu() == 1
    assert events[0][0] == 'upsert'
    assert events[0][1]['vectors'][0]['id'] == '42'
    assert events[1] == ('delete', {'ids': ['99'], 'namespace': 'aimenu'})


def test_embedding_failure_does_not_clear_index(monkeypatch):
    events = []
    target = SimpleNamespace(delete=lambda **kwargs: events.append('delete'), upsert=lambda **kwargs: events.append('upsert'))
    fake_pinecone(monkeypatch, target)
    monkeypatch.setattr(vectors, 'get_menu_item_list', lambda: [{'id': 1}])
    monkeypatch.setattr(vectors, 'menu_text', lambda item: '菜品')
    def fail(text):
        raise RuntimeError('embedding failed')
    monkeypatch.setattr(vectors, 'embedding', fail)
    with pytest.raises(RuntimeError):
        vectors.sync_menu()
    assert events == []


def test_search_uses_live_menu_and_filters_unavailable_items(monkeypatch):
    matches = [SimpleNamespace(id='1', score=0.9), SimpleNamespace(id='2', score=0.8)]
    monkeypatch.setattr(vectors, 'index', lambda: SimpleNamespace(query=lambda **kwargs: SimpleNamespace(matches=matches)))
    monkeypatch.setattr(vectors, 'embedding', lambda text: [0.0] * 1536)
    monkeypatch.setattr(vectors, 'get_menu_item_list', lambda: [{'id': 1, 'price': '29.00'}])
    monkeypatch.setattr(vectors, 'menu_text', lambda item: item['price'])
    result = vectors.search_menu_items_with_id('推荐菜品')
    assert result == {'ids': ['1'], 'contents': ['29.00']}


def test_llm_chain_keeps_prompt_fields_separate(monkeypatch):
    pytest.importorskip('langchain_openai')
    from langchain_core.messages import AIMessage
    from langchain_core.runnables import RunnableLambda
    from tools.llm_tool import call_llm
    import config

    seen = []
    def respond(prompt):
        seen.extend(prompt.to_messages())
        return AIMessage(content='收到')
    monkeypatch.setattr(config, 'AI_ENABLED', True)
    monkeypatch.setenv('DASHSCOPE_API_KEY', 'fake-test-key')
    monkeypatch.setattr('langchain_openai.ChatOpenAI', lambda **kwargs: RunnableLambda(respond))
    assert call_llm('当前问题', '系统提示', [{'role': 'user', 'content': '上一轮问题'}]) == '收到'
    assert [message.content for message in seen] == ['系统提示', '上一轮问题', '当前问题']
    assert [message.type for message in seen] == ['system', 'human', 'human']
