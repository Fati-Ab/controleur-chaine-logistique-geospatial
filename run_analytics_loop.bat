@echo off
title Recalcul analyses - Projet Logistique

cd /d C:\Users\Fati\projet_BI
call venv\Scripts\activate

:loop
echo ================================
echo Recalcul DBSCAN
echo ================================
python -m src.analysis.05_dbscan_clustering

echo ================================
echo Recalcul Score de risque
echo ================================
python -m src.analysis.06_risk_scoring

echo ================================
echo Recalcul Prévisions
echo ================================
python -m src.analysis.09_prophet_forecast

echo ================================
echo Recalcul Optimisation
echo ================================
python -m src.analysis.10_route_optimization

echo ================================
echo Attente 60 secondes...
echo ================================
timeout /t 60

goto loop
