"""Run: .venv/bin/python scripts/import_products.py [--file data/products.jsonl]."""

import argparse
import json
import sys
from pathlib import Path


root = Path.cwd()
sys.path.insert(0, str(root / "backend"))
from import_data import import_products

parser = argparse.ArgumentParser(description="Validate and import a product snapshot")
parser.add_argument("--file", type=Path, default=root / "data" / "products.jsonl")
parser.add_argument("--without-models", action="store_true")
arguments = parser.parse_args()
print(
    json.dumps(
        import_products(arguments.file, not arguments.without_models),
        ensure_ascii=False,
        indent=2,
    )
)
