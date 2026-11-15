import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


def frontmatter(**fields: str | list[str]) -> str:
    """Render frontmatter with inline lists, e.g. frontmatter(id="F-0001", blocks=["F-0002"])."""
    lines = ["---"]
    for key, value in fields.items():
        if isinstance(value, list):
            value = "[" + ", ".join(value) + "]"
        lines.append(f"{key}: {value}")
    lines += ["---", "", "body", ""]
    return "\n".join(lines)


@pytest.fixture
def product(tmp_path: Path) -> Path:
    """An empty product/ directory with an items/ subdirectory."""
    (tmp_path / "product" / "items").mkdir(parents=True)
    return tmp_path / "product"


@pytest.fixture
def write_item(product: Path) -> Callable[..., Path]:
    """write_item(name, text=None, **fields): write product/items/<name>, from raw text or fields."""

    def write(name: str, text: str | None = None, **fields: str | list[str]) -> Path:
        path = product / "items" / name
        path.write_text(text if text is not None else frontmatter(**fields), encoding="utf-8")
        return path

    return write


@pytest.fixture
def write_decision(product):
    """write_decision(name, directory=None, **fields): write product/decisions/<directory>/<name>.

    By default the directory follows the name: `pdrs/` for PDR-*, `adrs/` for
    ADR-*, and `decisions/` itself for anything else.
    """

    def write(name: str, directory: str | None = None, **fields: str) -> Path:
        if directory is None:
            directory = {"PDR": "pdrs", "ADR": "adrs"}.get(name[:3], "")
        (product / "decisions" / directory).mkdir(parents=True, exist_ok=True)
        path = product / "decisions" / directory / name
        lines = ["---", *(f"{k}: {v}" for k, v in fields.items()), "---", "", "body", ""]
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    return write


@pytest.fixture
def item_names(product: Path) -> Callable[[], list[str]]:
    """item_names(): sorted file names in product/items/."""
    return lambda: sorted(p.name for p in (product / "items").iterdir())


@pytest.fixture
def make_run(product: Path) -> Callable[[Path], Callable[..., subprocess.CompletedProcess[str]]]:
    """make_run(scripts_dir) -> run(script, *args): run a script against the fixture product dir."""

    def make(scripts_dir: Path) -> Callable[..., subprocess.CompletedProcess[str]]:
        def run_script(script: str, *args: str) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                [sys.executable, str(scripts_dir / script), "--product-dir", str(product), *args],
                capture_output=True,
                text=True,
                check=False,
            )

        return run_script

    return make
