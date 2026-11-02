# Systematic

Systematic is a locally running **experimental ML crypto manipulation-risk monitor**. It preserves the existing Next.js dashboard and Detection Lab, automatically scans eight coins, and combines headline sentiment, BTC-relative price correlation, volatility, momentum and volume features. FastAPI runs the scan scheduler and durable experiment jobs. C++ handles feature extraction, trained-model inference and parallel replay.

**Open the UI:** http://127.0.0.1:3000/dashboard/overview

**Open the API documentation:** http://127.0.0.1:8000/docs

Port **3000 is the UI**. Port **8000 is the API**, not a second dashboard. Use the explicit `127.0.0.1` URLs: an older, separate frontend was observed listening on IPv6 `localhost:3000` during this session.

## What is real, and what remains experimental

- Automatic scans start with the backend, without a button click, targeting a 60-second interval. A scan never overlaps another. If requests exceed the interval, the next scan starts after completion.
- BTC, ETH, SOL, DOGE, XRP, ADA, LINK and AVAX are monitored using completed five-minute USD candles.
- A NumPy softmax classifier is actually fitted, serialized and loaded into the C++ scoring path. It forecasts **weakly labeled abnormal price movement over the next 15 minutes**. The labels do not establish manipulation or identify manipulators.
- Both 32-run sweeps were executed. The final corrected sweep has **32 training experiments**, plus collection, measured replay and an identical-model rerun. Jobs, datasets, source snapshots, model parameters and measured metrics persist locally.
- The final model's held-out macro F1 is **0.243**, below the **0.323 always-normal baseline**. Pump/dump precision at the argmax decision rule is approximately **3.0% / 3.7%** on these weak labels. This baseline is **not a reliable predictive detector**. We did not validate directional-alert threshold precision or probability calibration.
- No scores, market history, training metrics or dashboard counters are fabricated. Missing prices become `unavailable`, not `clear`. RSS failures and missing headlines remain visible.

The engineering pipeline works. Predictive usefulness needs better labels, broader data, longer forward evaluation, threshold validation and calibration. The UI explicitly displays this limitation.

## Measured C++ performance

The original README claimed **12 min → 4 min** full-replay backtests. The original implementation did not substantiate that claim: it scaled an integer-loop microbenchmark into invented minute values. That claim is retained here as an **unverified historical target**, not an achieved result.

The corrected native implementation uses a fixed group of `std::thread` workers, an atomic block index, disjoint result slots and deterministic final reduction. **Work distribution is lock-free on this tested arm64 machine** (`std::atomic<int>::is_lock_free()` is reported). Thread creation and joining are not claimed to be lock-free. No mutex protects a shared work queue. Workers are created per replay call.

Measured on this host on November 2, 2026:

| Workload | One worker | Four workers | Speedup |
|---|---:|---:|---:|
| 15,856 recorded feature windows × 1,000 passes = 15,856,000 scores | 378.527 ms | 168.154 ms | **2.25×** |

Checksums matched. Inputs rotate between repetitions to prevent invariant scoring from being hoisted out of the benchmark loop. These are native **feature-window replay** timings, excluding network acquisition and Python orchestration, not a market execution/P&L backtest. They are one measured pair under local load, not a guaranteed speedup. A preliminary invalid benchmark remains in the ledger, clearly marked `valid_benchmark: false`. Use corrected replay `d036686c-bebf-4c9d-a770-5d992143a037`.

Evidence: [`experiment-results.json`](experiment-results.json).

## Dataflow

```text
Coinbase completed 5m candles ──┐
CoinGecko optional metadata ───┼─> timestamp alignment + freshness checks
Cointelegraph / Google RSS ────┘                 │
                       dated, preceding-24h headline sentiment
                                               │
                  C++ features: sentiment, correlation, volatility,
                  15m momentum, relative momentum, volume z-score
                                               │
                         ┌─────────────────────┴───────────────────┐
                         ▼                                         ▼
            immutable historical dataset                 live feature window
            chronological train/val/test                           │
            purged at split boundaries                             │
                         │                                         │
                REST → SQLite job queue                            │
                NumPy training → model JSON ──promotion──> C++ learned softmax
                         │                                         │
                 metrics + artifact hashes                pump / dump / watch
                         │                                         │
                         └────────────> FastAPI <──────────────────┘
                                         │
                              existing Next.js dashboard
```

A window contains 25 aligned candles, yielding 24 returns over two hours. BTC supplies the reference return series. BTC's own correlation is therefore 1 when nonconstant. Headline sentiment is a transparent positive/negative word lexicon over titles, not a pretrained language model or a social-media feed. Only articles published by the observation time may contribute. Retrospectively fetched headlines can have publication-time/reporting revisions: this is not a point-in-time news archive.

Feature order is versioned in `backend/detector/native.py`. Constant training features have zero weights. The final model disables `news_present` because all recorded windows had matching news. The nonconstant sentiment feature is learned. Training-only standardization and clipping are exported with the model, so Python and C++ consume the same parameters.

## Labels, splits and alerts

For each historical window, the label uses the next three five-minute candles. For non-BTC coins it measures the future log return minus BTC's future log return. BTC uses its own return. The anomaly threshold is `max(0.0015, 1.5 * past_volatility * sqrt(3))`. A pump label also requires a positive absolute move. A dump label requires a negative absolute move.

All coins share global chronological 60/20/20 train/validation/test cuts. A 135-minute purge before each later partition prevents overlapping two-hour feature windows and 15-minute future labels across partitions. There is no randomized temporal split. The 32-run sweep varies four L2 penalties and eight seeds, chooses by validation macro F1, then reports held-out metrics on promotion. If you repeatedly choose models after you view held-out scores, you invalidate that holdout.

The final dataset has **15,856 windows**: 14,992 normal, 407 pump and 457 dump weak labels. Inverse-class-frequency training addresses imbalance but produces **uncalibrated** scores. A displayed score is not an estimated real-world probability of manipulation.

- `pump`: pump class score ≥ 0.65 and at least the dump score.
- `dump`: dump class score ≥ 0.65.
- `watch`: combined non-normal score ≥ 0.50, below the directional threshold.
- `clear`: below those thresholds. This does not prove a market is safe.
- `unavailable`: no model, insufficient/gapped candles, provider failure, or last completed observation older than ten minutes.

No synthetic alerts are injected to make the dashboard look active. Scan history retains the observations recorded at that time. Current alerts are freshness-filtered on each read.

## External APIs and actual status

Verified with requests from this machine on November 2, 2026. Availability can change. The dashboard and `GET /api/detection/health` expose the most recent checks and timestamps.

| Source | Used for | Verified outcome | Failure behavior |
|---|---|---|---|
| Coinbase Exchange `GET /products/{SYMBOL}-USD/candles` | Historical and live 5m candles for all eight products | **Working, HTTP 200** | Affected coin becomes unavailable. BTC failure prevents paired scoring |
| CoinGecko `GET /api/v3/coins/markets` | Names/images, market cap, 24h change and volume metadata | **Working, HTTP 200** | Metadata omitted. Coinbase price scoring continues. 429 is reported |
| Cointelegraph `/rss` | Timestamped crypto headlines | **Working, HTTP 200** | Remaining news sources still contribute. Failure is visible |
| Google News `/rss/search` | Dated coin-specific headline searches, historical and current | **Working, HTTP 200** across eight coin queries | Failed query is recorded. Available RSS headlines still contribute |
| Binance `GET /api/v3/klines` | Startup diagnostic probe only | **Failed, HTTP 451** in this location | Coinbase is deliberately primary. Binance is not needed |
| TimescaleDB | Legacy warehouse | **Disabled, not part of this implementation** | SQLite provides real scan metrics. No remote table writes |
| Clerk | Legacy hosted authentication | **Disabled for local use** | No keys or login required |
| Social sentiment vendors | Social posts | **Not integrated** | Headline sentiment is labeled accurately. Never replaced with price/volume “sentiment” |
| Native C++ library | Feature extraction and model scoring | **Loaded and tested** | Explicit Python scoring fallback. Replay fails clearly without C++ |

Missing sentiment uses zero plus a missingness indicator. It is never described as measured neutral sentiment. CoinGecko sparklines are not used as minute candles. Providers use bounded timeouts. Feed and metadata caches refresh every five minutes. The eight-coin universe is explicit rather than pretending to scan every listed cryptocurrency.

Provider references: [Coinbase candle documentation](https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-candles), [CoinGecko market endpoint](https://docs.coingecko.com/reference/coins-markets), [Cointelegraph RSS](https://cointelegraph.com/rss), [Google News RSS](https://news.google.com/rss).

## Run locally

Requirements: Python 3.10+ (tested 3.12.3), Node 20+ (tested 24.1.0), npm, and a C++17 compiler (`clang++` on macOS / `g++` on Linux). This delivery reuses the original project's `venv` and `node_modules` through local symlinks. On another machine, install fresh dependencies. No private API keys are required.

From this `systematic` directory:

```bash
./scripts/setup.sh   # install dependencies, compile C++, build Next.js
./scripts/start.sh   # start API :8000 + UI :3000; Ctrl+C stops both
```

The local delivery includes recorded datasets, a trained model and a ledger. The GitHub repository excludes this runtime data. After a fresh clone, start the servers and run the following command to collect data, train the model and populate the dashboard:

```bash
backend/venv/bin/python scripts/experiments.py --refresh-data --days 7
```

To reproduce the sweep on the saved dataset without requests to historical providers:

```bash
backend/venv/bin/python scripts/experiments.py
```

For development, use two terminals:

```bash
# Terminal 1, from project root
make -C native/cpp
cd backend
./venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

```bash
# Terminal 2, from project root
cd frontend
npm run dev -- --hostname 127.0.0.1 --port 3000
```

After you change detector code or rebuild C++, restart the backend. Jobs reject a changed source/native identity so recorded hashes cannot silently describe different loaded code. Use **one backend process**: the local scheduler and worker are process-owned. Multi-worker Uvicorn deployment is not supported. This local app has no authentication and should remain bound to loopback.

Optional environment variables: `SCAN_INTERVAL_SEC` (default 60, ≥1) and `SYSTEMATIC_DATA_DIR` (default `backend/data`). Before you start the servers, export these variables in the shell. `.env.example` is documentation, not automatically loaded. Before you invoke `start.sh`, stop the existing servers. It fails rather than silently choosing other ports. Logs are under `work/`.

## REST experiments and provenance

| Method | Route | Purpose |
|---|---|---|
| GET | `/api/coins` | Freshness-filtered coin list with model scores and source details |
| GET | `/api/detection/scan` | Current automatic scanner snapshot |
| GET | `/api/detection/alerts` | Current possible pump/dump/watch alerts |
| GET | `/api/detection/health` | Providers, native engine, model quality and dataset identity |
| GET | `/api/detection/signals?symbol=BTC/USDT` | Selected coin's signals. `/USDT` is a legacy UI input, candles are USD |
| GET / POST | `/api/detection/jobs` | List or enqueue `ingest`, `train`, `replay`, `score` |
| GET | `/api/detection/jobs/{id}` | Full configuration, provenance, lifecycle, metrics and error |
| POST | `/api/detection/jobs/{id}/rerun` | Re-run pinned inputs under the same code identity |
| POST | `/api/detection/models/promote/{id}` | Promote a successful training run, report holdout metrics |
| GET | `/api/detection/artifacts/{sha256}` | Verified immutable JSON artifact |
| GET | `/api/detection/history` | Recent observed scan aggregates |
| GET | `/api/dashboard` | Real counters and current aggregate model score |

Example job:

```bash
curl -X POST http://127.0.0.1:8000/api/detection/jobs \
  -H 'Content-Type: application/json' \
  -d '{"kind":"train","seed":42,"l2":0.01,"epochs":350}'
```

A single bounded worker executes jobs FIFO. SQLite records queued/running/succeeded/failed states, config hash, seed, dataset/model hashes, source artifact, code hash, native binary hash, Python/NumPy versions, measured wall time and errors. On restart, interrupted running jobs are marked failed and queued jobs resume. Submit a new-code comparison as a new job. The reproduce route rejects a mismatched source version. `score` jobs replay saved windows for the selected symbol. The automatic scanner separately scores live data.

JSON artifacts are content-addressed and verified on read. The final sweep's rerun produced **the same model SHA-256 and config SHA-256** on this environment. Bit-identical results across different BLAS/compiler/platform versions are not promised. Preserve the entire data directory and recorded source artifact for long-term reproduction. Ingestion is time-dependent. An ingest rerun collects a new snapshot rather than reproducing an old live feed.

## Layout and verification

```text
backend/main.py             FastAPI routes and lifespan
backend/detector/           observation, model, job/storage and runtime modules
backend/data/               SQLite ledger + immutable JSON artifacts
native/cpp/                 C++17 features, scoring and replay
frontend/                   existing Next.js UI, extended in place
scripts/                    setup, start and 32-run REST sweep
tests/                      backend, native parity and regression tests
docs/                       design, plan and architecture notes
experiment-results.json     final corrected sweep and replay evidence
```

Run verification:

```bash
backend/venv/bin/python -m unittest discover -s tests -v
cd frontend && npm run build
```

The tests cover native/Python parity, replay checksums over actual feature rows, invalid and incomplete candles, temporal purging, future-news exclusion, provider outages, stale suppression, durable jobs, constant-feature handling, directional labels, source identity and invalid-payload health. The Next.js production build performs TypeScript validation. The final implementation also received an independent read-only review. Its four substantive findings were fixed and regression-tested.

The original Downloads checkout was left intact. This runnable copy contains the changes and preserves its existing dashboard structure, dark theme, sidebar, cards, coin list and Detection Lab. Legacy simulated training and destructive remote database writers were removed from this delivery.
