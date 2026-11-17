"""Export OpenAPI schema filtered by tag (e.g. mobile vs web)."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Add backend/src to path
repo_root = Path(__file__).resolve().parent.parent
backend_src = repo_root / "backend" / "src"
if str(backend_src) not in sys.path:
    sys.path.insert(0, str(backend_src))

from fw.main import app  # noqa: E402


def _collect_refs(node: Any, refs: set[str]) -> None:
    """Recursively collect all local #/components/schemas/<Name> references."""
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
            refs.add(ref.split("/")[-1])
        for v in node.values():
            _collect_refs(v, refs)
    elif isinstance(node, list):
        for item in node:
            _collect_refs(item, refs)


def _add_mobile_sync_entity_schemas(schemas: dict[str, Any]) -> None:
    """Include synced entity payload models in components.schemas for mobile codegen."""
    from fw.modules.sync.schemas import (
        AccommodationPayload,
        DayPlanPayload,
        JobPayload,
        ProfilePayload,
        ScheduleItemPayload,
        SettingsPayload,
    )

    sync_models = [
        ProfilePayload,
        SettingsPayload,
        DayPlanPayload,
        AccommodationPayload,
        JobPayload,
        ScheduleItemPayload,
    ]
    for model in sync_models:
        model_schema = model.model_json_schema(ref_template="#/components/schemas/{model}")
        defs = model_schema.pop("$defs", {})
        for def_name, def_body in defs.items():
            schemas.setdefault(def_name, def_body)
        schemas[model.__name__] = model_schema


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

    # Prune unreferenced components.schemas so the contract contains only schemas relevant to this tag
    all_schemas: dict[str, Any] = dict(schema.get("components", {}).get("schemas", {}))
    used_refs: set[str] = set()
    _collect_refs(filtered_paths, used_refs)

    # Transitively resolve nested $refs
    queue = list(used_refs)
    while queue:
        name = queue.pop()
        if name in all_schemas:
            nested: set[str] = set()
            _collect_refs(all_schemas[name], nested)
            for n in nested:
                if n not in used_refs:
                    used_refs.add(n)
                    queue.append(n)

    pruned_schemas = {k: all_schemas[k] for k in sorted(used_refs) if k in all_schemas}

    if tag == "mobile":
        _add_mobile_sync_entity_schemas(pruned_schemas)

    if "components" in filtered_schema:
        filtered_schema["components"] = dict(filtered_schema["components"])
        filtered_schema["components"]["schemas"] = dict(sorted(pruned_schemas.items()))

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
