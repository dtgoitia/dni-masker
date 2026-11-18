#!/usr/bin/env python3
"""Scaffold the product-management directory structure.

Creates, under TARGET_DIR (default: current directory):
    product/vision.md  -- copied from this skill's templates/vision.md
    product/items/     -- empty directory for items
    product/decisions/pdrs/ -- empty directory for product decision records
    product/decisions/adrs/ -- empty directory for architecture decision records
"""

import argparse
import shutil
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
VISION_TEMPLATE = SKILL_DIR / "templates" / "vision.md"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("target", nargs="?", default=".", help="project root (default: cwd)")
    parser.add_argument("--force", action="store_true", help="overwrite existing vision.md")
    args = parser.parse_args()

    if not VISION_TEMPLATE.is_file():
        print(f"error: template not found: {VISION_TEMPLATE}", file=sys.stderr)
        return 1

    product = Path(args.target).resolve() / "product"
    items = product / "items"
    vision = product / "vision.md"

    for directory in (items, product / "decisions" / "pdrs", product / "decisions" / "adrs"):
        if directory.is_dir():
            print(f"exists:  {directory}/")
        else:
            directory.mkdir(parents=True)
            print(f"created: {directory}/")

    if vision.exists() and not args.force:
        print(f"exists:  {vision} (use --force to overwrite)")
    else:
        shutil.copyfile(VISION_TEMPLATE, vision)
        print(f"created: {vision}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
