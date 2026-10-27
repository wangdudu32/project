"""Chinese tokenization and a small, readable set of explicit filter rules."""

import logging
import re

import jieba

import settings


jieba.setLogLevel(logging.WARNING)
jieba.dt.tmp_dir = str(settings.runtime)
stop_words = {
    "的",
    "了",
    "我",
    "想",
    "要",
    "找",
    "帮",
    "帮我",
    "一下",
    "一双",
    "一个",
    "一件",
    "适合",
    "有没有",
    "以内",
    "以下",
    "不要",
    "元",
    "推荐",
    "商品",
    "买",
    "不超过",
}
color_words = {
    "白色": ("白色", "白鞋", "米白", "雾白"),
    "黑色": ("黑色", "黑鞋", "曜黑"),
    "蓝色": ("蓝色", "蓝鞋", "海蓝"),
    "绿色": ("绿色", "绿鞋", "苔绿"),
    "灰色": ("灰色", "灰鞋", "岩灰"),
    "棕色": ("棕色", "棕鞋", "卡其"),
}
negative_attributes = r"厚底|皮革|高帮|低帮|网面|防水|黑色|白色|蓝色|绿色|灰色|棕色"


def tokenize(text):
    text = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff ]", " ", text.lower())
    return list(
        dict.fromkeys(
            word.strip()
            for word in jieba.cut_for_search(text)
            if word.strip() and word not in stop_words and len(word.strip()) > 1
        )
    )


def extract_constraints(message, previous=None):
    """Only change conditions explicitly mentioned; later turns retain earlier filters."""
    filters = {**(previous or {})}
    excluded = list(filters.get("exclude_tags", []))
    if re.search(r"重新开始|重新找|清空条件|换个需求|全部重置", message):
        filters = {}
        excluded = []
    if re.search(r"不限(?:预算|价格)|(?:预算|价格)不限|不限制价格", message):
        filters.pop("min_price", None)
        filters.pop("max_price", None)
    interval = re.search(
        r"(\d+(?:\.\d+)?)\s*(?:到|至|[-~～])\s*(\d+(?:\.\d+)?)\s*(?:元|块)", message
    )
    upper = re.search(r"(\d+(?:\.\d+)?)\s*(?:元|块)?\s*(?:以内|以下|之内)", message)
    prefix = re.search(
        r"(?:预算(?:改为|提高到|降到|提到)?|不超过|最多|低于|小于)\s*(\d+(?:\.\d+)?)",
        message,
    )
    lower = re.search(r"(\d+(?:\.\d+)?)\s*(?:元|块)?\s*(?:以上|起)", message)
    if interval:
        filters["min_price"] = float(interval[1])
        filters["max_price"] = float(interval[2])
    elif upper or prefix:
        filters["max_price"] = float((upper or prefix)[1])
        if filters.get("min_price", 0) > filters["max_price"]:
            filters.pop("min_price", None)
    if lower and not interval:
        filters["min_price"] = float(lower[1])
        if filters.get("max_price", float("inf")) < filters["min_price"]:
            filters.pop("max_price", None)
    if re.search(r"不限颜色|颜色不限|什么颜色都行", message):
        filters.pop("color", None)
        excluded = [tag for tag in excluded if tag not in color_words]
    for color, aliases in color_words.items():
        for alias in aliases:
            if alias not in message:
                continue
            position = message.index(alias)
            prefix_text = message[max(0, position - 5) : position]
            if re.search(r"(?:不要|排除|不想要|不考虑|不看)\s*$", prefix_text):
                excluded.append(color)
                if filters.get("color") == color:
                    filters.pop("color", None)
            else:
                filters["color"] = color
                excluded = [tag for tag in excluded if tag != color]
            break
    for match in re.finditer(
        r"(?:不要|排除|不想要|不考虑|不看)\s*(" + negative_attributes + r")", message
    ):
        excluded.append(match[1])
    filters["exclude_tags"] = list(dict.fromkeys(excluded))[:12]
    categories = (
        ("户外鞋", r"户外鞋|徒步鞋|登山鞋|越野鞋"),
        ("运动鞋", r"运动鞋|跑鞋|跑步鞋|德训鞋|板鞋|帆布鞋|通勤鞋"),
        ("包袋", r"双肩包|背包|斜挎包|托特包|旅行包|通勤包"),
        ("服饰", r"短袖|长袖|外套|冲锋衣|T恤|卫衣"),
        ("配饰", r"腕表|太阳镜|帽子|棒球帽"),
    )
    for category, pattern in categories:
        if re.search(pattern, message):
            filters["category"] = category
            break
    filters.setdefault("in_stock", True)
    return filters


def retrieval_text(query):
    """Keep exclusions as filters rather than positive retrieval terms."""
    text = re.sub(
        r"(?:不要|排除|不想要|不考虑|不看)\s*(?:"
        + negative_attributes
        + r")(?:的|款)?",
        " ",
        query,
    )
    text = re.sub(r"\d+(?:\.\d+)?\s*(?:元|块)?\s*(?:以内|以下|以上|之内)", " ", text)
    return text.strip()
