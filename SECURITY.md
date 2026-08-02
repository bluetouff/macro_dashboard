# Sécurité

## Architecture de production

`app_server.py` est le seul processus exposé par `us.l0g.fr`. Il ne possède pas
de clé FRED et ne fait aucun appel réseau. Il charge un bundle local après avoir
vérifié son schéma, sa couverture, ses empreintes SHA-256 et le SHA Git complet
du calculateur.

`snapshot_builder.py` est un processus distinct. Il lit `FRED_API_KEY` depuis
`/etc/macro_dashboard/env`, refuse un fichier d'environnement lisible par tous,
et publie les données de manière atomique. Un catalogue incomplet n'est jamais
promu.

## Mesures défensives

- dépendances directes épinglées et transitives contraintes ;
- protection XSRF et contrôle CORS Streamlit activés ;
- télémétrie Streamlit désactivée ;
- détails d'erreur masqués côté client ;
- aucune police, image, iframe, ressource ou script tiers chargé automatiquement ;
- paramètres de vue réduits à une liste fermée ;
- permissions de snapshots `0640`, répertoire `0750` ;
- validation CI par compilation, tests, Ruff, Bandit et `pip-audit`.

Les en-têtes HTTP de sécurité et TLS restent la responsabilité du reverse proxy
Apache. Ils doivent être contrôlés séparément après chaque mise en production.

## Signalement

Ne publiez pas de secret ou de preuve d'exploitation dans une issue publique.
Contactez l'administrateur de l0g.fr par un canal privé avec le périmètre, les
étapes de reproduction et l'impact observé.
