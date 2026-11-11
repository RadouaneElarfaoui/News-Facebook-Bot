"""
LLM — Base Protocol & Exceptions
=================================
Définit l'interface commune du moteur LLM et les exceptions associées.
"""
from __future__ import annotations

from typing import Protocol


class LLMError(Exception):
    """Erreur générique lors d'un appel au moteur LLM."""


class LLMAuthError(LLMError):
    """Erreur d'authentification (session agy expirée ou non connectée)."""


class LLMBackend(Protocol):
    """Interface d'un backend LLM capable de produire du JSON structuré."""
    name: str

    def generate_json(self, prompt: str, schema: dict) -> dict:
        ...
