# US Macro Risk Monitor

Moteur et interface de [us.l0g.fr](https://us.l0g.fr), fondés sur 47 séries
[FRED](https://fred.stlouisfed.org/) réparties en huit familles macro US.

Le score est un z-score signé et agrégé. Ce n'est ni une probabilité de
récession, ni une prévision datée, ni un conseil d'investissement. La méthode
complète est documentée dans [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md) et sur
[l0g.fr/methodologie/us-macro](https://l0g.fr/methodologie/us-macro/).

## Deux processus, un moteur

- `app.py` : développement local, collecte FRED directe.
- `snapshot_builder.py` : collecte et publie un bundle complet et versionné.
- `app_server.py` : production snapshots-only, sans clé FRED ni accès réseau.
- `scoring.py` : moteur pur commun aux deux chemins.
- `dashboard_view.py` et `ui.py` : vue et charte communes.
- `snapshot_contract.py` : validation fail-closed du bundle de production.

Cette séparation évite qu'une correction soit présente dans l'interface locale
mais absente du calculateur réellement servi.

## Installation locale

Python 3.11 à 3.14 est requis.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --requirement requirements-dev.txt
export FRED_API_KEY="votre_cle"
.venv/bin/streamlit run app.py
```

L'application écoute par défaut sur `http://localhost:8501`. Les dépendances
directes sont épinglées et les transitives contraintes dans `constraints.txt` ;
leur mise à jour doit être accompagnée des tests et de `pip-audit`.

## Calcul v2.0.0

- z-score signé sur cinq ans ;
- vrai glissement annuel calendaire avant z-score pour les séries non
  stationnaires ;
- drift face à 2015–2019 et momentum seulement lorsqu'ils ont un sens ;
- saturation fixe et symétrique des composantes à `±5` équivalents-z ;
- moyenne des composantes disponibles, pondérée `50 % / 25 % / 25 %` ;
- backtest du même score composite à 3, 6 et 12 mois avant quatre récessions
  NBER ;
- pénalité de faux positifs hors récession ;
- moyenne pondérée par série pour les scores famille et global.

L'historique est une reconstruction rétrospective avec les poids et les vintages
FRED actuels. Les observations datées après chaque point sont exclues, mais les
délais de publication et les révisions historiques ne sont pas rejoués comme
dans une base point-in-time ALFRED. Cette limite est affichée dans l'interface.

## Génération d'un snapshot

Le builder exige un SHA Git complet. Le secret FRED appartient à ce processus,
jamais au service public.

```bash
export FRED_API_KEY="votre_cle"
export MACRO_DASHBOARD_SOURCE_SHA="$(git rev-parse HEAD)"
.venv/bin/python snapshot_builder.py --output-dir ./snapshots --env-file /chemin/vers/env
```

Un bundle n'est publié que si les 47 séries, le backtest, l'historique et leurs
métadonnées passent le contrat. Les fichiers sont promus avant le manifest, ce
qui rend une lecture concurrente vérifiable et fail-closed.

## Production `us.l0g.fr`

Le service public lance :

```text
/opt/macro_dashboard/venv/bin/streamlit run /opt/macro_dashboard/app_server.py
```

Procédure de release recommandée :

1. sauvegarder l'état actif et noter son SHA ;
2. préparer un checkout neuf du SHA exact à publier ;
3. installer les dépendances épinglées et exécuter toute la validation ;
4. générer un bundle dans un répertoire temporaire avec ce même SHA ;
5. relire le bundle avec `load_snapshot_bundle` avant toute activation ;
6. activer code et données de manière atomique avec rollback préparé ;
7. vérifier séparément le service local, HTTPS, les en-têtes, le SHA affiché,
   la couverture et les surfaces desktop/mobile.

Ce dépôt ne suppose pas qu'un build réussi prouve le déploiement. Le SHA exposé
par le dashboard doit correspondre au checkout actif et au calculateur du
snapshot.

## Validation complète

```bash
PYTHONPYCACHEPREFIX=/tmp/macro_pycache .venv/bin/python -m py_compile catalog.py scoring.py data.py snapshot_contract.py snapshot_builder.py ui.py dashboard_view.py app.py app_server.py
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/ruff check .
.venv/bin/bandit -c pyproject.toml -r .
.venv/bin/pip-audit --local
```

Un contrôle ponctuel de toutes les séries via l'export public officiel FRED,
sans clé API, est aussi disponible :

```bash
.venv/bin/python -m scripts.verify_fred_public
```

La CI applique ces contrôles sur chaque pull request et push vers `main`, sans
tâche planifiée coûteuse. Les actions GitHub sont figées par SHA.

## Sécurité et confidentialité

Voir [`SECURITY.md`](SECURITY.md). L'interface ne charge automatiquement aucune
police, image, iframe, ressource ou télémétrie tierce. Les liens vers FRED et
l0g.fr ne déclenchent une connexion qu'après un clic explicite.
