from dataclasses import dataclass, field
from time import time
from typing import Any, Callable, Dict, List

from PyQt6.QtCore import QObject, pyqtSignal

try:
    from ai_content_classifier.views.events.event_types import EventType
except ImportError:  # pragma: no cover - compatibility import
    from views.events.event_types import EventType


@dataclass(slots=True)
class AppEvent:
    """Generic event payload transported on the event bus."""

    event_type: EventType
    payload: Dict[str, Any] = field(default_factory=dict)
    source: str = ""
    timestamp: float = field(default_factory=time)


class EventBus(QObject):
    """
    Lightweight in-process pub/sub bus for the views layer.

    Qt signal dispatch keeps callbacks on the UI thread.
    """

    event_published = pyqtSignal(object)  # AppEvent

    def __init__(self, parent=None):
        super().__init__(parent)
        self._subscribers: Dict[EventType, List[Callable[[AppEvent], None]]] = {}
        self.event_published.connect(self._dispatch)

    def subscribe(self, event_type: EventType, handler: Callable[[AppEvent], None]):
        """Registers a handler for a specific event type."""
        handlers = self._subscribers.setdefault(event_type, [])
        if handler not in handlers:
            handlers.append(handler)

    def publish(
        self,
        event_type: EventType,
        payload: Dict[str, Any] | None = None,
        source: str = "",
    ):
        """Publishes an event to all subscribed handlers."""
        self.event_published.emit(
            AppEvent(
                event_type=event_type,
                payload=payload or {},
                source=source,
            )
        )

    def _dispatch(self, event: AppEvent):
        """Dispatches an event to subscribed handlers."""
        for handler in self._subscribers.get(event.event_type, []):
            handler(event)
