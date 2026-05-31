import sys
from pathlib import Path

import pandas as pd
import psycopg2
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components


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
            "🗺️ Tournées",
            "🔵 Clusters DBSCAN",
            "⚠️ Score de risque",
            "📊 Prévisions",
            "🌧️ Météo Open-Meteo",
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

        if not counts_df.empty:
            st.markdown("### État de la table temps réel")
            st.dataframe(counts_df, use_container_width=True)


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
# PAGE 5 — SCORE DE RISQUE
# ============================================================

elif page == "⚠️ Score de risque":
    render_header(
        "Score de risque logistique",
        "Retard estimé + météo réelle + congestion DBSCAN",
        "⚠️",
        live=False
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


else:
    st.error("Page inconnue.")