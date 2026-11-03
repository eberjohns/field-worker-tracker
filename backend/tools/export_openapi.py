"""Export OpenAPI schema from FastAPI app to JSON."""

import json
from pathlib import Path

from fw.main import app


def export_openapi() -> None:
    schema = app.openapi()
    output_path = Path(__file__).resolve().parent.parent / "openapi.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2)
    print(f"Exported OpenAPI schema to {output_path}")


if __name__ == "__main__":
    export_openapi()
