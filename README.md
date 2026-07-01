# US Macro Risk Dashboard — App Streamlit

Tableau de bord macro US de type Bloomberg, exécution locale. Il agrège des
séries FRED pour suivre le stress macro américain par famille : crédit ménages,
stress bancaire, liquidité, corporate, immobilier, travail, consommation et
SLOOS.

La méthodologie détaillée est dans [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md).
Les consignes pour agents IA sont dans [`AGENTS.md`](AGENTS.md).

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

## Méthodologie courte

Chaque série est orientée dans le sens du risque, puis transformée en
composantes de stress :

- z-score glissant cinq ans ;
- drift par rapport au régime pré-COVID quand la série s'y prête ;
- momentum 3 mois annualisé et 1 an quand il est pertinent.

Le score `stress_final` ne prend plus le maximum brut entre ces composantes. Il
utilise une moyenne pondérée :

```text
stress_final = 0.50 * zscore + 0.25 * drift + 0.25 * momentum
```

Le backtest reste calibré sur les quatre récessions NBER codées dans
`catalog.py`, mais il mesure aussi les alertes hors fenêtre de récession et
pénalise les séries qui génèrent trop de faux positifs.

## Structure

```
macro_dashboard/
├── app.py             # Application Streamlit (interface)
├── catalog.py         # Catalogue des séries FRED + règles méthodologiques
├── data.py            # Téléchargement + calculs (avec cache Streamlit)
├── docs/              # Documentation méthodologique
├── AGENTS.md          # Consignes pour agents IA
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
- Les agents doivent citer FRED et la méthodologie, pas seulement le score.

## Stopper l'app

`Ctrl + C` dans le terminal où elle tourne.
