---
name: pm-complete
description: Mark a product item as done and unblock the items that depend on it; for a question, record its outcome as a decision (PDR or ADR). Use when the user runs /pm-complete or says an item is finished, shipped, deployed, or a question has been answered.
---

# pm-complete

Marks an item in `product/items/` as `done`, and moves the items it was blocking from `ready-but-blocked` to `ready` once nothing else blocks them. Run the bundled scripts (paths relative to this skill's base directory) from the project root; pass `--product-dir <path>` if the product directory isn't `./product`.

## Steps

1. **Identify the item.** If the user didn't give an ID, find the item they mean in `product/items/` (by title or description) and confirm it with them.

2. **Check it.**

   ```bash
   python3 <skill-base-dir>/scripts/complete_item.py check <ID>
   ```

   It prints the item's `type`, `status` and `open_blockers` as JSON. Then, with the user:
   - **Status:** `done` or `deprecated` can't be completed, so stop. Any status other than `in-progress` is unusual: say so and ask the user to confirm before going on.
   - **Blockers:** if `open_blockers` isn't empty, list them (ID, title, status) and ask the user to confirm completing the item anyway.
   - **Acceptance criteria:** read the item's `## Acceptance criteria` section and go through each criterion with the user, who confirms it is met. If any isn't, stop: the item isn't done. If the section is empty, ask the user to confirm the item is done as intended.

3. **Questions only: record the decision.** A `question` is answered by a decision record, written before the question is completed.
   - Ask the user what was decided and why, if it isn't clear from the conversation.
   - Propose its kind and let the user confirm: **PDR** (product decision) if it changes what users see or can do, **ADR** (architecture decision) if it changes how the system is built.
   - Agree on a short title, then get the ID and file path:

     ```bash
     python3 <skill-base-dir>/scripts/next_decision_id.py <pdr|adr> --title "<title>"
     ```

   - Read `<skill-base-dir>/templates/decision.md` and write it to the path printed by the script, exactly as printed: PDRs live in `product/decisions/pdrs/` and ADRs in `product/decisions/adrs/` (create the directory if missing). Fill in `id`, `title`, `question` (the question's ID), `created` (`date -Iseconds`) and the body from what the user said. Don't invent rationale.

4. **Complete it.**

   ```bash
   python3 <skill-base-dir>/scripts/complete_item.py complete <ID> [--decision <PDR-nnnn|ADR-nnnn>]
   ```

   `--decision` is required for questions, and only allowed for them. The script sets `status: done` and `completed: <timestamp>` (plus `decision:` for questions), then updates the item's direct dependents. Don't edit these fields by hand.

5. **Report** what happened, from the script's output:
   - `now ready:` dependents moved to `ready`
   - `still blocked:` dependents waiting on other items, and which ones
   - `no longer blocked:` dependents with no open blockers whose status isn't `ready` yet (e.g. `clarifying`); suggest `/pm-refine` for them
