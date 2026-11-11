import sys
from pathlib import Path
import httpx

# Ajoute la racine au sys.path pour les imports locaux
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from modules.core.config_loader import config
from modules.llm import get_backend

def test_agy():
    print("\n--- Test Antigravity CLI (agy) ---")
    ok, info = get_backend().check_health()
    if ok:
        print(f"✅ agy fonctionne ! {info}")
    else:
        print(f"❌ agy échec : {info}")

def test_gnews():
    print("\n--- Test GNews ---")
    api_key = config["apis"]["gnews"]["api_key"]
    if not api_key or "YOUR" in api_key:
        print("❌ GNews API Key non configurée.")
        return
    
    url = f"https://gnews.io/api/v4/top-headlines?token={api_key}&lang=en&max=1"
    try:
        resp = httpx.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if "articles" in data:
            print(f"✅ GNews fonctionne ! Trouvé {len(data['articles'])} articles.")
        else:
            print(f"❌ GNews a retourné des données inattendues : {data}")
    except Exception as e:
        print(f"❌ GNews échec : {e}")

def test_pexels():
    print("\n--- Test Pexels ---")
    api_key = config["apis"]["pexels"]["api_key"]
    if not api_key or "YOUR" in api_key:
        print("❌ Pexels API Key non configurée.")
        return
    
    url = "https://api.pexels.com/v1/search"
    headers = {"Authorization": api_key}
    params = {"query": "news", "per_page": 1}
    try:
        resp = httpx.get(url, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if "photos" in data and len(data["photos"]) > 0:
            print(f"✅ Pexels fonctionne ! Trouvé {len(data['photos'])} photos.")
        else:
            print(f"❌ Pexels n'a trouvé aucune photo.")
    except Exception as e:
        print(f"❌ Pexels échec : {e}")

def test_unsplash():
    print("\n--- Test Unsplash ---")
    api_key = config["apis"]["unsplash"]["access_key"]
    if not api_key or "YOUR" in api_key:
        print("❌ Unsplash API Key non configurée.")
        return
    
    url = "https://api.unsplash.com/photos/random"
    params = {"query": "news", "client_id": api_key}
    try:
        resp = httpx.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if "urls" in data:
            print(f"✅ Unsplash fonctionne ! URL photo : {data['urls']['regular'][:50]}...")
        else:
            print(f"❌ Unsplash a retourné des données inattendues.")
    except Exception as e:
        print(f"❌ Unsplash échec : {e}")

def test_facebook():
    print("\n--- Test Facebook ---")
    token = config["apis"]["facebook"]["access_token"]
    page_id = config["apis"]["facebook"]["page_id"]
    if not token or "YOUR" in token:
        print("❌ Facebook Access Token non configuré.")
        return
    
    url = f"https://graph.facebook.com/v19.0/{page_id}?access_token={token}"
    try:
        resp = httpx.get(url, timeout=10)
        if resp.status_code == 200:
            print(f"✅ Facebook fonctionne ! Données page : {resp.json()}")
        else:
            print(f"❌ Facebook échec : {resp.status_code} - {resp.text}")
    except Exception as e:
        print(f"❌ Facebook erreur : {e}")

if __name__ == "__main__":
    test_agy()
    test_gnews()
    test_pexels()
    test_unsplash()
    test_facebook()
