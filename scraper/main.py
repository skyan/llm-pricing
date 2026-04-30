"""Orchestrator: runs all scrapers, converts currencies, writes output."""

import json
import sys
from datetime import datetime, timezone
from dataclasses import asdict
from pathlib import Path

import yaml

from scraper.base import ModelPricing
from scraper.currency import get_usd_to_cny_rate
from scraper.history import load_summary, merge_snapshot_into_summary, write_summary
from scraper.providers import ALL_SCRAPERS

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
HISTORY_SUMMARY = DATA_DIR / "history" / "summary.json"
PRICING_FILE = DATA_DIR / "pricing.json"
CONFIG_FILE = Path(__file__).resolve().parent / "config.yaml"


def load_previous_pricing() -> dict | None:
    if PRICING_FILE.exists():
        try:
            return json.loads(PRICING_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return None
    return None


def has_changed(prev: dict | None, new: dict) -> bool:
    if prev is None:
        return True
    prev_models = {}
    for p in prev.get("providers", []):
        for m in p.get("models", []):
            prev_models[(p["id"], m["name"])] = (
                m.get("input_price"), m.get("output_price"),
                m.get("cached_input_price"),
            )
    new_models = {}
    for p in new.get("providers", []):
        for m in p.get("models", []):
            new_models[(p["id"], m["name"])] = (
                m.get("input_price"), m.get("output_price"),
                m.get("cached_input_price"),
            )
    if set(prev_models.keys()) != set(new_models.keys()):
        return True
    for key in prev_models:
        if prev_models[key] != new_models.get(key):
            return True
    return False


def update_history_summary(new_data: dict):
    summary = load_summary(HISTORY_SUMMARY)
    summary = merge_snapshot_into_summary(summary, new_data)
    write_summary(HISTORY_SUMMARY, summary)


def main():
    config = yaml.safe_load(CONFIG_FILE.read_text())
    rate = get_usd_to_cny_rate(
        fallback=config.get("exchange_rate", {}).get("fallback_usd_to_cny", 7.25)
    )

    prev_data = load_previous_pricing()
    prev_providers = {}
    if prev_data:
        for p in prev_data.get("providers", []):
            prev_providers[p["id"]] = p

    results = []
    for scraper_cls in ALL_SCRAPERS.values():
        scraper = scraper_cls()
        print(f"[INFO] Scraping {scraper.provider_id}...")
        result = scraper.run()
        if result.error:
            print(f"[WARN] {scraper.provider_id}: {result.error}", file=sys.stderr)
            # Fallback to previous data for this provider
            if scraper.provider_id in prev_providers:
                result.models = [
                    ModelPricing(**m) for m in prev_providers[scraper.provider_id].get("models", [])
                ]
                print(f"[INFO] {scraper.provider_id}: using {len(result.models)} fallback models")
        elif len(result.models) == 0:
            print(f"[WARN] {scraper.provider_id}: 0 models scraped", file=sys.stderr)
            if scraper.provider_id in prev_providers:
                result.models = [
                    ModelPricing(**m) for m in prev_providers[scraper.provider_id].get("models", [])
                ]
                print(f"[INFO] {scraper.provider_id}: using {len(result.models)} fallback models")

        if scraper.currency == "USD":
            for m in result.models:
                m.input_price = round(m.input_price * rate, 2)
                if m.cached_input_price is not None:
                    m.cached_input_price = round(m.cached_input_price * rate, 2)
                m.output_price = round(m.output_price * rate, 2)
        results.append(result)
        print(f"[INFO] {scraper.provider_id}: {len(result.models)} models")

    if len(results) == 0:
        print("[FATAL] No providers scraped successfully. Aborting write.", file=sys.stderr)
        sys.exit(1)

    output = {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "usd_to_cny_rate": round(rate, 4),
        "providers": [
            {
                "id": r.provider_id,
                "name": r.provider_name,
                "website": r.website,
                "pricing_page_url": r.pricing_page_url,
                "models": [asdict(m) for m in r.models],
            }
            for r in results
        ],
    }

    prev = load_previous_pricing()
    changed = has_changed(prev, output)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PRICING_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"[INFO] Wrote {PRICING_FILE}")

    update_history_summary(output)
    print(f"[INFO] Updated history summary")
    print(f"[INFO] Done. {len(results)} providers. Changed: {changed}")


if __name__ == "__main__":
    main()
