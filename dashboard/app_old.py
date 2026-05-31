import sys
from pathlib import Path

import pandas as pd
import psycopg2
import plotly.express as px
import streamlit as st


# ============================================================
# CONFIG
# ============================================================

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT_DIR / "src"))

from config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD


st.set_page_config(
    page_title="Système Logistique Porto",
    page_icon="🚚",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ============================================================
# CSS
# ============================================================

CUSTOM_CSS = """
<style>
.stApp {
    background: #070d18;
    color: #e5e7eb;
}

#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

.block-container {
    padding-top: 1.3rem;
    padding-left: 2rem;
    padding-right: 2rem;
    max-width: 100%;
}

section[data-testid="stSidebar"] {
    background: #0d1626;
    border-right: 1px solid #1e293b;
}

section[data-testid="stSidebar"] * {
    color: #dbeafe !important;
}

h1, h2, h3 {
    color: #f8fafc !important;
}

.header-card {
    background: linear-gradient(135deg, #0f172a 0%, #111827 70%);
    border: 1px solid #1e293b;
    border-radius: 18px;
    padding: 20px 24px;
    margin-bottom: 18px;
    box-shadow: 0 10px 30px rgba(0,0,0,0.28);
}

.header-title {
    font-size: 30px;
    font-weight: 850;
    color: #f8fafc;
}

.header-subtitle {
    color: #94a3b8;
    font-size: 14px;
    margin-top: 5px;
}

.badge {
    display: inline-block;
    background: #111827;
    border: 1px solid #253247;
    border-radius: 999px;
    padding: 7px 12px;
    margin-right: 8px;
    color: #bfdbfe;
    font-size: 13px;
    margin-top: 13px;
}

.badge-live {
    background: rgba(16,185,129,0.12);
    border: 1px solid rgba(52,211,153,0.45);
    color: #34d399;
    font-weight: 700;
}

.kpi-card {
    background: #0f172a;
    border: 1px solid #1e293b;
    border-radius: 18px;
    padding: 18px;
    min-height: 130px;
    box-shadow: 0 10px 25px rgba(0,0,0,0.25);
}

.kpi-title {
    color: #93c5fd;
    font-size: 14px;
    margin-bottom: 12px;
    font-weight: 650;
}

.kpi-value {
    font-size: 34px;
    font-weight: 850;
    line-height: 1;
}

.kpi-sub {
    color: #94a3b8;
    font-size: 13px;
    margin-top: 12px;
}

.ok { color: #34d399 !important; }
.warn { color: #f59e0b !important; }
.danger { color: #fb7185 !important; }
.blue { color: #38bdf8 !important; }

.panel-title {
    color: #bfdbfe;
    font-size: 17px;
    font-weight: 800;
    margin-bottom: 10px;
}

.vehicle-card {
    background: #111827;
    border: 1px solid #243246;
    border-radius: 16px;
    padding: 13px;
    margin-bottom: 11px;
}

.vehicle-title {
    color: #f8fafc;
    font-weight: 800;
    font-size: 15px;
    margin-bottom: 8px;
}

.vehicle-info {
    color: #94a3b8;
    font-size: 12.5px;
    margin-top: 4px;
}

.progress-bar-bg {
    height: 6px;
    width: 100%;
    background: #1e293b;
    border-radius: 999px;
    margin-top: 9px;
    overflow: hidden;
}

.progress-bar-fill {
    height: 6px;
    background: linear-gradient(90deg, #22c55e, #38bdf8);
    border-radius: 999px;
}

.sidebar-brand {
    font-size: 22px;
    font-weight: 850;
    color: #f8fafc;
}

.sidebar-sub {
    color: #93c5fd;
    font-size: 14px;
    font-weight: 700;
}

div[data-testid="stDataFrame"] {
    background: #0f172a;
    border-radius: 16px;
}
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ============================================================
# DATABASE
# ============================================================

def get_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )


def read_sql(query):
    conn = get_connection()
    df = pd.read_sql(query, conn)
    conn.close()
    return df


# ============================================================
# LOADERS
# ============================================================

def load_latest_positions():
    query = """
    SELECT DISTINCT ON (truck_id)
        truck_id,
        trip_id,
        latitude,
        longitude,
        speed,
        progress,
        estimated_delay_minutes,
        rain,
        route_risk_score,
        status,
        event_time
    FROM realtime_positions
    ORDER BY truck_id, event_time DESC
    LIMIT 304;
    """
    return read_sql(query)


def load_dbscan_clusters():
    query = """
    SELECT latitude, longitude, cluster_id, cluster_type
    FROM dbscan_clusters
    WHERE cluster_id <> -1
    LIMIT 1000;
    """
    return read_sql(query)


def load_dbscan_stats():
    query = """
    SELECT cluster_id, COUNT(*) AS nb_points
    FROM dbscan_clusters
    WHERE cluster_id <> -1
    GROUP BY cluster_id
    ORDER BY nb_points DESC;
    """
    return read_sql(query)


def load_risk_summary():
    query = """
    SELECT
        risk_level,
        COUNT(*) AS nb_trips,
        ROUND(AVG(risk_score)::numeric, 2) AS avg_score,
        ROUND(AVG(estimated_delay_minutes)::numeric, 2) AS avg_delay,
        ROUND(AVG(rain_mm)::numeric, 2) AS avg_rain,
        ROUND(AVG(wind_speed_kmh)::numeric, 2) AS avg_wind
    FROM route_scores
    GROUP BY risk_level
    ORDER BY
        CASE risk_level
            WHEN 'LOW' THEN 1
            WHEN 'MEDIUM' THEN 2
            WHEN 'HIGH' THEN 3
            WHEN 'CRITICAL' THEN 4
            ELSE 5
        END;
    """
    return read_sql(query)


def load_top_risky_routes():
    query = """
    SELECT
        trip_id,
        taxi_id,
        distance_km,
        duration_min,
        estimated_delay_minutes,
        rain_mm,
        wind_speed_kmh,
        congestion_flag,
        risk_score,
        risk_level
    FROM route_scores
    ORDER BY risk_score DESC
    LIMIT 20;
    """
    return read_sql(query)


def load_weather_summary():
    query = """
    SELECT
        COUNT(*) AS nb_hours,
        ROUND(AVG(temperature_2m)::numeric, 2) AS avg_temp,
        ROUND(AVG(rain)::numeric, 2) AS avg_rain,
        ROUND(MAX(rain)::numeric, 2) AS max_rain,
        ROUND(AVG(wind_speed_10m)::numeric, 2) AS avg_wind,
        ROUND(AVG(relative_humidity_2m)::numeric, 2) AS avg_humidity
    FROM weather_hourly;
    """
    return read_sql(query)


def load_weather_hourly():
    query = """
    SELECT
        weather_time,
        temperature_2m,
        rain,
        precipitation,
        wind_speed_10m,
        relative_humidity_2m
    FROM weather_hourly
    ORDER BY weather_time;
    """
    return read_sql(query)


def load_forecast_delays():
    query = """
    SELECT
        forecast_time,
        predicted_delay,
        lower_bound,
        upper_bound,
        model_name
    FROM forecast_delays
    ORDER BY forecast_time;
    """
    return read_sql(query)


def load_optimization_summary():
    query = """
    SELECT
        COUNT(*) AS total_routes,
        ROUND(SUM(distance_before_km)::numeric, 2) AS distance_before,
        ROUND(SUM(distance_after_km)::numeric, 2) AS distance_after,
        ROUND(SUM(savings_km)::numeric, 2) AS savings_km,
        ROUND(SUM(delay_before_min)::numeric, 2) AS delay_before,
        ROUND(SUM(delay_after_min)::numeric, 2) AS delay_after,
        ROUND(SUM(savings_cost)::numeric, 2) AS savings_cost
    FROM optimized_routes;
    """
    return read_sql(query)


def load_optimization_by_risk():
    query = """
    SELECT
        risk_level,
        COUNT(*) AS nb_routes,
        ROUND(SUM(distance_before_km)::numeric, 2) AS distance_before,
        ROUND(SUM(distance_after_km)::numeric, 2) AS distance_after,
        ROUND(SUM(savings_km)::numeric, 2) AS savings_km,
        ROUND(SUM(savings_cost)::numeric, 2) AS savings_cost
    FROM optimized_routes
    GROUP BY risk_level
    ORDER BY
        CASE risk_level
            WHEN 'LOW' THEN 1
            WHEN 'MEDIUM' THEN 2
            WHEN 'HIGH' THEN 3
            WHEN 'CRITICAL' THEN 4
            ELSE 5
        END;
    """
    return read_sql(query)


def load_top_optimized_routes():
    query = """
    SELECT
        trip_id,
        taxi_id,
        distance_before_km,
        distance_after_km,
        savings_km,
        delay_before_min,
        delay_after_min,
        savings_cost,
        risk_score,
        risk_level
    FROM optimized_routes
    ORDER BY savings_cost DESC
    LIMIT 20;
    """
    return read_sql(query)


def load_global_stats():
    query = """
    SELECT
        (SELECT COUNT(*) FROM gps_positions) AS total_gps_points,
        (SELECT COUNT(*) FROM trips) AS total_trips,
        (SELECT COUNT(DISTINCT taxi_id) FROM gps_positions) AS total_taxis,
        (SELECT COUNT(*) FROM dbscan_clusters WHERE cluster_id <> -1) AS total_cluster_points;
    """
    return read_sql(query)


# ============================================================
# UI HELPERS
# ============================================================

def render_header(title, subtitle, icon="🚚"):
    st.markdown(f"""
    <div class="header-card">
        <div class="header-title">{icon} {title}</div>
        <div class="header-subtitle">{subtitle}</div>
        <span class="badge">dataset: porto_january_2014.csv</span>
        <span class="badge">source: 304 taxis</span>
        <span class="badge">topic: gps_positions</span>
        <span class="badge">db: logistics_db</span>
        <span class="badge">PostGIS</span>
        <span class="badge badge-live">● KAFKA LIVE</span>
    </div>
    """, unsafe_allow_html=True)


def kpi(title, value, sub="", color_class="blue"):
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-title">{title}</div>
        <div class="kpi-value {color_class}">{value}</div>
        <div class="kpi-sub">{sub}</div>
    </div>
    """, unsafe_allow_html=True)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    st.markdown("""
    <div class="sidebar-brand">🚚 SYSTÈME LOGISTIQUE</div>
    <div class="sidebar-sub">PORTO</div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    page = st.radio(
        "NAVIGATION",
        [
            "📡 Temps réel",
            "🗺️ Tournées",
            "🔵 Clusters DBSCAN",
            "⚠️ Score de risque",
            "📊 Prévisions Prophet",
            "🌧️ Météo Open-Meteo",
            "🌐 Export Kepler.gl"
        ]
    )

    st.markdown("---")
    st.markdown("**Dataset :** porto_january_2014.csv")
    st.markdown("**Source :** 304 taxis réels")
    st.markdown("**Flux temps réel :** 304 taxis")
    st.markdown("**Topic Kafka :** gps_positions")
    st.markdown("**DB :** logistics_db")
    st.markdown("🟢 **Système opérationnel**")


# ============================================================
# PAGE 1 — TEMPS RÉEL
# ============================================================

if page == "📡 Temps réel":
    render_header(
        "SYSTÈME LOGISTIQUE - PORTO",
        "Supervision temps réel simulée avec Kafka, PostGIS et Streamlit",
        "🚚"
    )

    try:
        df = load_latest_positions()
        clusters_df = load_dbscan_clusters()
    except Exception as e:
        st.error(f"Erreur de chargement : {e}")
        st.stop()

    if df.empty:
        st.warning("Aucune donnée temps réel. Lance le consumer puis le producer Kafka.")
        st.stop()

    active_trucks = df["truck_id"].nunique()
    avg_delay = round(df["estimated_delay_minutes"].mean(), 1)
    avg_rain = round(df["rain"].mean(), 1)
    max_risk = round(df["route_risk_score"].max(), 1)
    ok_count = int((df["status"] == "OK").sum())

    c1, c2, c3, c4, c5 = st.columns(5)

    with c1:
        kpi("🚚 Taxis actifs", active_trucks, "sur 304 taxis", "blue")

    with c2:
        kpi("⏱️ Retard moyen", avg_delay, "minutes", "warn")

    with c3:
        kpi("🌧️ Pluie moyenne", avg_rain, "mm", "blue")

    with c4:
        risk_color = "danger" if max_risk >= 10 else "warn"
        kpi("⚠️ Risque max", max_risk, "score maximum", risk_color)

    with c5:
        kpi("✅ Statut OK", ok_count, f"sur {active_trucks} taxis", "ok")

    st.markdown("")

    map_col, side_col = st.columns([3.2, 1.05])

    with map_col:
        st.markdown(
            '<div class="panel-title">📍 Carte temps réel — 304 taxis GPS</div>',
            unsafe_allow_html=True
        )

        fig = px.scatter_mapbox(
            df,
            lat="latitude",
            lon="longitude",
            color="status",
            size="route_risk_score",
            hover_data={
                "truck_id": True,
                "trip_id": True,
                "speed": True,
                "progress": True,
                "estimated_delay_minutes": True,
                "rain": True,
                "route_risk_score": True,
                "latitude": False,
                "longitude": False
            },
            zoom=11,
            height=650,
            center={"lat": 41.1579, "lon": -8.6291},
            mapbox_style="carto-darkmatter"
        )

        if not clusters_df.empty:
            fig.add_scattermapbox(
                lat=clusters_df["latitude"],
                lon=clusters_df["longitude"],
                mode="markers",
                name="Zones DBSCAN",
                marker=dict(size=6, opacity=0.22),
                text=clusters_df["cluster_id"],
                hovertemplate="Cluster DBSCAN : %{text}<extra></extra>"
            )

        fig.update_layout(
            margin=dict(l=0, r=0, t=0, b=0),
            paper_bgcolor="#070d18",
            plot_bgcolor="#070d18",
            font=dict(color="#e5e7eb"),
            legend=dict(
                bgcolor="#0f172a",
                bordercolor="#1e293b",
                borderwidth=1
            )
        )

        st.plotly_chart(fig, use_container_width=True)

    with side_col:
        st.markdown(
            '<div class="panel-title">🚚 Véhicules actifs</div>',
            unsafe_allow_html=True
        )

        st.caption("Affichage détaillé limité aux 25 premiers taxis pour garder l’interface fluide.")

        for _, row in df.head(25).iterrows():
            status_icon = "🟢" if row["status"] == "OK" else "🟠" if row["status"] == "WARNING" else "🔴"
            delay_class = "ok" if row["estimated_delay_minutes"] == 0 else "warn"
            progress = int(row["progress"])

            st.markdown(f"""
            <div class="vehicle-card">
                <div class="vehicle-title">{status_icon} {row["truck_id"]}</div>
                <div class="vehicle-info">Vitesse : {row["speed"]} km/h</div>
                <div class="vehicle-info">Retard : <span class="{delay_class}">{row["estimated_delay_minutes"]} min</span></div>
                <div class="vehicle-info">Risque : {row["route_risk_score"]}</div>
                <div class="progress-bar-bg">
                    <div class="progress-bar-fill" style="width:{progress}%"></div>
                </div>
                <div class="vehicle-info">Progression : {progress}%</div>
            </div>
            """, unsafe_allow_html=True)

    st.info("304 taxis affichés sur la carte. Rafraîchissement manuel pour éviter le blocage.")

    if st.button("🔄 Actualiser les 304 taxis"):
        st.rerun()


# ============================================================
# PAGE 2 — TOURNÉES
# ============================================================

elif page == "🗺️ Tournées":
    render_header(
        "Optimisation des tournées",
        "Comparaison avant/après optimisation des routes",
        "🗺️"
    )

    try:
        summary_df = load_optimization_summary()
        risk_df = load_optimization_by_risk()
        top_df = load_top_optimized_routes()
    except Exception as e:
        st.error(f"Erreur optimisation : {e}")
        st.warning("Lance : python -m src.analysis.10_route_optimization")
        st.stop()

    if summary_df.empty or summary_df.iloc[0]["total_routes"] == 0:
        st.warning("Aucune optimisation disponible.")
        st.stop()

    total_routes = int(summary_df.iloc[0]["total_routes"])
    distance_before = float(summary_df.iloc[0]["distance_before"])
    distance_after = float(summary_df.iloc[0]["distance_after"])
    savings_km = float(summary_df.iloc[0]["savings_km"])
    delay_before = float(summary_df.iloc[0]["delay_before"])
    delay_after = float(summary_df.iloc[0]["delay_after"])
    savings_cost = float(summary_df.iloc[0]["savings_cost"])

    savings_percent = round((savings_km / distance_before) * 100, 2) if distance_before else 0
    delay_saved = round(delay_before - delay_after, 2)
    monthly_savings = round(savings_cost * 22, 2)

    c1, c2, c3, c4, c5 = st.columns(5)

    with c1:
        kpi("🛣️ Routes optimisées", total_routes, "trajets", "blue")

    with c2:
        kpi("📉 Distance économisée", savings_km, "km", "ok")

    with c3:
        kpi("📊 Gain distance", f"{savings_percent}%", "réduction", "ok")

    with c4:
        kpi("⏱️ Temps gagné", delay_saved, "minutes", "warn")

    with c5:
        kpi("💶 Économie mensuelle", monthly_savings, "€/mois estimés", "ok")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Distance avant/après")

        comparison_df = pd.DataFrame({
            "état": ["Avant optimisation", "Après optimisation"],
            "distance_km": [distance_before, distance_after]
        })

        fig = px.bar(
            comparison_df,
            x="état",
            y="distance_km",
            text="distance_km",
            height=420
        )

        fig.update_layout(
            paper_bgcolor="#070d18",
            plot_bgcolor="#070d18",
            font=dict(color="#e5e7eb"),
            xaxis_title="",
            yaxis_title="Distance km"
        )

        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("### Économies par niveau de risque")

        fig = px.bar(
            risk_df,
            x="risk_level",
            y="savings_cost",
            text="savings_cost",
            hover_data=["nb_routes", "savings_km"],
            height=420
        )

        fig.update_layout(
            paper_bgcolor="#070d18",
            plot_bgcolor="#070d18",
            font=dict(color="#e5e7eb"),
            xaxis_title="Risque",
            yaxis_title="Économie €"
        )

        st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Top 20 routes les plus rentables")
    st.dataframe(top_df, use_container_width=True)


# ============================================================
# PAGE 3 — DBSCAN
# ============================================================

elif page == "🔵 Clusters DBSCAN":
    render_header(
        "Clusters DBSCAN",
        "Détection automatique des zones denses",
        "🔵"
    )

    try:
        clusters_df = load_dbscan_clusters()
        stats_df = load_dbscan_stats()
    except Exception as e:
        st.error(f"Erreur DBSCAN : {e}")
        st.warning("Lance : python -m src.analysis.05_dbscan_clustering")
        st.stop()

    if clusters_df.empty or stats_df.empty:
        st.warning("Aucun cluster disponible.")
        st.stop()

    main_cluster = int(stats_df.iloc[0]["cluster_id"])
    main_count = int(stats_df.iloc[0]["nb_points"])

    c1, c2, c3 = st.columns(3)

    with c1:
        kpi("🔵 Clusters détectés", stats_df["cluster_id"].nunique(), "zones", "blue")

    with c2:
        kpi("📍 Points affichés", len(clusters_df), "limité pour fluidité", "blue")

    with c3:
        kpi("⚠️ Zone principale", main_cluster, f"{main_count} points", "danger")

    col1, col2 = st.columns([2.2, 1])

    with col1:
        fig = px.scatter_mapbox(
            clusters_df,
            lat="latitude",
            lon="longitude",
            color="cluster_id",
            hover_data=["cluster_id", "cluster_type"],
            zoom=11,
            height=620,
            center={"lat": 41.1579, "lon": -8.6291},
            mapbox_style="carto-darkmatter"
        )

        fig.update_layout(
            margin=dict(l=0, r=0, t=0, b=0),
            paper_bgcolor="#070d18",
            plot_bgcolor="#070d18",
            font=dict(color="#e5e7eb")
        )

        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("### Statistiques")
        st.dataframe(stats_df, use_container_width=True)


# ============================================================
# PAGE 4 — SCORE DE RISQUE
# ============================================================

elif page == "⚠️ Score de risque":
    render_header(
        "Score de risque logistique",
        "Retard + météo réelle + congestion DBSCAN",
        "⚠️"
    )

    try:
        summary_df = load_risk_summary()
        top_routes_df = load_top_risky_routes()
    except Exception as e:
        st.error(f"Erreur score : {e}")
        st.warning("Lance : python -m src.analysis.06_risk_scoring")
        st.stop()

    if summary_df.empty:
        st.warning("Aucun score disponible.")
        st.stop()

    total_routes = int(summary_df["nb_trips"].sum())
    avg_score = round((summary_df["avg_score"] * summary_df["nb_trips"]).sum() / total_routes, 2)
    high_count = int(summary_df[summary_df["risk_level"].isin(["HIGH", "CRITICAL"])]["nb_trips"].sum())
    high_percent = round((high_count / total_routes) * 100, 1)

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        kpi("🛣️ Trajets scorés", total_routes, "route_scores", "blue")

    with c2:
        kpi("⚠️ Score moyen", avg_score, "risque global", "warn")

    with c3:
        kpi("🔥 Trajets risqués", high_count, "HIGH / CRITICAL", "danger")

    with c4:
        kpi("📊 Risque élevé", f"{high_percent}%", "du total", "danger")

    col1, col2 = st.columns([1.1, 1])

    with col1:
        fig = px.bar(
            summary_df,
            x="risk_level",
            y="nb_trips",
            text="nb_trips",
            hover_data=["avg_score", "avg_delay", "avg_rain", "avg_wind"],
            height=420
        )

        fig.update_layout(
            paper_bgcolor="#070d18",
            plot_bgcolor="#070d18",
            font=dict(color="#e5e7eb"),
            xaxis_title="Niveau",
            yaxis_title="Trajets"
        )

        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("### Top trajets risqués")
        st.dataframe(top_routes_df, use_container_width=True)


# ============================================================
# PAGE 5 — PRÉVISIONS
# ============================================================

elif page == "📊 Prévisions Prophet":
    render_header(
        "Prévisions des retards",
        "Anticipation des retards futurs",
        "📊"
    )

    try:
        forecast_df = load_forecast_delays()
    except Exception as e:
        st.error(f"Erreur prévision : {e}")
        st.warning("Lance : python -m src.analysis.09_prophet_forecast")
        st.stop()

    if forecast_df.empty:
        st.warning("Aucune prévision disponible.")
        st.stop()

    avg_pred = round(forecast_df["predicted_delay"].mean(), 2)
    max_pred = round(forecast_df["predicted_delay"].max(), 2)
    model_name = forecast_df.iloc[0]["model_name"]

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        kpi("🕒 Horizon", len(forecast_df), "heures prévues", "blue")

    with c2:
        kpi("⏱️ Retard moyen", avg_pred, "minutes", "warn")

    with c3:
        kpi("🔥 Pic prévu", max_pred, "minutes max", "danger")

    with c4:
        kpi("🧠 Modèle", "OK", model_name, "ok")

    fig = px.line(
        forecast_df,
        x="forecast_time",
        y=["predicted_delay", "lower_bound", "upper_bound"],
        height=500,
        title="Prévision des retards"
    )

    fig.update_layout(
        paper_bgcolor="#070d18",
        plot_bgcolor="#070d18",
        font=dict(color="#e5e7eb"),
        xaxis_title="Temps",
        yaxis_title="Minutes"
    )

    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(forecast_df, use_container_width=True)


# ============================================================
# PAGE 6 — MÉTÉO
# ============================================================

elif page == "🌧️ Météo Open-Meteo":
    render_header(
        "Météo Open-Meteo",
        "Données météo réelles intégrées au score de risque",
        "🌧️"
    )

    try:
        weather_summary = load_weather_summary()
        weather_df = load_weather_hourly()
    except Exception as e:
        st.error(f"Erreur météo : {e}")
        st.warning("Lance : python -m src.enrichment.08_weather_openmeteo")
        st.stop()

    if weather_df.empty:
        st.warning("Aucune météo disponible.")
        st.stop()

    nb_hours = int(weather_summary.iloc[0]["nb_hours"])
    avg_temp = float(weather_summary.iloc[0]["avg_temp"])
    avg_rain = float(weather_summary.iloc[0]["avg_rain"])
    max_rain = float(weather_summary.iloc[0]["max_rain"])
    avg_wind = float(weather_summary.iloc[0]["avg_wind"])

    c1, c2, c3, c4, c5 = st.columns(5)

    with c1:
        kpi("🕒 Heures météo", nb_hours, "données horaires", "blue")

    with c2:
        kpi("🌡️ Température", avg_temp, "°C moyenne", "blue")

    with c3:
        kpi("🌧️ Pluie moyenne", avg_rain, "mm", "blue")

    with c4:
        kpi("⛈️ Pluie max", max_rain, "mm", "danger")

    with c5:
        kpi("💨 Vent moyen", avg_wind, "km/h", "warn")

    col1, col2 = st.columns(2)

    with col1:
        fig = px.line(
            weather_df,
            x="weather_time",
            y="rain",
            height=420,
            title="Pluie horaire à Porto"
        )

        fig.update_layout(
            paper_bgcolor="#070d18",
            plot_bgcolor="#070d18",
            font=dict(color="#e5e7eb"),
            xaxis_title="Temps",
            yaxis_title="Pluie mm"
        )

        st.plotly_chart(fig, use_container_width=True)

    with col2:
        fig = px.line(
            weather_df,
            x="weather_time",
            y=["temperature_2m", "wind_speed_10m", "relative_humidity_2m"],
            height=420,
            title="Température, vent, humidité"
        )

        fig.update_layout(
            paper_bgcolor="#070d18",
            plot_bgcolor="#070d18",
            font=dict(color="#e5e7eb"),
            xaxis_title="Temps",
            yaxis_title="Valeur"
        )

        st.plotly_chart(fig, use_container_width=True)

    st.dataframe(weather_df, use_container_width=True)


# ============================================================
# PAGE 7 — KEPLER
# ============================================================

elif page == "🌐 Export Kepler.gl":
    render_header(
        "Export Kepler.gl",
        "Export des couches géospatiales PostGIS vers GeoJSON",
        "🌐"
    )

    exports_path = ROOT_DIR / "data" / "exports"

    file_points = exports_path / "kepler_points.geojson"
    file_clusters = exports_path / "dbscan_clusters.geojson"
    file_routes = exports_path / "risk_routes.geojson"

    st.markdown("""
    Cette page vérifie les fichiers GeoJSON générés pour Kepler.gl :
    positions GPS, clusters DBSCAN et routes avec score de risque.
    """)

    c1, c2, c3 = st.columns(3)

    with c1:
        kpi(
            "📍 Points GPS",
            "✅" if file_points.exists() else "❌",
            "kepler_points.geojson",
            "ok" if file_points.exists() else "danger"
        )

    with c2:
        kpi(
            "🔵 DBSCAN",
            "✅" if file_clusters.exists() else "❌",
            "dbscan_clusters.geojson",
            "ok" if file_clusters.exists() else "danger"
        )

    with c3:
        kpi(
            "⚠️ Routes risque",
            "✅" if file_routes.exists() else "❌",
            "risk_routes.geojson",
            "ok" if file_routes.exists() else "danger"
        )

    st.markdown("### Commande d’export")
    st.code("python -m src.export.07_export_kepler", language="bash")

    st.markdown("### Fichiers générés")

    if exports_path.exists():
        files = list(exports_path.glob("*.geojson"))

        if files:
            for file in files:
                st.write(f"✅ `{file.name}`")
        else:
            st.warning("Aucun fichier GeoJSON trouvé.")
    else:
        st.warning("Le dossier data/exports n’existe pas.")

    st.markdown("### Utilisation")
    st.markdown("""
    Importer les fichiers `.geojson` dans Kepler.gl :
    - points GPS ;
    - clusters DBSCAN ;
    - routes colorées par `risk_level`.
    """)


else:
    st.error("Page inconnue.")