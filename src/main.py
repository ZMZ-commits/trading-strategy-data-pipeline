"""Pipeline entrypoint: stream Alpaca trades into Redis, and optionally Kafka.

Env vars:
  REDIS_URL          redis connection (default redis://localhost:6379)
  ALPACA_API_KEY     Alpaca key id        (required)
  ALPACA_SECRET_KEY  Alpaca secret key    (required)
  ALPACA_FEED        'iex' (free, default) or 'sip' (paid)
  SYMBOLS            comma-separated tickers (default: a basket of large caps)
  KAFKA_BOOTSTRAP    Kafka bootstrap servers. UNSET = Redis only, exactly as
                     before. Setting it adds a durable copy of every tick
                     WITHOUT changing the Redis path the backends subscribe to.
                       in-cluster : tsp-kafka-bootstrap.kafka.svc:9092
                       outside    : <node-ip>:30092
  KAFKA_TOPIC        topic for ticks (default market.trades)
"""
from __future__ import annotations
import logging
import os
import time

from .storage.redis_store import RedisStore
from .storage.fanout import FanoutStore
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

    # Kafka is additive and opt-in. Unset KAFKA_BOOTSTRAP and this behaves
    # exactly as it did before -- which is what makes deploying it safe
    # independently of turning it on.
    #
    # Redis stays the live path regardless: the backends subscribe to
    # ticks:{SYMBOL} and would all break if it were replaced. Kafka is the
    # durable copy, for replay, backtests and anything that starts late.
    tick_store = store
    kafka_bootstrap = os.getenv("KAFKA_BOOTSTRAP", "").strip()
    if kafka_bootstrap:
        # Imported here rather than at module scope so the absence of
        # confluent-kafka cannot stop the Redis-only path from starting.
        from .storage.kafka_store import KafkaStore

        kafka_store = KafkaStore(kafka_bootstrap, os.getenv("KAFKA_TOPIC", "market.trades"))
        tick_store = FanoutStore([store, kafka_store])
        log.info("Publishing ticks to Redis AND Kafka (%s)", kafka_bootstrap)
    else:
        log.info("KAFKA_BOOTSTRAP not set — Redis only")

    ingestor = AlpacaIngestor(tick_store, symbols)
    log.info("Starting Alpaca ingestion for %s", ingestor.symbols)
    try:
        ingestor.run()
    finally:
        # Anything still queued is in memory only. Without this a restart
        # silently loses the last batch, which linger.ms makes a certainty
        # rather than a possibility.
        if kafka_bootstrap:
            undelivered = kafka_store.flush()
            if undelivered:
                log.warning("%d Kafka messages undelivered at shutdown", undelivered)


if __name__ == "__main__":
    main()
