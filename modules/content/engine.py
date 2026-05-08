"""
Content — Engine
=================
Génère le titre, les mots-clés et la légende via Gemini 3/Gemma 4.
Utilise le nouveau SDK google-genai.
"""
import json
from google import genai
from modules.core.config_loader import config, prompts
from modules.core.logger import get_logger

logger = get_logger(__name__)

class ContentEngine:
    def __init__(self):
        self.client = genai.Client(api_key=config["apis"]["gemini"]["api_key"])
        self.model_name = config["apis"]["gemini"]["model"]

    def generate_post_data(self, article_text: str) -> dict | None:
        """
        Réécrit le news pour Screen Mix (Titre + Keywords).
        """
        prompt_cfg = prompts["rewrite_news"]
        brand_name = config.get("brand_name", "News Bot")
        sys_instr = prompt_cfg["system"].format(brand_name=brand_name)
        user_prompt = prompt_cfg["user_template"].format(article_text=article_text)

        try:
            logger.info("Génération du titre via Gemini (%s)...", self.model_name)
            response = self.client.models.generate_content(
                model=self.model_name,
                config={
                    "system_instruction": sys_instr,
                    "response_mime_type": "application/json"
                },
                contents=user_prompt
            )
            
            data = json.loads(response.text)
            logger.info("✓ Titre généré : %s", data.get("title"))
            return data
            
        except Exception as e:
            logger.error("Erreur génération contenu : %s", e)
            return None

    def generate_caption(self, title: str) -> str:
        """
        Génère une légende Facebook engageante.
        """
        prompt_cfg = prompts["caption_generator"]
        brand_name = config.get("brand_name", "News Bot")
        sys_instr = prompt_cfg["system"].format(brand_name=brand_name)
        user_prompt = prompt_cfg["user_template"].format(title=title)


        try:
            logger.info("Génération de la légende...")
            response = self.client.models.generate_content(
                model=self.model_name,
                config={"system_instruction": sys_instr},
                contents=user_prompt
            )
            return response.text.strip()
        except Exception as e:
            logger.error("Erreur génération légende : %s", e)
            return ""

    def generate_detail_comment(self, article_text: str) -> str:
        """
        Génère un résumé détaillé pour le premier commentaire.
        """
        prompt_cfg = prompts["detail_comment_generator"]
        brand_name = config.get("brand_name", "News Bot")
        sys_instr = prompt_cfg["system"].format(brand_name=brand_name)
        user_prompt = prompt_cfg["user_template"].format(article_text=article_text)

        try:
            logger.info("Génération du commentaire détaillé...")
            response = self.client.models.generate_content(
                model=self.model_name,
                config={"system_instruction": sys_instr},
                contents=user_prompt
            )
            return response.text.strip()
        except Exception as e:
            logger.error("Erreur génération commentaire détaillé : %s", e)
            return ""

