import streamlit as st
import xarray as xr
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import io
import os
import tempfile
import time
from datetime import datetime, timezone

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
@st.cache_data(ttl=3600, show_spinner=False)
def load_data():
    """
    Charge le NetCDF AROME depuis GitHub (supporte Git LFS).
    Ecrit toujours sur disque temporaire (netCDF4 n'accepte pas BytesIO).
    Secrets Streamlit : GITHUB_TOKEN = "ghp_xxx..."
    """
    REPO   = "Matthieu-Lacroix/AROME1.3km_IFM_Horaire"
    BRANCH = "main"
    NCFILE = "arome_fwi_complet.nc"
    
    # ── Token ────────────────────────────────────────────────────────────────
    token = None
    try:
        token = st.secrets["GITHUB_TOKEN"]
    except Exception:
        pass
    if not token:
        token = os.environ.get("GITHUB_TOKEN")
    if not token:
        st.warning("GITHUB_TOKEN absent — risque de rate-limit.")
    
    auth = {"Authorization": f"token {token}"} if token else {}
    
    # ── Helper : ouvrir un .nc sur disque avec fallback d'engines ────────────
    def open_nc(path):
        for engine in ["netcdf4", "h5netcdf", "scipy"]:
            try:
                return xr.open_dataset(path, engine=engine)
            except Exception:
                continue
        raise RuntimeError("Aucun engine xarray n'a pu lire le fichier.")
    
    # ── Helper : téléchargement streaming → fichier temporaire ───────────────
    def stream_to_tmp(url, headers, size_hint=0):
        tmp = tempfile.NamedTemporaryFile(suffix=".nc", delete=False)
        progress = st.progress(0, text="Téléchargement en cours…")
        downloaded = 0
        try:
            r = requests.get(url, headers=headers, stream=True, timeout=300)
            r.raise_for_status()
            for chunk in r.iter_content(chunk_size=512 * 1024):
                tmp.write(chunk)
                downloaded += len(chunk)
                if size_hint > 0:
                    pct = min(int(downloaded / size_hint * 100), 99)
                    mo_done = downloaded / 1024 / 1024
                    mo_tot  = size_hint  / 1024 / 1024
                    progress.progress(pct, text=f"Téléchargement {mo_done:.0f} / {mo_tot:.0f} Mo…")
            tmp.flush()
            tmp.close()
            progress.progress(100, text="Téléchargement terminé ✅")
            progress.empty()
            return tmp.name
        except Exception as e:
            tmp.close()
            try:
                os.unlink(tmp.name)
            except Exception:
                pass
            raise e
    
    # ── 1. Fichier local Streamlit Cloud ─────────────────────────────────────
    for local_path in [
        f"/mount/src/{REPO.split('/')[-1].lower()}/{NCFILE}",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), NCFILE),
    ]:
        if os.path.exists(local_path) and os.path.getsize(local_path) > 1000:
            try:
                return open_nc(local_path)
            except Exception as e:
                st.warning(f"Fichier local illisible ({e}) → téléchargement…")
    
    # ── 2. API GitHub : récupérer les métadonnées du fichier ─────────────────
    meta_url = f"https://api.github.com/repos/{REPO}/contents/{NCFILE}?ref={BRANCH}"
    try:
        meta_r = requests.get(
            meta_url,
            headers={**auth, "Accept": "application/vnd.github.v3+json"},
            timeout=20,
        )
        meta_r.raise_for_status()
        meta = meta_r.json()
    except requests.exceptions.HTTPError as e:
        code = e.response.status_code if e.response else "?"
        msgs = {403: "Accès refusé — vérifiez GITHUB_TOKEN dans Secrets.",
                404: f"Fichier introuvable : {REPO}/{NCFILE}"}
        st.error(f"❌ GitHub API {code} : {msgs.get(code, str(e))}")
        return None
    except Exception as e:
        st.error(f"❌ Erreur réseau : {e}")
        return None
    
    file_size = meta.get("size", 0)
    dl_url    = meta.get("download_url")
    
    # ── 3. Fichier Git LFS ───────────────────────────────────────────────────
    if not dl_url or file_size < 500:
        lfs_url = (f"https://media.githubusercontent.com/media/"
                   f"{REPO}/{BRANCH}/{NCFILE}")
        st.info("🔄 Fichier Git LFS détecté → téléchargement via media.githubusercontent.com")
        try:
            tmp_path = stream_to_tmp(
                lfs_url,
                {**auth, "Accept": "application/octet-stream"},
                size_hint=76 * 1024 * 1024,
            )
            ds = open_nc(tmp_path)
            os.unlink(tmp_path)
            return ds
        except Exception as e:
            st.error(f"❌ Échec téléchargement LFS : {e}")
            return None
    
    # ── 4. Fichier normal ────────────────────────────────────────────────────
    try:
        tmp_path = stream_to_tmp(
            dl_url,
            {**auth, "Accept": "application/octet-stream"},
            size_hint=file_size,
        )
        ds = open_nc(tmp_path)
        os.unlink(tmp_path)
        return ds
    except requests.exceptions.Timeout:
        st.error("⏱️ Timeout (> 5 min). Réessayez.")
        return None
    except Exception as e:
        st.error(f"❌ Erreur téléchargement/lecture : {e}")
        return None

# ─────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────
def ifm_level(val):
    if val < 10:
        return "Faible", "#2e7d32", "#e8f5e9"
    if val < 30:
        return "Modéré", "#f57f17", "#fff8e1"
    if val < 50:
        return "Fort", "#e65100", "#fff3e0"
    if val < 80:
        return "Très fort", "#c62828", "#ffebee"
    return "Exceptionnel", "#880e4f", "#fce4ec"

def clean_layout(**kwargs):
    """Layout Plotly sobre fond blanc."""
    base = dict(
        paper_bgcolor='#ffffff',
        plot_bgcolor='#fafafa',
        font=dict(family='Source Sans 3, sans-serif', size=12, color='#1a1a2e'),
        xaxis=dict(gridcolor='#ebebeb', zeroline=False, showline=True,
                   linecolor='#d0d0d0', linewidth=1),
        yaxis=dict(gridcolor='#ebebeb', zeroline=False, showline=True,
                   linecolor='#d0d0d0', linewidth=1),
        margin=dict(l=10, r=10, t=40, b=10),
        legend=dict(
            bgcolor='rgba(255,255,255,0.9)',
            bordercolor='#e0e0e0',
            borderwidth=1,
            font=dict(size=11),
        ),
        hoverlabel=dict(
            bgcolor='#ffffff',
            bordercolor='#c0392b',
            font=dict(family='Source Sans 3, sans-serif', size=12),
        ),
    )
    base.update(kwargs)
    return base

# ─────────────────────────────────────────────────────────────
#  CSS — Modern & Clean
# ─────────────────────────────────────────────────────────────
st.markdown("""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@300;400;600;700&family=Source+Code+Pro:wght@400;500&display=swap" rel="stylesheet">
<style>
:root {
    --bg:       #f4f5f7;
    --white:    #ffffff;
    --border:   #dde1e7;
    --text:     #1c2333;
    --muted:    #6b7280;
    --accent:   #c0392b;
    --accent-l: #fdf2f2;
    --nav-w:    220px;
    --sans:     'Source Sans 3', sans-serif;
    --mono:     'Source Code Pro', monospace;
}
html, body, [class*="css"] {
    font-family: var(--sans) !important;
    background-color: var(--bg) !important;
    color: var(--text) !important;
}
#MainMenu, footer, header { visibility: hidden; }
[data-testid="stToolbar"] { display: none; }
[data-testid="stDecoration"] { display: none; }
.block-container { padding-top: 1rem !important; padding-bottom: 1rem !important; }

/* Sidebar */
[data-testid="stSidebar"] {
    background: var(--white) !important;
    border-right: 1px solid var(--border) !important;
    min-width: 220px !important;
    max-width: 220px !important;
}
[data-testid="stSidebar"] * { color: var(--text) !important; }

/* Navigation */
[data-testid="stSidebar"] [data-testid="stRadio"] > div {
    flex-direction: column;
    gap: 2px;
}
[data-testid="stSidebar"] [data-testid="stRadio"] label {
    display: flex !important;
    align-items: center !important;
    padding: 9px 12px !important;
    border-radius: 5px !important;
    font-size: 0.85rem !important;
    font-weight: 400 !important;
    cursor: pointer !important;
    transition: background 0.15s !important;
    border: none !important;
    width: 100% !important;
}
[data-testid="stSidebar"] [data-testid="stRadio"] label:hover {
    background: var(--bg) !important;
}
[data-testid="stSidebar"] [data-testid="stRadio"] [aria-checked="true"] + div + label,
[data-testid="stSidebar"] [data-testid="stRadio"] label[data-selected="true"] {
    background: var(--accent-l) !important;
    color: var(--accent) !important;
    font-weight: 600 !important;
}
[data-testid="stSidebar"] [data-testid="stRadio"] input[type="radio"] {
    display: none !important;
}

/* Slider */
[data-testid="stSlider"] [data-baseweb="slider"] [data-testid="stTickBar"] { display: none; }
[data-testid="stSlider"] [data-baseweb="slider"] div[role="slider"] {
    background: var(--accent) !important;
    border-color: var(--accent) !important;
}
[data-testid="stSlider"] [data-baseweb="slider"] div[data-testid="stSlider-track-fill"] {
    background: var(--accent) !important;
}

/* Metric cards */
.metric-row {
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    gap: 10px;
    margin-bottom: 1rem;
}
.metric-card {
    background: var(--white);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 12px 14px;
    border-top: 3px solid var(--border);
}
.metric-card.accent { border-top-color: var(--accent); }
.metric-card.warn   { border-top-color: #e65100; }
.metric-card.ok     { border-top-color: #2e7d32; }
.metric-label {
    font-size: 0.68rem;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 4px;
}
.metric-val {
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--text);
    line-height: 1.1;
    font-family: var(--sans);
}
.metric-unit { font-size: 0.72rem; color: var(--muted); margin-top: 2px; }
.metric-delta { font-size: 0.7rem; margin-top: 3px; }
.up   { color: #c62828; }
.down { color: #2e7d32; }

/* IFM badge */
.ifm-badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 3px;
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}

/* Section title */
.section-title {
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--muted);
    padding-bottom: 6px;
    border-bottom: 1px solid var(--border);
    margin: 1rem 0 0.75rem;
}

/* Info block */
.info-block {
    background: var(--white);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 12px 14px;
    font-size: 0.8rem;
    color: var(--muted);
    line-height: 1.6;
}
.info-block b { color: var(--text); }

/* Header */
.app-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: var(--white);
    border: 1px solid var(--border);
    border-left: 4px solid var(--accent);
    border-radius: 0 6px 6px 0;
    padding: 10px 16px;
    margin-bottom: 1rem;
}
.app-header-title {
    font-size: 1rem;
    font-weight: 700;
    color: var(--text);
    letter-spacing: 0.03em;
}
.app-header-meta {
    font-size: 0.72rem;
    color: var(--muted);
    margin-top: 1px;
}
.app-header-right {
    font-size: 0.72rem;
    color: var(--muted);
    text-align: right;
}

/* IFM legend */
.ifm-legend-row {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 4px 0;
    font-size: 0.78rem;
    color: var(--muted);
}
.ifm-dot {
    width: 10px; height: 10px;
    border-radius: 2px;
    flex-shrink: 0;
}

/* DataFrame */
[data-testid="stDataFrame"] {
    border: 1px solid var(--border) !important;
    border-radius: 6px !important;
}

/* Echéance label */
.ech-label {
    font-size: 1rem;
    font-weight: 600;
    color: var(--accent);
    margin: 0.4rem 0 0.8rem;
}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
#  CHARGEMENT
# ─────────────────────────────────────────────────────────────
with st.spinner("Chargement des données…"):
    ds = load_data()

if ds is None:
    st.error("Impossible de charger le fichier NetCDF.")
    st.stop()

# ─────────────────────────────────────────────────────────────
#  PRÉPARATION
# ─────────────────────────────────────────────────────────────
time_coords = pd.to_datetime(ds.time.values)
n_steps = len(time_coords)
run_date = ds.attrs.get('run_date', time_coords[0].strftime('%d/%m/%Y %H:%M UTC'))
region = ds.attrs.get('region', 'Sud-Est France')

@st.cache_data(ttl=3600, show_spinner=False)
def compute_spatial_means(_ds):
    return _ds.mean(dim=['lat', 'lon']).to_dataframe()

df_mean = compute_spatial_means(ds)

# ─────────────────────────────────────────────────────────────
#  INITIALISATION SESSION STATE
# ─────────────────────────────────────────────────────────────
if 'step_idx' not in st.session_state:
    st.session_state.step_idx = 0
if 'playing' not in st.session_state:
    st.session_state.playing = False

# ─────────────────────────────────────────────────────────────
#  SIDEBAR — Navigation + contrôles temporels
# ─────────────────────────────────────────────────────────────
with st.sidebar:
    # Logo / titre
    st.markdown(f"""
    <div style="padding:12px 4px 8px;border-bottom:1px solid var(--border);margin-bottom:12px">
        <div style="font-size:1.0rem;font-weight:700;color:var(--text)">🔥 IFM · AROME</div>
        <div style="font-size:0.7rem;color:var(--muted);margin-top:2px">Prévision 1.3 km</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Navigation
    st.markdown('<div style="font-size:0.68rem;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:var(--muted);margin-bottom:6px">Navigation</div>', unsafe_allow_html=True)
    page = st.radio(
        "page",
        ["🗺  Cartographie", "📈  Séries temporelles", "🔬  Analyse"],
        label_visibility="collapsed",
    )
    st.markdown('<div style="height:1px;background:var(--border);margin:14px 0"></div>', unsafe_allow_html=True)
    
    # Contrôle temporel amélioré
    st.markdown('<div style="font-size:0.68rem;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:var(--muted);margin-bottom:8px">Contrôle Temporel</div>', unsafe_allow_html=True)
    
    # Boutons de contrôle
    col_play, col_prev, col_next = st.columns([1, 1, 1])
    with col_play:
        play_label = "⏸️" if st.session_state.playing else "▶️"
        if st.button(play_label, key="play_btn", use_container_width=True):
            st.session_state.playing = not st.session_state.playing
            st.rerun()
    with col_prev:
        if st.button("◀️", key="prev_btn", use_container_width=True):
            st.session_state.step_idx = max(0, st.session_state.step_idx - 1)
            st.session_state.playing = False
            st.rerun()
    with col_next:
        if st.button("▶️", key="next_btn", use_container_width=True):
            st.session_state.step_idx = min(n_steps - 1, st.session_state.step_idx + 1)
            st.session_state.playing = False
            st.rerun()
    
    # Slider temporel
    step_idx = st.slider(
        "Échéance",
        min_value=0, max_value=n_steps - 1, value=st.session_state.step_idx,
        label_visibility="collapsed",
    )
    st.session_state.step_idx = step_idx
    
    selected_time = time_coords[step_idx]
    st.markdown(f"""
    <div class="ech-label">{selected_time.strftime('%a %d/%m · %H:00 UTC')}</div>
    <div style="font-size:0.72rem;color:var(--muted)">+{step_idx}h depuis le run</div>
    """, unsafe_allow_html=True)
    
    # Animation speed
    st.markdown('<div style="font-size:0.65rem;color:var(--muted);margin-top:8px">Vitesse animation</div>', unsafe_allow_html=True)
    anim_speed = st.select_slider("Vitesse", options=[0.5, 1.0, 2.0, 3.0], value=1.0, label_visibility="collapsed")
    
    st.markdown('<div style="height:1px;background:var(--border);margin:14px 0"></div>', unsafe_allow_html=True)
    
    # Métadonnées run
    st.markdown('<div style="font-size:0.68rem;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:var(--muted);margin-bottom:8px">Run</div>', unsafe_allow_html=True)
    st.markdown(f"""
    <div class="info-block">
        <b>Date :</b> {run_date}<br>
        <b>Région :</b> {region}<br>
        <b>Résolution :</b> 1.3 km<br>
        <b>Échéances :</b> {n_steps} × 1h
    </div>
    """, unsafe_allow_html=True)
    st.markdown('<div style="height:1px;background:var(--border);margin:14px 0"></div>', unsafe_allow_html=True)
    
    # Légende IFM
    st.markdown('<div style="font-size:0.68rem;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:var(--muted);margin-bottom:8px">Niveaux IFM</div>', unsafe_allow_html=True)
    for label, col, bg in [
        ("Faible · < 10",        "#2e7d32", "#e8f5e9"),
        ("Modéré · 10–30",       "#f57f17", "#fff8e1"),
        ("Fort · 30–50",         "#e65100", "#fff3e0"),
        ("Très fort · 50–80",    "#c62828", "#ffebee"),
        ("Exceptionnel · > 80",  "#880e4f", "#fce4ec"),
    ]:
        st.markdown(f"""
        <div class="ifm-legend-row">
            <div class="ifm-dot" style="background:{col}"></div>
            <span>{label}</span>
        </div>""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
#  DONNÉES TRANCHE SÉLECTIONNÉE
# ─────────────────────────────────────────────────────────────
data_slice = ds.sel(time=selected_time)

def safe_mean(var):
    return float(data_slice[var].mean()) if var in data_slice else 0

def safe_max(var):
    return float(data_slice[var].max()) if var in data_slice else 0

ifm_mean = safe_mean('ifm')
ifm_max = safe_max('ifm')
temp_val = safe_mean('temp')
wind_val = safe_mean('wind')
hr_val = safe_mean('hr')
rain_val = float(data_slice['rain'].sum()) if 'rain' in data_slice else 0

level_lbl, level_col, level_bg = ifm_level(ifm_mean)

# Deltas
if step_idx > 0:
    prev = ds.isel(time=step_idx - 1)
    d_ifm = ifm_mean - float(prev['ifm'].mean()) if 'ifm' in prev else 0
    d_temp = temp_val - float(prev['temp'].mean()) if 'temp' in prev else 0
    d_wind = wind_val - float(prev['wind'].mean()) if 'wind' in prev else 0
else:
    d_ifm = d_temp = d_wind = 0

def delta_str(v, unit=''):
    if abs(v) < 0.05:
        return '<span style="color:var(--muted)">stable</span>'
    cls = 'up' if v > 0 else 'down'
    arr = '↑' if v > 0 else '↓'
    return f'<span class="{cls}">{arr} {abs(v):.1f}{unit}</span>'

# ─────────────────────────────────────────────────────────────
#  HEADER
# ─────────────────────────────────────────────────────────────
now_utc = datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M UTC')
st.markdown(f"""
<div class="app-header">
    <div>
        <div class="app-header-title">Indice Forêt Météo — AROME 1.3 km</div>
        <div class="app-header-meta">{selected_time.strftime('%A %d %B %Y · %H:00 UTC')} · +{step_idx}h · {region}</div>
    </div>
    <div class="app-header-right">
        Run : {run_date}<br>Dernière maj : {now_utc}
    </div>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
#  MÉTRIQUES
# ─────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="metric-row">
    <div class="metric-card accent">
        <div class="metric-label">IFM moyen</div>
        <div class="metric-val" style="color:{level_col}">{ifm_mean:.1f}</div>
        <div class="metric-unit">
            <span class="ifm-badge" style="background:{level_bg};color:{level_col}">{level_lbl}</span>
        </div>
        <div class="metric-delta">{delta_str(d_ifm)}</div>
    </div>
    <div class="metric-card">
        <div class="metric-label">IFM max</div>
        <div class="metric-val">{ifm_max:.1f}</div>
        <div class="metric-unit">valeur de pointe</div>
    </div>
    <div class="metric-card">
        <div class="metric-label">Température</div>
        <div class="metric-val">{temp_val:.1f}°</div>
        <div class="metric-unit">°C · moy. spatiale</div>
        <div class="metric-delta">{delta_str(d_temp, '°')}</div>
    </div>
    <div class="metric-card">
        <div class="metric-label">Vent</div>
        <div class="metric-val">{wind_val:.0f}</div>
        <div class="metric-unit">km/h · moy. spatiale</div>
        <div class="metric-delta">{delta_str(d_wind, ' km/h')}</div>
    </div>
    <div class="metric-card">
        <div class="metric-label">Humidité</div>
        <div class="metric-val">{hr_val:.0f}%</div>
        <div class="metric-unit">HR · moy. spatiale</div>
    </div>
    <div class="metric-card">
        <div class="metric-label">Précipitations</div>
        <div class="metric-val">{rain_val:.1f}</div>
        <div class="metric-unit">mm · cumul domaine</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
#  COLORSCALE IFM
# ─────────────────────────────────────────────────────────────
ifm_cs = [
    [0.00, '#1b5e20'],
    [0.10, '#43a047'],
    [0.25, '#fdd835'],
    [0.38, '#fb8c00'],
    [0.50, '#e53935'],
    [0.70, '#b71c1c'],
    [1.00, '#880e4f'],
]

# ══════════════════════════════════════════════════════════════
#  PAGE 1 — CARTOGRAPHIE INTERACTIVE (Style Leaflet)
# ══════════════════════════════════════════════════════════════
if page == "🗺  Cartographie":
    
    # Création de la carte avec Plotly (style Leaflet)
    fig_map = go.Figure()
    
    # Heatmap de base
    fig_map.add_trace(go.Heatmap(
        z=data_slice['ifm'].values,
        x=ds.lon.values,
        y=ds.lat.values,
        colorscale=ifm_cs,
        zmin=0, zmax=100,
        colorbar=dict(
            title=dict(text='IFM', font=dict(size=11)),
            tickvals=[0, 10, 30, 50, 80, 100],
            ticktext=['0', '10', '30', '50', '80', '100'],
            thickness=14, len=0.85,
            bgcolor='rgba(255,255,255,0.9)',
            bordercolor='#e0e0e0', borderwidth=1,
            tickfont=dict(size=10),
        ),
        hovertemplate='<b>IFM : %{z:.1f}</b><br>Lon : %{x:.3f}° | Lat : %{y:.3f}°<extra></extra>',
    ))
    
    # Contour danger IFM > 50
    fig_map.add_trace(go.Contour(
        z=data_slice['ifm'].values,
        x=ds.lon.values,
        y=ds.lat.values,
        contours=dict(start=50, end=50, size=1, coloring='none',
                      showlabels=True, labelfont=dict(size=9, color='#333')),
        line=dict(color='rgba(0,0,0,0.7)', width=2, dash='solid'),
        showscale=False,
        hoverinfo='skip',
        name='Seuil danger (50)'
    ))
    
    # Contour IFM > 30 (alerte)
    fig_map.add_trace(go.Contour(
        z=data_slice['ifm'].values,
        x=ds.lon.values,
        y=ds.lat.values,
        contours=dict(start=30, end=30, size=1, coloring='none',
                      showlabels=False),
        line=dict(color='rgba(245,127,23,0.6)', width=1.5, dash='dash'),
        showscale=False,
        hoverinfo='skip',
        name='Seuil modéré (30)'
    ))
    
    # Configuration style Leaflet
    fig_map.update_layout(
        **clean_layout(
            height=650,
            margin=dict(l=0, r=0, t=30, b=0),
            title=dict(
                text=f"Carte IFM — {selected_time.strftime('%d/%m %H:00 UTC')}",
                font=dict(size=14, family='Source Sans 3'),
                x=0.5
            ),
            xaxis=dict(
                title='Longitude',
                showgrid=False,
                linecolor='#d0d0d0',
                scaleanchor='y',
                scaleratio=1,
            ),
            yaxis=dict(
                title='Latitude',
                showgrid=False,
                linecolor='#d0d0d0',
            ),
            dragmode='pan',
            hovermode='closest',
        )
    )
    
    # Ajout des boutons de zoom style Leaflet
    fig_map.update_layout(
        updatemenus=[
            dict(
                type="buttons",
                direction="left",
                buttons=[
                    dict(args=[{"xaxis.autorange": True, "yaxis.autorange": True}], 
                         label="⊕ Reset", method="relayout"),
                ],
                pad={"r": 10, "t": 10},
                showactive=False,
                x=0.01,
                xanchor="left",
                y=0.99,
                yanchor="top",
                bgcolor='rgba(255,255,255,0.9)',
                bordercolor='#ccc',
                borderwidth=1,
            )
        ]
    )
    
    st.plotly_chart(fig_map, use_container_width=True, config={
        'displayModeBar': True,
        'scrollZoom': True,
        'modeBarButtonsToRemove': ['lasso2d', 'select2d'],
        'displaylogo': False,
    })
    
    # Statistiques sous la carte
    ifm_flat = data_slice['ifm'].values.flatten()
    ifm_flat = ifm_flat[~np.isnan(ifm_flat)]
    
    pct_d = (ifm_flat > 50).mean() * 100
    pct_f = ((ifm_flat > 30) & (ifm_flat <= 50)).mean() * 100
    pct_m = ((ifm_flat > 10) & (ifm_flat <= 30)).mean() * 100
    pct_o = (ifm_flat <= 10).mean() * 100
    pct_e = (ifm_flat > 80).mean() * 100
    
    c1, c2, c3, c4, c5 = st.columns(5)
    stats_data = [
        (c1, "Faible (≤10)", pct_o, "#2e7d32", "#e8f5e9"),
        (c2, "Modéré (10–30)", pct_m, "#f57f17", "#fff8e1"),
        (c3, "Fort (30–50)", pct_f, "#e65100", "#fff3e0"),
        (c4, "Danger (50–80)", pct_d, "#c62828", "#ffebee"),
        (c5, "Exceptionnel (>80)", pct_e, "#880e4f", "#fce4ec"),
    ]
    
    for col, label, pct, color, bg in stats_data:
        col.markdown(f"""
        <div style="background:{bg};border:1px solid {color}33;border-radius:5px;
                    padding:10px 12px;text-align:center">
            <div style="font-size:0.65rem;font-weight:700;color:{color};
                        text-transform:uppercase;letter-spacing:0.08em">{label}</div>
            <div style="font-size:1.4rem;font-weight:700;color:{color};margin-top:2px">{pct:.1f}%</div>
            <div style="background:{color};height:3px;border-radius:2px;
                        margin-top:6px;opacity:0.5;width:{min(pct,100):.0f}%"></div>
        </div>
        """, unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
#  PAGE 2 — SÉRIES TEMPORELLES
# ══════════════════════════════════════════════════════════════
elif page == "📈  Séries temporelles":
    vline = selected_time
    
    # Graphique principal IFM avec enveloppe
    if 'ifm' in ds:
        ifm_s = ds['ifm'].mean(dim=['lat', 'lon']).to_series()
        ifm_mn = ds['ifm'].min(dim=['lat', 'lon']).to_series()
        ifm_mx = ds['ifm'].max(dim=['lat', 'lon']).to_series()
        ifm_p90 = ds['ifm'].quantile(0.9, dim=['lat', 'lon']).to_series()
        ifm_p10 = ds['ifm'].quantile(0.1, dim=['lat', 'lon']).to_series()
        
        fig_ifm = go.Figure()
        
        # Enveloppe P10-P90
        fig_ifm.add_trace(go.Scatter(
            x=list(ifm_s.index) + list(ifm_s.index[::-1]),
            y=list(ifm_p90.values) + list(ifm_p10.values[::-1]),
            fill='toself', fillcolor='rgba(192,57,43,0.08)',
            line=dict(width=0), name='P10-P90', hoverinfo='skip',
        ))
        
        # Enveloppe min/max
        fig_ifm.add_trace(go.Scatter(
            x=list(ifm_s.index) + list(ifm_s.index[::-1]),
            y=list(ifm_mx.values) + list(ifm_mn.values[::-1]),
            fill='toself', fillcolor='rgba(192,57,43,0.04)',
            line=dict(width=0), name='Min/Max', hoverinfo='skip',
        ))
        
        # Ligne moyenne
        fig_ifm.add_trace(go.Scatter(
            x=ifm_s.index, y=ifm_s.values,
            line=dict(color='#c0392b', width=3), name='Moyenne',
            hovertemplate='<b>%{x|%d/%m %H:00}</b><br>IFM : %{y:.1f}<extra></extra>',
        ))
        
        # Seuils
        fig_ifm.add_hline(y=50, line_color='rgba(180,0,0,0.6)', line_dash='dash',
                          line_width=2, annotation_text='Danger (50)',
                          annotation_font=dict(size=11, color='#c0392b'))
        fig_ifm.add_hline(y=30, line_color='rgba(230,120,0,0.5)', line_dash='dot', 
                          line_width=1.5, annotation_text='Modéré (30)',
                          annotation_font=dict(size=10, color='#e65100'))
        
        # Ligne verticale temps sélectionné
        fig_ifm.add_vline(x=vline, line_color='rgba(0,0,0,0.4)', line_width=2,
                          annotation_text='Sélection', annotation_position='top')
        
        fig_ifm.update_layout(**clean_layout(
            height=350,
            title=dict(text='Évolution de l\'IFM — Moyenne spatiale avec enveloppes',
                       font=dict(size=14, family='Source Sans 3'), x=0),
            yaxis=dict(title='IFM', range=[0, None]),
            xaxis=dict(title='Date/Heure'),
            showlegend=True,
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        ))
        st.plotly_chart(fig_ifm, use_container_width=True, config={'displayModeBar': False})
    
    # Deux graphiques côte à côte
    col_a, col_b = st.columns(2)
    
    with col_a:
        if 'temp' in ds and 'hr' in ds:
            fig_th = make_subplots(specs=[[{"secondary_y": True}]])
            
            temp_s = ds['temp'].mean(dim=['lat', 'lon']).to_series()
            hr_s = ds['hr'].mean(dim=['lat', 'lon']).to_series()
            
            # Température avec gradient de couleur
            fig_th.add_trace(go.Scatter(
                x=temp_s.index, y=temp_s.values,
                line=dict(color='#e65100', width=2.5), name='Température (°C)',
                fill='tozeroy', fillcolor='rgba(230,81,0,0.1)',
            ), secondary_y=False)
            
            # Humidité
            fig_th.add_trace(go.Scatter(
                x=hr_s.index, y=hr_s.values,
                line=dict(color='#1565c0', width=2, dash='dot'), name='Humidité (%)',
            ), secondary_y=True)
            
            fig_th.add_vline(x=vline, line_color='rgba(0,0,0,0.3)', line_width=1.5)
            
            fig_th.update_layout(**clean_layout(
                height=300,
                title=dict(text='Température & Humidité Relative', 
                          font=dict(size=13, family='Source Sans 3'), x=0),
                legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
            ))
            fig_th.update_yaxes(title_text='Température (°C)', secondary_y=False, 
                               gridcolor='#ebebeb', color='#e65100')
            fig_th.update_yaxes(title_text='HR (%)', secondary_y=True, 
                               showgrid=False, color='#1565c0')
            st.plotly_chart(fig_th, use_container_width=True, config={'displayModeBar': False})
    
    with col_b:
        if 'wind' in ds:
            wind_s = ds['wind'].mean(dim=['lat', 'lon']).to_series()
            wind_mx = ds['wind'].max(dim=['lat', 'lon']).to_series()
            wind_mn = ds['wind'].min(dim=['lat', 'lon']).to_series()
            
            fig_w = go.Figure()
            
            # Zone min-max
            fig_w.add_trace(go.Scatter(
                x=list(wind_s.index) + list(wind_s.index[::-1]),
                y=list(wind_mx.values) + list(wind_mn.values[::-1]),
                fill='toself', fillcolor='rgba(21,101,192,0.08)',
                line=dict(width=0), name='Min/Max', hoverinfo='skip',
            ))
            
            # Vent moyen
            fig_w.add_trace(go.Scatter(
                x=wind_s.index, y=wind_s.values,
                line=dict(color='#1565c0', width=2.5), name='Vent moyen',
                fill='tozeroy', fillcolor='rgba(21,101,192,0.05)',
            ))
            
            fig_w.add_vline(x=vline, line_color='rgba(0,0,0,0.3)', line_width=1.5)
            
            fig_w.update_layout(**clean_layout(
                height=300,
                title=dict(text='Vitesse du Vent', font=dict(size=13, family='Source Sans 3'), x=0),
                yaxis=dict(title='km/h'),
                showlegend=False,
            ))
            st.plotly_chart(fig_w, use_container_width=True, config={'displayModeBar': False})
    
    # Tableau des échéances
    st.markdown('<div class="section-title">Tableau des échéances</div>', unsafe_allow_html=True)
    display_cols = [c for c in ['ifm', 'temp', 'wind', 'hr', 'rain'] if c in df_mean.columns]
    df_disp = df_mean[display_cols].copy().round(1)
    df_disp.index = df_disp.index.strftime('%a %d/%m · %H:00')
    df_disp.columns = [c.upper() for c in df_disp.columns]
    
    # Mise en évidence de la ligne sélectionnée
    st.dataframe(df_disp, use_container_width=True, height=280)

# ══════════════════════════════════════════════════════════════
#  PAGE 3 — ANALYSE
# ══════════════════════════════════════════════════════════════
elif page == "🔬  Analyse":
    available_vars = [v for v in ['ifm', 'temp', 'wind', 'hr', 'rain'] if v in data_slice]
    
    col_c1, col_c2 = st.columns(2)
    
    with col_c1:
        st.markdown('<div class="section-title">IFM vs Température (coloré par vent)</div>', 
                   unsafe_allow_html=True)
        if len(available_vars) >= 2:
            df_sc = pd.DataFrame({
                v: data_slice[v].values.flatten() for v in ['ifm', 'temp', 'wind', 'hr']
                if v in data_slice
            }).dropna()
            
            if len(df_sc) > 5000:
                df_sc = df_sc.sample(5000, random_state=42)
            
            fig_sc = go.Figure(go.Scatter(
                x=df_sc['temp'], y=df_sc['ifm'], mode='markers',
                marker=dict(
                    color=df_sc['wind'] if 'wind' in df_sc else '#c0392b',
                    colorscale='Blues',
                    size=4,
                    opacity=0.6,
                    colorbar=dict(title='Vent<br>(km/h)', thickness=12, len=0.7,
                                  tickfont=dict(size=10)),
                ),
                hovertemplate='T : %{x:.1f}°C | IFM : %{y:.1f} | Vent : %{marker.color:.0f} km/h<extra></extra>',
            ))
            
            # Ajout de lignes de régression
            if len(df_sc) > 10:
                z = np.polyfit(df_sc['temp'], df_sc['ifm'], 1)
                p = np.poly1d(z)
                x_line = np.linspace(df_sc['temp'].min(), df_sc['temp'].max(), 100)
                fig_sc.add_trace(go.Scatter(
                    x=x_line, y=p(x_line),
                    mode='lines', line=dict(color='rgba(192,57,43,0.5)', width=2, dash='dash'),
                    name='Tendance', hoverinfo='skip'
                ))
            
            fig_sc.update_layout(**clean_layout(
                height=350,
                xaxis=dict(title='Température (°C)'),
                yaxis=dict(title='IFM'),
            ))
            st.plotly_chart(fig_sc, use_container_width=True, config={'displayModeBar': False})
    
    with col_c2:
        st.markdown('<div class="section-title">Matrice de corrélation</div>', unsafe_allow_html=True)
        if len(available_vars) >= 3:
            df_corr = pd.DataFrame({
                v: data_slice[v].values.flatten() for v in available_vars
            }).dropna().corr()
            
            fig_co = go.Figure(go.Heatmap(
                z=df_corr.values,
                x=[v.upper() for v in df_corr.columns],
                y=[v.upper() for v in df_corr.index],
                colorscale=[[0, '#1565c0'], [0.5, '#f5f5f5'], [1, '#c62828']],
                zmin=-1, zmax=1,
                text=df_corr.values.round(2),
                texttemplate='%{text}',
                textfont=dict(size=12, color='#1a1a2e'),
                hovertemplate='%{x} vs %{y}<br>Corrélation : %{z:.2f}<extra></extra>',
            ))
            
            fig_co.update_layout(**clean_layout(
                height=350,
                margin=dict(l=40, r=10, t=20, b=10),
            ))
            st.plotly_chart(fig_co, use_container_width=True, config={'displayModeBar': False})
    
    # Box plots IFM par échéance
    st.markdown('<div class="section-title">Distribution IFM par échéance</div>', unsafe_allow_html=True)
    if 'ifm' in ds:
        step_sel = max(1, n_steps // 12)
        
        fig_box = go.Figure()
        colors_box = []
        
        for i, t in enumerate(time_coords[::step_sel]):
            vals = ds['ifm'].sel(time=t).values.flatten()
            vals = vals[~np.isnan(vals)]
            
            # Couleur selon la moyenne
            mean_val = np.mean(vals)
            if mean_val < 10:
                color = '#2e7d32'
            elif mean_val < 30:
                color = '#f57f17'
            elif mean_val < 50:
                color = '#e65100'
            elif mean_val < 80:
                color = '#c62828'
            else:
                color = '#880e4f'
            
            fig_box.add_trace(go.Box(
                y=vals, 
                name=pd.Timestamp(t).strftime('%d/%m %Hh'),
                marker_color=color,
                line=dict(color=color, width=1.5),
                fillcolor='rgba(255,255,255,0.3)',
                boxpoints=False, 
                whiskerwidth=0.5,
                hovertemplate='%{x}<br>IFM : %{y:.1f}<extra></extra>',
            ))
        
        fig_box.add_hline(y=50, line_color='rgba(180,0,0,0.5)', 
                         line_dash='dash', line_width=2,
                         annotation_text='Danger', annotation_position='right')
        fig_box.add_hline(y=30, line_color='rgba(230,120,0,0.4)', 
                         line_dash='dot', line_width=1.5,
                         annotation_text='Modéré', annotation_position='right')
        
        # Ligne verticale pour l'échéance sélectionnée
        selected_idx = step_idx // step_sel
        if selected_idx < len(time_coords[::step_sel]):
            fig_box.add_vline(x=selected_idx, line_color='rgba(0,0,0,0.5)', 
                            line_width=2, line_dash='solid')
        
        fig_box.update_layout(**clean_layout(
            height=350,
            showlegend=False,
            xaxis=dict(title='Échéance', tickangle=-45),
            yaxis=dict(title='IFM', range=[0, max(100, ds['ifm'].max().values * 1.1)]),
        ))
        st.plotly_chart(fig_box, use_container_width=True, config={'displayModeBar': False})

# ─────────────────────────────────────────────────────────────
#  FOOTER
# ─────────────────────────────────────────────────────────────
st.markdown(f"""
<div style="margin-top:1.5rem;padding:8px 0;border-top:1px solid var(--border);
            display:flex;justify-content:space-between;
            font-size:0.65rem;color:var(--muted)">
    <span>IFM · AROME 1.3 km · Données Météo-France</span>
    <span>Généré le {now_utc} · Cache 1h</span>
</div>
""", unsafe_allow_html=True)

# Auto-refresh pour l'animation
if st.session_state.playing:
    time.sleep(1.0 / anim_speed)
    if st.session_state.step_idx < n_steps - 1:
        st.session_state.step_idx += 1
    else:
        st.session_state.playing = False
    st.rerun()
