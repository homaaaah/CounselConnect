"""Generate (or check) the API snapshot without starting workers or a database."""

import argparse
import json
from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.main import create_app  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="Fail if the committed snapshot is stale"
    )
    args = parser.parse_args()
    target = BACKEND_ROOT.parent / "contracts" / "openapi.json"
    generated = (
        json.dumps(
            create_app(run_cleanup=False).openapi(), indent=2, ensure_ascii=False
        )
        + "\n"
    )
    if args.check:
        if not target.exists() or target.read_text(encoding="utf-8") != generated:
            raise SystemExit(
                "OpenAPI snapshot is stale; run python scripts/export_openapi.py"
            )
        print("OpenAPI snapshot matches the application")
    else:
        target.write_text(generated, encoding="utf-8", newline="\n")
        print("Generated contracts/openapi.json")


if __name__ == "__main__":
    main()
