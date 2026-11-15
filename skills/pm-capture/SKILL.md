---
name: pm-capture
description: Capture a new product idea as an item (feature, technical requirement, or open question) under product/items/. Use when the user runs /pm-capture or wants to log/capture/record a new product idea, requirement, or question.
---

# pm-capture

Guides the user to turn a raw idea into a new product item file in `product/items/`.

## Item types

| Type        | Prefix | What it is                                              | Examples                                                             |
|-------------|--------|---------------------------------------------------------|----------------------------------------------------------------------|
| `feature`   | `F`    | A capability a user sees                                | "export reports as CSV", "support dark mode"                         |
| `technical` | `T`    | A non-functional requirement                            | "add rate limits to the API", "migrate DB to Postgres 17"            |
| `question`  | `Q`    | An open issue that must be resolved to unblock work     | "should we support multi-tenant accounts?", "sync or async exports?" |

## Steps

1. **Get the idea.** If the user didn't describe it when invoking the skill, ask them to describe it in their own words.

2. **Classify it.** Ask the user clarifying questions until the type is unambiguous. Useful probes:
   - Would an end user notice or interact with this directly? → likely `feature`
   - Is it about how the system works (performance, security, scalability, infrastructure, maintainability) rather than what it does? → likely `technical`
   - Is it an undecided choice or unknown that blocks other work, whose outcome is a decision (PDR/ADR) rather than code? → likely `question`

   Propose the type you think fits and why, and have the user confirm it. Do not create the item until the type is confirmed.

3. **Pick a title.** Propose a short, descriptive title to the user, and allow the user adjust it or accept it.

4. **Generate the ID.** Run the bundled script (path relative to this skill's base directory) from the project root:

   ```bash
   python3 <skill-base-dir>/scripts/next_id.py <feature|technical|question> --title "<title>"
   ```

   It prints the next free ID (e.g. `F-0003`) on the first line and the item file name (e.g. `F-0003-export-reports-as-csv.md`) on the second. Pass `--product-dir <path>` if the product directory isn't `./product`. If it reports that `product/` doesn't exist, suggest running `/pm-init` first.

5. **Create the item.** Read `<skill-base-dir>/templates/item.md` and write it to `product/items/<file name printed by the script>` — use it verbatim, since `/pm-lint` renames files that don't match it. Fill in:
   - `id`: the generated ID
   - `title`: the agreed title
   - `type`: the confirmed type
   - `status`: `idea`
   - `created`: the current timestamp in ISO 8601 with UTC offset (e.g. `date -Iseconds`)
   - body sections: whatever the user already said about the idea; leave the rest for `/pm-refine`. Don't invent requirements.

6. **Confirm.** Tell the user the item's ID and file path.
