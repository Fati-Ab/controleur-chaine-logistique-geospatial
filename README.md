# Système intelligent d’optimisation logistique avec géospatial analytics

## 1. Présentation

Ce projet universitaire consiste à développer un système intelligent de supervision et d’optimisation logistique basé sur des données GPS réelles de taxis à Porto.

Le système permet de :

- lire un dataset GPS réel ;
- préparer les trajets et positions GPS ;
- simuler un flux temps réel avec Apache Kafka ;
- stocker les données dans PostgreSQL/PostGIS ;
- afficher les véhicules sur une carte interactive ;
- détecter les zones de congestion avec DBSCAN ;
- enrichir les trajets avec la météo réelle Open-Meteo ;
- calculer un score de risque logistique ;
- prévoir les retards futurs ;
- comparer les tournées avant/après optimisation ;
- exporter les données géospatiales vers Kepler.gl.

---

## 2. Objectif du projet

L’objectif est d’aider un responsable logistique à surveiller ses véhicules, identifier les trajets à risque, détecter les zones denses, anticiper les retards et mesurer les gains obtenus après optimisation des tournées.

Le projet répond aux questions suivantes :

- Où sont les véhicules en temps réel ?
- Quels trajets sont en retard ou à risque ?
- Quelles zones de Porto sont les plus denses ?
- Quel est l’impact de la météo sur les retards ?
- Combien peut-on économiser après optimisation ?
- Comment exporter les données vers Kepler.gl ?

---

## 3. Technologies utilisées

- Python
- Apache Kafka
- PostgreSQL
- PostGIS
- Streamlit
- Plotly Mapbox
- scikit-learn / DBSCAN
- Open-Meteo API
- pandas
- psycopg2
- Docker / Docker Compose
- Kepler.gl

---

## 4. Dataset utilisé

Le fichier utilisé est :

```text
data/raw/porto_january_2014.csv
```

Colonnes principales :

```text
taxi_id
trajectory_id
timestamp
source_point
target_point
date_depart
```

Après préparation des données :

```text
4997 trajets valides
124925 positions GPS
304 taxis différents
```

---

## 5. Architecture générale

```text
Dataset CSV Porto
        ↓
Préparation des données GPS
        ↓
PostgreSQL + PostGIS
        ↓
Kafka Producer
        ↓
Kafka Topic : gps_positions
        ↓
Kafka Consumer
        ↓
Table realtime_positions
        ↓
Dashboard Streamlit
```

Architecture analytique :

```text
gps_positions
        ↓
DBSCAN
        ↓
dbscan_clusters

trips + weather_hourly + dbscan_clusters
        ↓
Score de risque
        ↓
route_scores

route_scores
        ↓
Prévision des retards
        ↓
forecast_delays

route_scores
        ↓
Optimisation avant/après
        ↓
optimized_routes

PostGIS
        ↓
Export GeoJSON
        ↓
Kepler.gl
```

---

## 6. Structure du projet

```text
projet_BI/
│
├── data/
│   ├── raw/
│   │   └── porto_january_2014.csv
│   └── exports/
│       ├── kepler_points.geojson
│       ├── dbscan_clusters.geojson
│       ├── risk_routes.geojson
│       └── optimization_report.json
│
├── dashboard/
│   └── app.py
│
├── src/
│   ├── config.py
│   ├── 01_prepare_porto_data.py
│   │
│   ├── ingestion/
│   │   ├── 02_kafka_producer.py
│   │   └── 03_kafka_consumer_postgis.py
│   │
│   ├── analysis/
│   │   ├── 05_dbscan_clustering.py
│   │   ├── 06_risk_scoring.py
│   │   ├── 09_prophet_forecast.py
│   │   ├── 10_route_optimization.py
│   │   ├── check_dbscan.py
│   │   ├── check_forecast.py
│   │   └── check_optimization.py
│   │
│   ├── enrichment/
│   │   ├── 08_weather_openmeteo.py
│   │   └── check_weather.py
│   │
│   └── export/
│       └── 07_export_kepler.py
│
├── sql/
│   └── create_tables.sql
│
├── docker-compose.yml
├── requirements.txt
├── README.md
└── COMMANDES_UTILES.md
```

---

## 7. Installation

### 7.1 Créer l’environnement virtuel

```bash
cd C:\Users\Fati\projet_BI
python -m venv venv
venv\Scripts\activate
```

### 7.2 Installer les bibliothèques

```bash
pip install -r requirements.txt
```

Si l’installation complète pose problème :

```bash
pip install pandas psycopg2-binary sqlalchemy kafka-python streamlit plotly scikit-learn requests
```

### 7.3 Lancer Docker

```bash
docker compose up -d
```

Vérifier :

```bash
docker ps
```

Conteneurs attendus :

```text
logistics_postgis
logistics_kafka
logistics_zookeeper
```

---

## 8. Exécution du pipeline

### 8.1 Préparation des données

```bash
python src\01_prepare_porto_data.py
```

Vérification :

```bash
python src\check_gps_data.py
```

Résultat attendu :

```text
Nombre de trajets : 4997
Nombre de positions GPS : 124925
Nombre de taxis différents : 304
```

---

### 8.2 Lancer le flux temps réel Kafka

Terminal 1 — Consumer :

```bash
python -m src.ingestion.03_kafka_consumer_postgis
```

Terminal 2 — Producer :

```bash
python -m src.ingestion.02_kafka_producer
```

Le producer rejoue les positions GPS des taxis depuis PostGIS vers Kafka.  
Le consumer lit Kafka et insère les données dans `realtime_positions`.

Le flux est un **temps réel simulé à partir de données GPS réelles**.

---

### 8.3 Détection DBSCAN

```bash
python -m src.analysis.05_dbscan_clustering
```

Vérification :

```bash
python -m src.analysis.check_dbscan
```

DBSCAN permet de détecter les zones denses de circulation.

---

### 8.4 Récupération météo Open-Meteo

```bash
python -m src.enrichment.08_weather_openmeteo
```

Vérification :

```bash
python -m src.enrichment.check_weather
```

Exemple de résultat :

```text
72 heures météo
Température moyenne : 12.31 °C
Pluie moyenne : 0.96 mm
Pluie max : 4.5 mm
Vent moyen : 18.93 km/h
```

---

### 8.5 Calcul du score de risque

```bash
python -m src.analysis.06_risk_scoring
```

Le score de risque combine :

```text
retard estimé
+ pluie réelle
+ vent réel
+ appartenance à une zone DBSCAN
```

Formule utilisée :

```text
risk_score =
    estimated_delay_minutes
  + rain_mm * 2
  + wind_speed_kmh / 10
  + congestion_flag * 20
```

Niveaux de risque :

```text
LOW
MEDIUM
HIGH
CRITICAL
```

---

### 8.6 Prévision des retards

```bash
python -m src.analysis.09_prophet_forecast
```

Vérification :

```bash
python -m src.analysis.check_forecast
```

Les prévisions sont stockées dans :

```text
forecast_delays
```

---

### 8.7 Optimisation des tournées

```bash
python -m src.analysis.10_route_optimization
```

Vérification :

```bash
python -m src.analysis.check_optimization
```

Résultats obtenus :

```text
Routes optimisées : 4997
Distance économisée : 747.08 km
Gain distance : 3.98 %
Temps gagné : 1172.86 minutes
Économie mensuelle estimée : 26046.24 €
```

---

### 8.8 Export vers Kepler.gl

```bash
python -m src.export.07_export_kepler
```

Fichiers générés :

```text
kepler_points.geojson
dbscan_clusters.geojson
risk_routes.geojson
optimization_report.json
```

Ces fichiers peuvent être importés dans :

```text
https://kepler.gl/demo
```

---

## 9. Lancer le dashboard

```bash
streamlit run dashboard\app.py
```

Le dashboard contient les pages suivantes :

### Temps réel

Affiche les dernières positions GPS des taxis rejouées via Kafka.

Indicateurs :

- taxis actifs ;
- retard moyen ;
- pluie moyenne ;
- score de risque maximal ;
- statut OK / WARNING / RISK.

### Tournées

Affiche la comparaison avant/après optimisation :

- distance avant ;
- distance après ;
- km économisés ;
- temps gagné ;
- économie mensuelle estimée.

### Clusters DBSCAN

Affiche les zones denses détectées automatiquement.

### Score de risque

Affiche la répartition des trajets selon le risque :

- LOW ;
- MEDIUM ;
- HIGH ;
- CRITICAL.

### Prévisions Prophet

Affiche les prévisions de retards futurs.

### Météo Open-Meteo

Affiche :

- température ;
- pluie ;
- vent ;
- humidité ;
- évolution météo horaire.

### Export Kepler.gl

Vérifie la génération des fichiers GeoJSON.

---

## 10. Résultats principaux

```text
Trajets analysés : 4997
Positions GPS : 124925
Taxis uniques : 304
Routes optimisées : 4997
Distance économisée : 747.08 km
Gain distance : 3.98 %
Temps gagné : 1172.86 minutes
Économie mensuelle estimée : 26046.24 €
```

---

## 11. Conclusion

Ce projet démontre la mise en place d’un système complet de supervision logistique intelligente.

Il combine :

- données GPS réelles ;
- streaming Kafka ;
- stockage géospatial PostGIS ;
- clustering DBSCAN ;
- météo Open-Meteo ;
- scoring de risque ;
- prévision des retards ;
- optimisation des tournées ;
- visualisation dashboard ;
- export Kepler.gl.

Le système final peut être utilisé comme outil d’aide à la décision pour un responsable logistique.
