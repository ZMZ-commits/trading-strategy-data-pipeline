"""Kafka storage for the durable path.

Redis and Kafka are not alternatives here, they answer different questions.
Redis pub/sub is a push to whoever is listening *right now*; a subscriber that
connects a second later never learns the tick happened. Kafka keeps every tick
for its retention window, so a consumer can start late, replay from the
beginning, or fall behind and catch up. Backtests and bar-building need the
second; live browser updates need the first.

Ordering is why every message is keyed by symbol. Kafka guarantees order within
a partition, not across a topic, and a key always hashes to the same partition.
Ticks for AAPL therefore arrive in the order they happened -- which matters
because a bar built from out-of-order ticks has the wrong high and low.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from confluent_kafka import Producer

log = logging.getLogger("pipeline.kafka")


class KafkaStore:
    """Publishes normalized ticks to a Kafka topic.

    Deliberately shares the `publish_tick(tick)` shape with RedisStore so the
    ingestor cannot tell them apart.
    """

    def __init__(self, bootstrap: str, topic: str = "market.trades") -> None:
        self.topic = topic
        self._producer = Producer(
            {
                "bootstrap.servers": bootstrap,
                # Identifies this producer in the broker's logs and in the
                # console's client list, which is worth having when something
                # is misbehaving and several things are producing.
                "client.id": "trading-strategy-data-pipeline",
                # Compress on the wire. Ticks are small, repetitive JSON, so
                # this is close to free and the topic is configured
                # `compression.type=producer`, meaning the broker stores
                # whatever the producer chose rather than recompressing.
                "compression.type": "lz4",
                # Wait up to 20ms to fill a batch. At eight symbols the volume
                # is low, so this trades a barely-perceptible delay for far
                # fewer round trips.
                "linger.ms": 20,
                # Retry, but do not let the queue grow without bound. If Kafka
                # is unreachable the queue fills, produce() raises BufferError,
                # and we drop rather than consume memory forever -- Redis is
                # still carrying the live path, so a dropped Kafka write costs
                # history, not the running system.
                "retries": 5,
                "queue.buffering.max.messages": 100_000,
            }
        )
        log.info("Kafka producer ready: %s -> %s", bootstrap, topic)

    def _on_delivery(self, err: Any, msg: Any) -> None:
        # Only failures are logged. Eight symbols in a busy market is a lot of
        # ticks, and a line per successful delivery would bury everything else.
        if err is not None:
            log.warning("Kafka delivery failed for %s: %s", msg.key(), err)

    def publish_tick(self, tick: dict) -> None:
        symbol = tick["symbol"]
        try:
            self._producer.produce(
                self.topic,
                key=symbol.encode(),
                value=json.dumps(tick).encode(),
                on_delivery=self._on_delivery,
            )
            # Serves delivery callbacks for messages already sent. Non-blocking
            # with a 0 timeout; without it the callbacks queue up and the
            # library eventually complains.
            self._producer.poll(0)
        except BufferError:
            # The local queue is full, which means the broker has been
            # unreachable for a while. Drop this tick rather than block the
            # Alpaca websocket callback -- stalling here would back up the
            # stream and cost us the live path too.
            log.warning("Kafka queue full, dropping tick for %s", symbol)

    def flush(self, timeout: float = 10.0) -> int:
        """Block until queued messages are delivered. Returns the number still
        undelivered, which is non-zero only if the broker could not be reached."""
        return self._producer.flush(timeout)
