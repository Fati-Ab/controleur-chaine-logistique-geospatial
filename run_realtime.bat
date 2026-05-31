@echo off
title Projet Logistique Temps Reel

cd /d C:\Users\Fati\projet_BI

call venv\Scripts\activate

echo ==========================
echo Demarrage Docker
echo ==========================
docker compose up -d

echo ==========================
echo Reset realtime_positions
echo ==========================
python -c "import psycopg2; from src.config import DB_HOST,DB_PORT,DB_NAME,DB_USER,DB_PASSWORD; conn=psycopg2.connect(host=DB_HOST,port=DB_PORT,database=DB_NAME,user=DB_USER,password=DB_PASSWORD); cur=conn.cursor(); cur.execute('TRUNCATE TABLE realtime_positions RESTART IDENTITY;'); conn.commit(); cur.close(); conn.close(); print('Table videe')"

echo ==========================
echo Lancement Consumer
echo ==========================
start cmd /k "cd /d C:\Users\Fati\projet_BI && call venv\Scripts\activate && python -m src.ingestion.03_kafka_consumer_postgis"

timeout /t 5

echo ==========================
echo Lancement Producer
echo ==========================
start cmd /k "cd /d C:\Users\Fati\projet_BI && call venv\Scripts\activate && python -m src.ingestion.02_kafka_producer"

timeout /t 3

echo ==========================
echo Lancement Streamlit
echo ==========================
start cmd /k "cd /d C:\Users\Fati\projet_BI && call venv\Scripts\activate && streamlit run dashboard\app.py"

echo.
echo Projet lance avec succes
pause