Commandes utiles — Projet logistique géospatial

Aller dans le projetcd C:\Users\Fati\projet_BI

Activer l’environnement Pythonvenv\Scripts\activate

Lancer Dockerdocker compose up -d

Vérifier les conteneurs Dockerdocker psConteneurs attendus :

logistics_postgislogistics_kafkalogistics_zookeeper5. Arrêter Dockerdocker compose down6. Tester la connexion PostGISpython src\test_connection.pyRésultat attendu :

Connexion PostgreSQL/PostGIS OK7. Préparer les données GPSpython src\01_prepare_porto_data.py8. Vérifier les données GPSpython src\check_gps_data.pyRésultat attendu :

Nombre de trajets : 4997Nombre de positions GPS : 124925Nombre de taxis différents : 3049. Vider la table temps réelÀ utiliser avant de relancer une nouvelle simulation Kafka :

docker exec -i logistics_postgis psql -U postgres -d logistics_db -c "TRUNCATE TABLE realtime_positions RESTART IDENTITY;"10. Lancer Kafka ConsumerTerminal 1 :

cd C:\Users\Fati\projet_BIvenv\Scripts\activatepython -m src.ingestion.03_kafka_consumer_postgis11. Lancer Kafka ProducerTerminal 2 :

cd C:\Users\Fati\projet_BIvenv\Scripts\activatepython -m src.ingestion.02_kafka_producer12. Vérifier le nombre de taxis en temps réeldocker exec -i logistics_postgis psql -U postgres -d logistics_db -c "SELECT COUNT(DISTINCT truck_id) FROM realtime_positions;"Résultat attendu progressivement :

153045...30413. Voir les derniers véhicules insérésdocker exec -i logistics_postgis psql -U postgres -d logistics_db -c "SELECT truck_id, status, event_time FROM realtime_positions ORDER BY event_time DESC LIMIT 10;"14. Lancer DBSCANpython -m src.analysis.05_dbscan_clustering15. Vérifier DBSCANpython -m src.analysis.check_dbscan16. Lancer météo Open-Meteopython -m src.enrichment.08_weather_openmeteo17. Vérifier météopython -m src.enrichment.check_weather18. Calculer le score de risquepython -m src.analysis.06_risk_scoring19. Prévoir les retardspython -m src.analysis.09_prophet_forecast20. Vérifier les prévisionspython -m src.analysis.check_forecast21. Optimiser les tournéespython -m src.analysis.10_route_optimization22. Vérifier l’optimisationpython -m src.analysis.check_optimization23. Exporter vers Kepler.glpython -m src.export.07_export_kepler24. Vérifier les exportsdir data\exportsFichiers attendus :

kepler_points.geojsondbscan_clusters.geojsonrisk_routes.geojsonoptimization_report.json25. Lancer le dashboardTerminal 3 :

cd C:\Users\Fati\projet_BIvenv\Scripts\activatestreamlit run dashboard\app.py26. Pipeline complet dans l’ordrecd C:\Users\Fati\projet_BIvenv\Scripts\activate

docker compose up -d

python src\01_prepare_porto_data.pypython -m src.analysis.05_dbscan_clusteringpython -m src.enrichment.08_weather_openmeteopython -m src.analysis.06_risk_scoringpython -m src.analysis.09_prophet_forecastpython -m src.analysis.10_route_optimizationpython -m src.export.07_export_kepler

streamlit run dashboard\app.py27. Lancer la simulation temps réel complèteTerminal 1 — Consumer :

cd C:\Users\Fati\projet_BIvenv\Scripts\activatepython -m src.ingestion.03_kafka_consumer_postgisTerminal 2 — Producer :

cd C:\Users\Fati\projet_BIvenv\Scripts\activatepython -m src.ingestion.02_kafka_producerTerminal 3 — Dashboard :

cd C:\Users\Fati\projet_BIvenv\Scripts\activatestreamlit run dashboard\app.py28. Ouvrir Kepler.glAller sur :

https://kepler.gl/demoImporter :

data/exports/kepler_points.geojsondata/exports/dbscan_clusters.geojsondata/exports/risk_routes.geojson29. Nettoyer le cache pip si manque d’espacepip cache purge30. Supprimer un conteneur bloquédocker stop logistics_postgisdocker rm logistics_postgisPuis relancer :

docker compose up -d31. Vérifier les tables principalesdocker exec -i logistics_postgis psql -U postgres -d logistics_db -c "\dt"32. Compter les lignes des tables principalesdocker exec -i logistics_postgis psql -U postgres -d logistics_db -c "SELECT COUNT() FROM trips;"docker exec -i logistics_postgis psql -U postgres -d logistics_db -c "SELECT COUNT() FROM gps_positions;"docker exec -i logistics_postgis psql -U postgres -d logistics_db -c "SELECT COUNT() FROM realtime_positions;"docker exec -i logistics_postgis psql -U postgres -d logistics_db -c "SELECT COUNT() FROM dbscan_clusters;"docker exec -i logistics_postgis psql -U postgres -d logistics_db -c "SELECT COUNT() FROM weather_hourly;"docker exec -i logistics_postgis psql -U postgres -d logistics_db -c "SELECT COUNT() FROM route_scores;"docker exec -i logistics_postgis psql -U postgres -d logistics_db -c "SELECT COUNT() FROM forecast_delays;"docker exec -i logistics_postgis psql -U postgres -d logistics_db -c "SELECT COUNT() FROM optimized_routes;"33. Résumé rapide pour la démonstrationdocker compose up -d

python -m src.analysis.05_dbscan_clusteringpython -m src.enrichment.08_weather_openmeteopython -m src.analysis.06_risk_scoringpython -m src.analysis.09_prophet_forecastpython -m src.analysis.10_route_optimizationpython -m src.export.07_export_kepler

streamlit run dashboard\app.pyPuis lancer en parallèle :

python -m src.ingestion.03_kafka_consumer_postgispython -m src.ingestion.02_kafka_producer

34. Lancer GeoServer

Vérifier que GeoServer est démarré :

http://localhost:8080/geoserver

Identifiants :

admin
geoserver

Couches publiées :

* gps_positions
* realtime_positions
* dbscan_clusters

35. Tester le service WFS

Ouvrir :

http://localhost:8080/geoserver/logistics/ows?service=WFS&version=1.0.0&request=GetFeature&typeName=logistics:gps_positions&maxFeatures=10&outputFormat=application/json

Résultat attendu :

GeoJSON contenant les positions GPS.

36. Lancer le script automatique temps réel

Double-cliquer :

run_realtime.bat

Le script :

* démarre Docker ;
* vide realtime_positions ;
* lance le Consumer Kafka ;
* lance le Producer Kafka ;
* lance Streamlit.

37. Lancer le recalcul automatique des analyses

Double-cliquer :

run_analytics_loop.bat

Le script recalcule automatiquement :

* DBSCAN ;
* Score de risque ;
* Prévisions ;
* Optimisation.

38. Vérifier le dashboard final

Pages disponibles :

* 🏠 Vue globale
* 📡 Temps réel
* 🚨 Alertes temps réel
* 🗺️ Tournées
* 🔵 Clusters DBSCAN
* 🔥 Heatmap
* ⚠️ Score de risque
* 📊 Prévisions
* 🌧️ Météo Open-Meteo
* 🌍 GeoServer
* 🕒 Isochrones
* 🌐 Export Kepler.gl

39. Démonstration recommandée

Étape 1 :
run_realtime.bat

Étape 2 :
run_analytics_loop.bat

Étape 3 :
Montrer la montée progressive des taxis :

0 → 15 → 30 → 45 → ... → 304

Étape 4 :
Afficher :

* Heatmap
* DBSCAN
* Risques
* Prévisions
* GeoServer
* Isochrones

Étape 5 :
Montrer l’export Kepler.gl.

40. Push GitHub

git add .
git commit -m "Version finale temps réel avec GeoServer, Heatmap et Alertes"
git push
