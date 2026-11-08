"""Export OpenAPI schema filtered by tag (e.g. mobile vs web)."""

import argparse
import json
import sys
from pathlib import Path

# Add backend/src to path
repo_root = Path(__file__).resolve().parent.parent
backend_src = repo_root / "backend" / "src"
if str(backend_src) not in sys.path:
    sys.path.insert(0, str(backend_src))

from fw.main import app  # noqa: E402


def filter_schema_by_tag(schema: dict, tag: str | None = None) -> dict:
    if not tag:
        return schema

    filtered_paths = {}
    for path, path_item in schema.get("paths", {}).items():
        matching_ops = {}
        for method, operation in path_item.items():
            if method.lower() in ("get", "post", "put", "patch", "delete", "options", "head"):
                if tag in operation.get("tags", []):
                    matching_ops[method] = operation
        if matching_ops:
            filtered_paths[path] = matching_ops

    filtered_schema = dict(schema)
    filtered_schema["paths"] = filtered_paths
    filtered_schema["info"] = dict(schema.get("info", {}))
    filtered_schema["info"]["title"] = f"{schema.get('info', {}).get('title')} ({tag.capitalize()})"
    return filtered_schema


def main() -> None:
    parser = argparse.ArgumentParser(description="Export OpenAPI schema")
    parser.add_argument("--tag", type=str, default=None, help="Filter endpoints by tag")
    parser.add_argument("--out", type=str, default=None, help="Output file path (default: stdout)")

    args = parser.parse_args()
    schema = app.openapi()
    filtered = filter_schema_by_tag(schema, tag=args.tag)

    dumped = json.dumps(filtered, indent=2)

    if args.out:
        out_path = Path(args.out)
        out_path.write_text(dumped, encoding="utf-8")
        print(f"Exported schema to {out_path}", file=sys.stderr)
    else:
        sys.stdout.write(dumped)


if __name__ == "__main__":
    main()

