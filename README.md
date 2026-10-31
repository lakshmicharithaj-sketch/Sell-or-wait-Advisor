# HarvestWise — Sell-or-Wait Advisor

A hackathon-ready Flask + HTML/CSS/JavaScript prototype for exploring whether to sell a crop now or compare a transparent hypothetical wait scenario.

## Important: demo prices only

The bundled CSV is **fictional sample data** created for UI and workflow demonstrations. It is not live mandi data and must not be used to make real selling decisions. The app labels it as demo data. No official market API is wired in by default.

## Features

- Farmer inputs: crop, market, quantity, target price, wait period, spoilage assumption and other costs.
- Price history chart and simple cross-market comparison.
- Transparent price-change, moving-average and volatility calculations.
- Sell-now vs. illustrative wait scenario, including simplified costs and spoilage.
- Five what-if price-change scenarios.
- Optional OpenAI-compatible tool-calling explanation; without an API key, deterministic explanations work.
- REST API, input validation, error handling and pytest checks.
- Vercel-oriented structure: static assets are in `public/`, Flask entrypoint is `app.py`.

## Run locally

Requires Python 3.10+ (Python 3.12 recommended).

```bash
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows PowerShell: .venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000`.

## Tests

```bash
pytest -q
```

## Optional AI explanation

1. Copy `.env.example` to `.env`.
2. Set `OPENAI_API_KEY` and optionally `OPENAI_MODEL`.
3. Install a local environment-variable loader if desired, or export variables in your shell / configure them in Vercel Project Settings.
4. Restart the app.

The code sends analysis context to the configured model and exposes only four allow-listed tools: price history, market comparison, trend metrics, and simplified net return. The model's output is only an explanation. **Python calculation logic controls the decision and financial numbers.** If the API call fails, the app falls back to a deterministic explanation.

Do not commit `.env`, put secrets in JavaScript, or use an API key belonging to another person without authorization. AI API use can incur charges.

## REST endpoints

- `GET /api/health` — health, data mode and whether an AI key is configured.
- `GET /api/options` — available crops/markets and data warning.
- `GET /api/prices?crop=Tomato&market=Mysuru&days=14` — sample history.
- `GET /api/markets/compare?crop=Tomato` — market comparison.
- `POST /api/analyze` — decision analysis.
- `POST /api/simulate` — hypothetical price-change scenarios.
- `POST /api/alerts` — demo-only target alert acknowledgement (not persisted or sent).

Example POST body:

```json
{
  "crop": "Tomato",
  "market": "Mysuru",
  "quantity": 10,
  "target_price": 2200,
  "wait_days": 3,
  "spoilage_pct_per_day": 3.5,
  "other_costs": 0
}
```

## Deploy to Vercel

### GitHub + Vercel dashboard (recommended for beginners)

1. Create a GitHub repository and upload these project files.
2. Sign in to Vercel and choose **Add New → Project**.
3. Import the repository. Keep the project root as the repository root.
4. Vercel should detect the Python Flask app from `app.py`. The `public/` directory contains static assets.
5. In **Project Settings → Environment Variables**, add `DATA_MODE` with value `mock`. If you want optional AI explanations, add `OPENAI_API_KEY` and optionally `OPENAI_MODEL`. Never add secrets to frontend files or commit them.
6. Deploy. Open the assigned URL and check `/api/health`, then try an analysis.
7. Review Vercel function logs if the backend returns an error.

### Vercel CLI

Install Node.js first, then:

```bash
npm install --global vercel
vercel login
vercel dev
vercel
vercel --prod
```

The CLI commands and zero-config detection can change; consult the current Vercel Flask/Python documentation linked below if the dashboard asks for a build configuration.

### Deployment caveats

- This is designed for a serverless deployment but has not been deployed to your Vercel account by this generator.
- No persistent alert store is configured. Serverless local disk is not a database.
- Do not add SQLite as production persistence. Use a managed Postgres service if you later need accounts, saved alerts or history.
- External API calls have timeouts. Configure API secrets in Vercel environment settings and redeploy after changing environment variables.
- The app currently uses only mock prices. To switch to real market prices, first choose a verified provider, check its current documentation, licensing, availability, and access terms, then implement and test a provider adapter. Do not invent an API URL or mark fallback sample data as live.
- Weather, buyer discovery, SMS/WhatsApp alerts, multilingual voice, and validated forecasts are not wired up. Add them only with verified providers and clear consent/cost handling.

## Decision model limitations

The “wait” price is a **scenario**, not a forecast. It repeats the latest observed daily percentage move for the selected wait period, capped at ±8% per day. It does not have a validated confidence score. Cost inputs are simplified and should be replaced with local verified costs. Spoilage is an assumption supplied by the user, not a crop-specific scientific estimate. The recommendations are a hackathon prototype and not financial advice.

## Suggested next steps for a real-world pilot

1. Replace CSV with a provider interface backed by an official or licensed data source.
2. Record source, timestamp, unit, market, grade/variety and data-quality flags for every observation.
3. Add freshness thresholds and an explicit `INSUFFICIENT DATA` result when needed.
4. Evaluate forecasts on held-out historical data before showing any prediction.
5. Store alerts in a managed database and deliver notifications only after opt-in.
6. Ask local farmers/market experts to review assumptions and wording before field use.

## Judging criteria map

1. **Working agent end-to-end:** UI → REST API → calculations → evidence/explanation.
2. **Data/tool integration:** CSV provider plus allow-listed callable tools and REST endpoints.
3. **Reasoning/evidence/reliability:** visible metrics, assumptions, input validation, mock-data label, deterministic calculations.
4. **UI/UX and innovation:** chart, market comparison, scenario simulator and farmer-oriented dashboard.
5. **Practical impact:** compares cost-aware scenarios; real-world use requires verified live data and local validation.
6. **Demo/team understanding:** predictable demo flows, tests, API docs and limitations explained.
