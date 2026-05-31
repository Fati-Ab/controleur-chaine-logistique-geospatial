# Commandes utiles — Projet logistique géospatial

## 1. Aller dans le projet

```bash
cd C:\Users\Fati\projet_BI
```

---

## 2. Activer l’environnement Python

```bash
venv\Scripts\activate
```

---

## 3. Lancer Docker

```bash
docker compose up -d
```

---

## 4. Vérifier les conteneurs Docker

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

## 5. Arrêter Docker

```bash
docker compose down
```

---

## 6. Tester la connexion PostGIS

```bash
python src\test_connection.py
```

Résultat attendu :

```text
Connexion PostgreSQL/PostGIS OK
```

---

## 7. Préparer les données GPS

```bash
python src\01_prepare_porto_data.py
```

---

## 8. Vérifier les données GPS

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

## 9. Vider la table temps réel

À utiliser avant de relancer une nouvelle simulation Kafka :

```bash
docker exec -i logistics_postgis psql -U postgres -d logistics_db -c "TRUNCATE TABLE realtime_positions RESTART IDENTITY;"
```

---

## 10. Lancer Kafka Consumer

Terminal 1 :

```bash
cd C:\Users\Fati\projet_BI
venv\Scripts\activate
python -m src.ingestion.03_kafka_consumer_postgis
```

---

## 11. Lancer Kafka Producer

Terminal 2 :

```bash
cd C:\Users\Fati\projet_BI
venv\Scripts\activate
python -m src.ingestion.02_kafka_producer
```

---

## 12. Vérifier le nombre de taxis en temps réel

```bash
docker exec -i logistics_postgis psql -U postgres -d logistics_db -c "SELECT COUNT(DISTINCT truck_id) FROM realtime_positions;"
```

Résultat attendu progressivement :

```text
15
30
45
...
304
```

---

## 13. Voir les derniers véhicules insérés

```bash
docker exec -i logistics_postgis psql -U postgres -d logistics_db -c "SELECT truck_id, status, event_time FROM realtime_positions ORDER BY event_time DESC LIMIT 10;"
```

---

## 14. Lancer DBSCAN

```bash
python -m src.analysis.05_dbscan_clustering
```

---

## 15. Vérifier DBSCAN

```bash
python -m src.analysis.check_dbscan
```

---

## 16. Lancer météo Open-Meteo

```bash
python -m src.enrichment.08_weather_openmeteo
```

---

## 17. Vérifier météo

```bash
python -m src.enrichment.check_weather
```

---

## 18. Calculer le score de risque

```bash
python -m src.analysis.06_risk_scoring
```

---

## 19. Prévoir les retards

```bash
python -m src.analysis.09_prophet_forecast
```

---

## 20. Vérifier les prévisions

```bash
python -m src.analysis.check_forecast
```

---

## 21. Optimiser les tournées

```bash
python -m src.analysis.10_route_optimization
```

---

## 22. Vérifier l’optimisation

```bash
python -m src.analysis.check_optimization
```

---

## 23. Exporter vers Kepler.gl

```bash
python -m src.export.07_export_kepler
```

---

## 24. Vérifier les exports

```bash
dir data\exports
```

Fichiers attendus :

```text
kepler_points.geojson
dbscan_clusters.geojson
risk_routes.geojson
optimization_report.json
```

---

## 25. Lancer le dashboard

Terminal 3 :

```bash
cd C:\Users\Fati\projet_BI
venv\Scripts\activate
streamlit run dashboard\app.py
```

---

## 26. Pipeline complet dans l’ordre

```bash
cd C:\Users\Fati\projet_BI
venv\Scripts\activate

docker compose up -d

python src\01_prepare_porto_data.py
python -m src.analysis.05_dbscan_clustering
python -m src.enrichment.08_weather_openmeteo
python -m src.analysis.06_risk_scoring
python -m src.analysis.09_prophet_forecast
python -m src.analysis.10_route_optimization
python -m src.export.07_export_kepler

streamlit run dashboard\app.py
```

---

## 27. Lancer la simulation temps réel complète

Terminal 1 — Consumer :

```bash
cd C:\Users\Fati\projet_BI
venv\Scripts\activate
python -m src.ingestion.03_kafka_consumer_postgis
```

Terminal 2 — Producer :

```bash
cd C:\Users\Fati\projet_BI
venv\Scripts\activate
python -m src.ingestion.02_kafka_producer
```

Terminal 3 — Dashboard :

```bash
cd C:\Users\Fati\projet_BI
venv\Scripts\activate
streamlit run dashboard\app.py
```

---

## 28. Ouvrir Kepler.gl

Aller sur :

```text
https://kepler.gl/demo
```

Importer :

```text
data/exports/kepler_points.geojson
data/exports/dbscan_clusters.geojson
data/exports/risk_routes.geojson
```

---

## 29. Nettoyer le cache pip si manque d’espace

```bash
pip cache purge
```

---

## 30. Supprimer un conteneur bloqué

```bash
docker stop logistics_postgis
docker rm logistics_postgis
```

Puis relancer :

```bash
docker compose up -d
```

---

## 31. Vérifier les tables principales

```bash
docker exec -i logistics_postgis psql -U postgres -d logistics_db -c "\dt"
```

---

## 32. Compter les lignes des tables principales

```bash
docker exec -i logistics_postgis psql -U postgres -d logistics_db -c "SELECT COUNT(*) FROM trips;"
docker exec -i logistics_postgis psql -U postgres -d logistics_db -c "SELECT COUNT(*) FROM gps_positions;"
docker exec -i logistics_postgis psql -U postgres -d logistics_db -c "SELECT COUNT(*) FROM realtime_positions;"
docker exec -i logistics_postgis psql -U postgres -d logistics_db -c "SELECT COUNT(*) FROM dbscan_clusters;"
docker exec -i logistics_postgis psql -U postgres -d logistics_db -c "SELECT COUNT(*) FROM weather_hourly;"
docker exec -i logistics_postgis psql -U postgres -d logistics_db -c "SELECT COUNT(*) FROM route_scores;"
docker exec -i logistics_postgis psql -U postgres -d logistics_db -c "SELECT COUNT(*) FROM forecast_delays;"
docker exec -i logistics_postgis psql -U postgres -d logistics_db -c "SELECT COUNT(*) FROM optimized_routes;"
```

---

## 33. Résumé rapide pour la démonstration

```bash
docker compose up -d

python -m src.analysis.05_dbscan_clustering
python -m src.enrichment.08_weather_openmeteo
python -m src.analysis.06_risk_scoring
python -m src.analysis.09_prophet_forecast
python -m src.analysis.10_route_optimization
python -m src.export.07_export_kepler

streamlit run dashboard\app.py
```

Puis lancer en parallèle :

```bash
python -m src.ingestion.03_kafka_consumer_postgis
python -m src.ingestion.02_kafka_producer
```
