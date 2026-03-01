"""
Asynchronous Event Bus for SGR Kernel.
"""

import asyncio
import logging
from typing import Awaitable, Callable, Dict, List

from core.events import KernelEvent

logger = logging.getLogger(__name__)

# Type for event handler
EventHandler = Callable[[KernelEvent], Awaitable[None]]


class EventBus:
    """
    Simple Pub/Sub Event Bus for Kernel-wide communication.
    """

    def __init__(self, event_store=None):
        self._subscribers: Dict[str, List[EventHandler]] = {}
        self._global_subscribers: List[EventHandler] = []
        self.event_store = event_store

    def subscribe(self, event_type: str, handler: EventHandler):
        """Subscribe to a specific event type."""
        self._subscribers.setdefault(event_type, []).append(handler)
        logger.debug(f"Subscribed to {event_type}: {handler.__name__ if hasattr(handler, '__name__') else 'anonymous'}")

    def subscribe_all(self, handler: EventHandler):
        """Subscribe to all events (useful for logging/telemetry)."""
        self._global_subscribers.append(handler)

    async def publish(self, event: KernelEvent):
        """Publish an event to all interested subscribers."""
        # 1. PERSIST FIRST (Canonical Source of Truth)
        if self.event_store:
            try:
                await self.event_store.append(event)
            except Exception as e:
                logger.critical(f"🔥 FAILED TO PERSIST EVENT {event.event_id}: {e}")
                # We might choose to raise here to stop processing if persistence is mandatory
                # For now, we log critical error.
                pass

        handlers = self._subscribers.get(event.type, []).copy()
        handlers.extend(self._global_subscribers)

        if not handlers:
            return

        # Execute all handlers concurrently
        tasks = [handler(event) for handler in handlers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Log errors from handlers but don't stop the bus
        for res in results:
            if isinstance(res, Exception):
                logger.error(f"Error in EventBus handler: {res}", exc_info=res)
