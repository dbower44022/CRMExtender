"""Enrichment provider interface, data types, and registry."""

from __future__ import annotations

import enum
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


class SourceTier(enum.IntEnum):
    """Conflict-resolution precedence (higher = more authoritative)."""
    INFERRED = 1
    EMAIL_SIGNATURE = 2
    WEBSITE_SCRAPE = 3
    FREE_API = 4
    PAID_API = 5
    MANUAL = 6


@dataclass
class FieldValue:
    """A single enrichment result field."""
    field_name: str
    field_value: str
    confidence: float = 0.0
    source_url: str = ""


class EnrichmentProvider(ABC):
    """Base class for enrichment providers."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def tier(self) -> SourceTier: ...

    @property
    def entity_types(self) -> list[str]:
        return ["company"]

    @property
    def rate_limit(self) -> float:
        return 1.0

    @property
    def cost_per_lookup(self) -> float:
        return 0.0

    @property
    def refresh_cadence_days(self) -> int:
        return 90

    @abstractmethod
    def enrich(self, entity: dict) -> list[FieldValue]:
        """Run enrichment on an entity dict. Returns discovered field values."""
        ...


# ---------------------------------------------------------------------------
# Provider registry
# ---------------------------------------------------------------------------

_registry: dict[str, EnrichmentProvider] = {}


def register_provider(provider: EnrichmentProvider) -> None:
    """Register a provider instance by name."""
    _registry[provider.name] = provider


def get_provider(name: str) -> EnrichmentProvider | None:
    """Look up a registered provider by name."""
    return _registry.get(name)


def list_providers() -> list[EnrichmentProvider]:
    """Return all registered providers."""
    return list(_registry.values())
