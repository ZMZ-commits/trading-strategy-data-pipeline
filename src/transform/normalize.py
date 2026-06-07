"""Normalize provider-specific market events into one common tick schema.

Every ingestion source funnels through here so the rest of the platform
(backend, strategy engine) never has to care which provider a tick came from.
Adding a new source = add a normalize_* function that returns this shape.
"""
from __future__ import annotations
from datetime import datetime, timezone


def _iso(ts: datetime | None) -> str:
    return (ts or datetime.now(timezone.utc)).isoformat()


def normalize_trade(
    symbol: str,
    price: float,
    size: float | int,
    ts: datetime | None,
    source: str = "alpaca",
) -> dict:
    """A single executed trade (a 'tick')."""
    return {
        "symbol": symbol.upper(),
        "price": round(float(price), 4),
        "size": float(size),
        "timestamp": _iso(ts),
        "source": source,
        "type": "trade",
    }
