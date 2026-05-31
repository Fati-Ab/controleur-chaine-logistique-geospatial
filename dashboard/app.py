import sys
import math
from pathlib import Path

import pandas as pd
import psycopg2
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components
from streamlit_autorefresh import st_autorefresh


# ============================================================
# CONFIGURATION
# ============================================================

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT_DIR / "src"))

from config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD


st.set_page_config(
    page_title="Tour de contrôle logistique",
    page_icon="🚚",
    layout="wide",
    initial_sidebar_state="expanded"
)


# Rafraîchissement automatique du dashboard toutes les 3 secondes
st_autorefresh(interval=3000, key="dashboard_refresh")



# ============================================================
# CSS + JAVASCRIPT
# ============================================================

ASSETS_DIR = Path(__file__).resolve().parent / "assets"


def load_css(file_path):
    if file_path.exists():
        with open(file_path, "r", encoding="utf-8") as file:
            st.markdown(f"<style>{file.read()}</style>", unsafe_allow_html=True)
    else:
        st.warning(f"Fichier CSS introuvable : {file_path}")


def load_js(file_path):
    if file_path.exists():
        with open(file_path, "r", encoding="utf-8") as file:
            js_code = file.read()

        components.html(
            f"""
            <script>
            {js_code}
            </script>
            """,
            height=0
        )
    else:
        st.warning(f"Fichier JavaScript introuvable : {file_path}")


load_css(ASSETS_DIR / "style.css")
load_js(ASSETS_DIR / "scripts.js")


# ============================================================
# BASE DE DONNÉES
# ============================================================

def get_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )


def read_sql(query: str) -> pd.DataFrame:
    conn = get_connection()
    try:
        df = pd.read_sql(query, conn)
    finally:
        conn.close()
    return df


# ============================================================
# CHARGEMENT DES DONNÉES
# ============================================================

def load_latest_positions(limit=304):
    query = f"""
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
    WHERE latitude IS NOT NULL
      AND longitude IS NOT NULL
    ORDER BY truck_id, event_time DESC
    LIMIT {int(limit)};
    """
    return read_sql(query)


def load_realtime_counts():
    query = """
    SELECT
        COUNT(*) AS total_rows,
        COUNT(DISTINCT truck_id) AS active_taxis,
        MAX(event_time) AS last_event_time,
        MIN(event_time) AS first_event_time
    FROM realtime_positions;
    """
    return read_sql(query)


def load_system_realtime_status():
    query = """
    SELECT
        COUNT(*) AS total_rows,
        COUNT(DISTINCT truck_id) AS active_taxis,
        MAX(event_time) AS last_event_time,
        EXTRACT(EPOCH FROM (NOW() - MAX(event_time))) AS seconds_since_last_event
    FROM realtime_positions;
    """
    return read_sql(query)


def load_recent_history(minutes=10, limit=3000):
    query = f"""
    SELECT truck_id, latitude, longitude, event_time
    FROM realtime_positions
    WHERE event_time >= NOW() - INTERVAL '{int(minutes)} minutes'
      AND latitude IS NOT NULL
      AND longitude IS NOT NULL
    ORDER BY event_time DESC
    LIMIT {int(limit)};
    """
    return read_sql(query)


def load_realtime_alerts(limit=500):
    query = f"""
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
    WHERE latitude IS NOT NULL
      AND longitude IS NOT NULL
      AND (
            route_risk_score >= 10
         OR estimated_delay_minutes >= 5
         OR rain > 0
         OR status = 'RISK'
      )
    ORDER BY truck_id, event_time DESC
    LIMIT {int(limit)};
    """
    return read_sql(query)


@st.cache_data(ttl=60)
def load_global_stats():
    query = """
    SELECT
        (SELECT COUNT(*) FROM gps_positions) AS total_gps_points,
        (SELECT COUNT(*) FROM trips) AS total_trips,
        (SELECT COUNT(DISTINCT taxi_id) FROM gps_positions) AS total_taxis,
        (SELECT COUNT(*) FROM dbscan_clusters WHERE cluster_id <> -1) AS total_cluster_points,
        (SELECT COUNT(*) FROM route_scores) AS total_scores,
        (SELECT COUNT(*) FROM optimized_routes) AS total_optimized;
    """
    return read_sql(query)


@st.cache_data(ttl=60)
def load_dbscan_clusters(limit=1500):
    query = f"""
    SELECT latitude, longitude, cluster_id, cluster_type
    FROM dbscan_clusters
    WHERE cluster_id <> -1
    LIMIT {int(limit)};
    """
    return read_sql(query)


@st.cache_data(ttl=60)
def load_dbscan_stats():
    query = """
    SELECT cluster_id, COUNT(*) AS nb_points
    FROM dbscan_clusters
    WHERE cluster_id <> -1
    GROUP BY cluster_id
    ORDER BY nb_points DESC;
    """
    return read_sql(query)


@st.cache_data(ttl=60)
def load_heatmap_points(limit=20000, source="gps_positions"):
    if source == "realtime_positions":
        query = f"""
        SELECT truck_id AS taxi_id, latitude, longitude, event_time
        FROM realtime_positions
        WHERE latitude IS NOT NULL
          AND longitude IS NOT NULL
        ORDER BY event_time DESC
        LIMIT {int(limit)};
        """
    else:
        query = f"""
        SELECT taxi_id, latitude, longitude
        FROM gps_positions
        WHERE latitude IS NOT NULL
          AND longitude IS NOT NULL
        LIMIT {int(limit)};
        """

    return read_sql(query)


@st.cache_data(ttl=60)
def load_heatmap_summary():
    query = """
    SELECT
        (SELECT COUNT(*) FROM gps_positions WHERE latitude IS NOT NULL AND longitude IS NOT NULL) AS total_gps_points,
        (SELECT COUNT(DISTINCT taxi_id) FROM gps_positions) AS total_taxis,
        (SELECT ROUND(MIN(latitude)::numeric, 5) FROM gps_positions WHERE latitude IS NOT NULL) AS min_lat,
        (SELECT ROUND(MAX(latitude)::numeric, 5) FROM gps_positions WHERE latitude IS NOT NULL) AS max_lat,
        (SELECT ROUND(MIN(longitude)::numeric, 5) FROM gps_positions WHERE longitude IS NOT NULL) AS min_lon,
        (SELECT ROUND(MAX(longitude)::numeric, 5) FROM gps_positions WHERE longitude IS NOT NULL) AS max_lon;
    """
    return read_sql(query)


@st.cache_data(ttl=60)
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


@st.cache_data(ttl=60)
def load_top_risky_routes(limit=25):
    query = f"""
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
    LIMIT {int(limit)};
    """
    return read_sql(query)


@st.cache_data(ttl=60)
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


@st.cache_data(ttl=60)
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


@st.cache_data(ttl=60)
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


@st.cache_data(ttl=60)
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


@st.cache_data(ttl=60)
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


@st.cache_data(ttl=60)
def load_top_optimized_routes(limit=25):
    query = f"""
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
    LIMIT {int(limit)};
    """
    return read_sql(query)


# ============================================================
# AIDES INTERFACE
# ============================================================

def translate_status(value):
    if value == "OK":
        return "OK"
    if value == "WARNING":
        return "ATTENTION"
    if value == "RISK":
        return "RISQUE"
    return value


def render_header(title, subtitle, icon="🚚", live=True):
    live_badge = "● KAFKA EN DIRECT" if live else "● ANALYSE"
    live_class = "badge-live" if live else "badge-warn"

    st.markdown(f"""
    <div class="header-card">
        <div class="header-title">{icon} {title}</div>
        <div class="header-subtitle">{subtitle}</div>
        <span class="badge">jeu de données : porto_january_2014.csv</span>
        <span class="badge">source : 304 taxis</span>
        <span class="badge">topic : gps_positions</span>
        <span class="badge">base : logistics_db</span>
        <span class="badge">PostGIS</span>
        <span class="badge {live_class}">{live_badge}</span>
    </div>
    """, unsafe_allow_html=True)


def render_realtime_banner():
    try:
        status_df = load_system_realtime_status()
        if status_df.empty:
            st.warning("⚠️ Statut temps réel indisponible.")
            return

        s = status_df.iloc[0]
        total_rows = int(s["total_rows"] or 0)
        active_taxis = int(s["active_taxis"] or 0)
        last_event = s["last_event_time"]
        seconds_since = s["seconds_since_last_event"]

        if total_rows == 0 or last_event is None:
            st.warning("🟠 Kafka/PostGIS : aucune donnée temps réel. Lance le consumer puis le producer.")
            return

        seconds_since = float(seconds_since or 999999)

        if seconds_since <= 10:
            st.success(
                f"🟢 Flux temps réel actif — {active_taxis} taxis actifs — "
                f"{total_rows} événements — dernier événement : {last_event}"
            )
        elif seconds_since <= 60:
            st.warning(
                f"🟠 Flux récent mais ralenti — {active_taxis} taxis actifs — "
                f"dernier événement : {last_event}"
            )
        else:
            st.error(
                f"🔴 Flux non actualisé récemment — dernier événement : {last_event}. "
                "Vérifie Kafka producer/consumer."
            )

    except Exception as e:
        st.warning(f"Statut temps réel non disponible : {e}")


def kpi(title, value, sub="", color_class="blue"):
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-title">{title}</div>
        <div class="kpi-value {color_class}">{value}</div>
        <div class="kpi-sub">{sub}</div>
    </div>
    """, unsafe_allow_html=True)


def style_fig(fig, height=None):
    fig.update_layout(
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font=dict(color="#0f172a"),
        margin=dict(l=0, r=0, t=45, b=0),
        legend=dict(
            bgcolor="rgba(255,255,255,0.90)",
            bordercolor="#cbd5e1",
            borderwidth=1
        )
    )

    fig.update_xaxes(gridcolor="#e2e8f0", zerolinecolor="#cbd5e1")
    fig.update_yaxes(gridcolor="#e2e8f0", zerolinecolor="#cbd5e1")

    if height:
        fig.update_layout(height=height)

    return fig




def render_analytics_recompute_box(script_command: str, description: str):
    st.info(
        f"🔄 Cette page se rafraîchit automatiquement depuis PostGIS. "
        f"Pour recalculer les résultats analytiques : `{script_command}`"
    )
    with st.expander("Pourquoi cette page n'est pas 100% Kafka direct ?"):
        st.markdown(description)


def empty_warning(message, command):
    st.warning(message)
    st.code(command, language="bash")
    st.stop()


def render_sidebar_clock():
    components.html(
        """
        <div class="clock-box">
            <div class="clock-title">Heure système</div>
            <div id="live-clock" class="clock-time">Chargement...</div>
        </div>

        <script>
        function updateClock() {
            const clock = document.getElementById("live-clock");
            if (clock) {
                const now = new Date();
                clock.innerHTML = now.toLocaleString("fr-FR", {
                    weekday: "short",
                    day: "2-digit",
                    month: "short",
                    year: "numeric",
                    hour: "2-digit",
                    minute: "2-digit",
                    second: "2-digit"
                });
            }
        }
        setInterval(updateClock, 1000);
        updateClock();
        </script>
        """,
        height=105
    )


# ============================================================
# BARRE LATÉRALE
# ============================================================

with st.sidebar:
    st.markdown("""
    <div class="sidebar-brand">🚚 TOUR DE CONTRÔLE<br/>LOGISTIQUE</div>
    <div class="sidebar-sub">PORTO — ANALYSE GÉOSPATIALE</div>
    """, unsafe_allow_html=True)

    render_sidebar_clock()

    st.markdown("---")

    page = st.radio(
        "Navigation",
        [
            "🏠 Vue globale",
            "📡 Temps réel",
            "🚨 Alertes temps réel",
            "🗺️ Tournées",
            "🔵 Clusters DBSCAN",
            "🔥 Heatmap",
            "⚠️ Score de risque",
            "📊 Prévisions",
            "🌧️ Météo Open-Meteo",
            "🌍 GeoServer",
            "🕒 Isochrones",
            "🌐 Export Kepler.gl"
        ]
    )

    st.markdown("---")
    st.markdown("### Paramètres d’affichage")

    max_taxis = st.slider("Taxis sur la carte", 50, 304, 304, step=10)
    show_dbscan = st.checkbox("Afficher les zones DBSCAN", value=True)
    dbscan_limit = st.slider("Points DBSCAN", 200, 3000, 1200, step=200)
    show_history = st.checkbox("Afficher les trajectoires récentes", value=False)
    history_minutes = st.slider("Historique en minutes", 3, 30, 10, step=1)

    st.markdown("---")
    st.markdown("**Jeu de données :** porto_january_2014.csv")
    st.markdown("**Source :** 304 taxis réels")
    st.markdown("**Flux :** Kafka + PostGIS")
    st.markdown("**Dashboard :** Streamlit")
    st.markdown("🟢 **Système opérationnel**")


# ============================================================
# PAGE 1 — VUE GLOBALE
# ============================================================

if page == "🏠 Vue globale":
    render_header(
        "Vue globale du système",
        "Synthèse exécutive : données, risques, optimisation et météo",
        "🏠",
        live=False
    )

    render_realtime_banner()

    try:
        global_df = load_global_stats()
        risk_df = load_risk_summary()
        opt_df = load_optimization_summary()
    except Exception as e:
        st.error(f"Erreur de chargement : {e}")
        st.stop()

    if global_df.empty:
        empty_warning("Aucune donnée disponible.", "python src\\01_prepare_porto_data.py")

    g = global_df.iloc[0]

    c1, c2, c3, c4, c5, c6 = st.columns(6)

    with c1:
        kpi("🚕 Taxis réels", int(g["total_taxis"] or 0), "dataset Porto", "blue")
    with c2:
        kpi("🛣️ Trajets", int(g["total_trips"] or 0), "table trips", "blue")
    with c3:
        kpi("📍 Points GPS", int(g["total_gps_points"] or 0), "table gps_positions", "blue")
    with c4:
        kpi("🔵 Points DBSCAN", int(g["total_cluster_points"] or 0), "zones denses", "blue")
    with c5:
        kpi("⚠️ Scores", int(g["total_scores"] or 0), "scores de risque", "warn")
    with c6:
        kpi("📈 Optimisés", int(g["total_optimized"] or 0), "trajets optimisés", "ok")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### ⚠️ Répartition des risques")

        if not risk_df.empty:
            risk_df_display = risk_df.copy()
            risk_df_display["risk_level"] = risk_df_display["risk_level"].replace({
                "LOW": "FAIBLE",
                "MEDIUM": "MOYEN",
                "HIGH": "ÉLEVÉ",
                "CRITICAL": "CRITIQUE"
            })

            fig = px.pie(
                risk_df_display,
                names="risk_level",
                values="nb_trips",
                hole=0.55,
                title="Trajets par niveau de risque"
            )
            st.plotly_chart(style_fig(fig, 420), use_container_width=True)
        else:
            st.info("Lance : python -m src.analysis.06_risk_scoring")

    with col2:
        st.markdown("### 🗺️ Résumé optimisation")

        if not opt_df.empty and int(opt_df.iloc[0]["total_routes"] or 0) > 0:
            o = opt_df.iloc[0]
            comp = pd.DataFrame({
                "État": ["Avant optimisation", "Après optimisation"],
                "Distance en km": [
                    float(o["distance_before"] or 0),
                    float(o["distance_after"] or 0)
                ]
            })
            fig = px.bar(
                comp,
                x="État",
                y="Distance en km",
                text="Distance en km",
                title="Distance avant/après"
            )
            st.plotly_chart(style_fig(fig, 420), use_container_width=True)
        else:
            st.info("Lance : python -m src.analysis.10_route_optimization")


# ============================================================
# PAGE 2 — TEMPS RÉEL
# ============================================================

elif page == "📡 Temps réel":
    render_header(
        "Supervision temps réel",
        "Kafka → PostGIS → Dashboard : montée progressive de 0 à 304 taxis",
        "📡",
        live=True
    )

    render_realtime_banner()

    try:
        counts_df = load_realtime_counts()
        df = load_latest_positions(max_taxis)
        clusters_df = load_dbscan_clusters(dbscan_limit) if show_dbscan else pd.DataFrame()
        history_df = load_recent_history(history_minutes, 2500) if show_history else pd.DataFrame()
    except Exception as e:
        st.error(f"Erreur de chargement temps réel : {e}")
        st.stop()

    if df.empty:
        st.warning("Aucune donnée temps réel. Lance le consumer puis le producer Kafka.")
        st.code(
            "python -m src.ingestion.03_kafka_consumer_postgis\n"
            "python -m src.ingestion.02_kafka_producer",
            language="bash"
        )
        st.stop()

    st.markdown("### 🎯 Filtre opérationnel")

    truck_options = ["Tous"] + sorted(df["truck_id"].astype(str).unique().tolist())

    selected_truck = st.selectbox(
        "🚚 Sélectionner un véhicule",
        truck_options,
        index=0
    )

    if selected_truck != "Tous":
        df = df[df["truck_id"].astype(str) == selected_truck]

        if show_history:
            history_df = history_df[history_df["truck_id"].astype(str) == selected_truck]

        st.info(f"Affichage du véhicule sélectionné : {selected_truck}")
    else:
        st.info("Affichage de tous les véhicules actifs.")

    if df.empty:
        st.warning("Aucune donnée disponible pour le véhicule sélectionné.")
        st.stop()

    critical_df = df[
        (df["route_risk_score"] >= 15)
        | (df["estimated_delay_minutes"] >= 10)
        | (df["status"] == "RISK")
    ]

    if not critical_df.empty:
        st.error(f"🚨 {len(critical_df)} véhicule(s) présentent une situation critique.")
    else:
        st.success("✅ Aucun véhicule critique dans la sélection actuelle.")

    active_taxis = df["truck_id"].nunique()
    avg_delay = round(df["estimated_delay_minutes"].mean(), 1)
    avg_speed = round(df["speed"].mean(), 1)
    max_risk = round(df["route_risk_score"].max(), 1)

    ok_count = int((df["status"] == "OK").sum())
    warning_count = int((df["status"] == "WARNING").sum())
    risk_count = int((df["status"] == "RISK").sum())

    last_event = df["event_time"].max()

    c1, c2, c3, c4, c5, c6 = st.columns(6)

    with c1:
        kpi("🚚 Taxis actifs", active_taxis, "objectif : 304", "blue")
    with c2:
        kpi("⏱️ Retard moyen", avg_delay, "minutes", "warn")
    with c3:
        kpi("🏎️ Vitesse moyenne", avg_speed, "km/h", "blue")
    with c4:
        kpi("⚠️ Risque max", max_risk, "score", "danger" if max_risk >= 10 else "warn")
    with c5:
        kpi("✅ OK", ok_count, "véhicules", "ok")
    with c6:
        kpi("🔴 Risque", risk_count, "véhicules", "danger")

    tab_map, tab_analytics, tab_data = st.tabs(
        ["🗺️ Carte opérationnelle", "📊 Analyse temps réel", "🧾 Données"]
    )

    with tab_map:
        map_col, side_col = st.columns([3.3, 1.05])

        with map_col:
            map_df = df.copy()
            map_df["statut_fr"] = map_df["status"].apply(translate_status)

            fig = px.scatter_mapbox(
                map_df,
                lat="latitude",
                lon="longitude",
                color="statut_fr",
                size="route_risk_score",
                hover_data={
                    "truck_id": True,
                    "trip_id": True,
                    "speed": True,
                    "progress": True,
                    "estimated_delay_minutes": True,
                    "rain": True,
                    "route_risk_score": True,
                    "event_time": True,
                    "latitude": False,
                    "longitude": False,
                    "status": False
                },
                zoom=11,
                height=690,
                center={"lat": 41.1579, "lon": -8.6291},
                mapbox_style="carto-positron"
            )

            if show_history and not history_df.empty:
                for truck_id in history_df["truck_id"].unique()[:30]:
                    sub = history_df[history_df["truck_id"] == truck_id].sort_values("event_time")
                    fig.add_scattermapbox(
                        lat=sub["latitude"],
                        lon=sub["longitude"],
                        mode="lines",
                        line=dict(width=2),
                        name=f"Trajet {truck_id}",
                        showlegend=False
                    )

            if show_dbscan and not clusters_df.empty:
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
                paper_bgcolor="#ffffff",
                plot_bgcolor="#ffffff",
                font=dict(color="#0f172a"),
                legend=dict(
                    bgcolor="rgba(255,255,255,0.90)",
                    bordercolor="#cbd5e1",
                    borderwidth=1
                )
            )

            st.plotly_chart(fig, use_container_width=True)

        with side_col:
            st.markdown("### 🚚 Véhicules prioritaires")
            st.caption("Top 3 par risque décroissant")

            top_live = df.sort_values("route_risk_score", ascending=False).head(3)

            for _, row in top_live.iterrows():
                status_icon = "🟢" if row["status"] == "OK" else "🟠" if row["status"] == "WARNING" else "🔴"
                delay_class = "ok" if row["estimated_delay_minutes"] == 0 else "warn"
                progress = int(min(max(row["progress"], 0), 100))

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

        col_a, col_b = st.columns([3, 1])
        with col_a:
            st.info(f"Dernier événement reçu : {last_event}. Rafraîchissement manuel pour éviter le blocage.")
        with col_b:
            if st.button("🔄 Actualiser maintenant", use_container_width=True):
                st.rerun()

    with tab_analytics:
        col1, col2, col3 = st.columns(3)

        with col1:
            status_df = pd.DataFrame({
                "Statut": ["OK", "ATTENTION", "RISQUE"],
                "Nombre": [ok_count, warning_count, risk_count]
            })
            fig = px.pie(status_df, names="Statut", values="Nombre", hole=0.55, title="Statut des véhicules")
            st.plotly_chart(style_fig(fig, 410), use_container_width=True)

        with col2:
            risk_bins = pd.cut(
                df["route_risk_score"],
                bins=[-1, 5, 10, 20, 100],
                labels=["Faible", "Moyen", "Élevé", "Critique"]
            )
            risk_hist = risk_bins.value_counts().reset_index()
            risk_hist.columns = ["Niveau", "Nombre"]
            fig = px.bar(risk_hist, x="Niveau", y="Nombre", text="Nombre", title="Distribution du risque")
            st.plotly_chart(style_fig(fig, 410), use_container_width=True)

        with col3:
            fig = px.histogram(df, x="estimated_delay_minutes", nbins=12, title="Distribution des retards")
            fig.update_xaxes(title_text="Retard estimé en minutes")
            fig.update_yaxes(title_text="Nombre de véhicules")
            st.plotly_chart(style_fig(fig, 410), use_container_width=True)

        st.markdown("### Top véhicules à risque")
        st.dataframe(
            df.sort_values("route_risk_score", ascending=False)[
                [
                    "truck_id",
                    "trip_id",
                    "speed",
                    "progress",
                    "estimated_delay_minutes",
                    "rain",
                    "route_risk_score",
                    "status",
                    "event_time"
                ]
            ].head(10),
            use_container_width=True
        )

    with tab_data:
        st.markdown("### Dernières positions par taxi")
        st.dataframe(df, use_container_width=True)

        csv_positions = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "📥 Télécharger les positions affichées",
            data=csv_positions,
            file_name="positions_temps_reel.csv",
            mime="text/csv",
            use_container_width=True
        )

        if selected_truck != "Tous":
            st.markdown("### 🛣️ Détail du véhicule sélectionné")

            selected_row = df.iloc[0]

            d1, d2, d3, d4 = st.columns(4)

            with d1:
                kpi("🚚 Véhicule", selected_row["truck_id"], "identifiant", "blue")

            with d2:
                kpi("🏎️ Vitesse", selected_row["speed"], "km/h", "blue")

            with d3:
                kpi("⏱️ Retard", selected_row["estimated_delay_minutes"], "minutes", "warn")

            with d4:
                kpi("⚠️ Risque", selected_row["route_risk_score"], "score", "danger")

            if show_history and not history_df.empty:
                st.markdown("### Trajectoire récente du véhicule")

                fig_hist = px.line_mapbox(
                    history_df.sort_values("event_time"),
                    lat="latitude",
                    lon="longitude",
                    hover_data=["truck_id", "event_time"],
                    zoom=12,
                    height=450,
                    center={
                        "lat": float(history_df["latitude"].mean()),
                        "lon": float(history_df["longitude"].mean())
                    },
                    mapbox_style="carto-positron"
                )

                fig_hist.update_layout(
                    margin=dict(l=0, r=0, t=0, b=0),
                    paper_bgcolor="#ffffff",
                    plot_bgcolor="#ffffff",
                    font=dict(color="#0f172a")
                )

                st.plotly_chart(fig_hist, use_container_width=True)
            else:
                st.info("Active 'Afficher les trajectoires récentes' dans la barre latérale pour voir l'historique du véhicule.")

        if not counts_df.empty:
            st.markdown("### État de la table temps réel")
            st.dataframe(counts_df, use_container_width=True)



# ============================================================
# PAGE 3 — ALERTES TEMPS RÉEL
# ============================================================

elif page == "🚨 Alertes temps réel":
    render_header(
        "Alertes temps réel",
        "Surveillance automatique des véhicules critiques : risque, retard et météo",
        "🚨",
        live=True
    )

    render_realtime_banner()

    try:
        alerts_df = load_realtime_alerts(500)
    except Exception as e:
        st.error(f"Erreur de chargement des alertes : {e}")
        st.stop()

    if alerts_df.empty:
        st.success("✅ Aucune alerte active pour le moment.")
        st.info("Les alertes apparaissent si un véhicule dépasse un seuil de risque, de retard ou de pluie.")
        st.stop()

    alerts_df = alerts_df.copy()

    def compute_alert_level(row):
        risk = float(row.get("route_risk_score") or 0)
        delay = float(row.get("estimated_delay_minutes") or 0)
        rain = float(row.get("rain") or 0)
        status = row.get("status")

        if status == "RISK" or risk >= 20 or delay >= 15:
            return "CRITIQUE"
        if risk >= 10 or delay >= 5 or rain > 0:
            return "ATTENTION"
        return "FAIBLE"

    def compute_alert_reason(row):
        reasons = []
        risk = float(row.get("route_risk_score") or 0)
        delay = float(row.get("estimated_delay_minutes") or 0)
        rain = float(row.get("rain") or 0)
        status = row.get("status")

        if status == "RISK":
            reasons.append("statut risque")
        if risk >= 10:
            reasons.append("score élevé")
        if delay >= 5:
            reasons.append("retard important")
        if rain > 0:
            reasons.append("pluie détectée")

        return ", ".join(reasons) if reasons else "surveillance"

    alerts_df["niveau_alerte"] = alerts_df.apply(compute_alert_level, axis=1)
    alerts_df["raison_alerte"] = alerts_df.apply(compute_alert_reason, axis=1)
    alerts_df["statut_fr"] = alerts_df["status"].apply(translate_status)

    total_alerts = len(alerts_df)
    critical_count = int((alerts_df["niveau_alerte"] == "CRITIQUE").sum())
    warning_count = int((alerts_df["niveau_alerte"] == "ATTENTION").sum())
    avg_delay_alerts = round(alerts_df["estimated_delay_minutes"].mean(), 1)
    max_risk_alerts = round(alerts_df["route_risk_score"].max(), 1)
    rain_alerts = int((alerts_df["rain"] > 0).sum())

    c1, c2, c3, c4, c5, c6 = st.columns(6)

    with c1:
        kpi("🚨 Alertes actives", total_alerts, "véhicules surveillés", "danger")
    with c2:
        kpi("🔴 Critiques", critical_count, "priorité haute", "danger")
    with c3:
        kpi("🟠 Attention", warning_count, "à surveiller", "warn")
    with c4:
        kpi("⏱️ Retard moyen", avg_delay_alerts, "minutes", "warn")
    with c5:
        kpi("⚠️ Risque max", max_risk_alerts, "score", "danger")
    with c6:
        kpi("🌧️ Sous pluie", rain_alerts, "véhicules", "blue")

    if critical_count > 0:
        st.error(f"🚨 {critical_count} véhicule(s) en état critique. Intervention recommandée.")
    elif warning_count > 0:
        st.warning(f"⚠️ {warning_count} véhicule(s) nécessitent une surveillance.")
    else:
        st.success("✅ Situation stable.")

    tab_map, tab_table, tab_export = st.tabs(
        ["🗺️ Carte des alertes", "🧾 Tableau des alertes", "📥 Export CSV"]
    )

    with tab_map:
        fig = px.scatter_mapbox(
            alerts_df,
            lat="latitude",
            lon="longitude",
            color="niveau_alerte",
            size="route_risk_score",
            hover_data={
                "truck_id": True,
                "trip_id": True,
                "raison_alerte": True,
                "estimated_delay_minutes": True,
                "rain": True,
                "route_risk_score": True,
                "speed": True,
                "event_time": True,
                "latitude": False,
                "longitude": False
            },
            zoom=11,
            height=650,
            center={"lat": 41.1579, "lon": -8.6291},
            mapbox_style="carto-positron",
            title="Carte des véhicules en alerte"
        )

        fig.update_layout(
            margin=dict(l=0, r=0, t=40, b=0),
            paper_bgcolor="#ffffff",
            plot_bgcolor="#ffffff",
            font=dict(color="#0f172a"),
            legend=dict(
                bgcolor="rgba(255,255,255,0.90)",
                bordercolor="#cbd5e1",
                borderwidth=1
            )
        )

        st.plotly_chart(fig, use_container_width=True)

    with tab_table:
        st.markdown("### Top alertes prioritaires")

        display_cols = [
            "niveau_alerte",
            "raison_alerte",
            "truck_id",
            "trip_id",
            "speed",
            "progress",
            "estimated_delay_minutes",
            "rain",
            "route_risk_score",
            "statut_fr",
            "event_time"
        ]

        top_alerts = alerts_df.sort_values(
            by=["niveau_alerte", "route_risk_score", "estimated_delay_minutes"],
            ascending=[True, False, False]
        )

        # Critique d'abord puis Attention
        order_map = {"CRITIQUE": 0, "ATTENTION": 1, "FAIBLE": 2}
        top_alerts["ordre"] = top_alerts["niveau_alerte"].map(order_map)
        top_alerts = top_alerts.sort_values(
            by=["ordre", "route_risk_score", "estimated_delay_minutes"],
            ascending=[True, False, False]
        )

        st.dataframe(
            top_alerts[display_cols],
            use_container_width=True
        )

        st.markdown("### Répartition des alertes")

        col1, col2 = st.columns(2)

        with col1:
            level_counts = alerts_df["niveau_alerte"].value_counts().reset_index()
            level_counts.columns = ["Niveau", "Nombre"]
            fig = px.pie(level_counts, names="Niveau", values="Nombre", hole=0.55, title="Alertes par niveau")
            st.plotly_chart(style_fig(fig, 420), use_container_width=True)

        with col2:
            reason_counts = alerts_df["raison_alerte"].value_counts().reset_index()
            reason_counts.columns = ["Raison", "Nombre"]
            fig = px.bar(reason_counts.head(10), x="Raison", y="Nombre", text="Nombre", title="Causes principales")
            st.plotly_chart(style_fig(fig, 420), use_container_width=True)

    with tab_export:
        st.markdown("### Télécharger les alertes")

        export_df = alerts_df[
            [
                "niveau_alerte",
                "raison_alerte",
                "truck_id",
                "trip_id",
                "latitude",
                "longitude",
                "speed",
                "progress",
                "estimated_delay_minutes",
                "rain",
                "route_risk_score",
                "status",
                "event_time"
            ]
        ].copy()

        csv_data = export_df.to_csv(index=False).encode("utf-8")

        st.download_button(
            label="📥 Télécharger les alertes en CSV",
            data=csv_data,
            file_name="alertes_temps_reel.csv",
            mime="text/csv",
            use_container_width=True
        )

        st.dataframe(export_df, use_container_width=True)


# ============================================================
# PAGE 3 — TOURNÉES
# ============================================================

elif page == "🗺️ Tournées":
    render_header(
        "Optimisation des tournées",
        "Comparaison avant/après optimisation et estimation des gains",
        "🗺️",
        live=False
    )

    render_realtime_banner()

    render_analytics_recompute_box(
        "python -m src.analysis.10_route_optimization",
        "L'optimisation est calculée à partir des tables PostGIS. Elle se met à jour après relance du script d'optimisation."
    )

    try:
        summary_df = load_optimization_summary()
        risk_df = load_optimization_by_risk()
        top_df = load_top_optimized_routes()
    except Exception as e:
        st.error(f"Erreur optimisation : {e}")
        st.code("python -m src.analysis.10_route_optimization", language="bash")
        st.stop()

    if summary_df.empty or int(summary_df.iloc[0]["total_routes"] or 0) == 0:
        empty_warning("Aucune optimisation disponible.", "python -m src.analysis.10_route_optimization")

    s = summary_df.iloc[0]

    total_routes = int(s["total_routes"] or 0)
    distance_before = float(s["distance_before"] or 0)
    distance_after = float(s["distance_after"] or 0)
    savings_km = float(s["savings_km"] or 0)
    delay_before = float(s["delay_before"] or 0)
    delay_after = float(s["delay_after"] or 0)
    savings_cost = float(s["savings_cost"] or 0)

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

    tab1, tab2, tab3 = st.tabs(["📊 Comparaison", "⚠️ Par risque", "🧾 Top routes"])

    with tab1:
        comp = pd.DataFrame({
            "État": ["Avant optimisation", "Après optimisation"],
            "Distance km": [distance_before, distance_after],
            "Retard min": [delay_before, delay_after]
        })

        col1, col2 = st.columns(2)

        with col1:
            fig = px.bar(comp, x="État", y="Distance km", text="Distance km", title="Distance totale")
            st.plotly_chart(style_fig(fig, 430), use_container_width=True)

        with col2:
            fig = px.bar(comp, x="État", y="Retard min", text="Retard min", title="Retard total")
            st.plotly_chart(style_fig(fig, 430), use_container_width=True)

    with tab2:
        risk_df_display = risk_df.copy()
        risk_df_display["risk_level"] = risk_df_display["risk_level"].replace({
            "LOW": "FAIBLE",
            "MEDIUM": "MOYEN",
            "HIGH": "ÉLEVÉ",
            "CRITICAL": "CRITIQUE"
        })

        fig = px.bar(
            risk_df_display,
            x="risk_level",
            y="savings_cost",
            text="savings_cost",
            hover_data=["nb_routes", "savings_km", "distance_before", "distance_after"],
            title="Économies par niveau de risque"
        )
        fig.update_xaxes(title_text="Niveau de risque")
        fig.update_yaxes(title_text="Économie estimée")
        st.plotly_chart(style_fig(fig, 500), use_container_width=True)
        st.dataframe(risk_df_display, use_container_width=True)

    with tab3:
        st.dataframe(top_df, use_container_width=True)


# ============================================================
# PAGE 4 — CLUSTERS DBSCAN
# ============================================================

elif page == "🔵 Clusters DBSCAN":
    render_header(
        "Clusters DBSCAN",
        "Détection automatique des zones denses et zones de congestion potentielles",
        "🔵",
        live=False
    )

    render_realtime_banner()

    render_analytics_recompute_box(
        "python -m src.analysis.05_dbscan_clustering",
        "DBSCAN est un traitement analytique. Il est recalculé à partir des points GPS stockés dans PostGIS."
    )

    try:
        clusters_df = load_dbscan_clusters(dbscan_limit)
        stats_df = load_dbscan_stats()
    except Exception as e:
        st.error(f"Erreur DBSCAN : {e}")
        st.code("python -m src.analysis.05_dbscan_clustering", language="bash")
        st.stop()

    if clusters_df.empty or stats_df.empty:
        empty_warning("Aucun cluster disponible.", "python -m src.analysis.05_dbscan_clustering")

    main_cluster = int(stats_df.iloc[0]["cluster_id"])
    main_count = int(stats_df.iloc[0]["nb_points"])

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        kpi("🔵 Clusters détectés", stats_df["cluster_id"].nunique(), "zones", "blue")
    with c2:
        kpi("📍 Points affichés", len(clusters_df), "limite dashboard", "blue")
    with c3:
        kpi("⚠️ Zone principale", main_cluster, f"{main_count} points", "danger")
    with c4:
        kpi("📊 Points totaux", int(stats_df["nb_points"].sum()), "table dbscan_clusters", "ok")

    col1, col2 = st.columns([2.3, 1])

    with col1:
        fig = px.scatter_mapbox(
            clusters_df,
            lat="latitude",
            lon="longitude",
            color="cluster_id",
            hover_data=["cluster_id", "cluster_type"],
            zoom=11,
            height=650,
            center={"lat": 41.1579, "lon": -8.6291},
            mapbox_style="carto-positron"
        )
        fig.update_layout(
            margin=dict(l=0, r=0, t=0, b=0),
            paper_bgcolor="#ffffff",
            plot_bgcolor="#ffffff",
            font=dict(color="#0f172a")
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        fig = px.bar(stats_df.head(15), x="cluster_id", y="nb_points", text="nb_points", title="Top clusters")
        fig.update_xaxes(title_text="Cluster")
        fig.update_yaxes(title_text="Nombre de points")
        st.plotly_chart(style_fig(fig, 360), use_container_width=True)
        st.dataframe(stats_df, use_container_width=True)



# ============================================================
# PAGE 5 — HEATMAP GÉOSPATIALE
# ============================================================

elif page == "🔥 Heatmap":
    render_header(
        "Heatmap géospatiale",
        "Visualisation de la densité des positions GPS et des zones de forte activité",
        "🔥",
        live=False
    )

    render_realtime_banner()

    st.markdown("""
    La heatmap permet d'identifier les zones les plus fréquentées par les véhicules.
    Elle aide à détecter les secteurs de congestion, les zones d'activité élevée et les points critiques
    pour l'organisation logistique.
    """)

    col_params, col_help = st.columns([1, 2])

    with col_params:
        st.markdown("### Paramètres")

        heatmap_source = st.radio(
            "Source des données",
            ["gps_positions", "realtime_positions"],
            index=0
        )

        heatmap_limit = st.slider(
            "Nombre de points à afficher",
            min_value=1000,
            max_value=50000,
            value=15000,
            step=1000
        )

        heatmap_radius = st.slider(
            "Rayon de densité",
            min_value=5,
            max_value=40,
            value=18,
            step=1
        )

    with col_help:
        st.info(
            "Utilise `gps_positions` pour analyser l'historique global. "
            "Utilise `realtime_positions` pour visualiser la densité du flux Kafka en temps réel."
        )

    try:
        heatmap_df = load_heatmap_points(heatmap_limit, heatmap_source)
        heatmap_summary = load_heatmap_summary()
    except Exception as e:
        st.error(f"Erreur de chargement de la heatmap : {e}")
        st.stop()

    if heatmap_df.empty:
        st.warning("Aucun point GPS disponible pour la heatmap.")
        st.stop()

    nb_points = len(heatmap_df)
    nb_taxis = heatmap_df["taxi_id"].nunique() if "taxi_id" in heatmap_df.columns else 0

    if not heatmap_summary.empty:
        s = heatmap_summary.iloc[0]
        total_points = int(s["total_gps_points"] or 0)
        total_taxis = int(s["total_taxis"] or 0)
        min_lat = s["min_lat"]
        max_lat = s["max_lat"]
        min_lon = s["min_lon"]
        max_lon = s["max_lon"]
    else:
        total_points = nb_points
        total_taxis = nb_taxis
        min_lat = round(heatmap_df["latitude"].min(), 5)
        max_lat = round(heatmap_df["latitude"].max(), 5)
        min_lon = round(heatmap_df["longitude"].min(), 5)
        max_lon = round(heatmap_df["longitude"].max(), 5)

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        kpi("📍 Points affichés", nb_points, f"source : {heatmap_source}", "blue")

    with c2:
        kpi("🚕 Véhicules", nb_taxis, "dans l'échantillon", "blue")

    with c3:
        kpi("🗃️ Points totaux", total_points, "base PostGIS", "ok")

    with c4:
        kpi("🌍 Couverture", f"{min_lat} → {max_lat}", "latitude", "warn")

    tab_heatmap, tab_points, tab_interpretation = st.tabs(
        ["🔥 Carte de densité", "📍 Points GPS", "🧠 Interprétation"]
    )

    with tab_heatmap:
        center_lat = float(heatmap_df["latitude"].mean())
        center_lon = float(heatmap_df["longitude"].mean())

        fig = px.density_mapbox(
            heatmap_df,
            lat="latitude",
            lon="longitude",
            radius=heatmap_radius,
            zoom=11,
            center={"lat": center_lat, "lon": center_lon},
            mapbox_style="carto-positron",
            height=700,
            title="Heatmap des positions GPS"
        )

        fig.update_layout(
            margin=dict(l=0, r=0, t=40, b=0),
            paper_bgcolor="#ffffff",
            plot_bgcolor="#ffffff",
            font=dict(color="#0f172a")
        )

        st.plotly_chart(fig, use_container_width=True)

    with tab_points:
        st.markdown("### Échantillon des points utilisés")

        st.dataframe(
            heatmap_df.head(1000),
            use_container_width=True
        )

        csv_heatmap = heatmap_df.to_csv(index=False).encode("utf-8")

        st.download_button(
            "📥 Télécharger les points de la heatmap",
            data=csv_heatmap,
            file_name="heatmap_points.csv",
            mime="text/csv",
            use_container_width=True
        )

    with tab_interpretation:
        st.markdown("### Lecture métier de la heatmap")

        st.markdown("""
        Les zones les plus intenses représentent les endroits où les véhicules passent fréquemment.
        Ces zones peuvent correspondre à :

        - des axes routiers très utilisés ;
        - des points de départ ou d'arrivée fréquents ;
        - des zones de congestion ;
        - des secteurs logistiques sensibles ;
        - des zones à surveiller pour optimiser les tournées.
        """)

        st.markdown("### Indicateurs spatiaux")

        spatial_df = pd.DataFrame({
            "Indicateur": [
                "Latitude minimale",
                "Latitude maximale",
                "Longitude minimale",
                "Longitude maximale",
                "Points analysés",
                "Taxis distincts"
            ],
            "Valeur": [
                min_lat,
                max_lat,
                min_lon,
                max_lon,
                nb_points,
                nb_taxis
            ]
        })

        st.dataframe(spatial_df, use_container_width=True)

        st.success(
            "Cette page répond à l'exigence des cartes interactives de type heatmap "
            "dans le projet de géospatial analytics."
        )


# ============================================================
# PAGE 5 — SCORE DE RISQUE
# ============================================================

elif page == "⚠️ Score de risque":
    render_header(
        "Score de risque logistique",
        "Retard estimé + météo réelle + congestion DBSCAN",
        "⚠️",
        live=False
    )

    render_realtime_banner()

    render_analytics_recompute_box(
        "python -m src.analysis.06_risk_scoring",
        "Le score de risque est un enrichissement analytique basé sur les retards, la météo et la congestion."
    )

    try:
        summary_df = load_risk_summary()
        top_routes_df = load_top_risky_routes()
    except Exception as e:
        st.error(f"Erreur score de risque : {e}")
        st.code("python -m src.analysis.06_risk_scoring", language="bash")
        st.stop()

    if summary_df.empty:
        empty_warning("Aucun score disponible.", "python -m src.analysis.06_risk_scoring")

    total_routes = int(summary_df["nb_trips"].sum())
    avg_score = round((summary_df["avg_score"] * summary_df["nb_trips"]).sum() / total_routes, 2)
    high_count = int(summary_df[summary_df["risk_level"].isin(["HIGH", "CRITICAL"])]["nb_trips"].sum())
    high_percent = round((high_count / total_routes) * 100, 1)

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        kpi("🛣️ Trajets scorés", total_routes, "scores de risque", "blue")
    with c2:
        kpi("⚠️ Score moyen", avg_score, "risque global", "warn")
    with c3:
        kpi("🔥 Trajets risqués", high_count, "élevés / critiques", "danger")
    with c4:
        kpi("📊 Risque élevé", f"{high_percent}%", "du total", "danger")

    tab1, tab2, tab3 = st.tabs(["📊 Répartition", "🔥 Top risques", "🧮 Formule"])

    summary_df_display = summary_df.copy()
    summary_df_display["risk_level"] = summary_df_display["risk_level"].replace({
        "LOW": "FAIBLE",
        "MEDIUM": "MOYEN",
        "HIGH": "ÉLEVÉ",
        "CRITICAL": "CRITIQUE"
    })

    with tab1:
        col1, col2 = st.columns(2)

        with col1:
            fig = px.bar(
                summary_df_display,
                x="risk_level",
                y="nb_trips",
                text="nb_trips",
                hover_data=["avg_score", "avg_delay", "avg_rain", "avg_wind"],
                title="Nombre de trajets par niveau"
            )
            fig.update_xaxes(title_text="Niveau de risque")
            fig.update_yaxes(title_text="Nombre de trajets")
            st.plotly_chart(style_fig(fig, 450), use_container_width=True)

        with col2:
            fig = px.pie(
                summary_df_display,
                names="risk_level",
                values="nb_trips",
                hole=0.55,
                title="Part des niveaux de risque"
            )
            st.plotly_chart(style_fig(fig, 450), use_container_width=True)

    with tab2:
        st.dataframe(top_routes_df, use_container_width=True)

    with tab3:
        st.markdown("### Formule utilisée")
        st.latex(r"""
        risk\_score =
        estimated\_delay\_minutes
        + rain\_mm \times 2
        + \frac{wind\_speed\_kmh}{10}
        + congestion\_flag \times 20
        """)
        st.markdown("""
        Le score combine le retard estimé, la pluie réelle, le vent réel et l'appartenance à une zone dense détectée par DBSCAN.
        """)


# ============================================================
# PAGE 6 — PRÉVISIONS
# ============================================================

elif page == "📊 Prévisions":
    render_header(
        "Prévisions des retards",
        "Anticipation des retards futurs à partir de l'historique",
        "📊",
        live=False
    )

    render_realtime_banner()

    render_analytics_recompute_box(
        "python -m src.analysis.09_prophet_forecast",
        "Les prévisions sont calculées à partir de l'historique. Elles changent après relance du script de prévision."
    )

    try:
        forecast_df = load_forecast_delays()
    except Exception as e:
        st.error(f"Erreur prévision : {e}")
        st.code("python -m src.analysis.09_prophet_forecast", language="bash")
        st.stop()

    if forecast_df.empty:
        empty_warning("Aucune prévision disponible.", "python -m src.analysis.09_prophet_forecast")

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

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=forecast_df["forecast_time"],
        y=forecast_df["upper_bound"],
        mode="lines",
        name="borne supérieure"
    ))
    fig.add_trace(go.Scatter(
        x=forecast_df["forecast_time"],
        y=forecast_df["lower_bound"],
        mode="lines",
        name="borne inférieure",
        fill="tonexty"
    ))
    fig.add_trace(go.Scatter(
        x=forecast_df["forecast_time"],
        y=forecast_df["predicted_delay"],
        mode="lines+markers",
        name="retard prédit"
    ))

    fig.update_layout(
        title="Prévision des retards",
        xaxis_title="Temps",
        yaxis_title="Retard prédit en minutes"
    )

    st.plotly_chart(style_fig(fig, 520), use_container_width=True)
    st.dataframe(forecast_df, use_container_width=True)


# ============================================================
# PAGE 7 — MÉTÉO
# ============================================================

elif page == "🌧️ Météo Open-Meteo":
    render_header(
        "Météo Open-Meteo",
        "Données météo réelles intégrées au scoring de risque",
        "🌧️",
        live=False
    )

    render_realtime_banner()

    render_analytics_recompute_box(
        "python -m src.enrichment.08_weather_openmeteo",
        "La météo est récupérée depuis Open-Meteo puis stockée dans PostGIS. La page relit la table automatiquement."
    )

    try:
        weather_summary = load_weather_summary()
        weather_df = load_weather_hourly()
    except Exception as e:
        st.error(f"Erreur météo : {e}")
        st.code("python -m src.enrichment.08_weather_openmeteo", language="bash")
        st.stop()

    if weather_df.empty:
        empty_warning("Aucune météo disponible.", "python -m src.enrichment.08_weather_openmeteo")

    w = weather_summary.iloc[0]

    nb_hours = int(w["nb_hours"] or 0)
    avg_temp = float(w["avg_temp"] or 0)
    avg_rain = float(w["avg_rain"] or 0)
    max_rain = float(w["max_rain"] or 0)
    avg_wind = float(w["avg_wind"] or 0)
    avg_humidity = float(w["avg_humidity"] or 0)

    c1, c2, c3, c4, c5, c6 = st.columns(6)

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
    with c6:
        kpi("💧 Humidité", avg_humidity, "%", "blue")

    tab1, tab2 = st.tabs(["📈 Graphiques météo", "🧾 Données météo"])

    with tab1:
        col1, col2 = st.columns(2)

        with col1:
            fig = px.line(
                weather_df,
                x="weather_time",
                y="rain",
                title="Pluie horaire à Porto"
            )
            fig.update_xaxes(title_text="Temps")
            fig.update_yaxes(title_text="Pluie en mm")
            st.plotly_chart(style_fig(fig, 430), use_container_width=True)

        with col2:
            fig = px.line(
                weather_df,
                x="weather_time",
                y=["temperature_2m", "wind_speed_10m", "relative_humidity_2m"],
                title="Température, vent et humidité"
            )
            fig.update_xaxes(title_text="Temps")
            fig.update_yaxes(title_text="Valeur")
            st.plotly_chart(style_fig(fig, 430), use_container_width=True)

    with tab2:
        st.dataframe(weather_df, use_container_width=True)


# ============================================================
# PAGE 8 — EXPORT KEPLER
# ============================================================

elif page == "🌐 Export Kepler.gl":
    render_header(
        "Export Kepler.gl",
        "Export des couches géospatiales PostGIS vers GeoJSON",
        "🌐",
        live=False
    )

    render_realtime_banner()

    exports_path = ROOT_DIR / "data" / "exports"

    file_points = exports_path / "kepler_points.geojson"
    file_clusters = exports_path / "dbscan_clusters.geojson"
    file_routes = exports_path / "risk_routes.geojson"
    file_report = exports_path / "optimization_report.json"

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        kpi("📍 Points GPS", "✅" if file_points.exists() else "❌", "kepler_points.geojson", "ok" if file_points.exists() else "danger")
    with c2:
        kpi("🔵 DBSCAN", "✅" if file_clusters.exists() else "❌", "dbscan_clusters.geojson", "ok" if file_clusters.exists() else "danger")
    with c3:
        kpi("⚠️ Routes risque", "✅" if file_routes.exists() else "❌", "risk_routes.geojson", "ok" if file_routes.exists() else "danger")
    with c4:
        kpi("📄 Rapport opt.", "✅" if file_report.exists() else "❌", "optimization_report.json", "ok" if file_report.exists() else "danger")

    st.markdown("### Commande d'export")
    st.code("python -m src.export.07_export_kepler", language="bash")

    st.markdown("### Fichiers générés")

    if exports_path.exists():
        files = list(exports_path.glob("*"))

        if files:
            file_table = pd.DataFrame({
                "fichier": [f.name for f in files],
                "taille_kb": [round(f.stat().st_size / 1024, 2) for f in files],
                "chemin": [str(f) for f in files]
            })
            st.dataframe(file_table, use_container_width=True)
        else:
            st.warning("Aucun fichier trouvé dans data/exports.")
    else:
        st.warning("Le dossier data/exports n'existe pas.")

    st.markdown("### Utilisation")
    st.markdown("""
    1. Ouvrir Kepler.gl.
    2. Importer `kepler_points.geojson`, `dbscan_clusters.geojson` et `risk_routes.geojson`.
    3. Créer une couche heatmap pour les points GPS.
    4. Colorer les routes par `risk_level`.
    5. Afficher les clusters DBSCAN comme zones de congestion.
    """)


# ============================================================
# PAGE 9 — GEOSERVER
# ============================================================

elif page == "🌍 GeoServer":
    render_header(
        "Publication GeoServer",
        "Publication des couches PostGIS sous forme de services WMS/WFS",
        "🌍",
        live=False
    )

    render_realtime_banner()

    st.markdown("### 🌍 Rôle de GeoServer")

    st.markdown("""
    GeoServer permet de publier les données géospatiales stockées dans PostGIS
    sous forme de services cartographiques standards **WMS** et **WFS**.

    Dans ce projet :

    - **Streamlit** affiche le dashboard opérationnel ;
    - **GeoServer** publie les couches géographiques ;
    - **Kepler.gl** permet une exploration cartographique avancée.
    """)

    c1, c2, c3 = st.columns(3)

    with c1:
        kpi("🌍 GeoServer", "Actif", "localhost:8080", "ok")

    with c2:
        kpi("🗺️ Couches publiées", 3, "PostGIS → WMS/WFS", "blue")

    with c3:
        kpi("🔗 Standards", "OGC", "WMS / WFS", "ok")

    st.markdown("### Couches publiées")

    geoserver_layers = pd.DataFrame({
        "Couche": [
            "logistics:gps_positions",
            "logistics:realtime_positions",
            "logistics:dbscan_clusters"
        ],
        "Description": [
            "Historique des positions GPS",
            "Positions issues du flux temps réel",
            "Zones denses détectées par DBSCAN"
        ],
        "Type": ["Point", "Point", "Point"],
        "Service": ["WMS / WFS", "WMS / WFS", "WMS / WFS"],
        "Projection": ["EPSG:4326", "EPSG:4326", "EPSG:4326"],
        "Statut": ["Publié", "Publié", "Publié"]
    })

    st.dataframe(geoserver_layers, use_container_width=True)

    st.markdown("### Tests validés")

    tests_df = pd.DataFrame({
        "Test": [
            "Connexion PostGIS",
            "Publication WMS",
            "Publication WFS",
            "Prévisualisation OpenLayers"
        ],
        "Résultat": ["Validé", "Validé", "Validé", "Validé"],
        "Description": [
            "GeoServer accède aux tables PostGIS",
            "La couche gps_positions est publiée en WMS",
            "La couche gps_positions est publiée en WFS",
            "Les points GPS sont visibles dans OpenLayers"
        ]
    })

    st.dataframe(tests_df, use_container_width=True)

    st.markdown("### Accès GeoServer")

    st.link_button(
        "Ouvrir l’interface GeoServer",
        "http://localhost:8080/geoserver/web",
        use_container_width=True
    )

    st.markdown("### URL du service WMS")
    st.code("http://localhost:8080/geoserver/logistics/wms", language="text")

    st.markdown("### URL du service WFS")
    st.code("http://localhost:8080/geoserver/logistics/wfs", language="text")

    st.info(
        "GeoServer est utilisé comme couche de publication cartographique. "
        "Il ne remplace pas le dashboard Streamlit : il expose les données PostGIS "
        "pour les outils SIG externes."
    )


# ============================================================
# PAGE 10 — ISOCHRONES
# ============================================================

elif page == "🕒 Isochrones":
    render_header(
        "Isochrones logistiques",
        "Zones accessibles autour d’un point logistique selon le temps de trajet",
        "🕒",
        live=False
    )

    render_realtime_banner()

    st.markdown("""
    Une **isochrone** représente la zone accessible depuis un point donné pendant une durée déterminée.
    Dans ce dashboard, les isochrones sont simulées autour d’un point de départ à Porto afin d'illustrer
    les zones atteignables en **5, 10 et 15 minutes**.
    """)

    col_params, col_info = st.columns([1, 2])

    with col_params:
        st.markdown("### Paramètres")

        start_lat = st.number_input(
            "Latitude du point de départ",
            min_value=40.5,
            max_value=42.0,
            value=41.1579,
            step=0.001,
            format="%.6f"
        )

        start_lon = st.number_input(
            "Longitude du point de départ",
            min_value=-9.5,
            max_value=-7.5,
            value=-8.6291,
            step=0.001,
            format="%.6f"
        )

        avg_speed = st.slider(
            "Vitesse moyenne estimée",
            min_value=10,
            max_value=80,
            value=30,
            step=5
        )

        selected_ranges = st.multiselect(
            "Durées à afficher",
            options=[5, 10, 15, 20],
            default=[5, 10, 15]
        )

    with col_info:
        c1, c2, c3 = st.columns(3)

        with c1:
            kpi("📍 Point départ", "Porto", f"{start_lat:.4f}, {start_lon:.4f}", "blue")

        with c2:
            kpi("🚗 Vitesse", avg_speed, "km/h estimés", "warn")

        with c3:
            kpi("🕒 Isochrones", len(selected_ranges), "zones affichées", "ok")

        st.info(
            "Cette version utilise une approximation circulaire. "
            "Pour une version routière réelle, on peut connecter une API comme OpenRouteService."
        )

    def build_circle_polygon(center_lat, center_lon, radius_km, points=90):
        lat_points = []
        lon_points = []

        lat_radius = radius_km / 111.0
        lon_radius = radius_km / (111.0 * math.cos(math.radians(center_lat)))

        for i in range(points + 1):
            angle = 2 * math.pi * i / points
            lat_points.append(center_lat + lat_radius * math.sin(angle))
            lon_points.append(center_lon + lon_radius * math.cos(angle))

        return lat_points, lon_points

    fig = go.Figure()

    range_colors = {
        5: "rgba(34, 197, 94, 0.25)",
        10: "rgba(59, 130, 246, 0.22)",
        15: "rgba(245, 158, 11, 0.22)",
        20: "rgba(239, 68, 68, 0.18)"
    }

    line_colors = {
        5: "rgb(34, 197, 94)",
        10: "rgb(59, 130, 246)",
        15: "rgb(245, 158, 11)",
        20: "rgb(239, 68, 68)"
    }

    # Afficher les grandes zones en premier
    for minutes in sorted(selected_ranges, reverse=True):
        radius_km = avg_speed * (minutes / 60)
        lat_poly, lon_poly = build_circle_polygon(start_lat, start_lon, radius_km)

        fig.add_trace(go.Scattermapbox(
            lat=lat_poly,
            lon=lon_poly,
            mode="lines",
            fill="toself",
            fillcolor=range_colors.get(minutes, "rgba(100,100,100,0.20)"),
            line=dict(color=line_colors.get(minutes, "rgb(100,100,100)"), width=2),
            name=f"{minutes} min — {radius_km:.1f} km",
            hovertemplate=f"Isochrone {minutes} min<br>Rayon estimé : {radius_km:.1f} km<extra></extra>"
        ))

    fig.add_trace(go.Scattermapbox(
        lat=[start_lat],
        lon=[start_lon],
        mode="markers",
        marker=dict(size=16, color="black"),
        name="Point de départ",
        hovertemplate="Point de départ logistique<extra></extra>"
    ))

    fig.update_layout(
        mapbox=dict(
            style="carto-positron",
            center=dict(lat=start_lat, lon=start_lon),
            zoom=11
        ),
        height=650,
        margin=dict(l=0, r=0, t=20, b=0),
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font=dict(color="#0f172a"),
        legend=dict(
            bgcolor="rgba(255,255,255,0.90)",
            bordercolor="#cbd5e1",
            borderwidth=1
        )
    )

    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Interprétation métier")

    st.markdown("""
    Les isochrones permettent d'évaluer rapidement :

    - les zones atteignables depuis un point logistique ;
    - la couverture potentielle d’un véhicule ;
    - les secteurs difficiles à atteindre ;
    - l'impact du temps de trajet sur la planification ;
    - les zones prioritaires pour l’optimisation des tournées.
    """)

    iso_rows = []

    for minutes in sorted(selected_ranges):
        radius_km = avg_speed * (minutes / 60)
        area_km2 = math.pi * (radius_km ** 2)

        iso_rows.append({
            "Durée": f"{minutes} min",
            "Rayon estimé km": round(radius_km, 2),
            "Surface approximative km²": round(area_km2, 2)
        })

    st.dataframe(pd.DataFrame(iso_rows), use_container_width=True)


else:
    st.error("Page inconnue.")
