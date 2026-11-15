"""Shared helpers for reading product item files."""

import re
from dataclasses import dataclass
from pathlib import Path

from pm_common import slugify  # noqa: F401  (re-exported for skill scripts)

ID_RE = re.compile(r"^([FTQ]-\d{4,})(?=-|\.md$)")
DECISION_ID_RE = re.compile(r"^((?:PDR|ADR)-\d{4,})(?=-|\.md$)")
# Where each kind of decision lives, relative to <product_dir>/decisions/.
DECISION_DIRS = {"PDR": "pdrs", "ADR": "adrs"}
ANY_ID_RE = re.compile(r"\b[FTQ]-\d{4,}\b")
RELATION_FIELDS = ("related_to", "blocks", "blocked_by", "supersedes", "superseded_by")


def _scalar(value: str) -> str:
    value = value.strip()
    quoted = re.match(r"""^(["'])(.*?)\1(?:\s+#.*)?$""", value)
    if quoted:
        return quoted.group(2)
    return re.sub(r"\s+#.*$", "", value)


def parse_frontmatter(text: str) -> dict[str, str | list[str]]:
    """Minimal frontmatter parser: `key: value`, `key: [a, b]` and block lists.

    Block lists are `key:` followed by `- item` lines (indented or not).
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    fields: dict[str, str | list[str]] = {}
    current_list: list[str] | None = None
    for line in lines[1:]:
        if line.strip() == "---":
            break
        entry = re.match(r"^\s*-\s+(.*)$", line)
        if entry and current_list is not None:
            current_list.append(_scalar(entry.group(1)))
            continue
        current_list = None
        key, sep, value = line.partition(":")
        if not sep or line[:1].isspace():
            continue
        key, value = key.strip(), _scalar(value)
        if value.startswith("[") and value.endswith("]"):
            fields[key] = [_scalar(v) for v in value[1:-1].split(",") if v.strip()]
        elif value == "":
            fields[key] = current_list = []
        else:
            fields[key] = value
    return fields


def _str(value: str | list[str] | None) -> str | None:
    return value if isinstance(value, str) and value else None


def _ids(value: str | list[str] | None) -> list[str]:
    values = value if isinstance(value, list) else [value or ""]
    return [i for v in values for i in ANY_ID_RE.findall(v)]


@dataclass
class Item:
    path: Path
    id: str | None        # from frontmatter
    file_id: str | None   # from file name
    title: str | None
    relations: dict[str, list[str]]  # RELATION_FIELDS -> referenced IDs
    status: str | None = None
    type: str | None = None
    decision: str | None = None  # questions only: the decision that answered it
    created: str | None = None


def load_items(product_dir: Path) -> list[Item]:
    items = []
    for path in sorted((product_dir / "items").rglob("*.md")):
        try:
            fm = parse_frontmatter(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            fm = {}
        m = ID_RE.match(path.name)
        relations = {field: _ids(fm.get(field)) for field in RELATION_FIELDS}
        items.append(Item(path, _str(fm.get("id")), m.group(1) if m else None, _str(fm.get("title")), relations,
                          _str(fm.get("status")), _str(fm.get("type")), _str(fm.get("decision")),
                          _str(fm.get("created"))))
    return items


@dataclass
class Decision:
    path: Path
    id: str | None        # from frontmatter
    file_id: str | None   # from file name
    title: str | None
    question: str | None  # the question item this decision answers


def load_decisions(product_dir: Path) -> list[Decision]:
    """Decision records anywhere under <product_dir>/decisions/ (none if the directory is missing)."""
    decisions = []
    for path in sorted((product_dir / "decisions").rglob("*.md")):
        try:
            fm = parse_frontmatter(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            fm = {}
        m = DECISION_ID_RE.match(path.name)
        decisions.append(Decision(path, _str(fm.get("id")), m.group(1) if m else None, _str(fm.get("title")),
                                  _str(fm.get("question"))))
    return decisions


_FIELD_LINE_RE = re.compile(r"""^([\w-]+:[ \t]*)(?:(["'])(.*?)\2|(.*?))([ \t]+#.*)?$""")


def set_field(path: Path, key: str, value: str, after: str | None = None) -> None:
    """Set a scalar frontmatter field in place, changing nothing else in the file.

    An existing `key:` line keeps its quotes and trailing comment. A missing
    field is inserted right after the `after:` line, or at the end of the
    frontmatter if there is no such line. Not for block-list fields.
    """
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise ValueError(f"{path}: no frontmatter")
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        raise ValueError(f"{path}: unterminated frontmatter")

    def index_of(name: str) -> int | None:
        return next((i for i in range(1, end) if lines[i].startswith(f"{name}:")), None)

    i = index_of(key)
    if i is not None:
        body = lines[i].rstrip("\r\n")
        newline = lines[i][len(body):]
        m = _FIELD_LINE_RE.match(body)
        prefix = m.group(1) if m.group(1)[-1:].isspace() else m.group(1) + " "
        quote = m.group(2) or ""
        lines[i] = f"{prefix}{quote}{value}{quote}{m.group(5) or ''}{newline}"
    else:
        anchor = index_of(after) if after else None
        lines.insert(anchor + 1 if anchor is not None else end, f"{key}: {value}\n")
    path.write_text("".join(lines), encoding="utf-8")


def set_list(path: Path, key: str, values: list[str]) -> None:
    """Set a list frontmatter field as an inline list (`key: [a, b]`), in place.

    Inline and block lists (`key:` followed by `- a` lines) are both replaced
    by the inline form; a trailing comment on an inline list is kept. A
    missing field is inserted at the end of the frontmatter.
    """
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise ValueError(f"{path}: no frontmatter")
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        raise ValueError(f"{path}: unterminated frontmatter")

    inline = f"{key}: [{', '.join(values)}]"
    i = next((i for i in range(1, end) if lines[i].startswith(f"{key}:")), None)
    if i is None:
        lines.insert(end, inline + "\n")
    else:
        line = lines[i].rstrip("\r\n")
        newline = lines[i][len(line):] or "\n"
        comment = re.search(r"\]([ \t]+#.*)$", line)
        lines[i] = inline + (comment.group(1) if comment else "") + newline
        j = i + 1
        while j < end and re.match(r"^\s*-\s", lines[j]):  # drop block-list entries
            j += 1
        del lines[i + 1:j]
    path.write_text("".join(lines), encoding="utf-8")
