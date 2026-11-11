"""
LLM — Antigravity CLI Backend (agy)
====================================
Exécute le CLI `agy` en mode non-interactif (`-p`) avec validation
de schéma JSON (`--json-schema`), bac à sable (`--sandbox`) et permissions
verrouillées (`--settings`).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from modules.core.config_loader import BASE_DIR, config
from modules.core.logger import get_logger
from modules.llm.base import LLMAuthError, LLMError

logger = get_logger(__name__)

# Réglages de sécurité appliqués uniquement à la session (-p) sans toucher au settings.json global
LOCKED_SETTINGS = {
    "allowNonWorkspaceAccess": False,
    "toolPermission": "strict",
    "enableTerminalSandbox": True,
    "permissions": {
        "deny": [
            "command(*)",
            "mcp(*)",
        ]
    },
}

_AUTH_ERROR_KEYWORDS = (
    "not logged in",
    "unauthenticated",
    "please log in",
    "please sign in",
    "login required",
    "authentication required",
    "authentication failed",
    "invalid credentials",
    "token expired",
    "oauth",
)


class AgyBackend:
    name = "agy"

    def __init__(self, agy_cfg: dict | None = None):
        cfg = agy_cfg if agy_cfg is not None else config.get("llm", {}).get("agy", {})
        self.binary: str = cfg.get("binary", "agy") or "agy"
        self.model: str = cfg.get("model", "gemini-3.8-flash-medium")
        self.timeout: int = int(cfg.get("timeout_seconds", 180))
        self.keep_days: int = int(cfg.get("keep_conversations_days", 3))
        self.max_retries: int = int(cfg.get("max_retries", 2))

        workdir_raw = cfg.get("workdir", "data/agy-workspace")
        self.workdir = self._resolve_path(workdir_raw)
        self.workdir.mkdir(parents=True, exist_ok=True)

        home_raw = (cfg.get("home") or "").strip()
        if home_raw:
            self.custom_home: Path | None = self._resolve_path(home_raw)
            self.custom_home.mkdir(parents=True, exist_ok=True)
        else:
            self.custom_home = None

    @staticmethod
    def _resolve_path(raw: str | Path) -> Path:
        p = Path(raw)
        return p if p.is_absolute() else (BASE_DIR / p).resolve()

    def _build_env(self) -> dict[str, str]:
        env = dict(os.environ)
        if self.custom_home is not None:
            env["HOME"] = str(self.custom_home)
        return env

    def _build_command(self, prompt: str, schema: dict) -> list[str]:
        return [
            self.binary,
            "-p",
            prompt,
            "--model",
            self.model,
            "--output-format",
            "json",
            "--json-schema",
            json.dumps(schema, ensure_ascii=False),
            "--disable-slash-commands",
            "--sandbox",
            "--settings",
            json.dumps(LOCKED_SETTINGS),
            "--print-timeout",
            f"{self.timeout}s",
        ]

    @staticmethod
    def _looks_like_auth_error(text: str) -> bool:
        lower = text.lower()
        return any(kw in lower for kw in _AUTH_ERROR_KEYWORDS)

    def _parse_process_output(self, proc: subprocess.CompletedProcess) -> dict:
        stdout = (proc.stdout or "").strip()
        stderr = (proc.stderr or "").strip()
        combined = f"{stdout}\n{stderr}"

        if not stdout:
            if self._looks_like_auth_error(stderr):
                raise LLMAuthError(
                    f"Session agy non connectée ou expirée : {stderr[:200]}"
                )
            raise LLMError(
                f"agy a terminé sans sortie JSON (code={proc.returncode}) : {stderr[:200]}"
            )

        # Extrait l'objet JSON principal (dernière ligne JSON ou bloc complet)
        data = None
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            for line in reversed(stdout.splitlines()):
                line = line.strip()
                if line.startswith("{") and line.endswith("}"):
                    try:
                        data = json.loads(line)
                        break
                    except json.JSONDecodeError:
                        continue

        if not isinstance(data, dict):
            if self._looks_like_auth_error(combined):
                raise LLMAuthError(
                    f"Session agy non connectée ou expirée : {combined[:200]}"
                )
            raise LLMError(f"Sortie agy non-JSON (code={proc.returncode}) : {stdout[:200]}")

        status = data.get("status")
        if status != "SUCCESS":
            err_detail = data.get("error") or data.get("response") or stderr or str(status)
            if self._looks_like_auth_error(str(err_detail)):
                raise LLMAuthError(f"Authentification agy requise : {err_detail}")
            raise LLMError(f"Statut agy={status} : {str(err_detail)[:200]}")

        structured = data.get("structured_output")
        if not isinstance(structured, dict):
            raise LLMError("Réponse agy sans 'structured_output' valide.")

        duration = data.get("duration_seconds", 0.0)
        usage = data.get("usage") or {}
        total_tokens = usage.get("total_tokens", 0)
        logger.info(
            "✓ agy (%s) OK en %.1fs | tokens=%s",
            self.model,
            float(duration),
            total_tokens,
        )
        return structured

    def _cleanup_old_conversations(self):
        """
        Nettoie les anciennes conversations uniquement si un HOME dédié au bot est configuré.
        """
        if self.custom_home is None or self.keep_days <= 0:
            return

        cli_dir = self.custom_home / ".gemini" / "antigravity-cli"
        cutoff = time.time() - (self.keep_days * 86400)

        for subdir_name in ("conversations", "brain"):
            target_dir = cli_dir / subdir_name
            if not target_dir.exists():
                continue
            for item in target_dir.iterdir():
                try:
                    if item.stat().st_mtime < cutoff:
                        if item.is_dir():
                            shutil.rmtree(item, ignore_errors=True)
                        else:
                            item.unlink(missing_ok=True)
                except Exception as e:
                    logger.debug("Erreur nettoyage conversation %s : %s", item, e)

    def generate_json(self, prompt: str, schema: dict) -> dict:
        """
        Exécute un appel agy non-interactif et retourne le dictionnaire `structured_output`.
        """
        cmd = self._build_command(prompt, schema)
        env = self._build_env()
        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                proc = subprocess.run(
                    cmd,
                    cwd=str(self.workdir),
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout + 30,
                )
                result = self._parse_process_output(proc)
                self._cleanup_old_conversations()
                return result

            except LLMAuthError:
                # Pas de retry sur une erreur d'authentification
                raise
            except FileNotFoundError as e:
                raise LLMError(
                    f"Binaire agy introuvable ('{self.binary}'). Vérifiez qu'il est installé et dans le PATH."
                ) from e
            except subprocess.TimeoutExpired as e:
                last_error = LLMError(
                    f"Timeout agy après {self.timeout + 30}s (tentative {attempt}/{self.max_retries})."
                )
                logger.warning("⚠️ %s", last_error)
            except LLMError as e:
                last_error = e
                logger.warning(
                    "⚠️ Échec agy (tentative %d/%d) : %s",
                    attempt,
                    self.max_retries,
                    e,
                )
            except Exception as e:
                last_error = LLMError(f"Erreur inattendue agy : {e}")
                logger.warning(
                    "⚠️ Erreur inattendue agy (tentative %d/%d) : %s",
                    attempt,
                    self.max_retries,
                    e,
                )

            if attempt < self.max_retries:
                time.sleep(5 * attempt)

        assert last_error is not None
        raise last_error

    def run_interactive_login(self) -> int:
        """
        Lance `agy` en mode interactif avec l'environnement du bot pour permettre
        la connexion Google (lien navigateur -> coller le token).
        """
        env = self._build_env()
        home_display = str(self.custom_home) if self.custom_home else os.environ.get("HOME", "~")
        logger.info("🔐 Lancement de agy pour connexion interactive (HOME=%s)...", home_display)
        try:
            proc = subprocess.run([self.binary], cwd=str(self.workdir), env=env)
            return proc.returncode
        except FileNotFoundError:
            logger.error("❌ Binaire '%s' introuvable.", self.binary)
            return 1

    def check_health(self) -> tuple[bool, str]:
        """
        Vérifie rapidement que `agy` répond et que l'authentification est valide.
        """
        schema = {
            "type": "object",
            "properties": {"ok": {"type": "boolean"}, "message": {"type": "string"}},
            "required": ["ok", "message"],
        }
        start = time.time()
        try:
            res = self.generate_json(
                "Reply with ok=true and message='agy ready'.",
                schema=schema,
            )
            elapsed = time.time() - start
            return True, f"OK ({self.model}) en {elapsed:.1f}s -> {res}"
        except Exception as e:
            return False, str(e)
