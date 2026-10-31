import os
from flask import Flask, jsonify, render_template, request
from advisor import (
    get_options, get_prices, compare_markets, analyze_harvest,
    simulate_scenarios, create_alert, DATA_MODE
)


app = Flask(__name__, static_folder="public", static_url_path="")

@app.get("/")
def index():
    return render_template("index.html")

@app.get("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "app": "HarvestWise Sell-or-Wait Advisor",
        "data_mode": DATA_MODE,
        "ai_enabled": bool(os.getenv("OPENAI_API_KEY")),
    })

@app.get("/api/options")
def options():
    return jsonify(get_options())

@app.get("/api/prices")
def prices():
    crop = request.args.get("crop", "Tomato")
    market = request.args.get("market", "Mysuru")
    try:
        days = int(request.args.get("days", "14"))
    except ValueError:
        return jsonify({"error": "days must be an integer"}), 400
    if not 1 <= days <= 90:
        return jsonify({"error": "days must be between 1 and 90"}), 400
    try:
        return jsonify(get_prices(crop, market, days))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

@app.get("/api/markets/compare")
def markets_compare():
    crop = request.args.get("crop", "Tomato")
    try:
        return jsonify(compare_markets(crop))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

@app.post("/api/analyze")
def analyze():
    body = request.get_json(silent=True) or {}
    try:
        result = analyze_harvest(body)
        return jsonify(result)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception:
        app.logger.exception("Unexpected analysis error")
        return jsonify({"error": "Analysis is temporarily unavailable. Please try again."}), 500

@app.post("/api/simulate")
def simulate():
    body = request.get_json(silent=True) or {}
    try:
        return jsonify(simulate_scenarios(body))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

@app.post("/api/alerts")
def alerts():
    body = request.get_json(silent=True) or {}
    try:
        return jsonify(create_alert(body)), 201
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=os.getenv("FLASK_DEBUG") == "1")
