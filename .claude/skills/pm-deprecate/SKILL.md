---
name: pm-deprecate
description: Deprecate a product item (retire a shipped feature or drop an unbuilt idea), record why, link the item that replaces it, and review the items it was blocking. Use when the user runs /pm-deprecate or says an item is retired, removed, dropped, obsolete, or replaced by another one.
---

# pm-deprecate

Marks an item in `product/items/` as `deprecated`, records the rationale, and keeps the relationships around it consistent. Run the bundled script (path relative to this skill's base directory) from the project root; pass `--product-dir <path>` if the product directory isn't `./product`. Never edit `status`, `deprecated`, `supersedes`, `superseded_by`, `blocks` or `blocked_by` by hand: the script writes both sides of every relationship and refuses cycles.

## Steps

1. **Identify the item.** If the user didn't give an ID, find the item they mean in `product/items/` (by title or description) and confirm it with them.

2. **Check it.**

   ```bash
   python3 <skill-base-dir>/scripts/deprecate_item.py check <ID>
   ```

   It prints the item's `status`, the items already replacing it (`superseded_by`) and its open `dependents` (items it blocks) as JSON. An item that is already `deprecated` can't be deprecated again: stop. Any other status is fine: a `done` item is being retired, anything else is being dropped before it shipped. Say which one it is.

3. **Capture the rationale.** Ask the user, if it isn't clear from the conversation:
   - **why** it is deprecated (what changed: user needs, cost, a better approach, a decision)
   - **what replaces it**, if anything: an existing item, or a new one to capture now
   - for a `done` item, **what happens to what shipped** (removed, kept until a date, migrated)

   Don't invent reasons. If the user names a replacement that doesn't exist yet, capture it first, the same way `/pm-capture` does: get its ID and file name with `python3 <skill-base-dir>/../pm-capture/scripts/next_id.py <type> --title "<title>"` and write it from `<skill-base-dir>/../pm-capture/templates/item.md` with `status: idea`.

4. **Deprecate it.**

   ```bash
   python3 <skill-base-dir>/scripts/deprecate_item.py deprecate <ID> [--superseded-by <REPLACEMENT-ID>]
   ```

   It sets `status: deprecated` and `deprecated: <timestamp>`, and with `--superseded-by` writes `superseded_by` on the item and `supersedes` on the replacement. It refuses a replacement that is the item itself, unknown, already deprecated, or would create a supersession cycle; nothing is changed then.

   Then append a `## Deprecation` section at the end of the item's body, written from what the user said:

   ```markdown
   ## Deprecation

   - **Why:** <rationale>
   - **Replaced by:** <REPLACEMENT-ID and title, or "nothing">
   - **What happens to what shipped:** <done items only>
   ```

5. **Review the dependents.** The script's output ends with one `dependent:` line per open item that the deprecated item was blocking. A deprecated blocker counts as closed, so they may have just been unblocked (`ready-but-blocked -> ready`). Go through them one by one with the user:
   - **There is a replacement and the dependent needs it instead:** move the link.

     ```bash
     python3 <skill-base-dir>/scripts/deprecate_item.py relink <DEPENDENT-ID> <ID> <REPLACEMENT-ID>
     ```

   - **The dependent no longer needs the deprecated item:** drop the link.

     ```bash
     python3 <skill-base-dir>/scripts/deprecate_item.py unlink <DEPENDENT-ID> <ID>
     ```

   - **The dependent only made sense with the deprecated item:** offer to deprecate it too, starting this skill over for it.
   - **The dependent is still valid as is:** leave it.

   `relink` and `unlink` re-derive the dependent's `ready` / `ready-but-blocked` status and print it when it changes.

6. **Report** what was deprecated, what replaces it, and what happened to each dependent.
