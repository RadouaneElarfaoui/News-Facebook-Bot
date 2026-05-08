"""
Script de test visuel — Test Compositor
=========================================
Lance une composition complète avec une image de test
et affiche le résultat. Idéal pour valider le rendu
avant de brancher les vraies APIs.

Usage:
    python tests/test_compositor.py
"""
import sys
from pathlib import Path

# Ajoute le répertoire racine au path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw
import numpy as np

from modules.visual.compositor import compose_image
from modules.core.logger import get_logger

logger = get_logger("test_compositor")


def make_test_background() -> Image.Image:
    """Génère une image de fond de test (dégradé coloré)."""
    w, h = 1400, 800
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    for y in range(h):
        t = y / h
        # Bleu roi → violet profond
        arr[y, :, 0] = int(20 + 60 * t)
        arr[y, :, 1] = int(30 + 40 * t)
        arr[y, :, 2] = int(120 - 30 * t)

    img = Image.fromarray(arr, "RGB")
    draw = ImageDraw.Draw(img)

    # Quelques formes pour simuler une photo
    draw.ellipse([200, 100, 600, 500], fill=(40, 60, 150))
    draw.ellipse([800, 50, 1300, 600], fill=(30, 80, 130))
    return img


def run_test():
    logger.info("=== Démarrage du test compositor ===")

    # Données de test
    test_title = "حادث مفاجئ لحكم الـ VAR يهدد مباراة الزمالك وسموحة!"
    test_keywords = ["لقب", "دوري الأبطال", "الخامسة عشرة"]

    bg = make_test_background()

    output_path = compose_image(
        background=bg,
        title=test_title,
        keywords=test_keywords,
        output_filename="test_output.jpg",
    )

    logger.info("✅ Image générée avec succès : %s", output_path)
    logger.info("📂 Ouvre ce fichier pour vérifier le rendu :")
    logger.info("   %s", output_path)

    # Essaie d'ouvrir automatiquement avec le viewer par défaut
    import subprocess
    try:
        subprocess.Popen(["xdg-open", str(output_path)])
    except Exception:
        pass

    return output_path


if __name__ == "__main__":
    run_test()
