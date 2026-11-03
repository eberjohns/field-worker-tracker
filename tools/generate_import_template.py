#!/usr/bin/env python3
"""CLI tool to regenerate the import template workbook from the code registry."""

import os
import sys
from pathlib import Path

# Add backend/src to path
repo_root = Path(__file__).resolve().parent.parent
backend_src = repo_root / "backend" / "src"
sys.path.insert(0, str(backend_src))

from fw.modules.imports.generator import generate_import_template_bytes


def main() -> None:
    template_bytes = generate_import_template_bytes()
    output_dir = repo_root / "docs" / "import-templates"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "FieldWorkerTracker_Import_Template_v1.0.xlsx"

    with open(output_file, "wb") as f:
        f.write(template_bytes)

    print(f"Successfully generated import template at {output_file} ({len(template_bytes)} bytes)")


if __name__ == "__main__":
    main()

