#!/usr/bin/env python3
"""Print every product file in one deterministic read, for semantic review.

Output starts with an index, one tab-separated line per file:

    <ID>  <kind>  <status>  <title>  <path>

where kind is `vision`, `decision` or the item's type, and `-` stands for a
missing value. Then, under `# Files`, each file's full content follows a
`===== <path> =====` header. Order: product/vision.md, decisions by ID,
items by ID, then any file without an ID, by path. Every item is included,
whatever its status.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from pm_items import load_decisions, load_items  # noqa: E402


def cell(value: str | None) -> str:
    return " ".join(value.split()) if value else "-"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--product-dir", default="product", help="product directory (default: ./product)")
    args = parser.parse_args()

    product_dir = Path(args.product_dir)
    if not (product_dir / "items").is_dir():
        print(f"error: items directory not found: {(product_dir / 'items').resolve()}", file=sys.stderr)
        return 2

    rows: list[tuple[str, str, str, str | None, Path]] = []  # id, kind, status, title, path
    vision = product_dir / "vision.md"
    if vision.is_file():
        rows.append(("vision", "vision", "-", None, vision))

    without_id = []
    decisions = sorted(load_decisions(product_dir), key=lambda d: (d.id or "", str(d.path)))
    for d in decisions:
        row = (d.id or "-", "decision" if d.id else "-", "-", d.title, d.path)
        (rows if d.id else without_id).append(row)
    items = sorted(load_items(product_dir), key=lambda i: (i.id or "", str(i.path)))
    for i in items:
        row = (i.id or "-", cell(i.type), cell(i.status), i.title, i.path)
        (rows if i.id else without_id).append(row)
    rows += sorted(without_id, key=lambda row: str(row[4]))

    out = ["# Index", ""]
    if not rows:
        out.append("(no product files)")
        print("\n".join(out))
        return 0
    out += ["\t".join([row_id, kind, status, cell(title), str(path)]) for row_id, kind, status, title, path in rows]
    out += ["", "# Files", ""]
    sys.stdout.write("\n".join(out) + "\n")

    sections = []
    for *_, path in rows:
        text = path.read_text(encoding="utf-8", errors="replace")
        if not text.endswith("\n"):
            text += "\n"  # keep the next header on its own line
        sections.append(f"===== {path} =====\n{text}")
    sys.stdout.write("\n".join(sections))
    return 0


if __name__ == "__main__":
    sys.exit(main())
