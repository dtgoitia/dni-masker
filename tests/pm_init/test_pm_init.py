import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "skills" / "pm-init" / "scripts" / "pm_init.py"


def run(target: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), str(target)], capture_output=True, text=True, check=False)


def test_scaffolds_product_structure(tmp_path):
    result = run(tmp_path)

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "product" / "vision.md").is_file()
    assert (tmp_path / "product" / "items").is_dir()
    assert (tmp_path / "product" / "decisions" / "pdrs").is_dir()
    assert (tmp_path / "product" / "decisions" / "adrs").is_dir()


def test_is_idempotent_and_keeps_existing_files(tmp_path):
    run(tmp_path)
    vision = tmp_path / "product" / "vision.md"
    vision.write_text("my vision\n")

    result = run(tmp_path)

    assert result.returncode == 0
    assert vision.read_text() == "my vision\n"
    assert (tmp_path / "product" / "decisions" / "pdrs").is_dir()
    assert (tmp_path / "product" / "decisions" / "adrs").is_dir()


def test_adds_decisions_to_an_existing_product_dir(tmp_path):
    (tmp_path / "product" / "items").mkdir(parents=True)
    (tmp_path / "product" / "decisions").mkdir()

    result = run(tmp_path)

    assert result.returncode == 0
    assert (tmp_path / "product" / "decisions" / "pdrs").is_dir()
    assert (tmp_path / "product" / "decisions" / "adrs").is_dir()
