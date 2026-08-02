# Méthodologie US Macro Risk Monitor

Version méthodologique : `2.0.0`

Le dashboard décrit un stress macroéconomique relatif aux États-Unis à partir
de 47 séries FRED réparties en huit familles. Il ne prévoit pas une récession à
date fixe, ne calcule aucune probabilité de récession et ne constitue pas un
signal d'investissement.

La source primaire est [FRED, Federal Reserve Bank of St. Louis](https://fred.stlouisfed.org/).
Le catalogue versionné se trouve dans `catalog.py`.

La v2 remplace le code `H41RESPPALDKNWW`, qui désigne en réalité le
[Bank Term Funding Program désormais discontinué](https://fred.stlouisfed.org/series/H41RESPPALDKNWW),
par la série active de crédit primaire au discount window
[`WLCFLPCL`](https://fred.stlouisfed.org/series/WLCFLPCL). Elle corrige aussi
`BUSLOANS` en fréquence mensuelle et les unités de `ICSA` et `CCSA` en nombres
bruts, conformément aux métadonnées FRED.

## 1. Préparation et sens du risque

Pour chaque série, `direction` définit le signe qui transforme la donnée afin
qu'une valeur positive indique toujours davantage de stress :

```text
sign = +1 si une hausse représente du stress
sign = -1 si une baisse représente du stress
```

À une date d'évaluation donnée, les observations dont la date de période est
postérieure sont exclues. Une variation à trois mois ou un an prend la dernière
observation datée au plus tard à la cible calendaire. Elle ne compte jamais un
nombre fixe de lignes, car les fréquences FRED sont hétérogènes.

Ce corpus FRED contient les versions révisées courantes, pas le vintage qui
était réellement publié à chaque date passée. La troncature empêche d'utiliser
une observation portant une date future, mais ne reconstitue ni les délais de
publication ni les révisions comme le ferait une base point-in-time ALFRED.

## 2. Composantes du score de série

### Z-score glissant

- Série stationnaire : z-score du niveau sur les cinq années disponibles.
- Série marquée `NON_STATIONARY` : vrai glissement annuel calendaire, puis
  z-score de ce taux de variation sur cinq ans.
- L'écart-type utilisé est l'écart-type d'échantillon de pandas (`ddof=1`).
- Le résultat est multiplié par le sens du risque.

### Drift pré-COVID

Lorsqu'il est économiquement pertinent, le niveau courant est comparé à la
moyenne 2015–2019 :

```text
drift_pct = sign × (courant - moyenne_2015_2019) / abs(moyenne_2015_2019) × 100
drift_equivalent = drift_pct / (25 / 1.5)
```

Le drift n'est calculé qu'après observation complète de la référence au
31 décembre 2019. Il est désactivé pour les séries de régime, les niveaux
nominaux et les variables centrées autour de zéro listés dans `catalog.py`.

### Momentum

Lorsque la transformation a un sens :

```text
momentum_pct = moyenne(sign × variation_3_mois × 4, sign × variation_1_an)
momentum_equivalent = momentum_pct / (20 / 1.5)
```

Le facteur quatre annualise la variation à trois mois. Une composante
indisponible n'est pas remplacée par zéro.

### Agrégation des composantes

Avant agrégation, chaque composante orientée est saturée dans l'intervalle
fixe `[-5, +5]` équivalents-z. Cette borne n'est pas estimée sur l'historique :
elle empêche une variation en pourcentage extrême, telle que le choc des
inscriptions au chômage de 2020, de dominer seule un indice composé de 47
séries. Les valeurs brutes restent exposées dans le registre pour audit.

```text
stress_final = moyenne_pondérée_des_composantes_disponibles(
  zscore=50 %, drift=25 %, momentum=25 %
)
```

Les poids sont renormalisés sur les seules composantes valides. Cette moyenne
remplace l'ancien maximum brut, qui sur-réagissait mécaniquement à une seule
composante. Le score de chaque série et toute moyenne agrégée restent ainsi
compris entre `-5` et `+5`.

## 3. Calibrage et poids empiriques

Le calibrage évalue le même `stress_final` que le moteur courant, tronqué par
date d'observation. Il observe ce score 3, 6 et 12 mois avant le début des quatre
récessions NBER codées : juillet 1990, mars 2001, décembre 2007 et février 2020.

Le contrôle des faux positifs échantillonne le score chaque trimestre hors des
récessions et d'une zone tampon de douze mois avant et après chacune d'elles.
Un faux positif est un score au moins égal à `1.5` dans cette zone hors crise.

```text
calibration_raw = moyenne(score à 3, 6 et 12 mois avant récession)
calibration_net = calibration_raw - false_positive_rate
```

Le poids empirique est borné entre `0.5` et `3.0` par les paliers versionnés dans
`scoring.py`. Ce calibrage est in-sample : les mêmes quatre épisodes servent à
mesurer le signal et à fixer les poids. Il repose sur un échantillon très court,
n'est pas une validation prédictive hors échantillon et ne prouve pas la
stabilité future du modèle.

Une série doit disposer d'au moins deux récessions observées à chacun des trois
horizons. En dessous, sa calibration est déclarée indisponible et son poids
reste neutre à `1.0`.

## 4. Agrégation famille et globale

```text
score_famille = somme(stress_final × poids_empirique) / somme(poids_empirique)
score_global  = somme(stress_final × poids_empirique) / somme(poids_empirique)
```

Une ligne non finie est exclue du numérateur et du dénominateur. En production,
le contrat refuse cependant tout snapshot courant qui ne couvre pas les 47
séries ou contient un score non fini.

## 5. Reconstruction historique

À chaque premier jour du mois depuis 1990, les séries sont tronquées par date
d'observation et le score composite complet est recalculé. Les poids et les
vintages FRED sont ceux de la méthodologie actuelle. C'est donc une
reconstruction rétrospective, pas une simulation des données et décisions
réellement disponibles à l'époque.

Le score courant utilise, lui, la dernière observation disponible de chaque
série. Il peut donc différer du dernier point mensuel reconstruit.

## 6. Contrat de données de production

`snapshot_builder.py` échoue sans publier si une série manque. Le manifest
`metadata.json`, promu en dernier, contient :

- versions du schéma et de la méthode ;
- SHA Git complet du calculateur ;
- empreinte du catalogue ;
- couverture et absence d'erreur de collecte ;
- dates extrêmes des observations ;
- empreinte SHA-256 et taille de chaque Parquet.

`app_server.py` revérifie le manifest, les fichiers, les métadonnées du
catalogue, les dates et des plafonds de fraîcheur adaptés à la fréquence. Tout
bundle partiel, modifié ou incompatible est masqué.

Les plafonds sur la date de période la plus récente sont de 14 jours pour une
série quotidienne, 35 pour une hebdomadaire, 95 pour une mensuelle et 240 pour
une trimestrielle. Ces seuils tiennent compte du fait qu'une date de période
n'est pas une date de publication.

## 7. Limites

- FRED distribue des séries de producteurs multiples, révisables et publiées
  avec des délais différents.
- La reconstruction n'utilise pas les vintages ALFRED et n'est pas un backtest
  point-in-time.
- Les quatre récessions NBER forment un échantillon très court.
- Les choix de fenêtre, de seuil et de pondération restent des hypothèses de
  modèle explicites.
- La référence 2015–2019 ne décrit pas nécessairement un régime structurel
  stable.
- Un score agrégé peut masquer des signaux opposés ; le registre détaillé reste
  indispensable.
- Les niveaux ne sont pas directement comparables aux dashboards Dette US,
  Euro Macro ou Énergie, dont les normalisations diffèrent.

## Validation

```bash
PYTHONPYCACHEPREFIX=/tmp/macro_pycache python3 -m py_compile catalog.py scoring.py data.py snapshot_contract.py snapshot_builder.py ui.py dashboard_view.py app.py app_server.py
python3 -m unittest discover -s tests -v
ruff check .
bandit -c pyproject.toml -r .
pip-audit --local
```
