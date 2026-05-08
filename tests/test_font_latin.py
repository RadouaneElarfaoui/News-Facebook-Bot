from PIL import Image, ImageDraw, ImageFont
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
FONT_PATH = BASE_DIR / "modules" / "visual" / "assets" / "fonts" / "Cairo-Bold-New.ttf"

def test_font():
    img = Image.new("RGB", (200, 100), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(str(FONT_PATH), 40)
        draw.text((10, 10), "VAR", font=font, fill="black")
        img.save("tests/font_test.png")
        print("Test image saved to tests/font_test.png")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_font()
