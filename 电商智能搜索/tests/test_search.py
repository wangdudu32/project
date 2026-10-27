import json

import pytest
from fastapi.testclient import TestClient

import database
import ranking
import search_engine
from app import app
from import_data import import_products
from search import compare_products, search_products
from text import extract_constraints


def test_natural_language_budget_color_and_stock():
    result = search_products({"query": "500元以内的白色通勤运动鞋", "mode": "keyword"})
    assert result["products"]
    assert all(
        item["price"] <= 500 and item["color"] == "白色" and item["stock"] > 0
        for item in result["products"]
    )
    assert "p04" not in [item["id"] for item in result["products"]]


def test_excluded_attributes_are_not_reintroduced_by_vector_retrieval(monkeypatch):
    monkeypatch.setattr(ranking, "encode_query", lambda query: [1.0])
    monkeypatch.setattr(
        search_engine,
        "retrieve",
        lambda *arguments: (["p02", "p04", "p05", "p01"], ["p03", "p07", "invented"]),
    )
    result = search_products(
        {"query": "500元以内的白色通勤运动鞋，不要厚底", "mode": "hybrid"}
    )
    assert {item["id"] for item in result["products"]} == {"p01", "p07"}


def test_price_sort_and_pagination_are_consistent():
    first = search_products({"sort": "price_asc", "page_size": 2})
    second = search_products({"sort": "price_asc", "page_size": 2, "page": 2})
    first_ids = {item["id"] for item in first["products"]}
    second_ids = {item["id"] for item in second["products"]}
    assert first_ids.isdisjoint(second_ids)
    assert max(item["price"] for item in first["products"]) <= min(
        item["price"] for item in second["products"]
    )
    assert first["total"] == second["total"] == 6


def test_empty_results_respect_hard_constraints():
    result = search_products({"query": "白色运动鞋", "filters": {"max_price": 10}})
    assert result["products"] == []
    assert result["total"] == 0


def test_filters_treat_sql_and_wildcards_as_literal_text():
    result = search_products({"filters": {"brand": "' OR 1=1 --"}})
    assert result["total"] == 0
    result = search_products({"filters": {"exclude_tags": ["%"]}})
    assert result["total"] == 6


def test_later_turn_preserves_budget_and_color():
    first = extract_constraints("500元以内的白色运动鞋")
    second = extract_constraints("不要厚底的", first)
    third = extract_constraints("预算提高到800，换成黑色", second)
    assert second["max_price"] == 500 and second["color"] == "白色"
    assert "厚底" in second["exclude_tags"]
    assert third["max_price"] == 800 and third["color"] == "黑色"
    assert "厚底" in third["exclude_tags"]


def test_explicit_reset_clears_previous_conditions():
    conditions = extract_constraints(
        "重新开始，找一个双肩包", {"color": "白色", "max_price": 500}
    )
    assert "color" not in conditions and "max_price" not in conditions
    assert conditions["category"] == "包袋"


def test_negative_attribute_does_not_swallow_following_positive_requirements():
    conditions = extract_constraints("不要厚底的白色通勤鞋")
    assert conditions["color"] == "白色"
    assert conditions["exclude_tags"] == ["厚底"]
    result = search_products({"query": "不要厚底的白色通勤鞋", "mode": "keyword"})
    assert result["products"]
    assert all(
        item["color"] == "白色" and "厚底" not in item["tags"]
        for item in result["products"]
    )


def test_bad_import_does_not_destroy_existing_snapshot(tmp_path):
    path = tmp_path / "invalid.jsonl"
    path.write_text(json.dumps({"id": "broken"}))
    with pytest.raises(ValueError, match="缺少字段"):
        import_products(path, with_models=False)
    assert database.product_count() == 7


def test_duplicate_import_is_idempotent(tmp_path, isolated_shop):
    path = tmp_path / "products.jsonl"
    path.write_text(
        "\n".join(json.dumps(item) for item in isolated_shop + [isolated_shop[0]])
    )
    first = import_products(path, with_models=False)
    second = import_products(path, with_models=False)
    assert first["duplicates_removed"] == 1
    assert first["products"] == second["products"] == 7
    assert database.product_count() == 7


def test_comparison_rejects_missing_or_duplicate_products():
    with pytest.raises(LookupError):
        compare_products(["p01", "not-found"])
    with pytest.raises(ValueError):
        compare_products(["p01", "p01"])
    comparison = compare_products(["p01", "p07"])
    assert comparison["rows"][0]["values"] == [299.0, 459.0]


def test_api_rejects_invalid_ranges_and_unknown_fields():
    client = TestClient(app)
    assert (
        client.post(
            "/api/search", json={"filters": {"min_price": 800, "max_price": 300}}
        ).status_code
        == 422
    )
    assert client.post("/api/search", json={"page_size": 100}).status_code == 422
    assert client.post("/api/search", json={"unexpected": True}).status_code == 422
    assert client.get("/api/products/does-not-exist").status_code == 404


def test_api_reports_real_health_without_secrets():
    response = TestClient(app).get("/api/health")
    assert response.status_code == 200
    assert response.json()["products"] == 7
    assert "api_key" not in response.text.lower()
    assert "base_url" not in response.text.lower()
