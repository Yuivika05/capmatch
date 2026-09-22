"""embedding_service.py — the CONSUMER in the Kafka-style pipeline.

    New Investor --publish--> topic "investor.created"
                                    |
                                    v
                      embedding_service (this file)
                                    |
                                    v
                 embed the profile & add to the vector DB

Subscribes to "investor.created". When a new investor arrives it turns the
profile into a searchable document, adds it to the live vector index, and emits
an "investor.indexed" event — automatically, like a real Kafka consumer.
"""
from __future__ import annotations

from typing import Dict, List

from event_bus import subscribe, publish
import data_access

TOPIC_INVESTOR_CREATED = "investor.created"
TOPIC_INVESTOR_INDEXED = "investor.indexed"

_RUNTIME_INVESTORS: List[Dict] = []


def runtime_investors() -> List[Dict]:
    """Investors added live via the pipeline (not in the original JSON file)."""
    return list(_RUNTIME_INVESTORS)


def _on_investor_created(envelope: dict) -> None:
    """CONSUMER: react to a 'new investor' event by embedding + indexing it."""
    inv = envelope["value"]
    _RUNTIME_INVESTORS.append(inv)
    doc = data_access._investor_doc(inv)
    index = data_access._investor_index()
    mode = getattr(index, "mode", "fallback")
    try:
        index.add(doc, inv["id"])
        indexed = True
    except Exception as exc:
        print(f"[embedding_service] index add failed: {exc}")
        indexed = False
    publish(TOPIC_INVESTOR_INDEXED, {
        "investor_id": inv["id"],
        "name": inv.get("name"),
        "indexed": indexed,
        "vector_mode": mode,
    })
    print(f"[embedding_service] indexed investor '{inv.get('name')}' "
          f"(id={inv['id']}, mode={mode}, ok={indexed})")


# Register this consumer as soon as the module is imported.
subscribe(TOPIC_INVESTOR_CREATED, _on_investor_created)


def register_investor(investor: Dict) -> dict:
    """PRODUCER entry point: publish a new investor into the pipeline."""
    return publish(TOPIC_INVESTOR_CREATED, investor)