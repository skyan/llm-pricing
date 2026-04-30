"""Update R2 history/index.json after a snapshot upload."""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update history/index.json in R2.")
    parser.add_argument("--bucket", required=True, help="R2 bucket name")
    parser.add_argument("--date", required=True, help="Snapshot date in YYYY-MM-DD")
    parser.add_argument("--wrangler-bin", default="wrangler", help="Wrangler executable name")
    return parser.parse_args()


def run_wrangler(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def load_index(wrangler_bin: str, bucket: str) -> dict:
    object_path = f"{bucket}/history/index.json"
    with tempfile.NamedTemporaryFile(suffix=".json") as tmp:
        result = run_wrangler([
            wrangler_bin,
            "r2",
            "object",
            "get",
            object_path,
            "--remote",
            "--file",
            tmp.name,
        ])
        if result.returncode != 0:
            return {"updated": "", "dates": []}
        return json.loads(Path(tmp.name).read_text())


def write_index(wrangler_bin: str, bucket: str, payload: dict) -> None:
    object_path = f"{bucket}/history/index.json"
    with tempfile.NamedTemporaryFile(suffix=".json") as tmp:
        Path(tmp.name).write_text(json.dumps(payload, ensure_ascii=False, indent=2))
        result = run_wrangler([
            wrangler_bin,
            "r2",
            "object",
            "put",
            object_path,
            "--remote",
            "--file",
            tmp.name,
            "--content-type",
            "application/json; charset=utf-8",
            "--cache-control",
            "public, max-age=300",
        ])
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout or "").strip() or "failed to write history index")


def main() -> int:
    args = parse_args()
    payload = load_index(args.wrangler_bin, args.bucket)
    dates = sorted(set(payload.get("dates", []) + [args.date]))
    payload = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "dates": dates,
    }
    write_index(args.wrangler_bin, args.bucket, payload)
    print(f"[INFO] Updated history index with {len(dates)} date(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
