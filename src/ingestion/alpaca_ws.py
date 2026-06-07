"""Alpaca real-time ingestion.

Holds ONE WebSocket connection to Alpaca's stock data stream (free IEX feed),
subscribes to the configured symbols, normalizes each trade and pushes it to
Redis. This is the primary live feed; other sources (Schwab, Finnhub) can be
added later as sibling ingestors that share the same RedisStore.
"""
from __future__ import annotations
import logging
import os

from alpaca.data.live import StockDataStream
from alpaca.data.enums import DataFeed

from ..transform.normalize import normalize_trade
from ..storage.redis_store import RedisStore

log = logging.getLogger("pipeline.alpaca")

DEFAULT_SYMBOLS = ["AAPL", "TSLA", "NVDA", "MSFT", "AMZN", "GOOGL", "META", "SPY"]


class AlpacaIngestor:
    def __init__(self, store: RedisStore, symbols: list[str] | None = None):
        self.store = store
        self.symbols = symbols or DEFAULT_SYMBOLS
        key = os.environ["ALPACA_API_KEY"]
        secret = os.environ["ALPACA_SECRET_KEY"]
        # Free accounts use the IEX feed; paid plans can switch to SIP.
        feed = DataFeed.SIP if os.getenv("ALPACA_FEED", "iex").lower() == "sip" else DataFeed.IEX
        self.stream = StockDataStream(key, secret, feed=feed)

    async def _on_trade(self, trade) -> None:
        tick = normalize_trade(
            symbol=trade.symbol,
            price=trade.price,
            size=trade.size,
            ts=getattr(trade, "timestamp", None),
        )
        self.store.publish_tick(tick)

    def run(self) -> None:
        for sym in self.symbols:
            self.stream.subscribe_trades(self._on_trade, sym)
        log.info("Subscribed to trades: %s", ", ".join(self.symbols))
        # Blocking — manages its own asyncio loop and reconnects.
        self.stream.run()
