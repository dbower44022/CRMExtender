"""In-process event broadcast for the mail surface (Mail Client MAIL-37).

The scheduler and the outbox publish small JSON-able events from their
worker threads; the ``GET /mail/events`` route streams them to browsers as
server-sent events. Each subscriber owns a bounded queue; a slow consumer
drops its oldest events rather than blocking a publisher. The browser keeps
polling as its fallback, so a dropped event costs at most one poll interval.
"""

from __future__ import annotations

import json
import queue
import threading
from datetime import datetime, timezone

_subscribers: set[queue.Queue] = set()
_lock = threading.Lock()
_seq = 0

QUEUE_SIZE = 256


def publish(event_type: str, **data) -> dict:
    """Broadcast one event to every subscriber. Safe from any thread."""
    global _seq
    with _lock:
        _seq += 1
        event = {"id": _seq, "type": event_type, "at": datetime.now(timezone.utc).isoformat(), **data}
        subs = list(_subscribers)
    for q in subs:
        try:
            q.put_nowait(event)
        except queue.Full:
            try:
                q.get_nowait()          # drop the oldest; the client polls anyway
                q.put_nowait(event)
            except (queue.Empty, queue.Full):
                pass
    return event


def subscribe() -> queue.Queue:
    q: queue.Queue = queue.Queue(maxsize=QUEUE_SIZE)
    with _lock:
        _subscribers.add(q)
    return q


def unsubscribe(q: queue.Queue) -> None:
    with _lock:
        _subscribers.discard(q)


def subscriber_count() -> int:
    with _lock:
        return len(_subscribers)


def format_sse(event: dict) -> str:
    """One server-sent-events frame: ``id``, ``event`` and a JSON ``data`` line."""
    return f"id: {event['id']}\nevent: {event['type']}\ndata: {json.dumps(event)}\n\n"
