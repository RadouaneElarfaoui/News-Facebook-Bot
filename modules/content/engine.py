"""
Content — Engine
=================
Génère en un seul appel structuré via Antigravity CLI (`agy`) :
- le titre arabe punchy (`title`)
- les mots-clés à surligner en jaune (`keywords`)
- la requête de recherche d'image en anglais (`image_query`)
- la légende Facebook (`caption`)
- le résumé narratif en premier commentaire (`detail_comment`)
"""
from __future__ import annotations

import re
from modules.core.config_loader import config, prompts
from modules.core.logger import get_logger
from modules.llm import LLMAuthError, LLMBackend, LLMError, get_backend

logger = get_logger(__name__)

CTA_SUFFIX = "التفاصيل في أول تعليق 👇"

PACKAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "keywords": {"type": "array", "items": {"type": "string"}},
        "image_query": {"type": "string"},
        "caption": {"type": "string"},
        "detail_comment": {"type": "string"},
    },
    "required": [
        "title",
        "keywords",
        "image_query",
        "caption",
        "detail_comment",
    ],
}


class ContentEngine:
    def __init__(self, backend: LLMBackend | None = None):
        self.backend = backend or get_backend()

    @staticmethod
    def _brand_format_vars() -> dict:
        brand = config.get("brand", {})
        p = brand.get("persona", {})
        values = p.get("values", [])
        return {
            "brand_name": brand.get("name", "Screen Drop"),
            "brand_tagline": brand.get("tagline", ""),
            "brand_hook": brand.get("hook", ""),
            "brand_persona": p.get("style", ""),
            "brand_tone": p.get("tone", ""),
            "brand_age": p.get("age", ""),
            "brand_style": p.get("style", ""),
            "brand_values_line": "\n".join(f"- {v}" for v in values),
        }

    @staticmethod
    def _normalize_package(data: dict) -> dict | None:
        if not isinstance(data, dict):
            return None

        title = str(data.get("title") or "").strip()
        if not title:
            return None

        raw_keywords = data.get("keywords") or []
        if isinstance(raw_keywords, list):
            keywords = [str(k).strip() for k in raw_keywords if str(k).strip()][:3]
        else:
            keywords = []

        image_query = str(data.get("image_query") or "").strip() or "breaking news"

        caption = str(data.get("caption") or "").strip() or title
        if CTA_SUFFIX not in caption:
            caption = f"{caption}\n{CTA_SUFFIX}"

        detail_comment = str(data.get("detail_comment") or "").strip()
        # Nettoyage préventif des séparateurs markdown éventuels
        detail_comment = re.sub(r"^\s*(?:\*{3,}|-{3,}|#{1,6}\s+).*$", "", detail_comment, flags=re.MULTILINE).strip()

        return {
            "title": title,
            "keywords": keywords,
            "image_query": image_query,
            "caption": caption,
            "detail_comment": detail_comment,
        }

    def generate_package(self, article_text: str) -> dict | None:
        """
        Génère l'ensemble du contenu éditorial d'un article en un seul appel `agy`.
        Lève `LLMAuthError` si la session `agy` nécessite une reconnexion.
        """
        prompt_cfg = prompts["article_package"]
        bv = self._brand_format_vars()
        sys_instr = prompt_cfg["system"].format(**bv).strip()
        user_prompt = prompt_cfg["user_template"].format(article_text=article_text).strip()
        full_prompt = f"{sys_instr}\n\n{user_prompt}"

        try:
            logger.info("Génération du package éditorial via %s...", self.backend.name)
            raw_data = self.backend.generate_json(full_prompt, PACKAGE_SCHEMA)
            pkg = self._normalize_package(raw_data)
            if not pkg:
                logger.error("Package retourné invalide : %s", raw_data)
                return None

            logger.info("✓ Titre généré : %s", pkg["title"])
            return pkg

        except LLMAuthError:
            raise
        except LLMError as e:
            logger.error("Erreur LLM lors de la génération du contenu : %s", e)
            return None
        except Exception as e:
            logger.error("Erreur inattendue génération contenu : %s", e)
            return None
