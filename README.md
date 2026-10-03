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

La mise en production de la v2 le 3 août 2026 constitue une rupture de série.
Dans la normalisation 0–100 publiée par l0g, le premier snapshot v2 est passé de
`41` à `31`. Cette baisse ne décrit pas une détente macro survenue en une
journée : elle reflète le changement simultané du calculateur, du calibrage et
du catalogue. Les points antérieurs doivent rester visibles comme historique
legacy, mais aucune variation ne doit être calculée à travers cette rupture.

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

La fraîcheur est contrôlée par fréquence et, pour les publications
structurellement retardées, par série. Les plafonds spécifiques à `TOTALSL`,
`REVOLSL` (G.19 Consumer Credit) et `CSUSHPINSA` (Case-Shiller) couvrent leur
calendrier officiel sans assouplir le seuil des autres séries mensuelles.

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

### Supervision de la collecte

`deploy/macro-snapshot.timer` conserve la collecte quotidienne à 06:00, heure
du serveur. Son état persistant rattrape une exécution manquée pendant un arrêt.
Le service réutilise le builder et son compte `usdashboard` : il ne modifie ni
la méthode, ni les 47 séries exigées, ni les plafonds de fraîcheur.

Une exécution complète est limitée à 15 minutes, puis dispose de 30 secondes
pour se terminer. Un échec, y compris un dépassement de délai, entraîne une
nouvelle tentative 15 minutes plus tard. Il n'y a qu'un collecteur systemd à la
fois. Une réussite déclenche l'agrégateur l0g ; les erreurs restent consultables
avec `journalctl -u macro-snapshot.service`. `network-online.target` ne garantit
pas la disponibilité de DNS ou de FRED : la reprise après échec reste nécessaire.

L'installateur `deploy/install-snapshot-scheduler.sh <SHA complet>` est une
migration unique du cron Zen vérifié le 3 octobre 2026. L'administrateur le lance
depuis un checkout propre du SHA indiqué. Il refuse un cron modifié, des unités
déjà présentes ou une collecte active, conserve le cron et une commande de
rollback, puis active le timer et demande une collecte immédiate. Il ne touche
ni au service web, ni au réseau, ni aux clés, ni aux fichiers de données.

`SCHEDULER_INSTALLED` atteste seulement l'installation : attendre la réussite de
la collecte, puis vérifier la date du snapshot et `timelinessStatus` sur
`https://l0g.fr/api/v1/risk.json`. Le rollback refuse d'interrompre une collecte
en cours de publication. Les trois remplacements Parquet et celui du manifest
restent distincts : le lecteur existant refuse un mélange de générations.

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
.venv/bin/python scripts/verify_fred_public.py
```

La CI applique ces contrôles sur chaque pull request et push vers `main`, sans
tâche planifiée coûteuse. Les actions GitHub sont figées par SHA.

## Sécurité et confidentialité

Voir [`SECURITY.md`](SECURITY.md). L'interface ne charge automatiquement aucune
police, image, iframe, ressource ou télémétrie tierce. Les liens vers FRED et
l0g.fr ne déclenchent une connexion qu'après un clic explicite.
