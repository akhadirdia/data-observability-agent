Voici le cahier des charges complet et détaillé, basé sur l'ouvrage *Data Quality Fundamentals* de Barr Moses, Lior Gavish et Molly Vorwerck, que vous pouvez fournir à Claude Code pour construire votre Plateforme d'Observabilité des Données.

Ce projet vise à éradiquer le **"Data Downtime"** (les périodes où les données sont manquantes, erronées ou inexactes) en traitant les données avec la même rigueur que le code logiciel en production. 

Copiez-collez la structure suivante pour donner à Claude Code tout le contexte, les algorithmes et les stratégies nécessaires :

### 1. L'Architecture Fondamentale : Les 5 Piliers de l'Observabilité
Le système doit être architecturé pour auditer en continu les bases de données (ex: Snowflake, BigQuery) à travers cinq piliers stricts :
*   **La Fraîcheur (Freshness) :** Le code doit calculer les délais de mise à jour des tables. La formule SQL de base à implémenter pour détecter les anomalies de fraîcheur compare la date actuelle à la date précédente : `JULIANDAY(DATE_ADDED) - JULIANDAY(LAG(DATE_ADDED) OVER (ORDER BY DATE_ADDED))`.
*   **Le Volume :** Le système doit vérifier que la quantité de données entrantes (comptage de lignes ou bytes) correspond aux moyennes historiques pour éviter les pertes ou les duplications massives.
*   **La Distribution :** Le code doit extraire les statistiques des champs pour s'assurer qu'ils sont dans des plages acceptables. Claude doit coder des requêtes calculant le taux de valeurs nulles (`SUM(CASE WHEN champ IS NULL THEN 1 ELSE 0 END) / COUNT(*)`), le taux de zéros, et les moyennes numériques.
*   **Le Schéma (Schema) :** Le script doit alerter si la structure de la donnée change (ajout, suppression ou modification du type d'une colonne) en comparant les métadonnées actuelles (`information_schema`) avec un historique stocké.
*   **Le Lignage (Lineage) :** Le système doit cartographier les dépendances au niveau des champs (field-level lineage) en parsant les requêtes SQL (avec un outil comme ANTLR) pour lier les tables sources du Data Warehouse aux tableaux de bord de Business Intelligence en aval.

### 2. Les Algorithmes de Détection d'Anomalies (Machine Learning & Statistiques)
Le système ne doit pas reposer uniquement sur des règles manuelles, mais détecter les "inconnues inconnues" via des algorithmes. Demandez à Claude d'implémenter ces logiques :
*   **Moyennes Mobiles (Rolling Averages) :** Pour lisser le bruit, le code doit calculer la moyenne mobile sur 14 jours (ex: `AVG(taux_null) OVER (ROWS BETWEEN 14 PRECEDING AND CURRENT ROW)`) et alerter si la différence avec la valeur actuelle dépasse un certain seuil.
*   **Scores Standards (Z-Scores) :** En s'appuyant sur le théorème central limite pour les données distribuées normalement, l'algorithme doit soustraire la moyenne $\mu$ et diviser par l'écart-type $\sigma$ pour identifier les observations trop éloignées (outliers).
*   **Algorithmes ML Avancés :** Implémenter des modèles autorégressifs (ARIMA) ou des lissages exponentiels (Holt-Winters) pour tenir compte de la saisonnalité (ex: une baisse de volume normale le week-end). Des techniques de clustering comme l'Isolation Forest peuvent aussi être utilisées.
*   **Optimisation de la Précision et du Rappel (F-Score) :** Pour éviter la "fatigue d'alerte", l'algorithme doit être évalué par le score $F_\beta$ : $F_\beta = (1 + \beta^2) \times \frac{Precision \times Recall}{(\beta^2 \times Precision) + Recall}$. Configurer $\beta > 1$ (ex: F2 ou F3) si manquer une anomalie est plus grave que de générer une fausse alerte.

### 3. Stratégie DataOps : Tests et Coupe-Circuits (Circuit Breakers)
Le projet doit intégrer des processus de développement logiciel appliqués aux données (DataOps) :
*   **Tests Unitaires de Données :** Intégrer des validations utilisant des frameworks comme **dbt** (pour les tests génériques comme `unique`, `not_null`, `accepted_values`), **Great Expectations** (tests en Python via des fichiers YAML), ou **Deequ** (pour les environnements Apache Spark).
*   **L'Orchestrateur (Apache Airflow) et les Coupe-circuits :** Claude doit coder un DAG (Directed Acyclic Graph) sur Airflow qui bloque proactivement le pipeline si la donnée ne répond pas aux exigences de qualité. Cela s'implémente via le paramètre `sla_miss_callback`, un opérateur `LatestOnlyOperator`, ou des `SQLCheckOperator`. 

### 4. Tableaux de bord de Résolution (TTR/TTD) et ROI Financier
C'est ici que votre projet impressionnera les recruteurs de la finance. Le système doit inclure une interface calculant l'impact métier :
*   **Calcul du TTD (Time To Detection) et TTR (Time To Resolution) :** Suivi du temps nécessaire pour détecter puis résoudre un incident de données.
*   **Formule du Coût du Data Downtime (ROI) :** Coder une métrique financière avec la formule : `(Heures de TTD + Heures de TTR) × Coût horaire du temps d'arrêt`. Une alternative est : `Coût du travail + Risque de conformité + Coût d'opportunité`.
*   **Gestion des SLA, SLI, et SLO :** L'interface doit permettre de définir des Accords de Niveau de Service (SLA). Par exemple, un Objectif de Niveau de Service (SLO) pourrait être "La table X sera mise à jour d'ici 8h00, 99% du temps", mesuré par des Indicateurs de Niveau de Service (SLI).

### 5. Workflow de Root Cause Analysis (Analyse des causes profondes)
Votre plateforme doit guider l'ingénieur à travers les 5 étapes du Root Cause Analysis recommandées par les auteurs lorsqu'une alerte est déclenchée :
1.  **Lignage :** Remonter aux nœuds les plus en amont du système pour trouver l'origine.
2.  **Code :** Examiner la logique ETL/SQL qui a généré la table.
3.  **Données :** Segments temporels ou catégories pour voir où se concentre l'anomalie.
4.  **Environnement Opérationnel :** Analyser les logs d'Airflow ou dbt pour des erreurs de temps d'exécution.
5.  **Pairs :** Identifier les propriétaires de la donnée grâce au catalogue pour collaborer.

