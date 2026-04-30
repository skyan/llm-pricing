"""Rebuild history summary from daily R2 snapshots."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "data" / "history" / "summary.json"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scraper.history import merge_snapshot_into_summary, write_summary  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rebuild data/history/summary.json from R2 daily snapshots."
    )
    parser.add_argument("--bucket", required=True, help="R2 bucket name")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output summary path")
    parser.add_argument("--days", type=int, default=365, help="How many days to scan when start-date is omitted")
    parser.add_argument("--start-date", help="Inclusive start date in YYYY-MM-DD")
    parser.add_argument("--end-date", help="Inclusive end date in YYYY-MM-DD")
    parser.add_argument("--wrangler-bin", default="wrangler", help="Wrangler executable name")
    return parser.parse_args()


def parse_day(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def iter_days(start_day: date, end_day: date):
    current = start_day
    while current <= end_day:
        yield current
        current += timedelta(days=1)


def run_wrangler(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def load_history_index(wrangler_bin: str, bucket: str) -> list[date]:
    object_path = f"{bucket}/history/index.json"
    with tempfile.NamedTemporaryFile(suffix=".json") as tmp:
        cmd = [
            wrangler_bin,
            "r2",
            "object",
            "get",
            object_path,
            "--remote",
            "--file",
            tmp.name,
        ]
        result = run_wrangler(cmd)
        if result.returncode != 0:
            return []
        payload = json.loads(Path(tmp.name).read_text())
    days = []
    for value in payload.get("dates", []):
        try:
            days.append(parse_day(value))
        except ValueError:
            continue
    return sorted(set(days))


def download_snapshot(wrangler_bin: str, bucket: str, day: date) -> dict | None:
    object_path = f"{bucket}/history/{day.isoformat()}.json"
    with tempfile.NamedTemporaryFile(suffix=".json") as tmp:
        cmd = [
            wrangler_bin,
            "r2",
            "object",
            "get",
            object_path,
            "--remote",
            "--file",
            tmp.name,
        ]
        result = run_wrangler(cmd)
        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            print(f"[WARN] Missing or unreadable snapshot: {object_path} ({stderr or 'unknown error'})")
            return None
        return json.loads(Path(tmp.name).read_text())


def resolve_range(args: argparse.Namespace) -> tuple[date, date]:
    end_day = parse_day(args.end_date) if args.end_date else datetime.now(timezone.utc).date()
    if args.start_date:
        start_day = parse_day(args.start_date)
    else:
        start_day = end_day - timedelta(days=max(args.days - 1, 0))
    if start_day > end_day:
        raise ValueError("start-date must be on or before end-date")
    return start_day, end_day


def main() -> int:
    args = parse_args()
    start_day, end_day = resolve_range(args)
    summary = {"updated": "", "models": {}}
    found = 0
    indexed_days = [
        day for day in load_history_index(args.wrangler_bin, args.bucket)
        if start_day <= day <= end_day
    ]
    days_to_fetch = indexed_days if indexed_days else list(iter_days(start_day, end_day))

    for day in days_to_fetch:
        snapshot = download_snapshot(args.wrangler_bin, args.bucket, day)
        if snapshot is None:
            continue
        summary = merge_snapshot_into_summary(summary, snapshot, date_str=day.isoformat())
        found += 1

    if found == 0:
        print("[ERROR] No snapshots found in the requested R2 date range.", file=sys.stderr)
        return 1

    write_summary(args.output, summary)
    print(
        f"[INFO] Rebuilt {args.output} from {found} snapshot(s) between "
        f"{start_day.isoformat()} and {end_day.isoformat()}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
