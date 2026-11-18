---
name: pm-status
description: Show which product items are ready to be picked up, in progress and blocked (and by what). Read-only. Use when the user runs /pm-status or asks for the status of the product items, what's ready, what's being worked on, or what's blocked.
---

# pm-status

Reports the items in `product/items/` that are ready, in progress and blocked. It never changes any file. Run the bundled script (path relative to this skill's base directory) from the project root; pass `--product-dir <path>` if the product directory isn't `./product`.

## Steps

1. **Get the report.**

   ```bash
   python3 <skill-base-dir>/scripts/status.py
   ```

   It prints JSON with three groups, built from each item's `status` field as written:
   - `ready`: `ready` items, already in the order `/pm-next` picks them (most open work unblocked first, then oldest, then lowest ID). `unblocks` lists the open items each one unblocks.
   - `in_progress`: `in-progress` items.
   - `blocked`: `ready-but-blocked` items, with their `open_blockers` (ID, title, type, status).

   Keep the order and grouping the script gives; don't re-sort or regroup items by hand.

2. **Show it** as three short sections, **Ready**, **In progress** and **Blocked**, one line per item: ID, title and type. Say "none" for an empty section. Add:
   - **Ready:** the number of items it unblocks, when there are any. Mark questions: people answer them (recorded with `/pm-complete`), so `/pm-next` never picks them, even when they're first.
   - **Blocked:** its open blockers (ID, title, status).

3. **Suggest a next step**, briefly, from what the report shows:
   - a ready feature or technical item: `/pm-next` picks the first one
   - a ready question, especially one blocking other items: answer it and record the decision with `/pm-complete <ID>`
   - nothing ready or in progress: `/pm-refine` to get items `ready`, or `/pm-capture` for new ones
   - a blocked item with no open blockers, or a ready item that looks blocked: its status is stale, run `/pm-lint`
