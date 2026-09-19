"""Write each tick to several stores, without letting one take down the others.

The ingestor holds exactly one `store` and calls `publish_tick` on it. Rather
than teach it about a second destination, this presents the same interface and
forwards to each underlying store in turn.

The isolation is the point. Kafka being unreachable must not stop ticks
reaching Redis, because Redis is what the browsers are watching -- a history
outage should never become a live outage.
"""
from __future__ import annotations

import logging
from typing import Protocol, Sequence

log = logging.getLogger("pipeline.fanout")


class TickStore(Protocol):
    def publish_tick(self, tick: dict) -> None: ...


class FanoutStore:
    def __init__(self, stores: Sequence[TickStore]) -> None:
        self._stores = list(stores)

    def publish_tick(self, tick: dict) -> None:
        for store in self._stores:
            try:
                store.publish_tick(tick)
            except Exception:  # noqa: BLE001
                # Deliberately broad, and deliberately not re-raised. This runs
                # inside the websocket callback; an exception escaping here
                # would tear down the stream for every symbol because one
                # destination was unhappy.
                log.exception("%s failed to publish; continuing", type(store).__name__)
