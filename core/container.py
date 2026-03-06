"""
Dependency Injection Container for SGR Kernel.
Manages lifecycle of core services.
"""

import logging
from typing import Any, Dict, TypeVar

T = TypeVar("T")

logger = logging.getLogger(__name__)


class Container:
    """
    Simple dependency container for service management.
    """

    _services: Dict[str, Any] = {}
    _providers: Dict[str, Any] = {}

    @classmethod
    def register(cls, name: str, service: Any) -> None:
        """Register a pre-instantiated service."""
        cls._services[name] = service
        logger.debug(f"Service registered: {name}")

    @classmethod
    def register_provider(cls, name: str, provider: Any) -> None:
        """Register a provider function/class for lazy instantiation."""
        cls._providers[name] = provider
        logger.debug(f"Provider registered: {name}")

    @classmethod
    def get(cls, name: str) -> Any:
        """Get a service by name. Instantiates if provider exists and not yet created."""
        if name in cls._services:
            return cls._services[name]

        if name in cls._providers:
            provider = cls._providers[name]
            if callable(provider):
                service = provider()
            else:
                service = provider
            cls._services[name] = service
            return service

        raise ValueError(f"Service '{name}' not found in container.")

    @classmethod
    def reset(cls):
        """Clear all services and providers."""
        cls._services.clear()
        cls._providers.clear()
