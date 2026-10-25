# AI_CONTEXT — trading-strategy-data-pipeline

> Per-repo living context for AI assistants. Overall system:
> `trading-strategy-platform/docs/ARCHITECTURE.md`. Read that + this, then
> recompute the newest branch (`docs/AI_ONBOARDING.md` §2).
> **Live git state always wins over this snapshot.**
>
> **Last synced:** 2026-10-24 · **Newest branch at sync:** `main` (fully
> promoted — `dev`/`staging` are content-identical, behind only by merge commits)

---

## 1. What this repo is

The **live market-data pipeline**. It holds the **single** Alpaca WebSocket
connection (free IEX tier allows one stream), normalizes every trade into a
common tick schema, and publishes each tick to **Redis and Kafka**. All three
backends subscribe to that one Redis and fan ticks out to browsers — so only
**one** pipeline instance runs platform-wide.

**Redis and Kafka are not alternatives.** Understand this before changing
anything here. Redis pub/sub is a push to whoever is listening *right now* — a
subscriber that connects a second late never learns the tick happened. Kafka
keeps every tick for its retention window, so a consumer can start late, replay
from the beginning, or fall behind and catch up. Browser updates need the first;
backtests and bar-building need the second. Redis is the **live** path and
replacing it breaks all three backends. Kafka is the **durable** copy.

- **Run locally:** `pip install -r requirements.txt && python -m src.main`
- **Key env vars:** `REDIS_URL`, `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`,
  `ALPACA_FEED` (`iex` default / `sip`), `SYMBOLS` (comma-separated),
  `KAFKA_BOOTSTRAP` (**unset = Redis only**), `KAFKA_TOPIC` (default
  `market.trades`).

---

## 2. Branches & environments

| Env | Branch | Deployed? |
|-----|--------|-----------|
| Production | `main` | **One shared instance** on the Hetzner VM |
| Staging | `staging` | (shares the single instance) |
| Dev | `dev` | (shares the single instance) |

Image: `ghcr.io/zmz-commits/trading-strategy-data-pipeline:latest`. Because
Alpaca's free tier permits a single stream, the compose stack runs **one**
pipeline, not one per env.

**CI is `build.yml` + `deploy-prod.yml`, and only `main` deploys.**
`deploy-dev.yml` and `deploy-staging.yml` were deleted: they targeted compose
services (`data-pipeline-dev`, `data-pipeline-stg`) that do not exist, and had
never run. `deploy-prod.yml` was equally broken — it pushed `:prod` and
restarted `data-pipeline-prod`, while compose names the service `pipeline` and
pulls `:latest`. **This repo had no successful workflow run until 2026-10-07.**
`dev` and `staging` now build without pushing, which catches a broken
Dockerfile before a push to `main` that is also a deploy.

**Live credentials reach the VM through `deploy/.env`,** written from repository
secrets by the platform repo's `deploy.yml`. Before that the pipeline logged
`ALPACA_API_KEY not set — pipeline idle` on every start and ingested nothing,
invisibly, for months. Rotating a key is `gh secret set` plus a re-run, not an
SSH session.

---

## 3. Functions & modules (what the code does)

### `src/main.py` — entrypoint
- Reads env, builds `RedisStore`, waits up to ~60 s for Redis (30 × 2 s retries).
- If Alpaca keys are missing, **idles** (sleeps) instead of crash-looping — so the
  container is healthy before `deploy/.env` is filled in; restart once keys are set.
  *This is also how months of silent non-ingestion went unnoticed: an idle
  container is a healthy container. Check the logs, not the status.*
- If `KAFKA_BOOTSTRAP` is set, wraps the Redis store in a `FanoutStore` with a
  `KafkaStore`. Unset, the behaviour is byte-for-byte what it was before Kafka
  existed — which is what made deploying Kafka safe independently of turning it
  on. `confluent_kafka` is imported **inside** that branch so its absence cannot
  stop the Redis-only path from starting.
- Then constructs `AlpacaIngestor` and calls `.run()` (blocking), with a
  `finally` that `flush()`es Kafka. Without that flush a restart silently loses
  the last batch — which `linger.ms` makes a certainty rather than a risk.

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

### `src/storage/kafka_store.py`
- `KafkaStore(bootstrap, topic="market.trades")`. Deliberately shares
  `publish_tick(tick)` with `RedisStore` so the ingestor cannot tell them apart.
- **Keyed by symbol**, because Kafka guarantees order *within a partition*, not
  across a topic, and a key always hashes to the same partition. A bar built
  from out-of-order ticks has the wrong high and low.
- `lz4` compression (topic is `compression.type=producer`, so the broker stores
  what the producer chose); `linger.ms=20` to batch; `retries=5`;
  `queue.buffering.max.messages=100_000`.
- **On `BufferError` it drops the tick and logs.** This runs inside the Alpaca
  websocket callback, so blocking would back up the stream and cost the *live*
  path. A dropped Kafka write costs history; a stalled callback costs the
  running system.
- `flush(timeout=10)` returns the number still undelivered — non-zero only if
  the broker was unreachable.

### `src/storage/fanout.py`
- `FanoutStore([stores...])` — same `publish_tick` interface, forwards to each.
- The `except Exception` is **deliberately broad and deliberately not
  re-raised.** It runs inside the websocket callback; an exception escaping
  would tear down the stream *for every symbol* because one destination was
  unhappy. Kafka being unreachable must never become a live outage.

### `src/transform/normalize.py`
- `normalize_trade(symbol, price, size, ts, source="alpaca")` → common tick dict
  (`symbol, price, size, timestamp, source, type="trade"`). The single funnel so
  the rest of the platform is provider-agnostic; add a `normalize_*` per new source.

---

## 4. Features
- Single-connection Alpaca live ingestion (IEX free / SIP paid).
- Provider-agnostic normalized tick schema.
- Redis pub/sub fan-out + latest-price cache (the **live** path).
- Durable Kafka copy, keyed by symbol, opt-in via `KAFKA_BOOTSTRAP` (the
  **history** path). Topic `market.trades`, 6 partitions, 30-day retention.
- Fan-out isolation: a Kafka outage cannot become a live outage.
- Resilient startup: waits for Redis; idles gracefully without keys.
- Dockerized. CI builds on `dev`/`staging`, deploys only from `main`.

---

## 5. Latest Changes (Living)
> Prepend newest first. Recompute: `git log origin/main --no-merges --oneline`.

- **2026-10-07** (`main`) — stop tracking `.env`, which held live credentials.
  They were committed by a `git add -A`, were public for ~24 h, and have been
  rotated. History was **not** rewritten; the old keys are dead, not absent.
- **2026-10-07** (`main`) — build on `dev`/`staging`, deploy only from `main`.
  Replaced `deploy-dev.yml` / `deploy-staging.yml`, which named compose services
  that never existed and had never run.
- **2026-10-07** (`main`) — keep a durable copy of every tick in Kafka
  (`kafka_store.py`, `fanout.py`). Additive and opt-in; Redis unchanged.
- **2026-09-16** (`main`) — link the live environments from the README.
- **2026-06-11** (`main`) — add GHCR docker login to VM deploy step.
- **2026-06-10** (`main`) — 3-env GitHub Actions CI/CD (Hetzner).
- **2026-06-09** (`main`) — 3-tier branching docs.
- **2026-06-07** (`main`) — pipeline idles instead of crashing when Alpaca keys absent; Alpaca live ingestion → normalize → Redis pipeline.

## 6. What's next / TODO
- **Move this container into the cluster** (Phase 3+ of the platform's
  `docs/K8S_MIGRATION.md`). It still runs on the Hetzner VM via compose and
  reaches Kafka over a **NodePort** (`<node-ip>:30092`) because it is outside.
  Once inside, `KAFKA_BOOTSTRAP` becomes
  `tsp-kafka-bootstrap.kafka.svc:9092` and the NodePorts can close again — they
  are currently the one hole in the cluster firewall, restricted to the VM's IP.
- A consumer that reads `market.trades` and builds minute bars. Nothing
  consumes the topic yet, so the durable path is write-only today.
- Add additional ingestion sources (Schwab/Finnhub) as sibling ingestors
  sharing the same `TickStore` protocol (not `RedisStore` specifically — the
  protocol is what `FanoutStore` and `KafkaStore` already satisfy).
