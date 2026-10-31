"""HarvestWise market data, deterministic calculations, and optional tool-using AI."""
import csv
import json
import math
import os
import urllib.request
import urllib.error
from datetime import date, datetime
from pathlib import Path
from statistics import mean, pstdev

BASE_DIR = Path(__file__).resolve().parent
CSV_PATH = BASE_DIR / "data" / "market_prices.csv"
DATA_MODE = os.getenv("DATA_MODE", "mock").strip().lower()
if DATA_MODE not in {"mock", "live"}:
    DATA_MODE = "mock"

ALLOWED_CROPS = {"Tomato", "Onion", "Potato"}
ALLOWED_MARKETS = {"Mysuru", "Mandya", "Bengaluru"}
MARKET_COSTS_PER_QUINTAL = {"Mysuru": 110, "Mandya": 95, "Bengaluru": 180}
STORAGE_COST_PER_QUINTAL_DAY = 12
DEFAULT_SPOILAGE_RATE_PER_DAY = 0.035

def _load_rows():
    if not CSV_PATH.exists():
        return []
    with CSV_PATH.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        row["price"] = float(row["price"])
    return rows

def _validate_crop_market(crop, market=None):
    if crop not in ALLOWED_CROPS:
        raise ValueError(f"Unsupported crop. Choose one of: {', '.join(sorted(ALLOWED_CROPS))}.")
    if market is not None and market not in ALLOWED_MARKETS:
        raise ValueError(f"Unsupported market. Choose one of: {', '.join(sorted(ALLOWED_MARKETS))}.")

def get_options():
    return {
        "crops": sorted(ALLOWED_CROPS),
        "markets": sorted(ALLOWED_MARKETS),
        "units": ["quintal"],
        "data_mode": DATA_MODE,
        "data_note": "DEMO DATA — sample prices are fictional and are not current mandi quotations." if DATA_MODE == "mock" else "Live mode is configured, but no verified live provider is implemented until you add one."
    }

def get_prices(crop, market, days=14):
    _validate_crop_market(crop, market)
    rows = [r for r in _load_rows() if r["crop"] == crop and r["market"] == market]
    rows.sort(key=lambda r: r["date"])
    rows = rows[-days:]
    if not rows:
        return {"crop": crop, "market": market, "prices": [], "data_status": "unavailable"}
    return {
        "crop": crop,
        "market": market,
        "prices": [{"date": r["date"], "price": r["price"]} for r in rows],
        "latest_price": rows[-1]["price"],
        "previous_price": rows[-2]["price"] if len(rows) > 1 else None,
        "data_status": "demo_mock",
        "data_mode": "mock",
        "unit": "INR/quintal",
        "freshness": "Sample dataset ending 2026-10-30; not live data"
    }

def _series(crop, market):
    return get_prices(crop, market, 90)["prices"]

def _metrics(prices):
    vals = [float(p["price"]) for p in prices]
    if not vals:
        return {"count": 0, "latest": None, "change_abs": None, "change_pct": None, "ma3": None, "ma7": None, "volatility_pct": None}
    latest = vals[-1]
    previous = vals[-2] if len(vals) > 1 else None
    change_abs = latest - previous if previous is not None else None
    change_pct = (change_abs / previous * 100) if previous not in (None, 0) else None
    returns = [(vals[i] - vals[i-1]) / vals[i-1] * 100 for i in range(1, len(vals)) if vals[i-1] != 0]
    return {
        "count": len(vals), "latest": latest, "previous": previous,
        "change_abs": round(change_abs, 2) if change_abs is not None else None,
        "change_pct": round(change_pct, 2) if change_pct is not None else None,
        "ma3": round(mean(vals[-3:]), 2),
        "ma7": round(mean(vals[-7:]), 2),
        "volatility_pct": round(pstdev(returns), 2) if len(returns) > 1 else 0.0,
        "trend": "rising" if len(vals) > 1 and vals[-1] > vals[0] else "falling" if len(vals) > 1 and vals[-1] < vals[0] else "flat"
    }

def compare_markets(crop):
    _validate_crop_market(crop)
    output = []
    for market in sorted(ALLOWED_MARKETS):
        prices = _series(crop, market)
        metric = _metrics(prices)
        if metric["latest"] is not None:
            net = round(metric["latest"] - MARKET_COSTS_PER_QUINTAL[market], 2)
            output.append({
                "market": market, "latest_price": metric["latest"], "net_price_estimate": net,
                "change_pct": metric["change_pct"], "trend": metric.get("trend", "unknown"),
                "transport_and_market_cost": MARKET_COSTS_PER_QUINTAL[market]
            })
    output.sort(key=lambda x: x["net_price_estimate"], reverse=True)
    return {"crop": crop, "markets": output, "data_status": "demo_mock", "note": "Net estimate subtracts a simple illustrative per-quintal cost; confirm actual transport, fees, quality and buyer terms."}

def _validate_payload(payload):
    crop = payload.get("crop", "Tomato")
    market = payload.get("market", "Mysuru")
    _validate_crop_market(crop, market)
    try:
        quantity = float(payload.get("quantity", 10))
        days = int(payload.get("wait_days", 3))
        target = float(payload.get("target_price", 0) or 0)
        other_costs = float(payload.get("other_costs", 0) or 0)
        spoilage = float(payload.get("spoilage_pct_per_day", 3.5) or 3.5)
    except (TypeError, ValueError):
        raise ValueError("Quantity, wait days, target price and costs must be valid numbers.")
    if not math.isfinite(quantity) or not 0.1 <= quantity <= 100000:
        raise ValueError("Quantity must be between 0.1 and 100,000 quintals.")
    if not 0 <= days <= 30:
        raise ValueError("Wait days must be between 0 and 30.")
    if not math.isfinite(target) or target < 0 or target > 1000000:
        raise ValueError("Target price must be between 0 and 1,000,000.")
    if not math.isfinite(other_costs) or not 0 <= other_costs <= 100000000:
        raise ValueError("Other costs must be between 0 and 100,000,000 INR.")
    if not math.isfinite(spoilage) or not 0 <= spoilage <= 50:
        raise ValueError("Daily spoilage must be between 0% and 50%.")
    return crop, market, quantity, days, target, other_costs, spoilage

def _tool_get_market_prices(args):
    return get_prices(args.get("crop", "Tomato"), args.get("market", "Mysuru"), int(args.get("days", 14)))

def _tool_compare_markets(args):
    return compare_markets(args.get("crop", "Tomato"))

def _tool_calculate_price_trend(args):
    crop, market = args.get("crop", "Tomato"), args.get("market", "Mysuru")
    return _metrics(_series(crop, market))

def _tool_calculate_net_returns(args):
    crop, market = args.get("crop", "Tomato"), args.get("market", "Mysuru")
    quantity = max(0.1, min(float(args.get("quantity", 10)), 100000))
    metrics = _metrics(_series(crop, market))
    if metrics["latest"] is None:
        return {"status": "insufficient_data"}
    gross = metrics["latest"] * quantity
    costs = MARKET_COSTS_PER_QUINTAL[market] * quantity
    return {"gross_revenue": round(gross, 2), "estimated_market_transport_cost": round(costs, 2), "net_before_other_costs": round(gross-costs, 2)}

def _tool_schema():
    return [
        {"type":"function","function":{"name":"get_market_prices","description":"Fetch sample price history for a crop and market. These are mock demo prices, not live quotations.","parameters":{"type":"object","properties":{"crop":{"type":"string","enum":sorted(ALLOWED_CROPS)},"market":{"type":"string","enum":sorted(ALLOWED_MARKETS)},"days":{"type":"integer","minimum":1,"maximum":90}},"required":["crop","market"]}}},
        {"type":"function","function":{"name":"compare_markets","description":"Compare estimated net price across the available markets for a crop.","parameters":{"type":"object","properties":{"crop":{"type":"string","enum":sorted(ALLOWED_CROPS)}},"required":["crop"]}}},
        {"type":"function","function":{"name":"calculate_price_trend","description":"Calculate latest change, moving averages, and volatility from available sample prices.","parameters":{"type":"object","properties":{"crop":{"type":"string","enum":sorted(ALLOWED_CROPS)},"market":{"type":"string","enum":sorted(ALLOWED_MARKETS)}},"required":["crop","market"]}}},
        {"type":"function","function":{"name":"calculate_net_returns","description":"Calculate simple estimated gross and net return before other costs.","parameters":{"type":"object","properties":{"crop":{"type":"string","enum":sorted(ALLOWED_CROPS)},"market":{"type":"string","enum":sorted(ALLOWED_MARKETS)},"quantity":{"type":"number","minimum":0.1,"maximum":100000}},"required":["crop","market","quantity"]}}}
    ]

TOOL_FUNCTIONS = {
    "get_market_prices": _tool_get_market_prices,
    "compare_markets": _tool_compare_markets,
    "calculate_price_trend": _tool_calculate_price_trend,
    "calculate_net_returns": _tool_calculate_net_returns,
}

def _optional_ai_summary(context):
    """Optional OpenAI-compatible tool-call loop. Deterministic decision remains authoritative."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    messages = [
        {"role":"system","content":(
            "You are HarvestWise, a cautious agricultural market explanation assistant. "
            "Use tools to inspect data before explaining. The data may be fictional demo data. "
            "Never invent prices, dates, sources, forecasts, or confidence percentages. "
            "Do not claim that sample data is live. Do not change the deterministic recommendation. "
            "Give a short explanation, evidence, key uncertainty, and practical next step. "
            "If evidence is insufficient, say so. Respond in plain English."
        )},
        {"role":"user","content":"Explain this analysis without changing the deterministic decision:\n"+json.dumps(context)}
    ]
    tools = _tool_schema()
    for _ in range(4):
        body = {"model": model, "messages": messages, "tools": tools, "tool_choice": "auto", "temperature": 0.2}
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers={"Authorization": "Bearer "+api_key, "Content-Type":"application/json"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=12) as response:
                result = json.loads(response.read().decode("utf-8"))
            message = result["choices"][0]["message"]
            messages.append(message)
            calls = message.get("tool_calls") or []
            if not calls:
                return message.get("content")
            for call in calls:
                name = call["function"]["name"]
                try:
                    args = json.loads(call["function"].get("arguments") or "{}")
                    if name not in TOOL_FUNCTIONS:
                        output = {"error":"Tool not permitted"}
                    else:
                        output = TOOL_FUNCTIONS[name](args)
                except Exception as exc:
                    output = {"error": str(exc)}
                messages.append({"role":"tool","tool_call_id":call["id"],"content":json.dumps(output)})
        except (urllib.error.URLError, TimeoutError, KeyError, ValueError, json.JSONDecodeError):
            return None
    return None

def analyze_harvest(payload):
    crop, market, quantity, wait_days, target, other_costs, spoilage_pct = _validate_payload(payload)
    prices = _series(crop, market)
    metrics = _metrics(prices)
    if len(prices) < 3 or metrics["latest"] is None:
        return {
            "recommendation":"INSUFFICIENT DATA",
            "reason":"There are not enough observations to provide a responsible recommendation.",
            "evidence":[], "data_status":"unavailable", "ai_used":False
        }
    latest = metrics["latest"]
    costs_per_q = MARKET_COSTS_PER_QUINTAL[market]
    sell_now_gross = latest * quantity
    sell_now_costs = costs_per_q * quantity + other_costs
    sell_now_net = sell_now_gross - sell_now_costs

    # This is a transparent scenario estimate, not a forecast. It assumes the latest
    # observed percentage move repeats once per day, capped to avoid extreme extrapolation.
    daily_change = (metrics["change_pct"] or 0) / 100
    bounded_daily_change = max(-0.08, min(0.08, daily_change))
    illustrative_future_price = latest * ((1 + bounded_daily_change) ** wait_days)
    spoilage_fraction = min(0.95, (spoilage_pct / 100) * wait_days)
    remaining_quantity = quantity * (1 - spoilage_fraction)
    storage_cost = quantity * STORAGE_COST_PER_QUINTAL_DAY * wait_days
    wait_gross = illustrative_future_price * remaining_quantity
    wait_costs = costs_per_q * remaining_quantity + other_costs + storage_cost
    wait_net = wait_gross - wait_costs

    if target > 0 and latest >= target:
        recommendation = "SELL"
        reason = "The latest sample price meets or exceeds your target price."
    elif wait_days == 0:
        recommendation = "SELL"
        reason = "You selected no waiting period, so the sell-now scenario is the relevant option."
    elif wait_net > sell_now_net * 1.03 and metrics["trend"] == "rising" and spoilage_pct <= 2:
        recommendation = "WAIT (CAUTIOUSLY)"
        reason = "The illustrative wait scenario is higher after estimated costs, and the recent sample trend is rising. This is not a reliable forecast."
    elif wait_net < sell_now_net * 0.97 or spoilage_pct >= 5:
        recommendation = "SELL"
        reason = "Estimated storage/spoilage costs or the illustrative wait scenario make waiting less attractive."
    else:
        recommendation = "SELL PARTIALLY"
        reason = "The scenarios are close or uncertain; selling part now can reduce exposure while preserving some upside."

    context = {
        "crop": crop, "market": market, "quantity_quintals": quantity,
        "recommendation": recommendation, "latest_sample_price": latest,
        "price_change_percent": metrics["change_pct"], "moving_average_3": metrics["ma3"],
        "moving_average_7": metrics["ma7"], "volatility_percent": metrics["volatility_pct"],
        "sell_now_net_estimate": round(sell_now_net, 2),
        "wait_scenario_net_estimate": round(wait_net, 2),
        "wait_days": wait_days, "daily_spoilage_percent_assumption": spoilage_pct,
        "data_status": "mock demo data"
    }
    ai_summary = _optional_ai_summary(context)
    evidence = [
        {"label":"Latest sample price","value":f"₹{latest:,.0f}/quintal"},
        {"label":"Latest day-over-day change","value":f"{metrics['change_pct']:+.2f}%" if metrics["change_pct"] is not None else "Not available"},
        {"label":"3-observation average","value":f"₹{metrics['ma3']:,.0f}/quintal"},
        {"label":"7-observation average","value":f"₹{metrics['ma7']:,.0f}/quintal"},
        {"label":"Observed volatility","value":f"{metrics['volatility_pct']:.2f}% (std. dev. of daily % moves)"},
        {"label":"Data source","value":"Fictional local CSV demo dataset; not live mandi data"}
    ]
    return {
        "recommendation": recommendation,
        "reason": reason,
        "ai_explanation": ai_summary or "Rule-based explanation shown. Add OPENAI_API_KEY to enable the optional tool-using AI explanation; calculations and the final decision rule remain deterministic.",
        "ai_used": bool(ai_summary),
        "crop": crop, "market": market, "quantity": quantity,
        "metrics": metrics,
        "financials": {
            "currency":"INR", "unit":"quintal",
            "sell_now_gross":round(sell_now_gross,2),
            "sell_now_costs":round(sell_now_costs,2),
            "sell_now_net":round(sell_now_net,2),
            "illustrative_future_price":round(illustrative_future_price,2),
            "estimated_quantity_after_spoilage":round(remaining_quantity,2),
            "estimated_storage_cost":round(storage_cost,2),
            "wait_scenario_net":round(wait_net,2),
            "difference_wait_minus_sell":round(wait_net-sell_now_net,2),
        },
        "evidence": evidence,
        "assumptions": [
            f"Transport/market cost assumed at ₹{costs_per_q}/quintal for {market}.",
            f"Storage assumed at ₹{STORAGE_COST_PER_QUINTAL_DAY}/quintal/day.",
            f"Spoilage assumed at {spoilage_pct}% per day; actual losses depend on crop, weather and storage.",
            "The wait price is an illustrative scenario based on the latest observed move, capped at ±8% per day; it is not a validated forecast.",
            "Subtract or add actual local costs, quality deductions, commissions and buyer terms before acting."
        ],
        "data_status":"demo_mock",
        "data_warning":"DEMO ONLY: sample data is fictional. Do not use this result as a real trading or financial recommendation."
    }

def simulate_scenarios(payload):
    crop, market, quantity, wait_days, target, other_costs, spoilage_pct = _validate_payload(payload)
    prices = _series(crop, market)
    metrics = _metrics(prices)
    if not metrics["latest"]:
        raise ValueError("No prices are available for this crop and market.")
    latest = metrics["latest"]
    scenarios = []
    for change in [-10, -5, 0, 5, 10]:
        future = latest * (1 + change / 100)
        loss_fraction = min(0.95, spoilage_pct / 100 * wait_days)
        remain = quantity * (1-loss_fraction)
        net = future * remain - MARKET_COSTS_PER_QUINTAL[market] * remain - other_costs - quantity*STORAGE_COST_PER_QUINTAL_DAY*wait_days
        scenarios.append({"price_change_pct":change,"future_price":round(future,2),"net_estimate":round(net,2)})
    return {"crop":crop,"market":market,"latest_sample_price":latest,"scenarios":scenarios,"note":"What-if scenarios only; they are not forecasts. Data is fictional demo data."}

def create_alert(payload):
    crop, market, quantity, days, target, other_costs, spoilage = _validate_payload(payload)
    if target <= 0:
        raise ValueError("Enter a target price greater than zero.")
    return {
        "status":"created_in_demo_session",
        "alert":{"crop":crop,"market":market,"target_price":target,"condition":"price >= target"},
        "message":"Demo alert recorded for this response only. No persistent notification is configured yet.",
        "persistence":"not_configured"
    }
