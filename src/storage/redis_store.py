"""Redis storage for the live path.

Two roles:
  - pub/sub channel `ticks:{SYMBOL}` so subscribers (backend WS) get pushed every tick
  - key `price:{SYMBOL}` caching the latest tick so a new subscriber gets an
    immediate value instead of waiting for the next trade.
"""
from __future__ import annotations
import json

import redis


class RedisStore:
    def __init__(self, url: str):
        self.r = redis.from_url(url, decode_responses=True)

    def publish_tick(self, tick: dict) -> None:
        symbol = tick["symbol"]
        payload = json.dumps(tick)
        self.r.publish(f"ticks:{symbol}", payload)
        # Cache latest with a 1-day expiry so stale prices don't linger forever.
        self.r.set(f"price:{symbol}", payload, ex=86400)

    def get_latest(self, symbol: str) -> dict | None:
        v = self.r.get(f"price:{symbol.upper()}")
        return json.loads(v) if v else None

    def ping(self) -> bool:
        return bool(self.r.ping())
