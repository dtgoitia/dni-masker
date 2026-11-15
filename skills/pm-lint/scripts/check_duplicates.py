#!/usr/bin/env python3
"""Report item and decision files that share the same ID.

Items (product/items/) and decisions (product/decisions/) are both scanned.
A file's ID is taken from its frontmatter `id:` field, falling back to the
ID in its file name. Duplicates are reported on stderr; the exit code is 1
if any are found, 0 otherwise.
"""

import argparse
import sys
from collections import defaultdict
from pathlib import Path

from _items import load_decisions, load_items


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--product-dir", default="product", help="product directory (default: ./product)")
    args = parser.parse_args()

    product_dir = Path(args.product_dir)
    if not (product_dir / "items").is_dir():
        print(f"error: items directory not found: {(product_dir / 'items').resolve()}", file=sys.stderr)
        return 2

    by_id: dict[str, list[Path]] = defaultdict(list)
    for item in [*load_items(product_dir), *load_decisions(product_dir)]:
        item_id = item.id or item.file_id
        if item_id:
            by_id[item_id].append(item.path)

    duplicates = {i: paths for i, paths in sorted(by_id.items()) if len(paths) > 1}
    for item_id, paths in duplicates.items():
        print(f"duplicate ID {item_id}:", file=sys.stderr)
        for path in paths:
            print(f"  {path}", file=sys.stderr)

    if not duplicates:
        print("no duplicate IDs found")
    return 1 if duplicates else 0


if __name__ == "__main__":
    sys.exit(main())
