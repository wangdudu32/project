import asyncio
import json

import httpx
import pytest
import respx

import agent
import database
import settings


def model_reply(content=None, name=None, arguments=None):
    message = {"role": "assistant", "content": content}
    if name:
        message["tool_calls"] = [
            {
                "id": "call_test",
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(arguments)},
            }
        ]
    return httpx.Response(200, json={"choices": [{"message": message}]})


@pytest.fixture
def configured_model(monkeypatch):
    monkeypatch.setattr(settings, "api_key", "test-key-only")
    monkeypatch.setattr(settings, "base_url", "https://model.test/v1")
    monkeypatch.setitem(agent.model_status, "model", "test-chat")


def test_real_tool_execution_and_persisted_conversation(configured_model):
    with respx.mock as mock:
        route = mock.post("https://model.test/v1/chat/completions")
        route.side_effect = [
            model_reply(
                name="search_products", arguments={"query": "通勤运动鞋", "filters": {}}
            ),
            model_reply("找到几件符合预算的白色通勤鞋，可以继续比较。"),
        ]
        answer = asyncio.run(agent.answer_message("500元以内的白色通勤运动鞋"))
    assert answer["degraded"] is False
    assert answer["products"]
    assert all(
        item["price"] <= 500 and item["color"] == "白色" for item in answer["products"]
    )
    assert len(database.get_messages(answer["session_id"])) == 2


def test_model_cannot_drop_previous_budget_or_exclusions(configured_model):
    session_id, state = database.load_session()
    state.update(
        query="通勤运动鞋",
        filters={"max_price": 500, "color": "白色", "exclude_tags": ["厚底"]},
    )
    database.save_turn(session_id, state, "之前的需求", {"message": "已记住"})
    with respx.mock as mock:
        mock.post("https://model.test/v1/chat/completions").side_effect = [
            model_reply(
                name="search_products",
                arguments={
                    "query": "通勤运动鞋",
                    "filters": {"max_price": 9999, "exclude_tags": []},
                },
            ),
            model_reply("保留之前的预算、颜色和排除条件，找到这些商品。"),
        ]
        answer = asyncio.run(agent.answer_message("再看看其他款", session_id))
    assert answer["filters"]["max_price"] == 500
    assert "厚底" in answer["filters"]["exclude_tags"]
    assert {item["id"] for item in answer["products"]} == {"p01", "p07"}


def test_upstream_failure_returns_actual_filtered_products(configured_model):
    with respx.mock as mock:
        mock.post("https://model.test/v1/chat/completions").respond(503)
        answer = asyncio.run(agent.answer_message("500元以内白色运动鞋，不要厚底"))
    assert answer["degraded"] is True
    assert {item["id"] for item in answer["products"]} == {"p01", "p07"}
    assert "HTTP 503" in answer["notices"][0]


def test_model_without_tool_calls_cannot_invent_product_results(configured_model):
    with respx.mock as mock:
        mock.post("https://model.test/v1/chat/completions").mock(
            return_value=model_reply("推荐一件数据库里没有的神奇商品。")
        )
        answer = asyncio.run(agent.answer_message("500元以内白色运动鞋"))
    assert answer["degraded"] is True
    assert "神奇" not in answer["message"]
    assert all(
        database.get_product(item["id"]) is not None for item in answer["products"]
    )


def test_comparison_uses_current_candidate_ids_and_database_values():
    state = {"query": "运动鞋", "filters": {}, "product_ids": ["p01", "p07"]}
    comparison = agent.execute_tool(
        "compare_products", {"product_ids": ["p01", "p07"]}, state
    )
    assert comparison["rows"][0]["values"] == [299.0, 459.0]
    with pytest.raises(ValueError, match="候选列表"):
        agent.execute_tool("compare_products", {"product_ids": ["p01", "p05"]}, state)
    with pytest.raises(ValueError, match="未知工具"):
        agent.execute_tool("run_shell", {"command": "ignored"}, state)


def test_explicitly_cleared_budget_is_not_reintroduced_by_model():
    state = {
        "query": "运动鞋",
        "filters": {"color": "白色"},
        "cleared_filters": ["max_price"],
        "product_ids": [],
    }
    result = agent.execute_tool(
        "search_products", {"query": "运动鞋", "filters": {"max_price": 100}}, state
    )
    assert "max_price" not in result["filters"]
    assert any(item["price"] > 100 for item in result["products"])


def test_bad_session_and_blank_messages_are_rejected():
    with pytest.raises(ValueError):
        asyncio.run(agent.answer_message("找鞋", "not-a-session"))
    with pytest.raises(ValueError):
        asyncio.run(agent.answer_message("  "))
