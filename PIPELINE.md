# 🔄 Pipeline de Fonctionnement — Screen Drop Bot

Architecture technique et flux d'exécution du bot Facebook.

---

## 1. Flowchart d'un Run

```mermaid
flowchart TD
    START["main.py --once ou --schedule"] --> DB["init_db() (SQLite WAL)"]
    DB --> CLEAN["Nettoyage des images > 14j"]
    CLEAN --> GNEWS["GNews API (lang=ar, < 24h)"]
    
    GNEWS --> CHECK{"Articles trouvés ?"}
    CHECK -- "Non" --> ALERT_CHECK["Incrémente échecs consécutifs"]
    CHECK -- "Oui" --> DEDUP{"article_exists(url) ?"}
    
    DEDUP -- "Oui" --> NEXT["Article suivant"]
    DEDUP -- "Non" --> AGY_PKG["ContentEngine.generate_package()<br/>Appel unique agy -p (Google AI Pro)"]
    
    AGY_PKG --> IMG_SEARCH["Recherche d'images (Pexels / Unsplash)"]
    IMG_SEARCH --> AGY_IMG["Sélection photo via agy"]
    AGY_IMG --> COMP["compose_image()<br/>Pillow RTL + libraqm + Watermark"]
    
    COMP --> POST{"is_draft: false ?"}
    POST -- "Oui" --> FB_IMG["publish_photo() sur Facebook"]
    FB_IMG --> FB_COM["publish_comment() : 1er commentaire narratif"]
    FB_COM --> SAVE["save_article() & mark_article_posted()"]
    
    POST -- "Non (draft)" --> DRAFT_LOG["Log de simulation sans écriture BDD"]
    
    SAVE --> HEARTBEAT["Écriture heartbeat (data/bot.alive)"]
    DRAFT_LOG --> HEARTBEAT
```

---

## 2. Diagramme de Séquence

```mermaid
sequenceDiagram
    autonumber
    participant Main as main.py
    participant DB as SQLite (database.py)
    participant GNews as GNews API (aggregator.py)
    participant Agy as Antigravity CLI (agy_backend.py)
    participant Img as Pexels / Unsplash (image_fetcher.py)
    participant Comp as Pillow RTL (compositor.py)
    participant FB as Facebook API (fb_api.py)

    Main->>DB: init_db()
    Main->>GNews: fetch_trending_news()
    GNews-->>Main: Liste des articles

    loop Pour chaque nouvel article (jusqu'à posts_per_run)
        Main->>DB: article_exists(url)
        DB-->>Main: False

        Main->>Agy: generate_package(source_text)
        Note over Agy: 1 seul appel structuré JSON :<br/>title, keywords, image_query, caption, detail_comment
        Agy-->>Main: Package éditorial complet

        Main->>Img: get_image(image_query, source_text)
        Img->>Agy: Sélection de la meilleure photo parmi les candidats
        Agy-->>Img: Index sélectionné
        Img-->>Main: Image de fond (PIL)

        Main->>Comp: compose_image(bg, title, keywords)
        Comp-->>Main: Fichier output/post_timestamp.jpg

        alt is_draft: false (Production)
            Main->>FB: publish_photo(image, caption)
            FB-->>Main: fb_post_id
            Main->>FB: publish_comment(fb_post_id, detail_comment)
            Main->>DB: save_article() & mark_article_posted()
        else is_draft: true (Test)
            Main->>Main: Simulation réussie (aucun post FB, pas de BDD)
        end
    end

    Main->>DB: save_metadata("last_run", now)
    Main->>Main: Écriture data/bot.alive
```

---

## 3. Détail des étapes

### Étape 1 : Collecte GNews (`modules/radar/aggregator.py`)
- Requête sur `top-headlines` (arabe, catégorie `general`).
- Filtre strict : rejet automatique des articles datant de plus de 24h.

### Étape 2 : Déduplication (`modules/core/database.py`)
- Vérification de l'URL dans la table `articles`.
- En production, l'article n'est enregistré qu'après succès de la publication Facebook.

### Étape 3 : Rédaction unifiée `agy` (`modules/content/engine.py`)
- Exécute `agy -p` avec `--json-schema` et `--sandbox` (modèle `gemini-3.8-flash-medium`).
- Produit en un seul appel :
  - `title` : Titre court en arabe (≤ 10 mots).
  - `keywords` : 2 à 3 mots-clés du titre pour surlignage doré.
  - `image_query` : 1 ou 2 mots en anglais pour la banque d'images.
  - `caption` : Légende Facebook avec appel au premier commentaire.
  - `detail_comment` : Résumé narratif sans balises markdown.

### Étape 4 : Image & Composition (`modules/visual/`)
- Récupération des candidats sur Pexels (ou Unsplash).
- `agy` choisit l'image la plus pertinente selon le texte de l'article.
- Composition 1200×630 : crop centré, gradient sombre, texte arabe RTL avec `libraqm` (`Cairo-Bold`), ombre portée, surlignage mot-à-mot en `#FFD700` et watermark `logo.png`.

### Étape 5 : Publication Facebook (`modules/publisher/fb_api.py`)
- `POST /{page_id}/photos` : Publication de l'image avec légende.
- `POST /{post_id}/comments` : Publication immédiate du résumé en premier commentaire.

---

## 4. Schéma de la Base de Données

```mermaid
erDiagram
    ARTICLES ||--o{ POSTS : "est publié dans"

    ARTICLES {
        INTEGER id PK
        TEXT url UK "URL unique (anti-doublon)"
        TEXT title_ar "Titre généré"
        TEXT category "Catégorie"
        TEXT image_url "Image source"
        INTEGER processed "Statut traitement"
        INTEGER posted "Statut publication"
        TEXT created_at "Horodatage"
    }

    POSTS {
        INTEGER id PK
        INTEGER article_id FK
        TEXT fb_post_id "ID Facebook"
        TEXT image_path "Chemin JPEG"
        TEXT caption "Légende"
        TEXT posted_at "Date UTC"
        TEXT status "published / draft"
    }

    METADATA {
        TEXT key PK "last_run, last_publish, consecutive_failures"
        TEXT value "Valeur"
    }
```

---

## 5. Résilience & Monitoring

- **Isolation `agy`** : Exécution en bac à sable strict avec permissions verrouillées (`deny: ["command(*)", "mcp(*)"]`).
- **Détection d'expiration** : Alerte immédiate dans `data/bot.alert` si la session `agy` nécessite une reconnexion (`python main.py --agy-login`).
- **Alerte d'inactivité** : Alerte si aucune publication réussie n'a eu lieu depuis plus de 24h (`alert_no_publish_hours`).
- **Heartbeat** : Fichier `data/bot.alive` mis à jour à chaque cycle pour les sondes Docker / monitoring.
- **Rattrapage** : Le scheduler exécute jusqu'à 3 runs manqués en cas de redémarrage après coupure.
