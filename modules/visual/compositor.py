"""
Visual Factory — Compositor
=============================
Génère des images professionnelles pour les réseaux sociaux :
  ✓ Image de fond réaliste
  ✓ Overlay gradient noir (bas → haut)
  ✓ Texte arabe RTL avec mots surlignés en jaune
  ✓ Watermark logo en position fixe

Dépendances : Pillow, arabic-reshaper, python-bidi
"""
from __future__ import annotations

import random
from pathlib import Path
from typing import Sequence

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# Support texte arabe natif (Pillow + libraqm)
from PIL import features
RAQM_SUPPORT = features.check("raqm")

from modules.core.config_loader import config
from modules.core.logger import get_logger

logger = get_logger(__name__)

# ── Chemins ────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent.parent
ASSETS_DIR = Path(__file__).resolve().parent / "assets"
OUTPUT_DIR = BASE_DIR / config["visual"]["output_dir"]
OUTPUT_DIR.mkdir(exist_ok=True)

# ── Constantes visuelles (depuis config) ───────────────────
CFG_V = config["visual"]
IMG_W = CFG_V["image_width"]
IMG_H = CFG_V["image_height"]
QUALITY = CFG_V["quality"]

OVERLAY_COLOR = tuple(CFG_V["overlay"]["color"])
OVERLAY_MAX_ALPHA = CFG_V["overlay"]["max_alpha"]
OVERLAY_POWER = CFG_V["overlay"]["gradient_power"]

TEXT_WHITE = tuple(CFG_V["text"]["default_color"])
TEXT_YELLOW = tuple(CFG_V["text"]["highlight_color"])
FONT_PATH = BASE_DIR / CFG_V["text"]["font_path"]
FONT_SIZE = CFG_V["text"]["font_size_base"]
PAD_BOTTOM = CFG_V["text"]["padding_bottom"]
PAD_SIDES = CFG_V["text"]["padding_sides"]
LINE_SPACING = CFG_V["text"]["line_spacing"]

WM_PATH = BASE_DIR / CFG_V["watermark"]["path"]
WM_POSITION = CFG_V["watermark"]["position"]
WM_SCALE = CFG_V["watermark"]["scale"]
WM_MARGIN = CFG_V["watermark"]["margin"]
WM_OPACITY = CFG_V["watermark"]["opacity"]


# ═══════════════════════════════════════════════════════════
# 1. Gradient Overlay
# ═══════════════════════════════════════════════════════════

def _make_gradient_overlay(width: int, height: int) -> Image.Image:
    """
    Crée un overlay RGBA avec un gradient noir bas→haut.
    """
    arr = np.zeros((height, width, 4), dtype=np.uint8)
    for y in range(height):
        t = (y / height) ** OVERLAY_POWER
        alpha = int(OVERLAY_MAX_ALPHA * t)
        arr[y, :, :3] = OVERLAY_COLOR
        arr[y, :, 3] = alpha
    return Image.fromarray(arr, "RGBA")


# ═══════════════════════════════════════════════════════════
# 2. Texte Arabe Natif + Mots Surlignés
# ═══════════════════════════════════════════════════════════

def _get_font(size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(str(FONT_PATH), size)
    except (IOError, OSError):
        logger.warning("Police %s introuvable, utilisation de la police par défaut.", FONT_PATH)
        return ImageFont.load_default()


def _wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """
    Découpe le texte en lignes en utilisant la largeur réelle (RTL).
    """
    words = text.split()
    lines: list[str] = []
    current_line = ""

    for word in words:
        test_line = (current_line + " " + word).strip()
        # On utilise direction='rtl' pour obtenir la vraie largeur
        w = font.getlength(test_line, direction="rtl")
        if w <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word

    if current_line:
        lines.append(current_line)

    return lines


def _render_text_with_highlights(
    draw: ImageDraw.ImageDraw,
    title: str,
    keywords: Sequence[str],
    font: ImageFont.FreeTypeFont,
    start_y: int,
    canvas_width: int,
    max_text_width: int
):
    """
    Rendu natif avec support RTL et surlignage.
    """
    lines = _wrap_text(title, font, max_text_width)
    line_height = font.size + LINE_SPACING
    
    clean_keywords = [k.strip(".,!؟،:").lower() for k in keywords]

    for i, line in enumerate(lines):
        y = start_y + i * line_height
        
        # Calcul de la largeur totale de la ligne pour le centrage
        line_w = font.getlength(line, direction="rtl")
        # Point de départ X (droite de la ligne centrée)
        x_right = (canvas_width + line_w) // 2

        # 1. Ombre portée (RTL)
        for offset in [(2,2), (1,1), (-1,1), (1,-1)]:
            draw.text((x_right + offset[0], y + offset[1]), line, font=font, 
                      fill=(0, 0, 0, 200), direction="rtl", anchor="ra")

        # 2. Rendu par mots pour le surlignage
        # Note: On dessine de droite à gauche
        words = line.split()
        cursor_x = x_right
        
        for word in words:
            # On nettoie le mot pour comparer aux mots-clés
            clean_word = word.strip(".,!؟،:").lower()
            # On surligne si le mot est un mot-clé ou fait partie d'un groupe de mots-clés
            is_highlight = any(clean_word in kw for kw in clean_keywords)
            
            color = TEXT_YELLOW if is_highlight else TEXT_WHITE
            
            # Dessine le mot
            draw.text((cursor_x, y), word, font=font, fill=color, 
                      direction="rtl", anchor="ra")
            
            # Avance le curseur (mot + espace)
            word_w = font.getlength(word + " ", direction="rtl")
            cursor_x -= word_w


# ═══════════════════════════════════════════════════════════
# 3. Watermark Logo
# ═══════════════════════════════════════════════════════════

def _apply_watermark(base: Image.Image) -> Image.Image:
    """
    Superpose le logo avec transparence intelligente.
    Gère le cas où le logo a un fond noir au lieu d'être transparent.
    """
    if not WM_PATH.exists():
        logger.warning("Logo watermark introuvable : %s", WM_PATH)
        return base

    logo = Image.open(WM_PATH).convert("RGBA")

    # --- FIX: Gère le fond noir UNIQUEMENT si l'image n'est pas déjà transparente ---
    # On vérifie si l'image a de la vraie transparence (alpha < 255)
    extrema = logo.getextrema()
    # extrema[3] correspond au canal Alpha (min, max)
    has_transparency = (extrema[3][0] < 255)

    if not has_transparency:
        logger.info("Logo sans transparence détecté, application du masque de luminance (fond noir).")
        grayscale = logo.convert("L")
        logo.putalpha(grayscale)
    else:
        logger.info("Logo avec transparence native détecté.")


    # Redimensionne proportionnellement
    target_w = int(IMG_W * WM_SCALE)
    ratio = target_w / logo.width
    target_h = int(logo.height * ratio)
    logo = logo.resize((target_w, target_h), Image.LANCZOS)

    # Applique l'opacité configurée (max 255)
    opacity_factor = min(255, WM_OPACITY)
    r, g, b, a = logo.split()
    a = a.point(lambda p: int(p * opacity_factor / 255))
    logo.putalpha(a)


    # Calcule la position
    margin = WM_MARGIN
    positions = {
        "bottom-right": (IMG_W - target_w - margin, IMG_H - target_h - margin),
        "bottom-left":  (margin, IMG_H - target_h - margin),
        "top-right":    (IMG_W - target_w - margin, margin),
        "top-left":     (margin, margin),
    }
    pos = positions.get(WM_POSITION, positions["bottom-right"])

    # Légère variation aléatoire
    pos = (pos[0] + random.randint(-5, 5), pos[1] + random.randint(-3, 3))

    result = base.copy()
    result.paste(logo, pos, mask=logo)
    return result


# ═══════════════════════════════════════════════════════════
# 4. Fonction Principale
# ═══════════════════════════════════════════════════════════

def compose_image(
    background: Image.Image,
    title: str,
    keywords: Sequence[str] = (),
    output_filename: str = "output.jpg",
) -> Path:
    """
    Génère l'image finale "Screen Mix" et la sauvegarde.

    Args:
        background:      Image PIL de fond (sera redimensionnée à IMG_W×IMG_H).
        title:           Titre du news (arabe ou latin).
        keywords:        Mots à surligner en jaune.
        output_filename: Nom du fichier de sortie (dans OUTPUT_DIR).

    Returns:
        Path vers l'image générée.
    """
    logger.info("Composition de l'image : '%s'", title[:50])

    # ── 1. Redimensionne le fond (crop centré) ──────────────
    bg = background.convert("RGBA")
    bg_ratio = bg.width / bg.height
    target_ratio = IMG_W / IMG_H

    if bg_ratio > target_ratio:
        new_h = IMG_H
        new_w = int(new_h * bg_ratio)
    else:
        new_w = IMG_W
        new_h = int(new_w / bg_ratio)

    bg = bg.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - IMG_W) // 2
    top = (new_h - IMG_H) // 2
    bg = bg.crop((left, top, left + IMG_W, top + IMG_H))

    # ── 2. Léger blur de fond pour focus sur le texte ───────
    bg_blurred = bg.filter(ImageFilter.GaussianBlur(radius=0.8))

    # ── 3. Overlay gradient ─────────────────────────────────
    overlay = _make_gradient_overlay(IMG_W, IMG_H)
    canvas = Image.alpha_composite(bg_blurred, overlay)

    # ── 4. Prépare les paramètres de texte ─────────────
    # Adapte la taille de police à la longueur du titre
    font_size = FONT_SIZE
    if len(title) > 60:
        font_size = max(40, FONT_SIZE - 12)
    elif len(title) > 40:
        font_size = max(46, FONT_SIZE - 6)

    font = _get_font(font_size)
    max_text_width = IMG_W - (PAD_SIDES * 2)

    # Calcule la hauteur totale pour le positionnement Y
    logical_lines = _wrap_text(title, font, max_text_width)
    line_height = font_size + LINE_SPACING
    total_text_height = len(logical_lines) * line_height
    text_start_y = IMG_H - PAD_BOTTOM - total_text_height

    # ── 5. Dessine le texte ─────────────────────────────────
    draw = ImageDraw.Draw(canvas)
    _render_text_with_highlights(
        draw=draw, 
        title=title, 
        keywords=keywords, 
        font=font, 
        start_y=text_start_y, 
        canvas_width=IMG_W,
        max_text_width=max_text_width
    )

    # ── 6. Watermark ────────────────────────────────────────
    canvas = _apply_watermark(canvas)

    # ── 7. Sauvegarde ───────────────────────────────────────
    output_path = OUTPUT_DIR / output_filename
    canvas_rgb = canvas.convert("RGB")
    canvas_rgb.save(str(output_path), "JPEG", quality=QUALITY, optimize=True)

    logger.info("Image sauvegardée : %s", output_path)
    return output_path
