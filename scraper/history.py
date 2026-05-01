"""History summary helpers shared by scraper and rebuild scripts."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

MAX_SUMMARY_POINTS = 365
USD_PROVIDER_IDS = {
    "anthropic",
    "google",
    "openai",
    "xai",
}
RAW_PRICE_EPSILON = 0.002


def load_summary(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"updated": "", "models": {}}


def snapshot_date(snapshot: dict, fallback: str | None = None) -> str:
    last_updated = snapshot.get("last_updated")
    if isinstance(last_updated, str) and len(last_updated) >= 10:
        return last_updated[:10]
    if fallback:
        return fallback
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def infer_raw_currency(provider_id: str, model: dict) -> str:
    return model.get("raw_price_currency") or model.get("price_currency") or (
        "USD" if provider_id in USD_PROVIDER_IDS else "CNY"
    )


def infer_raw_price(value: float | None, raw_value: float | None, currency: str, rate: float | None) -> float | None:
    if raw_value is not None:
        return raw_value
    if value is None:
        return None
    if currency != "USD" or not rate:
        return value
    return round(value / rate, 6)


def same_effective_price(left: float | None, right: float | None) -> bool:
    if left is None or right is None:
        return left is right
    return abs(left - right) <= RAW_PRICE_EPSILON


def merge_snapshot_into_summary(
    summary: dict,
    snapshot: dict,
    date_str: str | None = None,
    max_points: int = MAX_SUMMARY_POINTS,
) -> dict:
    day = date_str or snapshot_date(snapshot)
    rate = snapshot.get("usd_to_cny_rate")
    if isinstance(rate, (int, float)):
        rate = float(rate)
    else:
        rate = None
    models = summary.setdefault("models", {})
    seen_keys = set()

    for provider in snapshot.get("providers", []):
        provider_id = provider["id"]
        for model in provider.get("models", []):
            key = f"{provider_id}:{model['name']}"
            seen_keys.add(key)
            raw_currency = infer_raw_currency(provider_id, model)
            entry = {
                "d": day,
                "i": model.get("input_price", 0),
                "c": model.get("cached_input_price"),
                "o": model.get("output_price", 0),
                "ri": infer_raw_price(model.get("input_price"), model.get("raw_input_price"), raw_currency, rate),
                "rc": infer_raw_price(model.get("cached_input_price"), model.get("raw_cached_input_price"), raw_currency, rate),
                "ro": infer_raw_price(model.get("output_price"), model.get("raw_output_price"), raw_currency, rate),
                "cur": raw_currency,
            }
            if key not in models:
                models[key] = {
                    "provider": provider_id,
                    "name": model.get("display_name", model["name"]),
                    "series": [],
                    "first_seen": day,
                    "last_seen": day,
                    "active": True,
                }
            series = models[key]["series"]
            models[key]["provider"] = provider_id
            models[key]["name"] = model.get("display_name", model["name"])
            models[key]["first_seen"] = models[key].get("first_seen") or day
            models[key]["last_seen"] = day
            models[key]["active"] = True
            if series and series[-1].get("d") == day:
                series[-1] = entry
            elif not series or (
                series[-1].get("cur") != entry["cur"]
                or not same_effective_price(
                    series[-1].get("ri", series[-1].get("i")),
                    entry["ri"] if entry["ri"] is not None else entry["i"],
                )
                or not same_effective_price(
                    series[-1].get("ro", series[-1].get("o")),
                    entry["ro"] if entry["ro"] is not None else entry["o"],
                )
                or not same_effective_price(
                    series[-1].get("rc", series[-1].get("c")),
                    entry["rc"] if entry["rc"] is not None else entry["c"],
                )
            ):
                series.append(entry)
            if len(series) > max_points:
                models[key]["series"] = series[-max_points:]

    for key, meta in models.items():
        if key not in seen_keys:
            meta["active"] = meta.get("last_seen") == day

    summary["updated"] = datetime.now(timezone.utc).isoformat()
    return summary


def write_summary(path: Path, summary: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2))
