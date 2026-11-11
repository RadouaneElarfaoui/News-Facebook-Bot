"""
LLM Package
===========
Point d'accès centralisé vers le backend LLM (Antigravity CLI `agy`).
"""
from __future__ import annotations

from modules.llm.agy_backend import AgyBackend
from modules.llm.base import LLMAuthError, LLMBackend, LLMError

_BACKEND_INSTANCE: AgyBackend | None = None


def get_backend() -> AgyBackend:
    """Retourne l'instance singleton du backend agy."""
    global _BACKEND_INSTANCE
    if _BACKEND_INSTANCE is None:
        _BACKEND_INSTANCE = AgyBackend()
    return _BACKEND_INSTANCE


__all__ = [
    "AgyBackend",
    "LLMAuthError",
    "LLMBackend",
    "LLMError",
    "get_backend",
]
