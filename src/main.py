"""Pipeline entrypoint: stream Alpaca trades into Redis.

Env vars:
  REDIS_URL          redis connection (default redis://localhost:6379)
  ALPACA_API_KEY     Alpaca key id        (required)
  ALPACA_SECRET_KEY  Alpaca secret key    (required)
  ALPACA_FEED        'iex' (free, default) or 'sip' (paid)
  SYMBOLS            comma-separated tickers (default: a basket of large caps)
"""
from __future__ import annotations
import logging
import os
import time

from .storage.redis_store import RedisStore
from .ingestion.alpaca_ws import AlpacaIngestor

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("pipeline")


def main() -> None:
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    symbols_env = os.getenv("SYMBOLS", "")
    symbols = [s.strip().upper() for s in symbols_env.split(",") if s.strip()] or None

    store = RedisStore(redis_url)
    # Wait for Redis to be reachable (it may start a moment after this container).
    for attempt in range(30):
        try:
            if store.ping():
                log.info("Connected to Redis at %s", redis_url)
                break
        except Exception as e:  # noqa: BLE001
            log.warning("Redis not ready (%s), retrying...", e)
            time.sleep(2)
    else:
        raise SystemExit("Could not reach Redis")

    # Idle gracefully if keys aren't provided yet (avoids crash-looping before
    # deploy/.env is filled in). Restart the container once keys are set.
    if not os.getenv("ALPACA_API_KEY", "").strip() or not os.getenv("ALPACA_SECRET_KEY", "").strip():
        log.warning("ALPACA_API_KEY/SECRET not set — pipeline idle. Add keys to deploy/.env and restart.")
        while True:
            time.sleep(3600)

    ingestor = AlpacaIngestor(store, symbols)
    log.info("Starting Alpaca ingestion for %s", ingestor.symbols)
    ingestor.run()


if __name__ == "__main__":
    main()
