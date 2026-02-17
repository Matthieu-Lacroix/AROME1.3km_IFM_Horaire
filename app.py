import streamlit as st
import xarray as xr
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import io
from datetime import datetime

# ─────────────────────────────────────────────────────────────
#  CONFIGURATION DE LA PAGE
# ─────────────────────────────────────────────────────────────
st.set_page_config(
    layout="wide",
    page_title="IFM · AROME 1.3km",
    page_icon="🔥",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────
#  DESIGN SYSTEM — Dark Ops / Salle de veille incendie
# ─────────────────────────────────────────────────────────────
st.markdown("""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=IBM+Plex+Mono:wght@300;400;500&display=swap" rel="stylesheet">

<style>
/* ── Palette ── */
:root {
    --bg:       #0d0f14;
    --surface:  #13161e;
    --surface2: #1a1e28;
    --border:   rgba(255,255,255,0.07);
    --accent:   #ff5722;
    --accent2:  #ff8c42;
    --danger:   #e53935;
    --warn:     #ffb300;
    --ok:       #43a047;
    --text:     #e8eaf0;
    --muted:    rgba(232,234,240,0.45);
    --mono:     'IBM Plex Mono', monospace;
    --display:  'Syne', sans-serif;
}

/* ── Base ── */
html, body, [class*="css"] {
    font-family: var(--mono);
    background-color: var(--bg) !important;
    color: var(--text) !important;
}

.main .block-container {
    background: var(--bg);
    padding-top: 1.5rem;
    padding-bottom: 2rem;
    max-width: 100%;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: var(--surface) !important;
    border-right: 1px solid var(--border);
}
[data-testid="stSidebar"] * { color: var(--text) !important; }
[data-testid="stSidebar"] hr { border-color: var(--border); }

/* ── Header ── */
.ops-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.6rem 1.2rem;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 6px;
    margin-bottom: 1.2rem;
    font-family: var(--display);
}
.ops-header-title {
    font-size: 1.25rem;
    font-weight: 800;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--accent);
}
.ops-header-sub {
    font-family: var(--mono);
    font-size: 0.72rem;
    color: var(--muted);
    letter-spacing: 0.12em;
}
.ops-pulse {
    width: 10px; height: 10px;
    border-radius: 50%;
    background: var(--ok);
    box-shadow: 0 0 0 0 rgba(67,160,71,0.6);
    animation: pulse 2s infinite;
    display: inline-block;
    margin-right: 6px;
}
@keyframes pulse {
    0%   { box-shadow: 0 0 0 0 rgba(67,160,71,0.6); }
    70%  { box-shadow: 0 0 0 8px rgba(67,160,71,0); }
    100% { box-shadow: 0 0 0 0 rgba(67,160,71,0); }
}

/* ── Metric cards ── */
.metric-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: 10px;
    margin-bottom: 1rem;
}
.metric-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 12px 16px;
    position: relative;
    overflow: hidden;
    transition: border-color 0.2s;
}
.metric-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, var(--accent), transparent);
}
.metric-card:hover { border-color: rgba(255,87,34,0.3); }
.metric-label {
    font-size: 0.62rem;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 4px;
}
.metric-value {
    font-family: var(--display);
    font-size: 1.6rem;
    font-weight: 700;
    color: var(--text);
    line-height: 1;
}
.metric-unit {
    font-size: 0.72rem;
    color: var(--muted);
    margin-top: 2px;
}
.metric-delta {
    font-size: 0.65rem;
    margin-top: 4px;
}
.delta-up   { color: var(--danger); }
.delta-down { color: var(--ok); }

/* ── IFM badge ── */
.ifm-badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 3px;
    font-weight: 700;
    font-size: 0.7rem;
    letter-spacing: 0.12em;
    text-transform: uppercase;
}

/* ── Tabs ── */
[data-testid="stTabs"] [data-baseweb="tab-list"] {
    gap: 4px;
    background: var(--surface);
    padding: 4px;
    border-radius: 6px;
    border: 1px solid var(--border);
    margin-bottom: 1rem;
}
[data-testid="stTabs"] [data-baseweb="tab"] {
    background: transparent !important;
    border-radius: 4px !important;
    color: var(--muted) !important;
    font-family: var(--mono) !important;
    font-size: 0.75rem !important;
    letter-spacing: 0.08em;
    padding: 8px 16px !important;
    border: none !important;
}
[data-testid="stTabs"] [aria-selected="true"] {
    background: var(--accent) !important;
    color: white !important;
}

/* ── Slider ── */
[data-testid="stSlider"] > div > div > div {
    background: var(--accent) !important;
}

/* ── Dataframe ── */
[data-testid="stDataFrame"] {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: 6px;
}

/* ── Section titles ── */
.section-title {
    font-family: var(--display);
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: var(--muted);
    border-left: 2px solid var(--accent);
    padding-left: 10px;
    margin: 1rem 0 0.6rem;
}

/* ── Timeline indicator ── */
.timeline-bar {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 10px 16px;
    margin-bottom: 1rem;
    display: flex;
    align-items: center;
    gap: 12px;
}
.timeline-echo {
    font-family: var(--display);
    font-size: 1.1rem;
    font-weight: 700;
    color: var(--accent2);
}

/* ── Info boxes ── */
.info-box {
    background: var(--surface2);
    border: 1px solid var(--border);
    border-left: 3px solid var(--accent);
    border-radius: 0 6px 6px 0;
    padding: 10px 14px;
    font-size: 0.75rem;
    color: var(--muted);
    margin-bottom: 0.6rem;
}

/* ── Hide Streamlit default elements ── */
#MainMenu, footer, header { visibility: hidden; }
[data-testid="stToolbar"] { display: none; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
#  CHARGEMENT DES DONNÉES
# ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def load_data():
    """
    Charge le NetCDF depuis GitHub via l'API (supporte les fichiers > 50 Mo).

    Priorité :
      1. Fichier local  → si 'arome_fwi_complet.nc' existe à côté du script
      2. API GitHub     → avec token (st.secrets["GITHUB_TOKEN"] ou variable d'env)
      3. API GitHub     → sans token (rate-limit strict, déconseillé en prod)

    Configuration dans .streamlit/secrets.toml :
      GITHUB_TOKEN = "ghp_xxxxxxxxxxxxxxxxxxxx"

    Ou dans Streamlit Community Cloud :
      Settings → Secrets → ajouter GITHUB_TOKEN
    """

    REPO    = "Matthieu-Lacroix/AROME1.3km_IFM_Horaire"
    BRANCH  = "main"
    NCFILE  = "arome_fwi_complet.nc"

    # ── 1. Fichier local (déploiement avec le fichier dans le repo) ──────────
    import os
    local_path = os.path.join(os.path.dirname(__file__), NCFILE)
    if os.path.exists(local_path):
        try:
            return xr.open_dataset(local_path, engine="netcdf4")
        except Exception as e:
            st.warning(f"Fichier local trouvé mais illisible : {e}")

    # ── 2. Récupérer le token GitHub ─────────────────────────────────────────
    token = None
    try:
        token = st.secrets["GITHUB_TOKEN"]
    except Exception:
        token = os.environ.get("GITHUB_TOKEN")

    headers = {"Accept": "application/vnd.github.v3.raw"}
    if token:
        headers["Authorization"] = f"token {token}"
    else:
        st.warning("⚠️ Aucun GITHUB_TOKEN trouvé — rate limit strict (60 req/h).")

    # ── 3. Téléchargement via API GitHub (supporte > 50 Mo) ──────────────────
    api_url = f"https://api.github.com/repos/{REPO}/contents/{NCFILE}?ref={BRANCH}"

    try:
        # Étape A : récupérer les métadonnées (taille, download_url, LFS)
        meta_r = requests.get(api_url, headers={**headers,
                              "Accept": "application/vnd.github.v3+json"},
                              timeout=15)
        meta_r.raise_for_status()
        meta = meta_r.json()

        file_size = meta.get("size", 0)
        dl_url    = meta.get("download_url")
        encoding  = meta.get("encoding", "")

        # Étape B : si fichier Git LFS → download_url pointe vers le vrai contenu
        if dl_url:
            r = requests.get(dl_url, headers=headers, timeout=120,
                             stream=True)
            r.raise_for_status()

            # Lecture en streaming pour les gros fichiers
            buf = io.BytesIO()
            downloaded = 0
            progress = st.progress(0, text="Chargement du NetCDF…")
            for chunk in r.iter_content(chunk_size=1024 * 256):  # 256 Ko
                buf.write(chunk)
                downloaded += len(chunk)
                if file_size > 0:
                    pct = min(int(downloaded / file_size * 100), 100)
                    progress.progress(pct, text=f"Chargement… {downloaded//1024//1024} Mo / {file_size//1024//1024} Mo")
            progress.empty()

            buf.seek(0)
            ds = xr.open_dataset(buf, engine="netcdf4")
            return ds

        # Étape C : contenu base64 inline (fichiers < 1 Mo, normalement pas le cas)
        elif encoding == "base64":
            import base64
            content = base64.b64decode(meta["content"])
            ds = xr.open_dataset(io.BytesIO(content), engine="netcdf4")
            return ds

        else:
            st.error("Format de réponse GitHub inattendu.")
            return None

    except requests.exceptions.Timeout:
        st.error("⏱️ Timeout : le fichier met trop de temps à se télécharger (> 2 min).")
        return None
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response else "?"
        if status == 403:
            st.error("🔒 GitHub API : accès refusé (rate limit ou token invalide).")
        elif status == 404:
            st.error(f"❌ Fichier introuvable : {REPO}/{NCFILE} sur {BRANCH}")
        else:
            st.error(f"❌ Erreur HTTP {status} : {e}")
        return None
    except Exception as e:
        st.error(f"❌ Erreur inattendue : {e}")
        return None

# ─────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────
def ifm_level(val):
    """Retourne (label, couleur) selon le niveau IFM."""
    if val < 10:   return "Faible",     "#43a047"
    if val < 30:   return "Modéré",     "#ffb300"
    if val < 50:   return "Fort",       "#ff7043"
    if val < 80:   return "Très fort",  "#e53935"
    return             "Exceptionnel", "#b71c1c"

def dark_plotly_layout(**kwargs):
    """Layout Plotly commun dark ops."""
    base = dict(
        paper_bgcolor='#13161e',
        plot_bgcolor='#0d0f14',
        font=dict(family='IBM Plex Mono', size=11, color='#e8eaf0'),
        xaxis=dict(gridcolor='rgba(255,255,255,0.05)', zeroline=False, showline=False),
        yaxis=dict(gridcolor='rgba(255,255,255,0.05)', zeroline=False, showline=False),
        margin=dict(l=10, r=10, t=36, b=10),
        legend=dict(
            bgcolor='rgba(19,22,30,0.8)',
            bordercolor='rgba(255,255,255,0.07)',
            borderwidth=1,
            font=dict(size=10),
        ),
        hoverlabel=dict(
            bgcolor='#1a1e28',
            bordercolor='rgba(255,87,34,0.4)',
            font=dict(family='IBM Plex Mono', size=11),
        ),
    )
    base.update(kwargs)
    return base

# ─────────────────────────────────────────────────────────────
#  CHARGEMENT
# ─────────────────────────────────────────────────────────────
with st.spinner(""):
    ds = load_data()

if ds is None:
    st.markdown("""
    <div style="background:#1a1e28;border:1px solid #e53935;border-radius:6px;
                padding:20px;text-align:center;margin-top:40px;">
        <div style="font-size:2rem;margin-bottom:8px;">⚠️</div>
        <div style="font-family:'Syne',sans-serif;font-size:1rem;color:#e53935;font-weight:700;">
            DONNÉES INDISPONIBLES
        </div>
        <div style="font-size:0.75rem;color:rgba(255,255,255,0.4);margin-top:8px;">
            Impossible de charger le fichier NetCDF. Vérifiez l'URL ou le workflow GitHub.
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# ─────────────────────────────────────────────────────────────
#  PRÉPARATION DES DONNÉES
# ─────────────────────────────────────────────────────────────
time_coords = pd.to_datetime(ds.time.values)
n_steps     = len(time_coords)
run_date    = ds.attrs.get('run_date', time_coords[0].strftime('%Y-%m-%d %H:%M UTC'))
region      = ds.attrs.get('region', 'Sud-Est France')

# Moyennes spatiales (calculé une fois)
@st.cache_data(ttl=3600, show_spinner=False)
def compute_spatial_means(_ds):
    ds_mean = _ds.mean(dim=['lat', 'lon'])
    return ds_mean.to_dataframe()

df_mean = compute_spatial_means(ds)

# ─────────────────────────────────────────────────────────────
#  HEADER PRINCIPAL
# ─────────────────────────────────────────────────────────────
now_utc = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
st.markdown(f"""
<div class="ops-header">
    <div>
        <div class="ops-header-title">🔥 IFM · AROME 1.3 km</div>
        <div class="ops-header-sub">Indice Forêt Météo · Prévision numérique haute résolution</div>
    </div>
    <div style="text-align:right">
        <div style="font-size:0.7rem;color:var(--muted)">
            <span class="ops-pulse"></span>LIVE · {now_utc}
        </div>
        <div style="font-size:0.7rem;color:var(--muted);margin-top:3px">
            Run : {run_date} · {region} · {n_steps} échéances
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
#  SIDEBAR
# ─────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="section-title">⏱ Contrôle temporel</div>', unsafe_allow_html=True)

    step_idx = st.slider(
        "Échéance",
        min_value=0,
        max_value=n_steps - 1,
        value=0,
        format="%d",
        label_visibility="collapsed",
    )
    selected_time = time_coords[step_idx]

    st.markdown(f"""
    <div class="timeline-bar">
        <div>
            <div class="metric-label">Échéance sélectionnée</div>
            <div class="timeline-echo">{selected_time.strftime('%a %d/%m · %H:00 UTC')}</div>
            <div class="metric-unit">+{step_idx}h depuis le run</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Navigation rapide
    cols_nav = st.columns(3)
    if cols_nav[0].button("⏮", use_container_width=True, help="Début"):
        step_idx = 0
    if cols_nav[1].button("▶", use_container_width=True, help="Suivant"):
        step_idx = min(step_idx + 1, n_steps - 1)
    if cols_nav[2].button("⏭", use_container_width=True, help="Fin"):
        step_idx = n_steps - 1

    st.markdown("---")
    st.markdown('<div class="section-title">📋 Métadonnées</div>', unsafe_allow_html=True)
    st.markdown(f"""
    <div class="info-box">
        <b>Run :</b> {run_date}<br>
        <b>Région :</b> {region}<br>
        <b>Résolution :</b> 1.3 km<br>
        <b>Échéances :</b> {n_steps} × 1h<br>
        <b>Variables :</b> {', '.join(list(ds.data_vars)[:5])}
    </div>
    """, unsafe_allow_html=True)

    # Légende IFM
    st.markdown('<div class="section-title">📊 Niveaux IFM</div>', unsafe_allow_html=True)
    levels = [
        ("Faible",       "< 10",    "#43a047"),
        ("Modéré",       "10–30",   "#ffb300"),
        ("Fort",         "30–50",   "#ff7043"),
        ("Très fort",    "50–80",   "#e53935"),
        ("Exceptionnel", "> 80",    "#b71c1c"),
    ]
    for name, rng, col in levels:
        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:8px;margin:3px 0">
            <div style="width:10px;height:10px;border-radius:2px;background:{col};flex-shrink:0"></div>
            <div style="font-size:0.72rem;color:var(--muted)">{name} <span style="color:rgba(255,255,255,0.25)">({rng})</span></div>
        </div>
        """, unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
#  DONNÉES DE LA TRANCHE TEMPORELLE
# ─────────────────────────────────────────────────────────────
data_slice = ds.sel(time=selected_time)

# Métriques pour la tranche sélectionnée
ifm_vals  = float(data_slice['ifm'].mean())   if 'ifm'  in data_slice else 0
temp_val  = float(data_slice['temp'].mean())  if 'temp' in data_slice else 0
wind_val  = float(data_slice['wind'].mean())  if 'wind' in data_slice else 0
hr_val    = float(data_slice['hr'].mean())    if 'hr'   in data_slice else 0
rain_val  = float(data_slice['rain'].sum())   if 'rain' in data_slice else 0
ifm_max   = float(data_slice['ifm'].max())    if 'ifm'  in data_slice else 0

level_label, level_color = ifm_level(ifm_vals)

# Deltas vs étape précédente
if step_idx > 0:
    prev_slice = ds.isel(time=step_idx - 1)
    d_ifm  = ifm_vals - float(prev_slice['ifm'].mean())
    d_temp = temp_val - float(prev_slice['temp'].mean())
    d_wind = wind_val - float(prev_slice['wind'].mean())
else:
    d_ifm = d_temp = d_wind = 0

def delta_html(val, unit='', invert=False):
    if val == 0: return f'<span style="color:var(--muted)">→ stable</span>'
    up = val > 0
    cls = 'delta-up' if (up and not invert) or (not up and invert) else 'delta-down'
    arrow = '↑' if up else '↓'
    return f'<span class="metric-delta {cls}">{arrow} {abs(val):.1f}{unit}</span>'

# ─────────────────────────────────────────────────────────────
#  METRICS BAR
# ─────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="metric-grid">
    <div class="metric-card">
        <div class="metric-label">IFM moyen</div>
        <div class="metric-value" style="color:{level_color}">{ifm_vals:.1f}</div>
        <div class="metric-unit">
            <span class="ifm-badge" style="background:{level_color}22;color:{level_color}">{level_label}</span>
        </div>
        {delta_html(d_ifm)}
    </div>
    <div class="metric-card">
        <div class="metric-label">IFM max</div>
        <div class="metric-value">{ifm_max:.1f}</div>
        <div class="metric-unit">valeur de pointe</div>
    </div>
    <div class="metric-card">
        <div class="metric-label">Température</div>
        <div class="metric-value">{temp_val:.1f}°</div>
        <div class="metric-unit">°C · moyenne</div>
        {delta_html(d_temp, '°')}
    </div>
    <div class="metric-card">
        <div class="metric-label">Vent moyen</div>
        <div class="metric-value">{wind_val:.0f}</div>
        <div class="metric-unit">km/h</div>
        {delta_html(d_wind, 'km/h')}
    </div>
    <div class="metric-card">
        <div class="metric-label">Humidité relative</div>
        <div class="metric-value">{hr_val:.0f}%</div>
        <div class="metric-unit">moyenne spatiale</div>
    </div>
    <div class="metric-card">
        <div class="metric-label">Précipitations</div>
        <div class="metric-value">{rain_val:.1f}</div>
        <div class="metric-unit">mm · cumul domaine</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
#  TABS
# ─────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs([
    "🗺️  Cartographie IFM",
    "📈  Séries temporelles",
    "🔬  Analyse multi-variables",
])

# ══════════════════════════════════════════════════════════════
#  TAB 1 — CARTE
# ══════════════════════════════════════════════════════════════
with tab1:

    col_map, col_info = st.columns([3, 1])

    with col_map:
        st.markdown(
            f'<div class="section-title">Indice Forêt Météo — {selected_time.strftime("%d %B %Y · %H:00 UTC")} (+{step_idx}h)</div>',
            unsafe_allow_html=True
        )

        # Colorscale IFM custom (vert → jaune → orange → rouge → bordeaux)
        ifm_colorscale = [
            [0.00, '#1b5e20'],
            [0.12, '#43a047'],
            [0.25, '#ffee58'],
            [0.37, '#ffb300'],
            [0.50, '#ff7043'],
            [0.65, '#e53935'],
            [0.80, '#b71c1c'],
            [1.00, '#4a0000'],
        ]

        fig_map = px.imshow(
            data_slice['ifm'],
            x=ds.lon.values,
            y=ds.lat.values,
            color_continuous_scale=ifm_colorscale,
            zmin=0, zmax=100,
            origin='lower',
            aspect='equal',
            labels=dict(color='IFM', x='Longitude', y='Latitude'),
        )

        fig_map.update_traces(
            hovertemplate=(
                '<b>IFM : %{z:.1f}</b><br>'
                'Lon : %{x:.3f}° | Lat : %{y:.3f}°'
                '<extra></extra>'
            )
        )

        # Ligne de contour danger (IFM > 50)
        fig_map.add_trace(go.Contour(
            z=data_slice['ifm'].values,
            x=ds.lon.values,
            y=ds.lat.values,
            contours=dict(
                start=50, end=50, size=1,
                coloring='none',
                showlabels=True,
                labelfont=dict(size=9, color='white'),
            ),
            line=dict(color='rgba(255,255,255,0.7)', width=1.5, dash='dot'),
            showscale=False,
            name='Seuil danger (50)',
            hoverinfo='skip',
        ))

        fig_map.update_layout(
            **dark_plotly_layout(
                height=580,
                margin=dict(l=0, r=0, t=0, b=0),
                coloraxis_colorbar=dict(
                    title='IFM',
                    titlefont=dict(size=10),
                    tickfont=dict(size=9),
                    tickvals=[0, 10, 30, 50, 80, 100],
                    ticktext=['0', '10', '30', '50', '80', '100'],
                    thickness=14,
                    len=0.85,
                    bgcolor='rgba(13,15,20,0.8)',
                    bordercolor='rgba(255,255,255,0.1)',
                    borderwidth=1,
                ),
                xaxis=dict(title='Longitude', showgrid=False),
                yaxis=dict(title='Latitude',  showgrid=False),
            )
        )
        st.plotly_chart(fig_map, use_container_width=True, config={'displayModeBar': False})

    with col_info:
        st.markdown('<div class="section-title" style="margin-top:2.5rem">Distribution IFM</div>', unsafe_allow_html=True)

        # Histogramme de distribution
        ifm_flat = data_slice['ifm'].values.flatten()
        ifm_flat = ifm_flat[~np.isnan(ifm_flat)]

        fig_hist = go.Figure(go.Histogram(
            x=ifm_flat,
            nbinsx=30,
            marker=dict(
                color=ifm_flat,
                colorscale=ifm_colorscale,
                cmin=0, cmax=100,
                line=dict(width=0),
            ),
        ))
        # Ligne de seuil danger
        fig_hist.add_vline(x=50, line_color='rgba(255,255,255,0.4)', line_dash='dot', line_width=1)
        fig_hist.add_vline(x=30, line_color='rgba(255,180,0,0.3)',   line_dash='dot', line_width=1)

        fig_hist.update_layout(
            **dark_plotly_layout(
                height=200,
                margin=dict(l=0, r=0, t=20, b=0),
                title=dict(text='Fréquence par classe', font=dict(size=10), x=0),
                showlegend=False,
                xaxis=dict(title='IFM', title_font=dict(size=9)),
                yaxis=dict(title='Nb pixels', title_font=dict(size=9)),
                bargap=0.05,
            )
        )
        st.plotly_chart(fig_hist, use_container_width=True, config={'displayModeBar': False})

        # Stats spatiales
        pct_danger = (ifm_flat > 50).mean() * 100
        pct_fort   = ((ifm_flat > 30) & (ifm_flat <= 50)).mean() * 100
        pct_ok     = (ifm_flat <= 30).mean() * 100

        st.markdown(f"""
        <div class="section-title">Répartition surface</div>
        <div class="info-box">
            <div style="margin-bottom:6px">
                <div style="font-size:0.65rem;color:var(--muted)">DANGER (IFM > 50)</div>
                <div style="font-size:1.1rem;font-weight:700;color:#e53935">{pct_danger:.1f}%</div>
                <div style="background:#e5393533;border-radius:2px;height:4px;margin-top:2px">
                    <div style="background:#e53935;height:4px;border-radius:2px;width:{pct_danger:.1f}%"></div>
                </div>
            </div>
            <div style="margin-bottom:6px">
                <div style="font-size:0.65rem;color:var(--muted)">FORT (30–50)</div>
                <div style="font-size:1.1rem;font-weight:700;color:#ff7043">{pct_fort:.1f}%</div>
                <div style="background:#ff704333;border-radius:2px;height:4px;margin-top:2px">
                    <div style="background:#ff7043;height:4px;border-radius:2px;width:{pct_fort:.1f}%"></div>
                </div>
            </div>
            <div>
                <div style="font-size:0.65rem;color:var(--muted)">MODÉRÉ/FAIBLE (≤ 30)</div>
                <div style="font-size:1.1rem;font-weight:700;color:#43a047">{pct_ok:.1f}%</div>
                <div style="background:#43a04733;border-radius:2px;height:4px;margin-top:2px">
                    <div style="background:#43a047;height:4px;border-radius:2px;width:{pct_ok:.1f}%"></div>
                </div>
            </div>
        </div>

        <div class="section-title">Statistiques spatiales</div>
        <div class="info-box" style="font-size:0.7rem">
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:4px">
                <div>Min</div>  <div style="color:var(--text);text-align:right">{ifm_flat.min():.1f}</div>
                <div>Max</div>  <div style="color:var(--accent);text-align:right">{ifm_flat.max():.1f}</div>
                <div>Moy</div>  <div style="color:var(--text);text-align:right">{ifm_flat.mean():.1f}</div>
                <div>P90</div>  <div style="color:var(--warn);text-align:right">{np.percentile(ifm_flat,90):.1f}</div>
                <div>P95</div>  <div style="color:var(--danger);text-align:right">{np.percentile(ifm_flat,95):.1f}</div>
                <div>σ</div>    <div style="color:var(--text);text-align:right">{ifm_flat.std():.1f}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
#  TAB 2 — SÉRIES TEMPORELLES
# ══════════════════════════════════════════════════════════════
with tab2:
    st.markdown('<div class="section-title">Évolution temporelle — Moyennes spatiales sur le domaine</div>', unsafe_allow_html=True)

    # Ligne verticale = échéance sélectionnée
    vline_x = selected_time

    # ── IFM avec enveloppe min/max ──
    if 'ifm' in ds:
        ifm_mean = ds['ifm'].mean(dim=['lat','lon']).to_series()
        ifm_min  = ds['ifm'].min(dim=['lat','lon']).to_series()
        ifm_max_s= ds['ifm'].max(dim=['lat','lon']).to_series()
        ifm_p90  = ds['ifm'].quantile(0.9, dim=['lat','lon']).to_series()

        fig_ifm = go.Figure()

        # Zone min/max
        fig_ifm.add_trace(go.Scatter(
            x=list(ifm_mean.index) + list(ifm_mean.index[::-1]),
            y=list(ifm_max_s.values) + list(ifm_min.values[::-1]),
            fill='toself',
            fillcolor='rgba(255,87,34,0.08)',
            line=dict(width=0),
            name='Min/Max',
            hoverinfo='skip',
        ))
        # P90
        fig_ifm.add_trace(go.Scatter(
            x=ifm_p90.index, y=ifm_p90.values,
            line=dict(color='rgba(255,87,34,0.4)', width=1, dash='dot'),
            name='P90',
        ))
        # Moyenne
        fig_ifm.add_trace(go.Scatter(
            x=ifm_mean.index, y=ifm_mean.values,
            line=dict(color='#ff5722', width=2.5),
            name='Moyenne',
            hovertemplate='<b>%{x|%d/%m %H:00}</b><br>IFM moy : %{y:.1f}<extra></extra>',
        ))
        # Ligne seuil danger
        fig_ifm.add_hline(y=50, line_color='rgba(229,57,53,0.5)', line_dash='dash', line_width=1,
                          annotation_text='Seuil danger', annotation_font_size=9,
                          annotation_font_color='rgba(229,57,53,0.7)')
        fig_ifm.add_hline(y=30, line_color='rgba(255,180,0,0.3)', line_dash='dot', line_width=1)
        # Curseur temps
        fig_ifm.add_vline(x=vline_x, line_color='rgba(255,255,255,0.3)', line_width=1)

        fig_ifm.update_layout(
            **dark_plotly_layout(
                height=280,
                title=dict(text='Indice Forêt Météo (IFM)', font=dict(size=12, family='Syne'), x=0),
                yaxis=dict(title='IFM', range=[0, None]),
            )
        )
        st.plotly_chart(fig_ifm, use_container_width=True, config={'displayModeBar': False})

    # ── Température + Humidité ──
    col_a, col_b = st.columns(2)

    with col_a:
        if 'temp' in ds and 'hr' in ds:
            fig_th = make_subplots(specs=[[{"secondary_y": True}]])
            temp_s = ds['temp'].mean(dim=['lat','lon']).to_series()
            hr_s   = ds['hr'].mean(dim=['lat','lon']).to_series()

            fig_th.add_trace(go.Scatter(
                x=temp_s.index, y=temp_s.values,
                line=dict(color='#ff8c42', width=2),
                name='Temp (°C)',
                hovertemplate='%{y:.1f}°C<extra>Température</extra>',
            ), secondary_y=False)

            fig_th.add_trace(go.Scatter(
                x=hr_s.index, y=hr_s.values,
                line=dict(color='#42a5f5', width=1.5, dash='dot'),
                name='HR (%)',
                hovertemplate='%{y:.0f}%<extra>Humidité</extra>',
            ), secondary_y=True)

            fig_th.add_vline(x=vline_x, line_color='rgba(255,255,255,0.3)', line_width=1)

            fig_th.update_layout(**dark_plotly_layout(
                height=240,
                title=dict(text='Température & Humidité relative', font=dict(size=11, family='Syne'), x=0),
            ))
            fig_th.update_yaxes(title_text='°C', secondary_y=False,
                                gridcolor='rgba(255,255,255,0.05)')
            fig_th.update_yaxes(title_text='%', secondary_y=True, showgrid=False)

            st.plotly_chart(fig_th, use_container_width=True, config={'displayModeBar': False})

    with col_b:
        if 'wind' in ds:
            wind_s = ds['wind'].mean(dim=['lat','lon']).to_series()
            wind_max_s = ds['wind'].max(dim=['lat','lon']).to_series()

            fig_wind = go.Figure()
            fig_wind.add_trace(go.Scatter(
                x=wind_s.index, y=wind_max_s.values,
                fill='tozeroy',
                fillcolor='rgba(100,181,246,0.06)',
                line=dict(width=0),
                name='Max vent',
                hoverinfo='skip',
            ))
            fig_wind.add_trace(go.Scatter(
                x=wind_s.index, y=wind_s.values,
                line=dict(color='#64b5f6', width=2),
                name='Vent moy (km/h)',
                hovertemplate='%{y:.1f} km/h<extra>Vent moyen</extra>',
            ))
            fig_wind.add_vline(x=vline_x, line_color='rgba(255,255,255,0.3)', line_width=1)

            fig_wind.update_layout(**dark_plotly_layout(
                height=240,
                title=dict(text='Vent (km/h)', font=dict(size=11, family='Syne'), x=0),
                yaxis=dict(title='km/h'),
            ))
            st.plotly_chart(fig_wind, use_container_width=True, config={'displayModeBar': False})

    # ── Tableau récapitulatif ──
    st.markdown('<div class="section-title">Tableau des échéances</div>', unsafe_allow_html=True)

    display_cols = [c for c in ['ifm', 'temp', 'wind', 'hr', 'rain'] if c in df_mean.columns]
    df_display = df_mean[display_cols].copy()
    df_display.index = df_display.index.strftime('%a %d/%m · %H:00')
    df_display.columns = [c.upper() for c in df_display.columns]

    def style_df(val, col):
        if col == 'IFM':
            _, c = ifm_level(val)
            return f'color: {c}; font-weight: bold'
        return ''

    styled = df_display.style\
        .format(precision=1)\
        .background_gradient(subset=['IFM'] if 'IFM' in df_display.columns else [],
                             cmap='YlOrRd', vmin=0, vmax=100)\
        .set_properties(**{
            'background-color': '#13161e',
            'color': '#e8eaf0',
            'border': '1px solid rgba(255,255,255,0.05)',
            'font-family': 'IBM Plex Mono',
            'font-size': '0.75rem',
        })

    st.dataframe(styled, use_container_width=True, height=300)

# ══════════════════════════════════════════════════════════════
#  TAB 3 — ANALYSE MULTI-VARIABLES
# ══════════════════════════════════════════════════════════════
with tab3:
    st.markdown('<div class="section-title">Corrélations & Distributions — échéance sélectionnée</div>', unsafe_allow_html=True)

    available_vars = [v for v in ['ifm', 'temp', 'wind', 'hr', 'rain'] if v in data_slice]

    col_c1, col_c2 = st.columns(2)

    with col_c1:
        if len(available_vars) >= 2:
            # Scatter IFM vs Température coloré par vent
            df_scatter = pd.DataFrame({
                'ifm':  data_slice['ifm'].values.flatten()  if 'ifm'  in data_slice else [],
                'temp': data_slice['temp'].values.flatten() if 'temp' in data_slice else [],
                'wind': data_slice['wind'].values.flatten() if 'wind' in data_slice else [],
                'hr':   data_slice['hr'].values.flatten()   if 'hr'   in data_slice else [],
            }).dropna()

            # Sous-échantillonnage pour la perf
            if len(df_scatter) > 5000:
                df_scatter = df_scatter.sample(5000, random_state=42)

            fig_scat = go.Figure(go.Scatter(
                x=df_scatter['temp'],
                y=df_scatter['ifm'],
                mode='markers',
                marker=dict(
                    color=df_scatter['wind'],
                    colorscale='Blues',
                    size=3,
                    opacity=0.5,
                    colorbar=dict(title='Vent', thickness=10, len=0.7),
                ),
                hovertemplate='T : %{x:.1f}°C | IFM : %{y:.1f}<extra></extra>',
            ))
            fig_scat.update_layout(**dark_plotly_layout(
                height=320,
                title=dict(text='IFM vs Température (couleur = vent)', font=dict(size=11, family='Syne'), x=0),
                xaxis=dict(title='Température (°C)'),
                yaxis=dict(title='IFM'),
            ))
            st.plotly_chart(fig_scat, use_container_width=True, config={'displayModeBar': False})

    with col_c2:
        # Heatmap des corrélations
        if len(available_vars) >= 3:
            df_corr_data = pd.DataFrame({
                v: data_slice[v].values.flatten() for v in available_vars
            }).dropna()
            corr = df_corr_data.corr()

            fig_corr = go.Figure(go.Heatmap(
                z=corr.values,
                x=[v.upper() for v in corr.columns],
                y=[v.upper() for v in corr.index],
                colorscale=[
                    [0, '#1565c0'], [0.5, '#13161e'], [1, '#b71c1c']
                ],
                zmin=-1, zmax=1,
                text=corr.values.round(2),
                texttemplate='%{text}',
                textfont=dict(size=11),
                hoverongaps=False,
            ))
            fig_corr.update_layout(**dark_plotly_layout(
                height=320,
                title=dict(text='Matrice de corrélation (pixels)', font=dict(size=11, family='Syne'), x=0),
                margin=dict(l=40, r=10, t=40, b=10),
            ))
            st.plotly_chart(fig_corr, use_container_width=True, config={'displayModeBar': False})

    # Box plots par variable
    st.markdown('<div class="section-title">Distributions spatiales — comparaison temporelle (toutes échéances)</div>', unsafe_allow_html=True)

    if 'ifm' in ds:
        # Sélection d'échéances régulières pour éviter trop de données
        step_sel = max(1, n_steps // 12)
        times_sel = time_coords[::step_sel]

        fig_box = go.Figure()
        for t in times_sel:
            vals = ds['ifm'].sel(time=t).values.flatten()
            vals = vals[~np.isnan(vals)]
            fig_box.add_trace(go.Box(
                y=vals,
                name=pd.Timestamp(t).strftime('%d/%m %Hh'),
                marker_color='rgba(255,87,34,0.6)',
                line=dict(color='#ff5722', width=1),
                fillcolor='rgba(255,87,34,0.1)',
                boxpoints=False,
                whiskerwidth=0.5,
            ))

        fig_box.add_hline(y=50, line_color='rgba(229,57,53,0.4)', line_dash='dash', line_width=1)
        fig_box.update_layout(**dark_plotly_layout(
            height=300,
            title=dict(text='Distribution IFM par échéance (1 sur {})'.format(step_sel), font=dict(size=11, family='Syne'), x=0),
            showlegend=False,
            xaxis=dict(title='Échéance', tickangle=-45),
            yaxis=dict(title='IFM'),
        ))
        st.plotly_chart(fig_box, use_container_width=True, config={'displayModeBar': False})

# ─────────────────────────────────────────────────────────────
#  FOOTER
# ─────────────────────────────────────────────────────────────
st.markdown(f"""
<div style="margin-top:2rem;padding:12px 16px;border-top:1px solid var(--border);
            display:flex;justify-content:space-between;align-items:center">
    <div style="font-size:0.65rem;color:var(--muted)">
        🔥 IFM · AROME 1.3 km · Données Météo-France
    </div>
    <div style="font-size:0.65rem;color:var(--muted)">
        Généré le {now_utc} · Cache 1h
    </div>
</div>
""", unsafe_allow_html=True)
