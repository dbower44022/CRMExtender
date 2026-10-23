"""Provider adapter registry (email-provider-sync-prd.md EPS-02).

``get_provider(name)`` resolves the value of ``provider_accounts.provider``
to an adapter instance. Adapters are imported lazily so that
``poc.gmail_client`` can import :mod:`poc.providers.base` without a cycle.
"""

from __future__ import annotations

from .base import (
    Action,
    ActionKind,
    ActionResult,
    ActionStatus,
    CursorInvalid,
    Delta,
    Folder,
    FolderKind,
    MailMessage,
    MailProvider,
    OutboundMessage,
    ProviderError,
    SyncStatus,
)

__all__ = [
    "Action",
    "ActionKind",
    "ActionResult",
    "ActionStatus",
    "CursorInvalid",
    "Delta",
    "Folder",
    "FolderKind",
    "MailMessage",
    "MailProvider",
    "OutboundMessage",
    "ProviderError",
    "SyncStatus",
    "UnknownProviderError",
    "get_provider",
    "register_provider",
    "registered_providers",
]


class UnknownProviderError(ProviderError):
    """No adapter is registered for the requested provider name."""


_REGISTRY: dict[str, type[MailProvider]] = {}
_INSTANCES: dict[str, MailProvider] = {}


def register_provider(cls: type[MailProvider]) -> type[MailProvider]:
    """Class decorator: register ``cls`` under ``cls.name``."""
    if not cls.name:
        raise ValueError(f"{cls.__name__} must set a non-empty 'name'")
    _REGISTRY[cls.name] = cls
    _INSTANCES.pop(cls.name, None)
    return cls


def _load_builtin_adapters() -> None:
    if "gmail" not in _REGISTRY:
        from . import gmail  # noqa: F401  (registers GmailProvider on import)


def registered_providers() -> list[str]:
    _load_builtin_adapters()
    return sorted(_REGISTRY)


def get_provider(name: str) -> MailProvider:
    """Return the adapter instance for ``name`` (e.g. ``"gmail"``)."""
    _load_builtin_adapters()
    key = (name or "").lower()
    cls = _REGISTRY.get(key)
    if cls is None:
        raise UnknownProviderError(
            f"No mail provider adapter registered for {name!r}; "
            f"known: {', '.join(sorted(_REGISTRY)) or 'none'}"
        )
    inst = _INSTANCES.get(key)
    if inst is None:
        inst = _INSTANCES[key] = cls()
    return inst
