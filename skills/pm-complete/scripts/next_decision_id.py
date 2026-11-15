#!/usr/bin/env python3
"""Print the next available decision ID (PDR-nnnn or ADR-nnnn).

PDRs (product decisions) and ADRs (architecture decisions) each have their
own counter. Every file under <product-dir>/decisions/ is scanned, misplaced
ones included, matching IDs both in file names and in frontmatter `id:`
fields. With --title, also prints the path the new decision must be written
to: <product-dir>/decisions/pdrs/ for PDRs, <product-dir>/decisions/adrs/
for ADRs.
"""

import argparse
import re
import sys
from pathlib import Path

# Shared helpers live in the repo's top-level scripts/ directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from pm_common import slugify  # noqa: E402
from pm_items import DECISION_DIRS, parse_frontmatter  # noqa: E402

ID_RE = re.compile(r"^(PDR|ADR)-(\d{4,})(?=-|\.md$)")


def used_numbers(decisions_dir: Path, prefix: str) -> set[int]:
    numbers: set[int] = set()
    if not decisions_dir.is_dir():
        return numbers
    for path in decisions_dir.rglob("*.md"):
        candidates = [path.name]
        try:
            fm_id = parse_frontmatter(path.read_text(encoding="utf-8")).get("id")
        except (OSError, UnicodeDecodeError):
            fm_id = None
        if isinstance(fm_id, str):
            candidates.append(fm_id + ".md")
        for candidate in candidates:
            m = ID_RE.match(candidate)
            if m and m.group(1) == prefix:
                numbers.add(int(m.group(2)))
    return numbers


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("kind", choices=["pdr", "adr"], help="pdr: product decision, adr: architecture decision")
    parser.add_argument("--title", help="also print the decision file path for this title")
    parser.add_argument("--product-dir", default="product", help="product directory (default: ./product)")
    args = parser.parse_args()

    product_dir = Path(args.product_dir)
    if not product_dir.is_dir():
        print(f"error: product directory not found: {product_dir.resolve()} (run /pm-init first)", file=sys.stderr)
        return 1

    prefix = args.kind.upper()
    decision_id = f"{prefix}-{max(used_numbers(product_dir / 'decisions', prefix), default=0) + 1:04d}"
    print(decision_id)
    if args.title is not None:
        slug = slugify(args.title)
        name = f"{decision_id}-{slug}.md" if slug else f"{decision_id}.md"
        print(product_dir / "decisions" / DECISION_DIRS[prefix] / name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
