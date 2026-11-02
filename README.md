# FantasyEdge AI

FantasyEdge AI is a lightweight fantasy cricket companion built for a two-day MVP. The project is split into a Vite React frontend and a FastAPI backend.

## Current scope

- Dark sports analytics landing/dashboard screen
- Frontend-to-backend communication through Axios
- FastAPI health check at `GET /api/health`
- Loading and backend error state in the dashboard
- Environment-variable template for future provider and Gemini credentials

The backend includes deterministic fantasy scoring, Cricket Data integration, and an
optional Gemini-powered match and player analyst. No mock match scores are displayed.

## Run locally

Run commands from the project root unless noted otherwise.

### Backend (PowerShell)

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
Copy-Item backend\.env.example backend\.env
python -m uvicorn backend.app.main:app --reload --port 8000
```

Verify the backend in a second terminal:

```powershell
curl.exe http://localhost:8000/api/health
```

Expected response:

```json
{"status":"ok","message":"FantasyEdge AI backend is ready"}
```

### Frontend (second PowerShell)

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. Vite proxies `/api` requests to `http://localhost:8000`.

### Tests and production build

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests -q
Set-Location frontend
npm test
npm run build
```

The frontend production output is written to `frontend\dist`.

For a deployed frontend, set `VITE_API_BASE_URL` to the deployed Render API URL plus `/api`, for example `https://your-api.onrender.com/api`.

## Fantasy points calculator

Run the calculator tests from the project root:

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests -q
```

The calculator endpoint accepts a `FantasyPointsRequest` JSON payload at
`POST /api/fantasy/calculate`. The response contains `batting`, `bowling`,
`fielding`, and `bonuses` breakdowns, plus `subtotal`, `multiplier`,
`total_points`, `complete`, and `missing_statistics`. Omitted statistics remain
unknown; send an explicit `0` when a statistic is known to be zero.

Captain and vice-captain multipliers are represented by `multiplier: 2` and
`multiplier: 1.5`. The service does not claim exact Dream11 equivalence when
required statistics are missing.

The players endpoint fetches a provider scorecard and returns player-level
batting, bowling, fielding, and `fantasy_inputs` objects. It aggregates rows by
provider player ID across innings. Unknown values remain `null`; player roles,
lineup status, substitute status, dot balls, and direct-hit run-out categories
are not inferred.

The provider service has a process-local successful-response cache:

- Current/live matches: 60 seconds
- Recent matches: 5 minutes
- Scorecards/player statistics: 2 minutes

Provider errors are never cached. The cache uses a one-way digest of the API
key for isolation and never stores or exposes the credential itself.

## Environment variables

Backend-only variables belong in `backend\.env` for local development and in
the Render backend environment settings for deployment:

- `FRONTEND_ORIGINS`: comma-separated explicit browser origins.
- `CRICKET_DATA_API_KEY`
- `CRICKET_DATA_API_BASE_URL`
- `DEMO_MODE`
- `GEMINI_API_KEY`
- `GEMINI_MODEL`

The frontend exposes only `VITE_API_BASE_URL`, configured in Vercel. Vite
embeds `VITE_*` values into browser assets, so never put credentials there.
The backend rejects wildcard CORS origins because credentials are enabled.

## Local demo mode

To inspect the complete dashboard without calling Cricket Data, set this
backend-only variable in your local environment:

```text
DEMO_MODE=true
```

The default is `false`. Demo mode reads the saved
`backend/app/data/demo/durham_warwickshire_scorecard.json` fixture and exposes
one clearly labelled local demo match through the same match/player response
contracts. It is not live or current and does not consume provider quota.
Unset `DEMO_MODE` or set it to `false` to use the real provider and its TTL
cache. Never enable demo mode by exposing credentials to the frontend.

## Cricket Data integration

The backend provider boundary uses the documented Cricket Data API (formerly
CricAPI). It authenticates with the backend-only `CRICKET_DATA_API_KEY` query
parameter and calls:

- `GET https://api.cricapi.com/v1/currentMatches?apikey=...&offset=0`
- `GET https://api.cricapi.com/v1/recentMatches?apikey=...&offset=0`
- `GET https://api.cricapi.com/v1/match_scorecard?apikey=...&offset=0&id=...`

The application endpoints are:

- `GET /api/matches/live`
- `GET /api/matches/recent`
- `GET /api/matches/{match_id}/scorecard`
- `GET /api/matches/{match_id}/players`

Provider failures are returned as a safe `502` response with the upstream HTTP
status and any available provider `status`, `message`, or `reason`. Logs contain
only the endpoint name and redacted diagnostic text; API keys, request headers,
and credential-bearing URLs are never logged.

The provider website documents a lifetime free plan with 100 hits per day and
states that free data is a few minutes behind real time. API responses expose
usage information in their response metadata. The provider advertises
scorecards, over/ball-by-ball data, and player data, but optional fields are
preserved as unknown by the normalizer until they are present in an actual
response. No provider response is treated as mock data.

Set `CRICKET_DATA_API_KEY` only in the backend `.env` or deployment secret
store. It is never sent to the frontend.

## Gemini player analyst

The optional analyst is exposed at `POST /api/ai/analyze-player`. It only runs
after a player is selected and Python has calculated fantasy points. The Python
total and scoring breakdown are passed through as facts; Gemini explains them
but does not recalculate points, make predictions, or recommend teams.

Add these values manually to the backend `.env` when enabling the feature:

```text
GEMINI_API_KEY=your-key
GEMINI_MODEL=gemini-2.0-flash
DEMO_MODE=false
```

The API key is backend-only and is never returned to the frontend or logged.
If the key is absent, the analyst returns a clear unavailable error. With
`DEMO_MODE=true`, explanations are labelled as based on the saved local fixture,
which is not live or current.

## Historical demo data

`backend/app/data/demo/historical_matches.json` contains one genuine demo
fixture and two explicitly labelled synthetic records. The synthetic records
are incomplete testing data, not real cricket history, and reuse some player
IDs only to exercise identity handling. Repository callers exclude synthetic
records by default; callers that explicitly include them must preserve and
display their synthetic provenance.

## Deployment architecture

Deploy the Vite frontend to Vercel and the FastAPI application to Render.

Recommended settings:

- Vercel root directory: `frontend`
- Vercel build command: `npm run build`
- Vercel output directory: `dist`
- Render build command: `python -m pip install -r backend/requirements.txt`
- Render start command: `python -m uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT`
- Render runtime: Python 3.13.6, declared in `runtime.txt`

Set `VITE_API_BASE_URL` on Vercel to the Render API URL ending in `/api`.
Set `FRONTEND_ORIGINS` on Render to the exact Vercel origin. Do not use
wildcards or expose backend credentials to Vercel.
