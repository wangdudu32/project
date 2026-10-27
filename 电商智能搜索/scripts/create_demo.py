"""Create transparent, reproducible demo data and download local photo assets."""

import json
import urllib.request
from pathlib import Path


root = Path.cwd()
data_folder = root / "data"
assets = root / "frontend" / "public" / "images"
data_folder.mkdir(exist_ok=True)
assets.mkdir(parents=True, exist_ok=True)

# These photos illustrate style, not a real SKU. All product specifications are simulated.
photos = {
    "white-runner": "photo-1600185365483-26d7a4cc7519",
    "red-runner": "photo-1542291026-7eec264c27ff",
    "cream-runner": "photo-1549298916-b41d501d3772",
    "daily-runner": "photo-1549298916-b41d501d3772",
    "sport-shoe": "photo-1608231387042-66d1773070a5",
    "canvas-shoe": "photo-1525966222134-fcfa99b8ae77",
    "jacket": "photo-1551028719-00167b16eac5",
    "shirt": "photo-1521572163474-6864f9cf17ab",
    "backpack": "photo-1553062407-98eeb64c6a62",
    "shoulder-bag": "photo-1548036328-c9fa89d128fa",
    "watch": "photo-1523275335684-37898b6baf30",
    "sunglasses": "photo-1572635196237-14b3f281503f",
    "cap": "photo-1588850561407-ed78c282e89b",
}
sources = []
for name, photo in photos.items():
    target = assets / f"{name}.jpg"
    url = f"https://images.unsplash.com/{photo}?auto=format&fit=crop&w=720&q=85"
    if not target.exists():
        try:
            request = urllib.request.Request(
                url, headers={"User-Agent": "SEEK-demo/1.0"}
            )
            with urllib.request.urlopen(request, timeout=20) as response:
                image = response.read()
            if len(image) < 1000:
                raise ValueError("Image response is too short")
            target.write_bytes(image)
            print(f"Downloaded {name}", flush=True)
        except Exception as error:
            print(f"Could not download {name}: {error}", flush=True)
    sources.append(
        {
            "file": f"images/{name}.jpg",
            "url": url,
            "source": "Unsplash",
            "purpose": "Style illustration for simulated products",
        }
    )

# name, category, color, price, brand, tags, photo
templates = [
    (
        "AIR FORM 轻量缓震跑鞋",
        "运动鞋",
        "白色",
        399,
        "SEEK STUDIO",
        ["通勤", "轻量", "缓震", "透气", "低帮", "薄底"],
        "white-runner",
    ),
    (
        "DAILY WALK 复古德训鞋",
        "运动鞋",
        "白色",
        329,
        "步履",
        ["通勤", "复古", "百搭", "低帮", "薄底", "皮革"],
        "canvas-shoe",
    ),
    (
        "CLOUD STEP 厚底休闲鞋",
        "运动鞋",
        "白色",
        459,
        "轻行",
        ["通勤", "厚底", "缓震", "增高", "网面"],
        "sport-shoe",
    ),
    (
        "PACE ONE 城市跑步鞋",
        "运动鞋",
        "黑色",
        429,
        "HORIZON",
        ["跑步", "轻量", "透气", "缓震", "低帮"],
        "sport-shoe",
    ),
    (
        "COURT LOW 经典板鞋",
        "运动鞋",
        "白色",
        269,
        "日常制造",
        ["通勤", "板鞋", "薄底", "低帮", "百搭"],
        "canvas-shoe",
    ),
    (
        "STREET FLEX 复古运动鞋",
        "运动鞋",
        "蓝色",
        369,
        "SEEK STUDIO",
        ["复古", "街头", "通勤", "低帮", "网面"],
        "white-runner",
    ),
    (
        "SPEED KNIT 透气跑鞋",
        "运动鞋",
        "灰色",
        359,
        "轻行",
        ["跑步", "健身", "透气", "轻量", "网面", "薄底"],
        "white-runner",
    ),
    (
        "CITY HIGH 高帮帆布鞋",
        "运动鞋",
        "黑色",
        239,
        "步履",
        ["街头", "高帮", "帆布", "复古"],
        "canvas-shoe",
    ),
    (
        "RETRO TRACK 复古慢跑鞋",
        "运动鞋",
        "棕色",
        389,
        "HORIZON",
        ["复古", "通勤", "缓震", "麂皮"],
        "daily-runner",
    ),
    (
        "AIR LITE 轻盈日常跑鞋",
        "运动鞋",
        "白色",
        299,
        "轻行",
        ["跑步", "通勤", "轻量", "透气", "薄底"],
        "white-runner",
    ),
    (
        "TRAIL ZERO 轻量越野鞋",
        "户外鞋",
        "绿色",
        599,
        "山野",
        ["徒步", "越野", "防滑", "轻量", "低帮"],
        "sport-shoe",
    ),
    (
        "RIDGE PRO 防水徒步鞋",
        "户外鞋",
        "黑色",
        699,
        "山野",
        ["徒步", "防水", "防滑", "高帮", "耐磨"],
        "sport-shoe",
    ),
    (
        "WILD ROUTE 城市户外鞋",
        "户外鞋",
        "灰色",
        499,
        "HORIZON",
        ["徒步", "通勤", "防滑", "低帮", "耐磨"],
        "daily-runner",
    ),
    (
        "SUMMIT 防水登山鞋",
        "户外鞋",
        "棕色",
        799,
        "山野",
        ["登山", "徒步", "防水", "高帮", "耐磨"],
        "daily-runner",
    ),
    (
        "FIELD WALK 轻徒步鞋",
        "户外鞋",
        "白色",
        469,
        "轻行",
        ["徒步", "轻量", "通勤", "低帮", "薄底"],
        "white-runner",
    ),
    (
        "URBAN SHELL 轻量防风外套",
        "服饰",
        "黑色",
        499,
        "山野",
        ["通勤", "防风", "轻量", "户外", "外套"],
        "jacket",
    ),
    (
        "DAILY TEE 纯棉基础短袖",
        "服饰",
        "白色",
        129,
        "日常制造",
        ["通勤", "纯棉", "短袖", "宽松", "百搭"],
        "shirt",
    ),
    (
        "SOFT LAYER 宽松长袖",
        "服饰",
        "灰色",
        199,
        "SEEK STUDIO",
        ["通勤", "长袖", "宽松", "亲肤"],
        "shirt",
    ),
    (
        "RAIN GUARD 防水冲锋衣",
        "服饰",
        "绿色",
        699,
        "山野",
        ["徒步", "防水", "防风", "冲锋衣", "外套"],
        "jacket",
    ),
    (
        "MOVE FREE 速干运动短袖",
        "服饰",
        "蓝色",
        169,
        "轻行",
        ["健身", "跑步", "速干", "透气", "短袖"],
        "shirt",
    ),
    (
        "WEEKEND 轻薄休闲外套",
        "服饰",
        "棕色",
        359,
        "HORIZON",
        ["通勤", "外套", "轻薄", "百搭"],
        "jacket",
    ),
    (
        "CITY PACK 轻量通勤双肩包",
        "包袋",
        "黑色",
        299,
        "HORIZON",
        ["通勤", "双肩包", "轻量", "电脑", "大容量"],
        "backpack",
    ),
    (
        "DAY TRIP 户外旅行背包",
        "包袋",
        "绿色",
        459,
        "山野",
        ["徒步", "旅行", "双肩包", "防泼水", "大容量"],
        "backpack",
    ),
    (
        "SOFT TOTE 日常托特包",
        "包袋",
        "棕色",
        229,
        "日常制造",
        ["通勤", "托特包", "帆布", "大容量"],
        "shoulder-bag",
    ),
    (
        "MINI CROSS 轻便斜挎包",
        "包袋",
        "黑色",
        189,
        "SEEK STUDIO",
        ["通勤", "斜挎包", "轻量", "小巧"],
        "shoulder-bag",
    ),
    (
        "WEEKENDER 短途旅行包",
        "包袋",
        "灰色",
        399,
        "HORIZON",
        ["旅行", "大容量", "健身", "手提包"],
        "backpack",
    ),
    (
        "FORM WATCH 极简腕表",
        "配饰",
        "白色",
        499,
        "SEEK STUDIO",
        ["通勤", "腕表", "简约", "石英"],
        "watch",
    ),
    (
        "SHADE ONE 经典太阳镜",
        "配饰",
        "黑色",
        199,
        "日常制造",
        ["太阳镜", "旅行", "户外", "百搭"],
        "sunglasses",
    ),
    (
        "TRAIL CAP 透气运动帽",
        "配饰",
        "绿色",
        129,
        "山野",
        ["帽子", "徒步", "跑步", "透气", "速干"],
        "cap",
    ),
    (
        "DAILY CAP 经典棒球帽",
        "配饰",
        "黑色",
        99,
        "步履",
        ["帽子", "通勤", "纯棉", "百搭"],
        "cap",
    ),
    (
        "CITY TIME 复古腕表",
        "配饰",
        "棕色",
        399,
        "HORIZON",
        ["腕表", "复古", "通勤", "皮革"],
        "watch",
    ),
    (
        "LIGHT FRAME 轻量太阳镜",
        "配饰",
        "灰色",
        159,
        "轻行",
        ["太阳镜", "轻量", "旅行", "户外"],
        "sunglasses",
    ),
]

products = []
display_order = [0, 5, 21, 15, 10, 26, 1, 22, 16, 27, 2, 23] + [
    index
    for index in range(len(templates))
    if index not in [0, 5, 21, 15, 10, 26, 1, 22, 16, 27, 2, 23]
]
for index, (name, category, color, price, brand, tags, photo) in enumerate(templates):
    for edition in range(8):
        current_price = price + edition * 20
        product_id = f"p{index * 8 + edition + 1:04d}"
        image_name = photo if (assets / f"{photo}.jpg").exists() else "white-runner"
        product = {
            "id": product_id,
            "family_id": f"series{index + 1:02d}",
            "name": f"{name} {edition + 1:02d}",
            "subtitle": " / ".join(tags[:3]),
            "brand": brand,
            "category": category,
            "color": color,
            "color_label": {
                "白色": "雾白",
                "黑色": "曜黑",
                "蓝色": "海蓝",
                "灰色": "岩灰",
                "绿色": "苔绿",
                "棕色": "沙棕",
            }[color],
            "price": current_price,
            "original_price": current_price + 100,
            "stock": 0 if edition == 7 else 8 + ((index * 7 + edition * 3) % 80),
            "popularity": 10000 - edition * 1000 - display_order.index(index) * 10,
            "tags": tags,
            "description": f"以{tags[0]}场景为灵感，结合{'、'.join(tags[1:4])}设计。{name.split(' ')[0]} 系列适合在城市与日常之间自由切换。此条商品及规格为项目演示数据。",
            "material": "网布 / 合成材料"
            if "鞋" in category
            else ("棉 / 聚酯纤维" if category == "服饰" else "合成材料"),
            "sizes": ["36", "37", "38", "39", "40", "41", "42", "43"]
            if "鞋" in category
            else (["S", "M", "L", "XL"] if category == "服饰" else ["均码"]),
            "weight": f"{210 + index * 4 + edition * 2} g",
            "image": f"/images/{image_name}.jpg",
            "created_at": f"2026-10-{27 - (index % 20):02d}",
            "is_demo": True,
        }
        products.append(product)

# Each query's grading rules are independent of the retrieval implementation.
specifications = [
    ("白色通勤运动鞋", {"category": "运动鞋", "color": "白色"}, ["通勤"]),
    (
        "500元以内的白色跑鞋",
        {"category": "运动鞋", "color": "白色", "max_price": 500},
        ["跑步"],
    ),
    (
        "不要厚底的白色通勤鞋",
        {"color": "白色", "exclude": "厚底", "category": "运动鞋"},
        ["通勤", "薄底"],
    ),
    ("轻量透气跑步鞋", {"category": "运动鞋"}, ["轻量", "透气", "跑步"]),
    ("黑色高帮帆布鞋", {"category": "运动鞋", "color": "黑色"}, ["高帮", "帆布"]),
    ("复古德训鞋", {"category": "运动鞋"}, ["复古", "薄底", "皮革"]),
    ("适合健身的透气运动鞋", {"category": "运动鞋"}, ["健身", "透气"]),
    ("蓝色街头运动鞋", {"category": "运动鞋", "color": "蓝色"}, ["街头"]),
    ("缓震厚底休闲鞋", {"category": "运动鞋"}, ["厚底", "缓震"]),
    ("300元以内的板鞋", {"category": "运动鞋", "max_price": 300}, ["板鞋"]),
    ("轻量越野徒步鞋", {"category": "户外鞋"}, ["越野", "轻量", "徒步"]),
    ("黑色防水高帮徒步鞋", {"category": "户外鞋", "color": "黑色"}, ["防水", "高帮"]),
    ("600元以内的户外鞋", {"category": "户外鞋", "max_price": 600}, ["徒步"]),
    ("白色低帮轻徒步鞋", {"category": "户外鞋", "color": "白色"}, ["低帮", "轻量"]),
    ("耐磨防滑登山鞋", {"category": "户外鞋"}, ["登山", "耐磨", "防水"]),
    ("轻薄防风通勤外套", {"category": "服饰"}, ["防风", "轻量", "通勤"]),
    ("白色纯棉短袖", {"category": "服饰", "color": "白色"}, ["纯棉", "短袖"]),
    (
        "200元以内的速干运动短袖",
        {"category": "服饰", "max_price": 200},
        ["速干", "短袖"],
    ),
    ("徒步防水冲锋衣", {"category": "服饰"}, ["徒步", "防水", "冲锋衣"]),
    ("宽松长袖日常穿", {"category": "服饰"}, ["宽松", "长袖"]),
    ("能装电脑的黑色双肩包", {"category": "包袋", "color": "黑色"}, ["电脑", "双肩包"]),
    ("300元以内的通勤包", {"category": "包袋", "max_price": 300}, ["通勤"]),
    ("户外旅行大容量背包", {"category": "包袋"}, ["旅行", "大容量", "双肩包"]),
    ("轻便小巧斜挎包", {"category": "包袋"}, ["斜挎包", "轻量", "小巧"]),
    ("帆布托特包", {"category": "包袋"}, ["帆布", "托特包"]),
    ("简约白色腕表", {"category": "配饰", "color": "白色"}, ["腕表", "简约"]),
    ("200元以内的太阳镜", {"category": "配饰", "max_price": 200}, ["太阳镜"]),
    ("跑步速干透气帽子", {"category": "配饰"}, ["帽子", "速干", "透气"]),
    ("黑色纯棉棒球帽", {"category": "配饰", "color": "黑色"}, ["帽子", "纯棉"]),
    (
        "棕色复古皮革腕表",
        {"category": "配饰", "color": "棕色"},
        ["腕表", "复古", "皮革"],
    ),
]
queries = []
for index, (query, conditions, wanted_tags) in enumerate(specifications):
    judgments = {}
    for product in products:
        eligible = product["stock"] > 0
        for field in ("category", "color"):
            eligible = eligible and (
                not conditions.get(field) or product[field] == conditions[field]
            )
        eligible = eligible and product["price"] <= conditions.get("max_price", 100000)
        eligible = eligible and conditions.get("exclude", "") not in product["tags"]
        matches = sum(tag in product["tags"] for tag in wanted_tags)
        grade = (
            (3 if matches == len(wanted_tags) else 1 if matches else 0)
            if eligible
            else 0
        )
        if grade:
            judgments[product["id"]] = grade
    queries.append(
        {
            "id": f"q{index + 1:02d}",
            "query": query,
            "relevance": judgments,
            "label_source": "Rule-generated synthetic regression judgments, not human relevance labels",
        }
    )

for name, rows in (("products.jsonl", products), ("queries.jsonl", queries)):
    (data_folder / name).write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n"
    )
(data_folder / "image_sources.json").write_text(
    json.dumps(sources, ensure_ascii=False, indent=2) + "\n"
)
print(
    f"Created {len(products)} simulated products and {len(queries)} regression queries."
)
