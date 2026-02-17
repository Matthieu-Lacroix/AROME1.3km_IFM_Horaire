import streamlit as st
import xarray as xr
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import io, json, os, tempfile
from datetime import datetime

# ─────────────────────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────────────────────
st.set_page_config(
    layout="wide",
    page_title="IFM · AROME 1.3km",
    page_icon="🔥",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────
#  CHARGEMENT DONNÉES
# ─────────────────────────────────────────────────────────────

def open_nc(path):
    for engine in ["netcdf4", "h5netcdf", "scipy"]:
        try:
            return xr.open_dataset(path, engine=engine)
        except Exception:
            continue
    raise RuntimeError("Aucun engine xarray disponible.")

@st.cache_data(ttl=3600, show_spinner=False)
def load_netcdf():
    """Charge le NetCDF AROME depuis GitHub (Git LFS)."""
    REPO   = "Matthieu-Lacroix/AROME1.3km_IFM_Horaire"
    BRANCH = "main"
    NCFILE = "arome_fwi_complet.nc"

    token = None
    try:    token = st.secrets["GITHUB_TOKEN"]
    except Exception: pass
    if not token: token = os.environ.get("GITHUB_TOKEN")

    auth = {"Authorization": f"token {token}"} if token else {}

    def stream_to_tmp(url, headers, size_hint=0):
        tmp = tempfile.NamedTemporaryFile(suffix=".nc", delete=False)
        r = requests.get(url, headers=headers, stream=True, timeout=300)
        r.raise_for_status()
        for chunk in r.iter_content(chunk_size=512 * 1024):
            tmp.write(chunk)
        tmp.flush(); tmp.close()
        return tmp.name

    # Tentative fichier local
    for local_path in [
        f"/mount/src/{REPO.split('/')[-1].lower()}/{NCFILE}",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), NCFILE),
    ]:
        if os.path.exists(local_path) and os.path.getsize(local_path) > 1000:
            try:
                return open_nc(local_path)
            except Exception:
                pass

    # API GitHub
    meta_url = f"https://api.github.com/repos/{REPO}/contents/{NCFILE}?ref={BRANCH}"
    meta_r = requests.get(meta_url, headers={**auth, "Accept": "application/vnd.github.v3+json"}, timeout=20)
    meta_r.raise_for_status()
    meta = meta_r.json()

    dl_url = meta.get("download_url")
    size   = meta.get("size", 0)

    # Git LFS
    if not dl_url or size < 500:
        lfs_url = f"https://media.githubusercontent.com/media/{REPO}/{BRANCH}/{NCFILE}"
        tmp_path = stream_to_tmp(lfs_url, {**auth, "Accept": "application/octet-stream"}, 76*1024*1024)
        ds = open_nc(tmp_path)
        os.unlink(tmp_path)
        return ds

    # Fichier normal
    tmp_path = stream_to_tmp(dl_url, {**auth, "Accept": "application/octet-stream"}, size)
    ds = open_nc(tmp_path)
    os.unlink(tmp_path)
    return ds

@st.cache_data(ttl=3600, show_spinner=False)
def load_geojson():
    """Charge dep.geojson depuis le même repo GitHub."""
    REPO   = "Matthieu-Lacroix/AROME1.3km_IFM_Horaire"
    BRANCH = "main"
    GEOFILE= "dep.geojson"

    token = None
    try:    token = st.secrets["GITHUB_TOKEN"]
    except Exception: pass
    if not token: token = os.environ.get("GITHUB_TOKEN")

    auth = {"Authorization": f"token {token}"} if token else {}

    # Essai fichier local
    for local_path in [
        f"/mount/src/{REPO.split('/')[-1].lower()}/{GEOFILE}",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), GEOFILE),
    ]:
        if os.path.exists(local_path):
            try:
                with open(local_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass

    # Raw GitHub
    raw_url = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/{GEOFILE}"
    r = requests.get(raw_url, headers=auth, timeout=30)
    r.raise_for_status()
    return r.json()

with st.spinner("Chargement…"):
    ds = load_netcdf()
    geojson = load_geojson()

if ds is None:
    st.error("Impossible de charger le NetCDF.")
    st.stop()

# ─────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────
def ifm_level(val):
    if val < 10:  return "Faible",       "#2e7d32"
    if val < 30:  return "Modéré",       "#f57f17"
    if val < 50:  return "Fort",         "#e65100"
    if val < 80:  return "Très fort",    "#c62828"
    return              "Exceptionnel",  "#880e4f"

time_coords = pd.to_datetime(ds.time.values)
n_steps     = len(time_coords)
run_date    = ds.attrs.get('run_date', time_coords[0].strftime('%d/%m/%Y %H:%M'))

# ─────────────────────────────────────────────────────────────
#  CSS
# ─────────────────────────────────────────────────────────────
st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@300;400;600;700&family=Source+Code+Pro:wght@400;500&display=swap" rel="stylesheet">
<style>
:root {
    --bg: #f5f5f5; --white: #fff; --border: #d0d0d0;
    --text: #1a1a2e; --muted: #6b7280; --accent: #c0392b;
}
html, body, [class*="css"] { font-family: 'Source Sans 3', sans-serif !important; }
#MainMenu, footer, header, [data-testid="stToolbar"], [data-testid="stDecoration"] { display: none !important; }
[data-testid="stSidebar"] { background: var(--white) !important; border-right: 1px solid var(--border) !important; }
.stButton button { background: var(--accent); color: white; border: none; border-radius: 4px; }
.metric-row { display: grid; grid-template-columns: repeat(6, 1fr); gap: 10px; margin-bottom: 1rem; }
.metric-card { background: var(--white); border: 1px solid var(--border); border-radius: 5px; padding: 10px 12px; }
.metric-label { font-size: 0.65rem; font-weight: 700; text-transform: uppercase; color: var(--muted); margin-bottom: 4px; }
.metric-val { font-size: 1.4rem; font-weight: 700; color: var(--text); }
.section-title { font-size: 0.7rem; font-weight: 700; text-transform: uppercase; color: var(--muted); border-bottom: 1px solid var(--border); padding-bottom: 4px; margin: 1rem 0 0.6rem; }
.timer-bar { background: var(--white); border: 1px solid var(--border); border-radius: 5px; padding: 10px 12px; margin-bottom: 1rem; }
.timer-label { font-size: 1rem; font-weight: 600; color: var(--accent); margin-bottom: 4px; }
.timer-controls { display: flex; gap: 6px; margin-top: 8px; }
.timer-btn { background: var(--white); border: 1px solid var(--border); border-radius: 3px; padding: 4px 10px; font-size: 0.75rem; cursor: pointer; }
.timer-btn:hover { background: var(--bg); }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
#  ÉTAT SESSION
# ─────────────────────────────────────────────────────────────
if 'step_idx' not in st.session_state:
    st.session_state.step_idx = 0
if 'is_playing' not in st.session_state:
    st.session_state.is_playing = False
if 'play_speed' not in st.session_state:
    st.session_state.play_speed = 1.0

# ─────────────────────────────────────────────────────────────
#  SIDEBAR
# ─────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="padding:10px 0;border-bottom:1px solid var(--border);margin-bottom:10px">
        <div style="font-size:1rem;font-weight:700">🔥 IFM · AROME 1.3km</div>
        <div style="font-size:0.7rem;color:var(--muted)">Prévision numérique</div>
    </div>
    """, unsafe_allow_html=True)

    # Navigation
    st.markdown('<div class="section-title">Navigation</div>', unsafe_allow_html=True)
    page = st.radio("page", ["🗺 Carte", "📊 Graphiques"], label_visibility="collapsed")

    st.markdown('<div style="height:1px;background:var(--border);margin:12px 0"></div>', unsafe_allow_html=True)

    # Timer
    st.markdown('<div class="section-title">Contrôle temporel</div>', unsafe_allow_html=True)

    selected_time = time_coords[st.session_state.step_idx]
    st.markdown(f"""
    <div class="timer-bar">
        <div class="timer-label">{selected_time.strftime('%d/%m %H:00 UTC')}</div>
        <div style="font-size:0.7rem;color:var(--muted)">+{st.session_state.step_idx}h depuis le run</div>
    </div>
    """, unsafe_allow_html=True)

    # Slider
    new_idx = st.slider("Échéance", 0, n_steps-1, st.session_state.step_idx, label_visibility="collapsed")
    if new_idx != st.session_state.step_idx:
        st.session_state.step_idx = new_idx
        st.session_state.is_playing = False

    # Boutons de contrôle
    col1, col2, col3, col4, col5 = st.columns(5)
    if col1.button("⏮", use_container_width=True):
        st.session_state.step_idx = 0
        st.session_state.is_playing = False
        st.rerun()
    if col2.button("◀", use_container_width=True):
        st.session_state.step_idx = max(0, st.session_state.step_idx - 1)
        st.session_state.is_playing = False
        st.rerun()

    play_label = "⏸ Pause" if st.session_state.is_playing else "▶ Play"
    if col3.button(play_label, use_container_width=True):
        st.session_state.is_playing = not st.session_state.is_playing
        st.rerun()

    if col4.button("▶", use_container_width=True):
        st.session_state.step_idx = min(n_steps-1, st.session_state.step_idx + 1)
        st.session_state.is_playing = False
        st.rerun()
    if col5.button("⏭", use_container_width=True):
        st.session_state.step_idx = n_steps - 1
        st.session_state.is_playing = False
        st.rerun()

    # Vitesse
    speed_opt = st.selectbox("Vitesse", ["0.5×", "1×", "2×", "4×"], index=1, label_visibility="collapsed")
    st.session_state.play_speed = {"0.5×":0.5, "1×":1.0, "2×":2.0, "4×":4.0}[speed_opt]

    st.markdown('<div style="height:1px;background:var(--border);margin:12px 0"></div>', unsafe_allow_html=True)

    # Métadonnées
    st.markdown('<div class="section-title">Run</div>', unsafe_allow_html=True)
    st.markdown(f"""
    <div style="background:var(--white);border:1px solid var(--border);border-radius:5px;padding:8px 10px;font-size:0.75rem">
        <b>Date :</b> {run_date}<br>
        <b>Résolution :</b> 1.3 km<br>
        <b>Échéances :</b> {n_steps} × 1h
    </div>
    """, unsafe_allow_html=True)

# Autoplay
if st.session_state.is_playing:
    import time
    time.sleep(1.0 / st.session_state.play_speed)
    st.session_state.step_idx = (st.session_state.step_idx + 1) % n_steps
    st.rerun()

# ─────────────────────────────────────────────────────────────
#  DONNÉES TRANCHE
# ─────────────────────────────────────────────────────────────
data_slice = ds.isel(time=st.session_state.step_idx)

def safe_mean(var): return float(data_slice[var].mean()) if var in data_slice else 0
def safe_max(var):  return float(data_slice[var].max())  if var in data_slice else 0

ifm_m  = safe_mean('ifm')
ifm_mx = safe_max('ifm')
temp_m = safe_mean('temp')
wind_m = safe_mean('wind')
hr_m   = safe_mean('hr')
rain_s = float(data_slice['rain'].sum()) if 'rain' in data_slice else 0

level_lbl, level_col = ifm_level(ifm_m)

# Header
now_utc = datetime.utcnow().strftime('%d/%m/%Y %H:%M UTC')
st.markdown(f"""
<div style="display:flex;justify-content:space-between;background:var(--white);border:1px solid var(--border);border-left:3px solid var(--accent);border-radius:0 5px 5px 0;padding:10px 14px;margin-bottom:1rem">
    <div>
        <div style="font-weight:700;font-size:0.95rem">Indice Forêt Météo — AROME 1.3 km</div>
        <div style="font-size:0.7rem;color:var(--muted)">{selected_time.strftime('%A %d %B %Y · %H:00 UTC')} · +{st.session_state.step_idx}h</div>
    </div>
    <div style="text-align:right;font-size:0.7rem;color:var(--muted)">
        Run : {run_date}<br>Dernière maj : {now_utc}
    </div>
</div>
""", unsafe_allow_html=True)

# Métriques
st.markdown(f"""
<div class="metric-row">
    <div class="metric-card">
        <div class="metric-label">IFM moyen</div>
        <div class="metric-val" style="color:{level_col}">{ifm_m:.1f}</div>
        <div style="font-size:0.65rem;margin-top:2px;color:{level_col}">{level_lbl}</div>
    </div>
    <div class="metric-card">
        <div class="metric-label">IFM max</div>
        <div class="metric-val">{ifm_mx:.1f}</div>
    </div>
    <div class="metric-card">
        <div class="metric-label">Température</div>
        <div class="metric-val">{temp_m:.1f}°</div>
    </div>
    <div class="metric-card">
        <div class="metric-label">Vent</div>
        <div class="metric-val">{wind_m:.0f}</div>
        <div style="font-size:0.65rem;margin-top:2px">km/h</div>
    </div>
    <div class="metric-card">
        <div class="metric-label">Humidité</div>
        <div class="metric-val">{hr_m:.0f}%</div>
    </div>
    <div class="metric-card">
        <div class="metric-label">Précip.</div>
        <div class="metric-val">{rain_s:.1f}</div>
        <div style="font-size:0.65rem;margin-top:2px">mm</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ═════════════════════════════════════════════════════════════
#  PAGE CARTE
# ═════════════════════════════════════════════════════════════
if page == "🗺 Carte":

    # Carte Mapbox avec fond OSM + IFM en overlay + départements GeoJSON
    ifm_vals = data_slice['ifm'].values
    lons = ds.lon.values
    lats = ds.lat.values

    # Grille IFM (raster discret)
    lon_mesh, lat_mesh = np.meshgrid(lons, lats)

    fig = go.Figure()

    # IFM en heatmap mapbox (approximation via scatter density)
    # Note: Plotly Mapbox ne supporte pas imshow directement, on utilise densitymapbox
    flat_lon = lon_mesh.flatten()
    flat_lat = lat_mesh.flatten()
    flat_ifm = ifm_vals.flatten()
    # Filtre NaN
    mask = ~np.isnan(flat_ifm)
    flat_lon = flat_lon[mask]
    flat_lat = flat_lat[mask]
    flat_ifm = flat_ifm[mask]

    # Sous-échantillonnage si trop de points (perf)
    if len(flat_ifm) > 10000:
        idx = np.random.choice(len(flat_ifm), 10000, replace=False)
        flat_lon = flat_lon[idx]
        flat_lat = flat_lat[idx]
        flat_ifm = flat_ifm[idx]

    fig.add_trace(go.Scattermapbox(
        lon=flat_lon,
        lat=flat_lat,
        mode='markers',
        marker=dict(
            size=8,
            color=flat_ifm,
            colorscale=[
                [0.00, '#2e7d32'],
                [0.10, '#43a047'],
                [0.30, '#fdd835'],
                [0.50, '#e65100'],
                [0.70, '#c62828'],
                [1.00, '#880e4f'],
            ],
            cmin=0, cmax=100,
            opacity=0.6,
            colorbar=dict(
                title="IFM",
                thickness=12, len=0.75,
                tickvals=[0, 10, 30, 50, 80, 100],
                bgcolor='rgba(255,255,255,0.9)',
                bordercolor='#d0d0d0', borderwidth=1,
            ),
        ),
        hovertemplate='<b>IFM : %{marker.color:.1f}</b><br>Lon : %{lon:.3f}° | Lat : %{lat:.3f}°<extra></extra>',
        name='IFM',
    ))

    # Overlay départements GeoJSON
    for feat in geojson.get('features', []):
        geom = feat.get('geometry', {})
        if geom.get('type') == 'Polygon':
            coords_list = [geom['coordinates']]
        elif geom.get('type') == 'MultiPolygon':
            coords_list = geom['coordinates']
        else:
            continue

        for polygon in coords_list:
            for ring in polygon:
                lons_dep = [c[0] for c in ring]
                lats_dep = [c[1] for c in ring]
                fig.add_trace(go.Scattermapbox(
                    lon=lons_dep,
                    lat=lats_dep,
                    mode='lines',
                    line=dict(color='rgba(0,0,0,0.5)', width=1.5),
                    hoverinfo='skip',
                    showlegend=False,
                ))

    # Centre de la carte
    center_lat = (lats.min() + lats.max()) / 2
    center_lon = (lons.min() + lons.max()) / 2

    fig.update_layout(
        mapbox=dict(
            style="open-street-map",
            center=dict(lat=center_lat, lon=center_lon),
            zoom=7,
        ),
        margin=dict(l=0, r=0, t=0, b=0),
        height=650,
        showlegend=False,
    )

    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

# ═════════════════════════════════════════════════════════════
#  PAGE GRAPHIQUES
# ═════════════════════════════════════════════════════════════
elif page == "📊 Graphiques":

    # Séries temporelles toutes variables
    vars_plot = ['ifm', 'temp', 'wind', 'hr', 'rain']
    existing  = [v for v in vars_plot if v in ds]

    fig = make_subplots(
        rows=len(existing), cols=1,
        shared_xaxes=True,
        vertical_spacing=0.06,
        subplot_titles=[v.upper() for v in existing],
    )

    for i, var in enumerate(existing, start=1):
        series = ds[var].mean(dim=['lat','lon']).to_series()
        fig.add_trace(go.Scatter(
            x=series.index, y=series.values,
            line=dict(color='#c0392b', width=2),
            name=var.upper(),
            hovertemplate='%{x|%d/%m %H:00}<br>%{y:.1f}<extra></extra>',
        ), row=i, col=1)

        # Ligne verticale échéance sélectionnée
        fig.add_vline(
            x=selected_time,
            line_color='rgba(0,0,0,0.25)',
            line_width=1,
            row=i, col=1,
        )

    fig.update_layout(
        height=200 * len(existing),
        showlegend=False,
        margin=dict(l=10, r=10, t=30, b=10),
        paper_bgcolor='#fff',
        plot_bgcolor='#fafafa',
        font=dict(family='Source Sans 3', size=11),
    )
    fig.update_xaxes(showgrid=True, gridcolor='#ebebeb')
    fig.update_yaxes(showgrid=True, gridcolor='#ebebeb')

    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

# Footer
st.markdown(f"""
<div style="margin-top:1.5rem;padding:6px 0;border-top:1px solid var(--border);
            font-size:0.65rem;color:var(--muted);display:flex;justify-content:space-between">
    <span>IFM · AROME 1.3 km · Météo-France</span>
    <span>Généré le {now_utc}</span>
</div>
""", unsafe_allow_html=True)
