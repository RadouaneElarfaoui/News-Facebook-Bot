"""
Content — Engine
=================
Génère le titre, les mots-clés et la légende via Gemini/Gemma.
Utilise le nouveau SDK google-genai avec retry + backoff automatique.
"""
import json
import re
import time
import random
from google import genai
from modules.core.config_loader import config, prompts
from modules.core.logger import get_logger

logger = get_logger(__name__)

# Délai minimum entre chaque appel Gemini (évite le rate limiting)
_GEMINI_CALL_DELAY = 3  # secondes


def _call_gemini_with_retry(client, model_name: str, gen_config: dict, contents: str,
                             max_retries: int = 3):
    """
    Appelle l'API Gemini avec retry + exponential backoff en cas d'erreur 500.

    Args:
        max_retries: Nombre max de tentatives (3 = 1 essai + 2 retries).

    Returns:
        L'objet response de l'API, ou lève l'exception si tous les retries échouent.
    """
    delay = 5  # délai initial avant le 1er retry (secondes)

    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=model_name,
                config=gen_config,
                contents=contents
            )
            # Pause systématique après chaque appel réussi (anti rate-limit)
            time.sleep(_GEMINI_CALL_DELAY)
            return response

        except Exception as e:
            error_str = str(e)
            is_server_error = "500" in error_str or "INTERNAL" in error_str
            is_rate_limit = "429" in error_str or "RESOURCE_EXHAUSTED" in error_str

            if attempt < max_retries - 1 and (is_server_error or is_rate_limit):
                wait = delay + random.uniform(0, 2)  # jitter pour éviter les pics
                logger.warning(
                    "⚠️ Gemini erreur temporaire (tentative %d/%d). Retry dans %.1fs : %s",
                    attempt + 1, max_retries, wait, error_str[:80]
                )
                time.sleep(wait)
                delay *= 2  # backoff exponentiel : 5s → 10s → 20s
            else:
                raise  # Erreur non-récupérable ou dernière tentative


class ContentEngine:
    def __init__(self):
        self.client = genai.Client(api_key=config["apis"]["gemini"]["api_key"])
        self.model_name = config["apis"]["gemini"]["model"]

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

    def generate_post_data(self, article_text: str) -> dict | None:
        """
        Réécrit le news (Titre + Keywords + image_query).
        """
        prompt_cfg = prompts["rewrite_news"]
        bv = self._brand_format_vars()
        sys_instr = prompt_cfg["system"].format(**bv)
        user_prompt = prompt_cfg["user_template"].format(article_text=article_text)

        try:
            logger.info("Génération du titre via Gemini (%s)...", self.model_name)
            response = _call_gemini_with_retry(
                self.client, self.model_name,
                gen_config={
                    "system_instruction": sys_instr,
                    "response_mime_type": "application/json"
                },
                contents=user_prompt
            )
            raw_text = response.text.strip() if (response and response.text) else ""
            if raw_text.startswith("```"):
                raw_text = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_text, flags=re.IGNORECASE).strip()

            data = json.loads(raw_text)
            if not isinstance(data, dict) or "title" not in data:
                logger.error("Dictionnaire retourné par Gemini invalide : %s", data)
                return None

            logger.info("✓ Titre généré : %s", data.get("title"))
            return data

        except json.JSONDecodeError as e:
            logger.error("Gemini a retourné un JSON invalide (après retries) : %s", e)
            return None
        except Exception as e:
            logger.error("Erreur génération contenu (après retries) : %s", e)
            return None

    def generate_caption(self, title: str) -> str:
        """
        Génère une légende Facebook engageante.
        """
        prompt_cfg = prompts["caption_generator"]
        bv = self._brand_format_vars()
        sys_instr = prompt_cfg["system"].format(**bv)
        user_prompt = prompt_cfg["user_template"].format(title=title)

        try:
            logger.info("Génération de la légende...")
            response = _call_gemini_with_retry(
                self.client, self.model_name,
                gen_config={"system_instruction": sys_instr},
                contents=user_prompt
            )
            return response.text.strip()

        except Exception as e:
            logger.error("Erreur génération légende (après retries) : %s", e)
            return title  # fallback : utiliser le titre comme légende

    def generate_detail_comment(self, article_text: str) -> str:
        """
        Génère un résumé détaillé pour le premier commentaire.
        """
        prompt_cfg = prompts["detail_comment_generator"]
        bv = self._brand_format_vars()
        sys_instr = prompt_cfg["system"].format(**bv)
        user_prompt = prompt_cfg["user_template"].format(article_text=article_text)

        try:
            logger.info("Génération du commentaire détaillé...")
            response = _call_gemini_with_retry(
                self.client, self.model_name,
                gen_config={"system_instruction": sys_instr},
                contents=user_prompt
            )
            return response.text.strip()

        except Exception as e:
            logger.error("Erreur génération commentaire détaillé (après retries) : %s", e)
            return ""  # commentaire vide, le post est publié quand même
