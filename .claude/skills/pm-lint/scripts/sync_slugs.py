#!/usr/bin/env python3
"""Rename item and decision files so their slug matches their frontmatter title.

The expected file name is `<id>-<slugify(title)>.md`; the title is the source
of truth. Files are skipped (with a warning on stderr) when they lack an `id`
or `title`, when the file-name ID disagrees with the frontmatter ID, or when
the target name already exists. Use --dry-run to preview.
"""

import argparse
import sys
from pathlib import Path

from _items import load_decisions, load_items, slugify


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--product-dir", default="product", help="product directory (default: ./product)")
    parser.add_argument("--dry-run", action="store_true", help="only print planned renames")
    args = parser.parse_args()

    product_dir = Path(args.product_dir)
    if not (product_dir / "items").is_dir():
        print(f"error: items directory not found: {(product_dir / 'items').resolve()}", file=sys.stderr)
        return 2

    skipped = renamed = 0
    for item in [*load_items(product_dir), *load_decisions(product_dir)]:
        if not item.id or not item.title:
            print(f"skip {item.path}: missing `id` or `title` in frontmatter", file=sys.stderr)
            skipped += 1
            continue
        if item.file_id and item.file_id != item.id:
            print(f"skip {item.path}: file name ID {item.file_id} != frontmatter ID {item.id}", file=sys.stderr)
            skipped += 1
            continue
        slug = slugify(item.title)
        target = item.path.with_name(f"{item.id}-{slug}.md" if slug else f"{item.id}.md")
        if target == item.path:
            continue
        if target.exists():
            print(f"skip {item.path}: target {target.name} already exists", file=sys.stderr)
            skipped += 1
            continue
        print(f"{'would rename' if args.dry_run else 'renamed'}: {item.path} -> {target.name}")
        if not args.dry_run:
            item.path.rename(target)
        renamed += 1

    if not renamed and not skipped:
        print("all file names match their titles")
    return 1 if skipped else 0


if __name__ == "__main__":
    sys.exit(main())
