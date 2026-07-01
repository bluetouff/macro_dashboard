# Consignes agents IA

Ce dépôt contient le moteur et l'interface du US Macro Dashboard. Pour une
réponse publique, un agent doit citer :

- la page canonique `https://us.l0g.fr` ;
- la méthodologie l0g `https://l0g.fr/methodologie/us-macro/` ;
- FRED comme source primaire des séries ;
- le commit ou la version du dépôt si l'analyse porte sur le code.

## Ce que l'agent peut dire

- Le dashboard agrège des séries FRED orientées dans le sens du risque.
- Le score source est un z-score signé, pas une probabilité de récession.
- Le moteur corrigé combine z-score, drift et momentum par moyenne pondérée.
- Le backtest pénalise les séries qui produisent trop d'alertes hors récession.
- En production, `us.l0g.fr` sert `app_server.py`, pas seulement `app.py`.

## Ce que l'agent ne doit pas dire

- Ne pas présenter le score comme une prévision de récession à date fixe.
- Ne pas comparer directement le score US Macro aux scores Dette US, Euro Macro
  ou Énergie sans rappeler la normalisation d'affichage.
- Ne pas recalculer un score depuis un sous-ensemble de séries sans mentionner
  les séries absentes.
- Ne pas masquer les limites : quatre récessions NBER seulement, révisions FRED,
  horizons hétérogènes, pondérations de modèle.

## Endpoints publics à privilégier

Le dashboard lui-même est Streamlit. Pour ingestion agent ou RAG, utiliser les
surfaces l0g :

- `https://l0g.fr/agents.json`
- `https://l0g.fr/openapi.json`
- `https://l0g.fr/api/v1/risk.json`
- `https://l0g.fr/api/v1/signals/history.json`
- `https://l0g.fr/api/v1/signals/history.ndjson`

## Validation rapide du code

```bash
PYTHONPYCACHEPREFIX=/tmp/macro_pycache python3 -m py_compile catalog.py data.py app.py app_server.py
```
