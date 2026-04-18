# Data Observability Agent — Guide de développement pour Claude Code

## Contexte et objectif

Agent IA de Data Quality qui se connecte à n'importe quelle base SQL, exécute automatiquement les 5 piliers de l'observabilité (Fraîcheur, Volume, Distribution, Schéma, Lignage), détecte les anomalies statistiques, et **génère une analyse Root Cause Analysis en langage naturel via Claude Sonnet**. L'IA remplace le triage manuel de l'ingénieur data.

**Référence théorique** : *Data Quality Fundamentals* — Barr Moses, Lior Gavish, Molly Vorwerck (`cahierdecharge.md`).

> ⚠️ **Instruction critique** : Pour chaque librairie (Agno, Anthropic SDK, SQLAlchemy, pandas, scipy), consulter la documentation officielle à jour avant d'écrire du code. Les APIs évoluent vite.

---

## Stack technique

| Composant | Technologie | Raison du choix |
|---|---|---|
| LLM / RCA | Claude Sonnet (Anthropic) | Analyse contextuelle, français, contexte long |
| Orchestration agent | Agno framework | Léger, natif multi-agents, cohérent avec stack existante |
| Connecteur DB | SQLAlchemy | Multi-DB universel (Postgres, MySQL, SQLite, BigQuery…) |
| Statistiques | pandas + scipy | Z-score, rolling averages, détection outliers |
| Interface | Streamlit | Déploiement simple, dashboard incidents |
| Déploiement | Streamlit Community Cloud | Gratuit, connecté au repo GitHub |
| Scheduling | APScheduler (local) / Cron (prod) | Vérifications périodiques sans Airflow |
| Alertes | smtplib + Slack webhook | Notifications légères sans dépendance lourde |

---

## Structure du projet

```
data-observability-agent/
├── app.py
├── agents/
│   ├── __init__.py
│   ├── monitor_agent.py        # Agent principal : orchestre les 5 piliers
│   └── rca_agent.py            # Agent RCA : analyse Claude Sonnet
├── checks/
│   ├── __init__.py
│   ├── freshness.py            # Pilier 1 : fraîcheur
│   ├── volume.py               # Pilier 2 : volume
│   ├── distribution.py         # Pilier 3 : distribution / taux nulls
│   ├── schema.py               # Pilier 4 : détection changements schéma
│   └── lineage.py              # Pilier 5 : lignage simplifié (dépendances)
├── anomaly/
│   ├── __init__.py
│   ├── zscore.py               # Détection Z-score
│   └── rolling.py              # Moyennes mobiles 14 jours
├── connectors/
│   ├── __init__.py
│   └── sql_connector.py        # SQLAlchemy : connexion + exécution queries
├── core/
│   ├── __init__.py
│   ├── config.py               # Settings pydantic-settings + singleton
│   └── incident_store.py       # Persistance incidents (SQLite local)
├── notifications/
│   ├── __init__.py
│   └── alerting.py             # Email + Slack webhook
├── prompts/
│   ├── rca_prompt.py           # Prompt RCA Claude Sonnet
│   └── summary_prompt.py       # Prompt résumé rapport quotidien
├── tests/
│   ├── test_checks.py
│   ├── test_anomaly.py
│   └── test_rca_agent.py
├── .env.example
├── .gitignore
├── docker-compose.yml          # SQLite only — pas de Qdrant ici
├── requirements.txt
└── README.md
```

---

## ✅ Étape 1 — Setup du projet (TERMINÉE)

**`requirements.txt`** — versions majeures fixées après vérification sur PyPI :
`anthropic`, `agno`, `sqlalchemy`, `pandas`, `scipy`, `streamlit`, `pydantic-settings`, `python-dotenv`, `tenacity`, `loguru`, `apscheduler`, `requests`.

**`core/config.py`** : classe `Settings` avec `pydantic_settings.BaseSettings`. Singleton via `@lru_cache`. Variables requises :
- `ANTHROPIC_API_KEY`
- `DATABASE_URL` — URL SQLAlchemy (ex: `postgresql://user:pass@host/db`)
- `SLACK_WEBHOOK_URL` — optionnel
- `ALERT_EMAIL` — optionnel
- `ENV` — `development` | `production`
- `CHECK_INTERVAL_MINUTES` — fréquence des vérifications (défaut : 60)

**`docker-compose.yml`** : aucun service requis en dev (SQLite local pour `incident_store`). Documenter comment pointer vers une vraie DB via `DATABASE_URL`.

**`.env.example`** : toutes les variables avec placeholder et commentaire. CE fichier EST commité.

**`.gitignore`** : `.env`, `__pycache__/`, `.streamlit/secrets.toml`, `outputs/`, `*.db`.

**✅ Validation** : `python -c "import agno, anthropic, sqlalchemy, pandas, scipy, streamlit; print('OK')"` sans erreur.

---

## ✅ Étape 2 — Connecteur SQL (TERMINÉE)

**`connectors/sql_connector.py`** : classe `SQLConnector` avec :
- `connect(database_url: str) -> Engine` — connexion SQLAlchemy
- `execute_query(query: str) -> pd.DataFrame` — exécute et retourne un DataFrame
- `get_table_list() -> list[str]` — liste toutes les tables disponibles
- `get_column_metadata(table: str) -> list[dict]` — nom, type, nullable pour chaque colonne

Toutes les méthodes dans un `try/except` avec `loguru`. Une erreur de connexion ne plante pas l'app — retourner un DataFrame vide ou une liste vide et logger l'erreur.

**✅ Validation** : connecter sur une base SQLite de test, lister les tables, exécuter `SELECT COUNT(*) FROM table`.

---

## ✅ Étape 3 — Les 5 piliers (checks/) (TERMINÉE)

Chaque check est une fonction pure qui prend un `SQLConnector` + un nom de table et retourne un `dict` standardisé :

```python
{
    "pillar": "freshness" | "volume" | "distribution" | "schema" | "lineage",
    "table": str,
    "status": "ok" | "warning" | "critical",
    "value": float | dict,
    "message": str,
    "timestamp": str  # ISO 8601
}
```

**`checks/freshness.py`** : calculer le délai entre les deux derniers enregistrements via une colonne `updated_at` ou `created_at` configurable. Formule SQL : `JULIANDAY(MAX(date_col)) - JULIANDAY(LAG(MAX(date_col)))`. Alerter si le délai dépasse le seuil configuré (ex: 2× la moyenne historique).

**`checks/volume.py`** : compter les lignes et comparer au volume moyen des 14 derniers jours. Alerte si variation > 20% (seuil configurable).

**`checks/distribution.py`** : pour chaque colonne numérique — taux de nulls (`SUM(CASE WHEN col IS NULL THEN 1 ELSE 0 END) / COUNT(*)`), taux de zéros, moyenne, min, max. Alerte si taux de nulls dépasse le seuil historique + 2 sigma.

**`checks/schema.py`** : récupérer `information_schema` et comparer au snapshot précédent stocké dans `incident_store`. Alerter sur tout ajout, suppression ou changement de type de colonne. Stocker le nouveau snapshot à chaque run réussi.

**`checks/lineage.py`** (MVP simplifié — pas d'ANTLR) : maintenir un fichier YAML de déclaration manuelle des dépendances entre tables. Exposer `get_upstream_tables(table: str) -> list[str]` et `get_downstream_tables(table: str) -> list[str]`. Le lignage automatique via parsing SQL est hors scope MVP.

**✅ Validation** : chaque check retourne le dict standardisé sur une table SQLite de test. Tester les cas limites : table vide, colonne entièrement nulle.

---

## Étape 4 — Détection d'anomalies (anomaly/)

**`anomaly/zscore.py`** : fonction `detect_zscore(series: pd.Series, threshold: float = 3.0) -> bool`. Implémentation : `(valeur - moyenne) / écart_type`. Retourner `True` si anomalie détectée. Gérer les cas où l'écart-type est 0 (série constante).

**`anomaly/rolling.py`** : fonction `detect_rolling_anomaly(series: pd.Series, window: int = 14, threshold_multiplier: float = 2.0) -> bool`. Calculer la moyenne mobile sur `window` périodes avec `pd.Series.rolling()`. Alerter si la valeur actuelle s'écarte de plus de `threshold_multiplier × écart-type`.

Ces deux fonctions sont appelées par les checks de Volume et Distribution pour enrichir la détection au-delà des règles fixes.

**✅ Validation** : tester avec une série synthétique contenant une anomalie connue à la position N. Vérifier que les deux algorithmes la détectent.

---

## Étape 5 — Agent RCA (Root Cause Analysis)

**Référence** : les 5 étapes RCA du cahier des charges (Lignage → Code → Données → Environnement → Pairs).

**`prompts/rca_prompt.py`** (v1.0) :
```
Tu es un expert en qualité de données. Tu reçois un rapport d'anomalie sur une table SQL.

Analyse en suivant ces 5 étapes dans l'ordre :
1. Lignage : quelles tables en amont peuvent avoir causé le problème ?
2. Code : quelle transformation ETL/SQL est probablement en cause ?
3. Données : dans quel segment temporel ou catégorie se concentre l'anomalie ?
4. Environnement : quelles causes opérationnelles sont possibles (job échoué, migration, charge) ?
5. Pairs : qui devrait être notifié et collaborer à la résolution ?

Sois factuel et direct. Ne spécule pas sans base. Maximum 300 mots. Réponds en français.
Structure ta réponse avec les 5 en-têtes numérotés.
```

**`agents/rca_agent.py`** : agent Agno avec Claude Sonnet. Méthode `analyze(incident: dict, lineage_context: str) -> str`. Injecter dans le prompt : le dict d'incident, le contexte de lignage, les métadonnées de la table. Timeout explicite de 30 secondes. `try/except` — si Claude échoue, retourner un message de fallback structuré.

**`agents/monitor_agent.py`** : agent principal qui :
1. Récupère la liste des tables à surveiller (config)
2. Exécute les 5 checks pour chaque table
3. Pour chaque résultat `warning` ou `critical`, appelle `rca_agent.analyze()`
4. Stocke les incidents dans `incident_store`
5. Déclenche les notifications si configurées

**✅ Validation** : simuler un incident avec un dict mocké. L'agent RCA retourne une analyse avec les 5 en-têtes. Aucune exception non gérée même si Claude timeout.

---

## Étape 6 — Persistance des incidents

**`core/incident_store.py`** : SQLite local via SQLAlchemy. Table `incidents` :

```python
{
    "id": int (PK, autoincrement),
    "table_name": str,
    "pillar": str,
    "status": str,
    "value": str (JSON),
    "message": str,
    "rca_analysis": str,
    "detected_at": datetime,
    "resolved_at": datetime | None,
    "ttd_minutes": float | None,   # Time To Detection
    "ttr_minutes": float | None    # Time To Resolution
}
```

Exposer : `save_incident()`, `get_open_incidents()`, `get_incident_history(table, days)`, `resolve_incident(id)`, `compute_roi(hourly_cost: float) -> dict`.

**Formule ROI** dans `compute_roi` : `(TTD_heures + TTR_heures) × coût_horaire`. Retourner aussi le nombre d'incidents par pilier pour identifier le pilier le plus coûteux.

**✅ Validation** : créer un incident, le lister, le résoudre, calculer le ROI.

---

## Étape 7 — Notifications

**`notifications/alerting.py`** : deux fonctions `send_slack_alert(incident: dict)` et `send_email_alert(incident: dict)`. Activer uniquement si les variables d'environnement correspondantes sont définies. Jamais d'exception levée — logger avec `loguru` si l'envoi échoue.

Format Slack : bloc structuré avec table, pilier, statut, message, extrait RCA.

**✅ Validation** : mocker les calls réseau. Vérifier que l'absence de webhook ne lève pas d'exception.

---

## Étape 8 — Interface Streamlit

**`app.py`** — trois onglets :

**"Tableau de bord"** : liste des incidents ouverts (status badge coloré), métriques agrégées (nb incidents par pilier, TTD/TTR moyens, ROI cumulé). `st.cache_resource` pour le connector DB et le monitor agent.

**"Lancer une analyse"** : sélecteur de table (liste dynamique depuis le connector), bouton "Analyser maintenant" avec `st.status()` affichant la progression pilier par pilier. Résultat : tableau des checks + analyse RCA en markdown.

**"Historique & ROI"** : filtres par table et période. Tableau des incidents passés. Métriques ROI avec champ "Coût horaire estimé (€)" paramétrable. Graphique ligne : incidents détectés dans le temps (par pilier).

**Sidebar** : statut DB (✅ connecté / ⚠️ erreur), statut Claude API, fréquence de vérification configurée.

**`st.session_state`** : `current_analysis`, `selected_table`, `analysis_in_progress`. Désactiver les boutons pendant l'analyse.

**Gestion des erreurs** : erreur DB → `st.error()` + explication claire. Erreur Claude → `st.warning()` + RCA de fallback affiché. Jamais de stack trace visible.

**✅ Validation** : pipeline complet via UI sur une base SQLite de test. Tester avec une table ayant un volume anormalement bas.

---

## Étape 9 — Tests unitaires

`pytest` + `unittest.mock`. Zéro appel réseau réel.

**`tests/test_checks.py`** : tester chaque check avec un DataFrame mocké. Tester les cas limites (table vide, colonne 100% nulle, schéma changé).

**`tests/test_anomaly.py`** : tester Z-score avec série normale vs série avec outlier. Tester rolling average avec saisonnalité simulée. Tester le cas écart-type = 0.

**`tests/test_rca_agent.py`** : Anthropic mocké. Tester que l'agent retourne les 5 en-têtes. Tester le fallback si Claude timeout.

**✅ Validation** : `pytest tests/ -v` → tous verts.

---

## Étape 10 — Déploiement

**README.md** (en anglais) : intro, démo GIF, schéma d'architecture, features, quick start en 5 commandes, tableau variables d'environnement.

**Avant le commit final** : `.env` absent, `requirements.txt` testé dans un venv propre, tous les tests verts.

**Streamlit Community Cloud** : fichier principal `app.py`. Secrets TOML : `ANTHROPIC_API_KEY`, `DATABASE_URL`, `SLACK_WEBHOOK_URL`, `ALERT_EMAIL`, `ENV=production`.

**✅ Validation** : URL publique accessible. Analyse complète sur une table de démo publique (ex: base Northwind sur SQLite).

---

## Bonnes pratiques

**Checks** : chaque check est une fonction pure testable indépendamment. Aucune logique métier dans `app.py`. Seuils configurables via variables d'environnement ou UI — jamais hardcodés.

**Anomalies** : commencer par Z-score uniquement (ARIMA est hors scope MVP). Documenter clairement où brancher des algorithmes plus avancés plus tard.

**RCA** : le prompt est versionné (`# v1.0`). Format de sortie contraint (5 en-têtes numérotés). Toujours injecter le contexte de lignage même s'il est vide.

**Incidents** : TTD calculé à la détection automatiquement. TTR mis à jour manuellement via l'UI (bouton "Marquer comme résolu").

**Code** : type hints sur toutes les fonctions. `loguru` pour tout le logging. Zéro API key en dur.

---

## Checklist finale

- [ ] `.env` absent du repo
- [ ] `.env.example` complet
- [ ] `requirements.txt` testé dans un venv propre
- [ ] `README.md` avec démo GIF et schéma d'architecture
- [ ] `pytest tests/ -v` → tous verts
- [ ] App fonctionnelle localement sur base SQLite de test
- [ ] App fonctionnelle en production (Streamlit Cloud)
- [ ] URL publique accessible
