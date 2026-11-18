---
name: pm-init
description: Scaffold the product-management structure (product/vision.md, product/items/ and product/decisions/) in the current project. Use when the user runs /pm-init or asks to initialize/set up product management files in a repo.
---

# pm-init

Scaffolds the following structure in the target project (defaults to the current working directory):

```text
product/
├── vision.md    # created from templates/vision.md
├── items/       # empty directory for work items
└── decisions/
    ├── pdrs/    # empty directory for product decision records
    └── adrs/    # empty directory for architecture decision records
```

## Steps

1. Run the scaffolding script bundled with this skill (paths are relative to this skill's base directory):

   ```bash
   python3 <skill-base-dir>/scripts/pm_init.py [TARGET_DIR]
   ```

   - `TARGET_DIR` is optional; omit it to scaffold into the current working directory.
   - Existing files are never overwritten; pass `--force` only if the user explicitly asks to overwrite `product/vision.md`.

2. Report to the user what the script created or skipped (its output lists each path).
