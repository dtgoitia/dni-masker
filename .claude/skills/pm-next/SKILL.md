---
name: pm-next
description: Pick the next unblocked, ready product item (feature or technical), claim it by moving it to in-progress, brief the task from the item and its related items and decisions, and start implementing it. Use when the user runs /pm-next or asks what to work on next, or for the next item/task to pick up.
---

# pm-next

Picks the next item to implement from `product/items/` and starts working on it. Run the bundled script (path relative to this skill's base directory) from the project root; pass `--product-dir <path>` if the product directory isn't `./product`.

## Steps

1. **Pick and claim.**

   ```bash
   python3 <skill-base-dir>/scripts/next_item.py
   ```

   It prints JSON and, if it picked an item, has already set its `status: in-progress`, so other agents won't pick it too. Never choose or claim an item by hand; the script decides deterministically:
   - **candidates:** features and technical items that are `ready` and whose blockers are all `done` or `deprecated`. Questions are never picked, since people answer them.
   - **order:** the candidate that unblocks the most open items (directly or transitively) comes first, then the oldest `created`, then the lowest ID.

   To see what would be picked without claiming it (e.g. when the user only asks what's next), add `--dry-run`.

2. **Nothing picked** (`picked` is `null`): tell the user, then use the rest of the output to say why:
   - `waiting`: ready items held up by `open_blockers`. Name the blockers, especially questions (they need an answer, recorded with `/pm-complete`).
   - `ready_questions`: unblocked questions waiting for an answer.
   - If both are empty, suggest `/pm-refine` to get more items `ready`, or `/pm-capture` for new ones.

   Stop here.

3. **Brief.** Read the picked item (`path`) and every file in `context`: its related, blocking, blocked and superseded items, and the decisions (PDRs/ADRs) that answered related questions. Summarise for the user:
   - the ID, title and type, and why this item was picked (`unblocks` lists the open items it unblocks)
   - the problem and the proposed behaviour
   - the acceptance criteria, which define when the item is done
   - constraints from the decisions and related items

   If the item turns out not to be implementable (its open questions aren't answered, or the acceptance criteria are missing), say so and stop: the user can move it back with `/pm-refine`.

4. **Start working.** Implement the item in the project, guided by its acceptance criteria. When every criterion is met, tell the user and suggest `/pm-complete <ID>`. Don't mark the item as done yourself.
