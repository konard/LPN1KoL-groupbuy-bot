#!/usr/bin/env python3
"""
Generate OpenAPI/Swagger documentation for the GroupBuy backend.

Usage:
    # From the repo root or deploy_v2 directory:
    python deploy_v2/scripts/generate_swagger.py

    # Or with a running backend:
    python deploy_v2/scripts/generate_swagger.py --url http://localhost:8000

Output:
    deploy_v2/docs/openapi.json   — full OpenAPI 3.x spec (JSON)
    deploy_v2/docs/openapi.yaml   — full OpenAPI 3.x spec (YAML)

The Swagger UI is also available at http://localhost:8000/docs when the
backend service is running (FastAPI serves it automatically).
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error

DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "docs")


def fetch_from_url(base_url: str) -> dict:
    url = base_url.rstrip("/") + "/openapi.json"
    print(f"Fetching spec from {url} …")
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:  # noqa: S310
            return json.loads(resp.read())
    except urllib.error.URLError as exc:
        print(f"ERROR: Could not connect to {url}: {exc}", file=sys.stderr)
        sys.exit(1)


def fetch_from_app() -> dict:
    """Import the FastAPI app directly and extract its OpenAPI schema."""
    backend_path = os.path.join(os.path.dirname(__file__), "..", "services", "backend")
    if backend_path not in sys.path:
        sys.path.insert(0, backend_path)

    print("Loading FastAPI app directly …")
    try:
        from app.main import app  # noqa: PLC0415
        return app.openapi()
    except ImportError as exc:
        print(f"ERROR: Could not import app: {exc}", file=sys.stderr)
        print("Tip: install dependencies first:  pip install -r services/backend/requirements.txt", file=sys.stderr)
        sys.exit(1)


def save_json(spec: dict, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(spec, fh, indent=2, ensure_ascii=False)
    print(f"  ✓ JSON: {path}")


def save_yaml(spec: dict, path: str) -> None:
    try:
        import yaml  # noqa: PLC0415
    except ImportError:
        print("  ! YAML output skipped (PyYAML not installed). Run: pip install pyyaml")
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        yaml.dump(spec, fh, allow_unicode=True, sort_keys=False, default_flow_style=False)
    print(f"  ✓ YAML: {path}")


def print_summary(spec: dict) -> None:
    info = spec.get("info", {})
    paths = spec.get("paths", {})
    print("\n── API Summary ────────────────────────────────────────")
    print(f"  Title   : {info.get('title', '—')}")
    print(f"  Version : {info.get('version', '—')}")
    print(f"  Endpoints: {len(paths)}")
    print("\n  Endpoints:")
    for path, methods in sorted(paths.items()):
        for method, op in methods.items():
            if method.upper() in ("GET", "POST", "PUT", "PATCH", "DELETE"):
                tags = ", ".join(op.get("tags", []))
                summary = op.get("summary", "")
                tag_str = f"  [{tags}]" if tags else ""
                print(f"    {method.upper():6} {path}{tag_str}  {summary}")
    print("────────────────────────────────────────────────────────\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Swagger/OpenAPI docs for GroupBuy backend")
    parser.add_argument(
        "--url",
        metavar="BASE_URL",
        default=None,
        help="Base URL of a running backend (e.g. http://localhost:8000). "
             "If omitted, the app module is imported directly.",
    )
    parser.add_argument(
        "--out-dir",
        metavar="DIR",
        default=DOCS_DIR,
        help="Output directory (default: deploy_v2/docs)",
    )
    args = parser.parse_args()

    spec = fetch_from_url(args.url) if args.url else fetch_from_app()

    json_path = os.path.join(args.out_dir, "openapi.json")
    yaml_path = os.path.join(args.out_dir, "openapi.yaml")

    print("\nSaving spec …")
    save_json(spec, json_path)
    save_yaml(spec, yaml_path)
    print_summary(spec)
    print("Done!")
    print(f"\nSwagger UI (when backend is running): http://localhost:8000/docs")
    print(f"ReDoc UI   (when backend is running): http://localhost:8000/redoc")


if __name__ == "__main__":
    main()
