"""Fetch USD to CNY exchange rate."""


def get_usd_to_cny_rate(fallback: float = 7.25) -> float:
    """Fetch current USD/CNY rate from exchangerate.host or return fallback."""
    import json
    import urllib.request

    try:
        url = "https://open.er-api.com/v6/latest/USD"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            rate = data["rates"]["CNY"]
            return float(rate)
    except Exception:
        try:
            url = "https://api.exchangerate.host/latest?base=USD&symbols=CNY"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                rate = data["rates"]["CNY"]
                return float(rate)
        except Exception:
            return fallback
