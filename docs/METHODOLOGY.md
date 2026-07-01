# Méthodologie US Macro Dashboard

Ce dashboard suit le régime macro américain à partir de séries FRED. Il ne
prévoit pas une récession à date fixe et ne produit pas de signal
d'investissement.

## Sources

Source principale : FRED, Federal Reserve Bank of St. Louis.

Le catalogue des séries est dans `catalog.py`. Chaque entrée définit :

- la famille macro ;
- le code FRED ;
- le nom lisible ;
- la fréquence ;
- le sens du risque, `up` ou `down` ;
- l'unité.

## Transformation des séries

Chaque série disponible est transformée dans `data.py` :

1. `zscore_5y` : écart au régime récent sur une fenêtre glissante de cinq ans.
2. `drift_zscore_equiv` : écart au régime pré-COVID, désactivé pour les séries
   où le régime monétaire ou le niveau nominal rend ce calcul trompeur.
3. `momentum_zscore_equiv` : combinaison du mouvement 3 mois annualisé et du
   mouvement 1 an, désactivée pour les séries où le momentum n'a pas de sens.

Le score de série corrigé combine les composantes disponibles :

```text
stress_final = weighted_mean({
  zscore: 0.50,
  drift: 0.25,
  momentum: 0.25
})
```

Cette règle remplace l'ancien maximum brut entre z-score, drift et momentum.
Elle réduit le biais mécanique d'alerte sans effacer le rôle des mouvements
rapides.

## Pondération empirique

Le backtest calcule la réaction de chaque série avant les récessions NBER de
1990, 2001, 2007-2009 et 2020, aux horizons 3, 6 et 12 mois.

La version corrigée ajoute une mesure hors récession :

- l'historique est échantillonné trimestriellement hors fenêtres de récession
  élargies ;
- une alerte hors récession est comptée quand le score dépasse le seuil
  d'avertissement ;
- le taux de faux positifs pénalise `pred_power`.

```text
pred_power = pred_power_raw - false_positive_rate
```

Le poids final d'une série reste dérivé de `pred_power` par paliers. Une série
qui réagit avant les récessions mais alerte trop souvent hors récession voit donc
son poids réduit.

## Agrégation

Le score famille est la moyenne pondérée des `stress_final` de ses séries. Le
score global est la moyenne pondérée de toutes les séries disponibles.

Les valeurs restent des z-scores internes. Elles ne sont pas des probabilités de
récession, ni une échelle comparable telle quelle avec Dette US, Euro Macro ou
Énergie.

## Limites

- Quatre récessions NBER forment un échantillon court.
- Les séries FRED ont des fréquences, délais et révisions hétérogènes.
- Un choc de marché peut précéder les données macro mensuelles ou trimestrielles.
- Les poids de composantes restent des choix de modèle explicites.
- Le backtest réduit le bruit de faux positifs, mais ne prouve pas la stabilité
  future du modèle.

## Validation locale

```bash
PYTHONPYCACHEPREFIX=/tmp/macro_pycache python3 -m py_compile catalog.py data.py app.py
```

Un test synthétique simple doit montrer que le moteur ne retourne plus le
maximum brut :

```bash
python3 -c 'from data import weighted_stress_component_score; print(weighted_stress_component_score({"zscore":0.2,"drift":3.0,"momentum":0.2}))'
```

La sortie attendue est `0.9`, pas `3.0`.
