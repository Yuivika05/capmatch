"""event_bus.py — a tiny Kafka-STYLE event pipeline (Plan part 4: messaging).

    New Investor  ->  topic  ->  embedding service  ->  store in vector DB

Real Kafka needs Java + Zookeeper (heavy for a laptop). This is the SAME PATTERN
in pure Python: producers publish() to named topics; consumers subscribe() and
react. Swap in real kafka-python later by rewriting ONLY this file.
  TOPIC = a named channel   PRODUCER = publish()   CONSUMER = subscribe()
"""
from __future__ import annotations

import datetime as _dt
from collections import defaultdict
from typing import Callable, Dict, List

_SUBSCRIBERS: Dict[str, List[Callable[[dict], None]]] = defaultdict(list)
_LOG: Dict[str, List[dict]] = defaultdict(list)


def subscribe(topic: str, handler: Callable[[dict], None]) -> None:
    """Register a consumer: `handler` runs every time an event hits `topic`."""
    _SUBSCRIBERS[topic].append(handler)


def publish(topic: str, event: dict) -> dict:
    """Producer: publish one event to a topic. All subscribers react at once."""
    envelope = {
        "topic": topic,
        "timestamp": _dt.datetime.utcnow().isoformat() + "Z",
        "offset": len(_LOG[topic]),
        "value": event,
    }
    _LOG[topic].append(envelope)
    for handler in _SUBSCRIBERS[topic]:
        try:
            handler(envelope)
        except Exception as exc:
            print(f"[event_bus] consumer error on '{topic}': {exc}")
    return envelope


def get_log(topic: str) -> List[dict]:
    """Return every event ever published to a topic (for the dashboard / debug)."""
    return list(_LOG[topic])


def all_topics() -> Dict[str, int]:
    """Map of topic -> number of events, so we can show pipeline activity."""
    return {t: len(evs) for t, evs in _LOG.items()}