# US Macro Risk Dashboard — App Streamlit

Tableau de bord macro US de type Bloomberg, exécution locale.

## Installation (une seule fois)

Ouvre un terminal dans ce dossier et tape :

```bash
pip install -r requirements.txt
```

## Configuration de la clé FRED

L'app a besoin de ta clé API FRED. Tu as deux options :

**Option A — Variable d'environnement (recommandé)** :

```bash
export FRED_API_KEY="ta_cle_ici"
```

(à mettre dans ton `.bashrc` ou `.zshrc` pour ne pas avoir à le refaire à chaque fois)

**Option B — Au démarrage** :

```bash
FRED_API_KEY="ta_cle_ici" streamlit run app.py
```

## Lancement

```bash
streamlit run app.py
```

L'app s'ouvre automatiquement dans ton navigateur sur `http://localhost:8501`.

## Comment ça marche

- **Premier lancement** : téléchargement des séries FRED depuis 1985 (~1 minute), puis backtest historique (~30 secondes), puis reconstruction du score mensuel depuis 1990 (~2 minutes). Total ~3-4 minutes pour le tout premier lancement.
- **Lancements suivants dans les 6 heures** : tout est en cache, ouverture instantanée.
- **Bouton "🔄 Refresh data"** en haut à droite pour forcer le rechargement (utile en cas de nouveau snapshot FRED).
- **Cache automatique** : 6h pour les données live, 24h pour les calculs lourds (backtest, reconstruction).

## Structure

```
macro_dashboard/
├── app.py             # Application Streamlit (interface)
├── catalog.py         # Catalogue des séries FRED + règles méthodologiques
├── data.py            # Téléchargement + calculs (avec cache Streamlit)
├── requirements.txt   # Dépendances Python
└── README.md          # Ce fichier
```

Pour modifier les séries surveillées : édite `catalog.py`.
Pour modifier la méthodologie de scoring : édite `data.py`.
Pour modifier l'interface : édite `app.py`.

## Sécurité

- L'app tourne uniquement en local (`localhost:8501`).
- La clé FRED n'est jamais exposée — elle vient de l'environnement, pas du code.
- Aucune donnée n'est envoyée à un tiers (sauf FRED bien sûr).

## Stopper l'app

`Ctrl + C` dans le terminal où elle tourne.
