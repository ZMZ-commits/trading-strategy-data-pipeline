# AI_CONTEXT — trading-strategy-data-pipeline

> Per-repo living context for AI assistants. Overall system:
> `trading-strategy-platform/docs/ARCHITECTURE.md`. Read that + this, then
> recompute the newest branch (`docs/AI_ONBOARDING.md` §2).
> **Live git state always wins over this snapshot.**
>
> **Last synced:** 2026-06-13 · **Newest branch at sync:** `main` (fully promoted)

---

## 1. What this repo is

The **live market-data pipeline**. It holds the **single** Alpaca WebSocket
connection (free IEX tier allows one stream), normalizes every trade into a
common tick schema, and publishes ticks to Redis. All three backends subscribe to
that one Redis and fan ticks out to browsers — so only **one** pipeline instance
runs platform-wide.

- **Run locally:** `pip install -r requirements.txt && python -m src.main`
- **Key env vars:** `REDIS_URL`, `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`,
  `ALPACA_FEED` (`iex` default / `sip`), `SYMBOLS` (comma-separated).

---

## 2. Branches & environments

| Env | Branch | Deployed? |
|-----|--------|-----------|
| Production | `main` | **One shared instance** on the Hetzner VM |
| Staging | `staging` | (shares the single instance) |
| Dev | `dev` | (shares the single instance) |

Image: `ghcr.io/zmz-commits/trading-strategy-data-pipeline:latest`. CI:
`deploy-{dev,staging,prod}.yml`. Because Alpaca's free tier permits a single
stream, the compose stack runs **one** pipeline, not one per env.

---

## 3. Functions & modules (what the code does)

### `src/main.py` — entrypoint
- Reads env, builds `RedisStore`, waits up to ~60 s for Redis (30 × 2 s retries).
- If Alpaca keys are missing, **idles** (sleeps) instead of crash-looping — so the
  container is healthy before `deploy/.env` is filled in; restart once keys are set.
- Otherwise constructs `AlpacaIngestor` and calls `.run()` (blocking).

### `src/ingestion/alpaca_ws.py`
- `AlpacaIngestor(store, symbols?)` — opens one `StockDataStream` (IEX or SIP via
  `ALPACA_FEED`), subscribes trades for each symbol. `DEFAULT_SYMBOLS` =
  AAPL, TSLA, NVDA, MSFT, AMZN, GOOGL, META, SPY.
- `_on_trade(trade)` — normalizes the trade and `publish_tick`s it.
- `run()` — subscribes all symbols and starts the stream (manages its own asyncio
  loop + reconnects). Designed so sibling ingestors (Schwab/Finnhub) could share
  the same `RedisStore` later.

### `src/storage/redis_store.py`
- `RedisStore(url)`; `publish_tick(tick)` → `PUBLISH ticks:{SYMBOL}` + `SET
  price:{SYMBOL}` (1-day expiry) for instant value on new subscribers;
  `get_latest(symbol)`; `ping()`.

### `src/transform/normalize.py`
- `normalize_trade(symbol, price, size, ts, source="alpaca")` → common tick dict
  (`symbol, price, size, timestamp, source, type="trade"`). The single funnel so
  the rest of the platform is provider-agnostic; add a `normalize_*` per new source.

---

## 4. Features
- Single-connection Alpaca live ingestion (IEX free / SIP paid).
- Provider-agnostic normalized tick schema.
- Redis pub/sub fan-out + latest-price cache.
- Resilient startup: waits for Redis; idles gracefully without keys.
- Dockerized; 3-env CI (one shared running instance).

---

## 5. Latest Changes (Living)
> Prepend newest first. Recompute: `git log origin/main --no-merges --oneline`.

- **2026-06-11** (`main`) — add GHCR docker login to VM deploy step.
- **2026-06-10** (`main`) — 3-env GitHub Actions CI/CD (Hetzner).
- **2026-06-09** (`main`) — 3-tier branching docs.
- **2026-06-07** (`main`) — pipeline idles instead of crashing when Alpaca keys absent; Alpaca live ingestion → normalize → Redis pipeline.

## 6. What's next / TODO
- Add additional ingestion sources (Schwab/Finnhub) as sibling ingestors sharing `RedisStore`.
- _(add upcoming work here)_
