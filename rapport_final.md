# Rapport final — Système intelligent d’optimisation logistique avec géospatial analytics

## 1. Introduction

Ce projet consiste à développer un système intelligent de supervision et d’optimisation logistique basé sur des données GPS réelles.  
L’objectif est de permettre à un transporteur de suivre ses véhicules, d’identifier les zones critiques, d’anticiper les retards et d’optimiser les tournées.

Le projet combine le streaming de données, le stockage géospatial, l’analyse spatiale, l’enrichissement météo, la prédiction des retards et la visualisation interactive.

---

## 2. Contexte

Un transporteur logistique souhaite optimiser ses tournées et surveiller les retards.  
Les véhicules génèrent des positions GPS qui peuvent être utilisées pour comprendre les déplacements, détecter les zones denses et améliorer la planification.

Les principaux problèmes traités sont :

- suivi en temps réel des véhicules ;
- détection des zones de congestion ;
- impact de la météo sur les retards ;
- prédiction des retards futurs ;
- optimisation des trajets ;
- visualisation des résultats sur cartes interactives.

---

## 3. Objectifs du projet

Les objectifs du projet sont :

- utiliser un dataset GPS réel ;
- simuler un flux temps réel avec Kafka ;
- stocker les positions dans PostgreSQL/PostGIS ;
- visualiser les positions GPS dans un dashboard ;
- détecter les clusters de trajectoires avec DBSCAN ;
- enrichir les trajets avec la météo Open-Meteo ;
- calculer un score de risque ;
- prévoir les retards futurs ;
- comparer les tournées avant et après optimisation ;
- exporter les données vers Kepler.gl.

---

## 4. Données utilisées

Le projet utilise un fichier CSV basé sur des trajets de taxis à Porto.

Le fichier utilisé est :

```text
porto_january_2014.csv