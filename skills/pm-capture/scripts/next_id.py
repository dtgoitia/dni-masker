#!/usr/bin/env python3
"""Print the next available item ID for a given item type.

IDs have the format X-nnnn, where X is the type prefix (F=feature,
T=technical, Q=question) and nnnn is a zero-padded counter that is
independent per prefix. Every file under the product directory is scanned,
matching IDs both in file names and in frontmatter `id:` fields, so the
result never collides with an existing item.
"""

import argparse
import re
import sys
from pathlib import Path

# Shared helpers live in the repo's top-level scripts/ directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from pm_common import slugify  # noqa: E402

PREFIXES = {"feature": "F", "technical": "T", "question": "Q"}
ID_RE = re.compile(r"\b([FTQ])-(\d{4,})\b")
FRONTMATTER_ID_RE = re.compile(r"^id:\s*([FTQ])-(\d{4,})\s*$", re.MULTILINE)


def used_numbers(product_dir: Path, prefix: str) -> set[int]:
    numbers: set[int] = set()
    for path in product_dir.rglob("*"):
        if not path.is_file():
            continue
        for p, n in ID_RE.findall(path.name):
            if p == prefix:
                numbers.add(int(n))
        if path.suffix == ".md":
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            for p, n in FRONTMATTER_ID_RE.findall(text):
                if p == prefix:
                    numbers.add(int(n))
    return numbers


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("type", choices=sorted(PREFIXES), help="item type")
    parser.add_argument("--title", help="also print the item file name for this title")
    parser.add_argument("--product-dir", default="product", help="product directory (default: ./product)")
    args = parser.parse_args()

    product_dir = Path(args.product_dir)
    if not product_dir.is_dir():
        print(f"error: product directory not found: {product_dir.resolve()} (run /pm-init first)", file=sys.stderr)
        return 1

    prefix = PREFIXES[args.type]
    numbers = used_numbers(product_dir, prefix)
    item_id = f"{prefix}-{max(numbers, default=0) + 1:04d}"
    print(item_id)
    if args.title is not None:
        slug = slugify(args.title)
        print(f"{item_id}-{slug}.md" if slug else f"{item_id}.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
