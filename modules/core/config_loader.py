"""
Core — Config Loader
Charge les fichiers YAML et injecte les secrets depuis .env.
Les valeurs ${VAR} dans settings.yaml sont remplacées par les variables d'environnement.
"""
import os
import re
import yaml
from pathlib import Path
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Charge le fichier .env s'il existe (ne fait rien si absent)
load_dotenv(BASE_DIR / ".env")


def _resolve_env_vars(value):
    """
    Résout récursivement les placeholders ${VAR} dans les valeurs YAML
    en les remplaçant par les variables d'environnement correspondantes.
    Convertit automatiquement les chaînes booléennes ("true"/"false") et entiers si applicable.
    """
    if isinstance(value, str):
        # Remplace tous les ${VAR} ou ${VAR:-defaut} trouvés
        def replacer(match):
            var_name = match.group(1)
            default_val = match.group(2)
            env_val = os.environ.get(var_name)
            if env_val is not None:
                return env_val
            if default_val is not None:
                return default_val
            raise EnvironmentError(
                f"Variable d'environnement manquante : '{var_name}'. "
                f"Vérifiez votre fichier .env (voir .env.example)."
            )
        resolved = re.sub(r"\$\{(\w+)(?::-([^}]*))?\}", replacer, value)
        # Typage automatique pour les booléens usuels
        lowered = resolved.lower()
        if lowered in ("true", "yes", "1"):
            return True
        if lowered in ("false", "no", "0"):
            return False
        return resolved
    elif isinstance(value, dict):
        return {k: _resolve_env_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [_resolve_env_vars(item) for item in value]
    return value


def load_config() -> dict:
    """Charge settings.yaml, résout les ${VAR} via .env, et retourne le dict de configuration."""
    config_path = BASE_DIR / "config" / "settings.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return _resolve_env_vars(raw)


def load_prompts() -> dict:
    """Charge prompts.yaml et retourne les templates."""
    prompts_path = BASE_DIR / "config" / "prompts.yaml"
    with open(prompts_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# Singletons accessibles depuis tous les modules
config = load_config()
prompts = load_prompts()
