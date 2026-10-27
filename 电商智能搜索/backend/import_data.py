"""Validate a complete snapshot before replacing searchable product data."""

import json
import math
import re
from datetime import date

import database
import ranking
import search_engine
import settings
from text import tokenize


def normalize_product(raw, line_number):
    product = dict(raw)
    required = ("id", "name", "brand", "category", "color", "price", "stock", "tags")
    missing = [field for field in required if field not in product]
    if missing:
        raise ValueError(f"第 {line_number} 行缺少字段：{', '.join(missing)}")
    if not isinstance(product["id"], str) or not re.fullmatch(
        r"[a-zA-Z0-9-]{1,40}", product["id"]
    ):
        raise ValueError(f"第 {line_number} 行商品 ID 格式不正确")
    for field in ("name", "brand", "category", "color"):
        if not isinstance(product[field], str) or not product[field].strip():
            raise ValueError(f"第 {line_number} 行 {field} 必须是非空字符串")
        product[field] = product[field].strip()
    product["price"] = round(float(product["price"]), 2)
    if not math.isfinite(product["price"]) or product["price"] < 0:
        raise ValueError(f"第 {line_number} 行价格不合法")
    product["stock"] = int(product["stock"])
    if product["stock"] < 0:
        raise ValueError(f"第 {line_number} 行库存不能为负数")
    if not isinstance(product["tags"], list) or any(
        not isinstance(tag, str) for tag in product["tags"]
    ):
        raise ValueError(f"第 {line_number} 行 tags 必须是字符串列表")
    product["tags"] = list(
        dict.fromkeys(tag.strip() for tag in product["tags"] if tag.strip())
    )
    product.setdefault("subtitle", " / ".join(product["tags"][:3]))
    product.setdefault("family_id", product["id"])
    product.setdefault("description", "")
    product.setdefault("original_price", product["price"])
    product.setdefault("popularity", 0)
    product.setdefault("created_at", date.today().isoformat())
    product.setdefault("color_label", product["color"])
    product.setdefault("material", "未提供")
    product.setdefault("weight", "未提供")
    product.setdefault("sizes", ["均码"])
    product.setdefault("image", "/images/white-runner.jpg")
    product.setdefault("is_demo", False)
    product["search_text"] = " ".join(
        [
            product["name"],
            product["brand"],
            product["category"],
            product["color"],
            " ".join(product["tags"]),
            product["description"],
            product["material"],
        ]
    )
    return product


def import_products(path, with_models=True):
    products_by_id = {}
    duplicate_count = 0
    with path.open() as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            product = normalize_product(json.loads(line), line_number)
            duplicate_count += product["id"] in products_by_id
            products_by_id[product["id"]] = product
    if not products_by_id:
        raise ValueError("导入文件不能为空")
    products = list(products_by_id.values())
    words = [" ".join(tokenize(product["search_text"])) for product in products]
    database.initialize_database()
    database.save_products(products, words)
    ranking.load_vectors.cache_clear()
    vectors_built = ranking.build_vectors(products) if with_models else False
    published = search_engine.publish_index(
        products, ranking.load_vectors() if vectors_built else None
    )
    result = {
        "products": len(products),
        "duplicates_removed": duplicate_count,
        "vectors_built": vectors_built,
        "opensearch_published": published,
    }
    (settings.runtime / "import_report.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2)
    )
    return result
