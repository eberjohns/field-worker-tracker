import subprocess
import sys
from pathlib import Path


def run_linter(backend_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-c",
            "from importlinter.cli import lint_imports_command; lint_imports_command(['--config', 'pyproject.toml'])",
        ],
        cwd=backend_dir,
        capture_output=True,
        text=True,
    )


def test_import_linter_passes_on_clean_codebase():
    backend_dir = Path(__file__).resolve().parent.parent
    result = run_linter(backend_dir)
    assert result.returncode == 0, f"import-linter failed:\n{result.stdout}\n{result.stderr}"


def test_deliberate_cross_module_import_fails_import_linter():
    backend_dir = Path(__file__).resolve().parent.parent
    settings_init = backend_dir / "src" / "fw" / "modules" / "settings" / "__init__.py"

    original_content = settings_init.read_text(encoding="utf-8")
    try:
        # Deliberately violate layers contract: settings (layer 8) imports attendance (layer 3)
        illegal_import = "import fw.modules.attendance  # ILLEGAL UPWARD IMPORT\n"
        settings_init.write_text(illegal_import + original_content, encoding="utf-8")

        result = run_linter(backend_dir)
        assert result.returncode != 0, "import-linter should have failed on illegal upward import!"
        assert (
            "BROKEN" in result.stdout
            or "contracts broken" in result.stdout
            or "Layer" in result.stdout
        )
    finally:
        # Restore original content
        settings_init.write_text(original_content, encoding="utf-8")
