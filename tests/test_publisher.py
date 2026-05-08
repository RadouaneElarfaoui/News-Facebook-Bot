"""
Test Publisher
==============
Vérifie la connexion à Facebook et la publication d'une image de test.
"""
import sys
from pathlib import Path

# Ajoute la racine au sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from modules.publisher.fb_api import publish_photo, publish_comment
from modules.core.config_loader import config

def test_fb_publish():
    print("=== Test de Publication Facebook ===")
    
    # On crée une petite image de test si elle n'existe pas
    test_img = Path("output/test_publish.jpg")
    test_img.parent.mkdir(exist_ok=True)
    
    if not test_img.exists():
        from PIL import Image
        img = Image.new("RGB", (800, 600), color=(73, 109, 137))
        img.save(test_img)
    
    caption = "Test automatique du module Publisher 🤖 #ScreenMix #Test"
    
    # On force temporairement le mode draft si on veut juste tester la logique
    # config["publisher"]["is_draft"] = True 
    
    post_id = publish_photo(test_img, caption)
    
    if post_id:
        print(f"✅ Succès ! Post ID : {post_id}")
        # Test du commentaire
        comment_text = "🔹 Ceci est un commentaire détaillé automatique.\n🔹 Ligne 2 du résumé.\n🔹 Ligne 3 du résumé."
        comment_id = publish_comment(post_id, comment_text)
        if comment_id:
            print(f"✅ Commentaire réussi ! ID : {comment_id}")
        else:
            print("❌ Échec du commentaire.")
    else:
        print("❌ Échec de la publication.")


if __name__ == "__main__":
    test_fb_publish()
