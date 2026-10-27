import pytest

import database
import ranking
import settings
from import_data import normalize_product
from text import tokenize


@pytest.fixture(autouse=True)
def isolated_shop(tmp_path, monkeypatch):
    """Tests use their own database and never call a paid service or download models."""
    monkeypatch.setattr(settings, "database_path", tmp_path / "test.db")
    monkeypatch.setattr(settings, "search_backend", "sqlite")
    monkeypatch.setattr(settings, "runtime", tmp_path)
    monkeypatch.setattr(ranking, "encode_query", lambda query: None)
    monkeypatch.setattr(ranking, "load_reranker", lambda: None)
    database.initialize_database()
    rows = [
        (
            "p01",
            "白色轻量通勤运动鞋",
            "运动鞋",
            "白色",
            299,
            10,
            ["通勤", "轻量", "薄底"],
        ),
        ("p02", "白色厚底通勤运动鞋", "运动鞋", "白色", 399, 20, ["通勤", "厚底"]),
        (
            "p03",
            "黑色轻量通勤运动鞋",
            "运动鞋",
            "黑色",
            259,
            10,
            ["通勤", "轻量", "薄底"],
        ),
        ("p04", "白色低价通勤运动鞋", "运动鞋", "白色", 99, 0, ["通勤", "薄底"]),
        ("p05", "白色高价通勤运动鞋", "运动鞋", "白色", 799, 10, ["通勤", "薄底"]),
        (
            "p06",
            "黑色电脑通勤双肩包",
            "包袋",
            "黑色",
            299,
            10,
            ["通勤", "电脑", "双肩包"],
        ),
        ("p07", "白色薄底日常运动鞋", "运动鞋", "白色", 459, 12, ["通勤", "薄底"]),
    ]
    products = []
    for product_id, name, category, color, price, stock, tags in rows:
        products.append(
            normalize_product(
                {
                    "id": product_id,
                    "name": name,
                    "category": category,
                    "color": color,
                    "price": price,
                    "stock": stock,
                    "tags": tags,
                    "brand": "测试品牌",
                },
                1,
            )
        )
    database.save_products(
        products, [" ".join(tokenize(item["search_text"])) for item in products]
    )
    return products
