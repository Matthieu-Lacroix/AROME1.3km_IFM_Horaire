import streamlit as st
import xarray as xr
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import io, json, os, tempfile
from datetime import datetime, UTC

st.set_page_config(layout="wide", page_title="IFM · AROME 1.3km", page_icon="🔥", initial_sidebar_state="auto")

# ─────────────────────────────────────────────────────────────
#  CHARGEMENT
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
    REPO, BRANCH, NCFILE = "Matthieu-Lacroix/AROME1.3km_IFM_Horaire", "main", "arome_fwi_complet.nc"
    token = None
    try:    token = st.secrets["GITHUB_TOKEN"]
    except Exception: pass
    if not token: token = os.environ.get("GITHUB_TOKEN")
    auth = {"Authorization": f"token {token}"} if token else {}

    def stream_to_tmp(url, headers):
        tmp = tempfile.NamedTemporaryFile(suffix=".nc", delete=False)
        r = requests.get(url, headers=headers, stream=True, timeout=300)
        r.raise_for_status()
        for chunk in r.iter_content(chunk_size=512*1024):
            tmp.write(chunk)
        tmp.flush(); tmp.close()
        return tmp.name

    for local_path in [f"/mount/src/{REPO.split('/')[-1].lower()}/{NCFILE}", os.path.join(os.path.dirname(os.path.abspath(__file__)), NCFILE)]:
        if os.path.exists(local_path) and os.path.getsize(local_path) > 1000:
            try:
                return open_nc(local_path)
            except Exception:
                pass

    meta_url = f"https://api.github.com/repos/{REPO}/contents/{NCFILE}?ref={BRANCH}"
    meta_r = requests.get(meta_url, headers={**auth, "Accept": "application/vnd.github.v3+json"}, timeout=20)
    meta_r.raise_for_status()
    meta = meta_r.json()
    dl_url, size = meta.get("download_url"), meta.get("size", 0)

    if not dl_url or size < 500:
        lfs_url = f"https://media.githubusercontent.com/media/{REPO}/{BRANCH}/{NCFILE}"
        tmp_path = stream_to_tmp(lfs_url, {**auth, "Accept": "application/octet-stream"})
        ds = open_nc(tmp_path)
        os.unlink(tmp_path)
        return ds

    tmp_path = stream_to_tmp(dl_url, {**auth, "Accept": "application/octet-stream"})
    ds = open_nc(tmp_path)
    os.unlink(tmp_path)
    return ds

@st.cache_data(ttl=3600, show_spinner=False)
def load_geojson():
    REPO, BRANCH, GEOFILE = "Matthieu-Lacroix/AROME1.3km_IFM_Horaire", "main", "dep.geojson"
    token = None
    try:    token = st.secrets["GITHUB_TOKEN"]
    except Exception: pass
    if not token: token = os.environ.get("GITHUB_TOKEN")
    auth = {"Authorization": f"token {token}"} if token else {}

    for local_path in [f"/mount/src/{REPO.split('/')[-1].lower()}/{GEOFILE}", os.path.join(os.path.dirname(os.path.abspath(__file__)), GEOFILE)]:
        if os.path.exists(local_path):
            try:
                with open(local_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass

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
    if val < 10:  return "Faible",       "#2e7d32", "#e8f5e9"
    if val < 30:  return "Modéré",       "#f57f17", "#fff8e1"
    if val < 50:  return "Fort",         "#e65100", "#fff3e0"
    if val < 80:  return "Très fort",    "#c62828", "#ffebee"
    return              "Exceptionnel",  "#880e4f", "#fce4ec"

def clean_layout(**kwargs):
    base = dict(
        paper_bgcolor='#ffffff', plot_bgcolor='#fafafa',
        font=dict(family='Source Sans 3, sans-serif', size=12, color='#1a1a2e'),
        xaxis=dict(gridcolor='#ebebeb', zeroline=False, showline=True, linecolor='#d0d0d0', linewidth=1),
        yaxis=dict(gridcolor='#ebebeb', zeroline=False, showline=True, linecolor='#d0d0d0', linewidth=1),
        margin=dict(l=10, r=10, t=40, b=10),
        legend=dict(bgcolor='rgba(255,255,255,0.9)', bordercolor='#e0e0e0', borderwidth=1, font=dict(size=11)),
        hoverlabel=dict(bgcolor='#ffffff', bordercolor='#c0392b', font=dict(family='Source Sans 3, sans-serif', size=12)),
    )
    base.update(kwargs)
    return base

time_coords = pd.to_datetime(ds.time.values)
n_steps     = len(time_coords)
run_date    = ds.attrs.get('run_date', time_coords[0].strftime('%d/%m/%Y %H:%M'))
region      = ds.attrs.get('region', 'Sud-Est France')

@st.cache_data(ttl=3600, show_spinner=False)
def compute_means(_ds):
    return _ds.mean(dim=['lat','lon']).to_dataframe()

df_mean = compute_means(ds)

# ─────────────────────────────────────────────────────────────
#  CSS
# ─────────────────────────────────────────────────────────────
st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@300;400;600;700&family=Source+Code+Pro:wght@400;500&display=swap" rel="stylesheet">
<style>
:root { --bg:#f4f5f7; --white:#fff; --border:#dde1e7; --text:#1c2333; --muted:#6b7280; --accent:#c0392b; --accent-l:#fdf2f2; }
html,body,[class*="css"]{font-family:'Source Sans 3',sans-serif!important;background:var(--bg)!important;color:var(--text)!important}
#MainMenu,footer,header,[data-testid="stToolbar"],[data-testid="stDecoration"]{display:none!important}
.block-container{padding-top:1rem!important;padding-bottom:1rem!important}
[data-testid="stSidebar"]{background:var(--white)!important;border-right:1px solid var(--border)!important}
[data-testid="stSidebar"] *{color:var(--text)!important}
[data-testid="stSidebar"] [data-testid="stRadio"] > div{flex-direction:column;gap:2px}
[data-testid="stSidebar"] [data-testid="stRadio"] label{display:flex!important;align-items:center!important;padding:9px 12px!important;border-radius:5px!important;font-size:0.85rem!important;font-weight:400!important;cursor:pointer!important;transition:background 0.15s!important;border:none!important;width:100%!important}
[data-testid="stSidebar"] [data-testid="stRadio"] label:hover{background:var(--bg)!important}
[data-testid="stSidebar"] [data-testid="stRadio"] [aria-checked="true"] + div + label{background:var(--accent-l)!important;color:var(--accent)!important;font-weight:600!important}
[data-testid="stSidebar"] [data-testid="stRadio"] input[type="radio"]{display:none!important}
[data-testid="stSlider"] [data-baseweb="slider"] div[role="slider"]{background:var(--accent)!important;border-color:var(--accent)!important}
[data-testid="stSlider"] [data-baseweb="slider"] div[data-testid="stSlider-track-fill"]{background:var(--accent)!important}
.metric-row{display:grid;grid-template-columns:repeat(6,1fr);gap:10px;margin-bottom:1rem}
.metric-card{background:var(--white);border:1px solid var(--border);border-radius:6px;padding:12px 14px;border-top:3px solid var(--border)}
.metric-card.accent{border-top-color:var(--accent)}
.metric-label{font-size:0.68rem;font-weight:600;letter-spacing:0.1em;text-transform:uppercase;color:var(--muted);margin-bottom:4px}
.metric-val{font-size:1.5rem;font-weight:700;color:var(--text);line-height:1.1}
.metric-unit{font-size:0.72rem;color:var(--muted);margin-top:2px}
.metric-delta{font-size:0.7rem;margin-top:3px}
.up{color:#c62828}.down{color:#2e7d32}
.ifm-badge{display:inline-block;padding:2px 8px;border-radius:3px;font-size:0.68rem;font-weight:700;letter-spacing:0.08em;text-transform:uppercase}
.section-title{font-size:0.72rem;font-weight:700;letter-spacing:0.14em;text-transform:uppercase;color:var(--muted);padding-bottom:6px;border-bottom:1px solid var(--border);margin:1rem 0 0.75rem}
.info-block{background:var(--white);border:1px solid var(--border);border-radius:6px;padding:12px 14px;font-size:0.8rem;color:var(--muted);line-height:1.6}
.info-block b{color:var(--text)}
.app-header{display:flex;align-items:center;justify-content:space-between;background:var(--white);border:1px solid var(--border);border-left:4px solid var(--accent);border-radius:0 6px 6px 0;padding:10px 16px;margin-bottom:1rem}
.app-header-title{font-size:1rem;font-weight:700;color:var(--text);letter-spacing:0.03em}
.app-header-meta{font-size:0.72rem;color:var(--muted);margin-top:1px}
.app-header-right{font-size:0.72rem;color:var(--muted);text-align:right}
.ifm-legend-row{display:flex;align-items:center;gap:8px;padding:4px 0;font-size:0.78rem;color:var(--muted)}
.ifm-dot{width:10px;height:10px;border-radius:2px;flex-shrink:0}
.ech-label{font-size:1rem;font-weight:600;color:var(--accent);margin:0.4rem 0 0.8rem}
[data-testid="stDataFrame"]{border:1px solid var(--border)!important;border-radius:6px!important}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
#  ÉTAT
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
    <div style="padding:12px 4px 8px;border-bottom:1px solid var(--border);margin-bottom:12px">
        <div style="font-size:1.0rem;font-weight:700;color:var(--text)">🔥 IFM · AROME</div>
        <div style="font-size:0.7rem;color:var(--muted);margin-top:2px">Prévision 1.3 km</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div style="font-size:0.68rem;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:var(--muted);margin-bottom:6px">Navigation</div>', unsafe_allow_html=True)
    page = st.radio("page", ["🗺  Cartographie", "📈  Séries temporelles", "📊  Graphiques"], label_visibility="collapsed")

    st.markdown('<div style="height:1px;background:var(--border);margin:14px 0"></div>', unsafe_allow_html=True)

    st.markdown('<div style="font-size:0.68rem;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:var(--muted);margin-bottom:8px">Échéance</div>', unsafe_allow_html=True)

    new_idx = st.slider("Échéance", 0, n_steps-1, st.session_state.step_idx, label_visibility="collapsed")
    if new_idx != st.session_state.step_idx:
        st.session_state.step_idx = new_idx
        st.session_state.is_playing = False

    selected_time = time_coords[st.session_state.step_idx]
    st.markdown(f"""
    <div class="ech-label">{selected_time.strftime('%a %d/%m · %H:00 UTC')}</div>
    <div style="font-size:0.72rem;color:var(--muted)">+{st.session_state.step_idx}h depuis le run</div>
    """, unsafe_allow_html=True)

    col1, col2, col3, col4, col5 = st.columns(5)
    if col1.button("⏮", width="stretch", key="first"):
        st.session_state.step_idx = 0
        st.session_state.is_playing = False
        st.rerun()
    if col2.button("◀", width="stretch", key="prev"):
        st.session_state.step_idx = max(0, st.session_state.step_idx - 1)
        st.session_state.is_playing = False
        st.rerun()
    play_label = "⏸" if st.session_state.is_playing else "▶"
    if col3.button(play_label, width="stretch", key="play"):
        st.session_state.is_playing = not st.session_state.is_playing
        st.rerun()
    if col4.button("▶", width="stretch", key="next"):
        st.session_state.step_idx = min(n_steps-1, st.session_state.step_idx + 1)
        st.session_state.is_playing = False
        st.rerun()
    if col5.button("⏭", width="stretch", key="last"):
        st.session_state.step_idx = n_steps - 1
        st.session_state.is_playing = False
        st.rerun()

    speed_opt = st.selectbox("Vitesse", ["0.5×", "1×", "2×", "4×"], index=1, label_visibility="collapsed")
    st.session_state.play_speed = {"0.5×":0.5, "1×":1.0, "2×":2.0, "4×":4.0}[speed_opt]

    st.markdown('<div style="height:1px;background:var(--border);margin:14px 0"></div>', unsafe_allow_html=True)

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

    st.markdown('<div style="font-size:0.68rem;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:var(--muted);margin-bottom:8px">Niveaux IFM</div>', unsafe_allow_html=True)
    for label, col, bg in [
        ("Faible · < 10",        "#2e7d32", "#e8f5e9"),
        ("Modéré · 10–30",       "#f57f17", "#fff8e1"),
        ("Fort · 30–50",         "#e65100", "#fff3e0"),
        ("Très fort · 50–80",    "#c62828", "#ffebee"),
        ("Exceptionnel · > 80",  "#880e4f", "#fce4ec"),
    ]:
        st.markdown(f'<div class="ifm-legend-row"><div class="ifm-dot" style="background:{col}"></div><span>{label}</span></div>', unsafe_allow_html=True)

# Autoplay
if st.session_state.is_playing:
    import time
    time.sleep(1.0 / st.session_state.play_speed)
    st.session_state.step_idx = (st.session_state.step_idx + 1) % n_steps
    st.rerun()

# ─────────────────────────────────────────────────────────────
#  DONNÉES
# ─────────────────────────────────────────────────────────────
data_slice = ds.isel(time=st.session_state.step_idx)

def safe_mean(var): return float(data_slice[var].mean()) if var in data_slice else 0
def safe_max(var):  return float(data_slice[var].max())  if var in data_slice else 0

ifm_mean  = safe_mean('ifm')
ifm_max   = safe_max('ifm')
temp_val  = safe_mean('temp')
wind_val  = safe_mean('wind')
hr_val    = safe_mean('hr')
rain_val  = float(data_slice['rain'].sum()) if 'rain' in data_slice else 0

level_lbl, level_col, level_bg = ifm_level(ifm_mean)

if st.session_state.step_idx > 0:
    prev = ds.isel(time=st.session_state.step_idx - 1)
    d_ifm  = ifm_mean - float(prev['ifm'].mean())  if 'ifm'  in prev else 0
    d_temp = temp_val - float(prev['temp'].mean()) if 'temp' in prev else 0
    d_wind = wind_val - float(prev['wind'].mean()) if 'wind' in prev else 0
else:
    d_ifm = d_temp = d_wind = 0

def delta_str(v, unit=''):
    if abs(v) < 0.05: return '<span style="color:var(--muted)">stable</span>'
    cls = 'up' if v > 0 else 'down'
    arr = '↑' if v > 0 else '↓'
    return f'<span class="{cls}">{arr} {abs(v):.1f}{unit}</span>'

now_utc = datetime.now(UTC).strftime('%d/%m/%Y %H:%M UTC')
st.markdown(f"""
<div class="app-header">
    <div>
        <div class="app-header-title">Indice Forêt Météo — AROME 1.3 km</div>
        <div class="app-header-meta">{selected_time.strftime('%A %d %B %Y · %H:00 UTC')} · +{st.session_state.step_idx}h · {region}</div>
    </div>
    <div class="app-header-right">Run : {run_date}<br>Dernière maj : {now_utc}</div>
</div>
""", unsafe_allow_html=True)

st.markdown(f"""
<div class="metric-row">
    <div class="metric-card accent">
        <div class="metric-label">IFM moyen</div>
        <div class="metric-val" style="color:{level_col}">{ifm_mean:.1f}</div>
        <div class="metric-unit"><span class="ifm-badge" style="background:{level_bg};color:{level_col}">{level_lbl}</span></div>
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

# ══════════════════════════════════════════════════════════════
#  PAGE CARTE — Scattermapbox interactif
# ══════════════════════════════════════════════════════════════
if page == "🗺  Cartographie":

    # Carte Mapbox OSM avec points IFM + départements
    lons = ds.lon.values
    lats = ds.lat.values
    ifm_vals = data_slice['ifm'].values

    lon_mesh, lat_mesh = np.meshgrid(lons, lats)
    flat_lon = lon_mesh.flatten()
    flat_lat = lat_mesh.flatten()
    flat_ifm = ifm_vals.flatten()
    mask = ~np.isnan(flat_ifm)
    flat_lon, flat_lat, flat_ifm = flat_lon[mask], flat_lat[mask], flat_ifm[mask]

    # Sous-échantillonnage pour perf
    if len(flat_ifm) > 8000:
        idx = np.random.choice(len(flat_ifm), 8000, replace=False)
        flat_lon, flat_lat, flat_ifm = flat_lon[idx], flat_lat[idx], flat_ifm[idx]

    fig = go.Figure()

    fig.add_trace(go.Scattermapbox(
        lon=flat_lon, lat=flat_lat, mode='markers',
        marker=dict(
            size=6, color=flat_ifm,
            colorscale=[
                [0.00, '#1b5e20'], [0.10, '#43a047'], [0.25, '#fdd835'],
                [0.38, '#fb8c00'], [0.50, '#e53935'], [0.70, '#b71c1c'], [1.00, '#880e4f'],
            ],
            cmin=0, cmax=100, opacity=0.65,
            colorbar=dict(
                title="IFM", thickness=12, len=0.7,
                tickvals=[0,10,30,50,80,100],
                bgcolor='rgba(255,255,255,0.9)',
                bordercolor='#d0d0d0', borderwidth=1,
            ),
        ),
        hovertemplate='<b>IFM : %{marker.color:.1f}</b><br>Lon : %{lon:.3f}° | Lat : %{lat:.3f}°<extra></extra>',
        name='IFM',
    ))

    # Départements GeoJSON
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
                    lon=lons_dep, lat=lats_dep, mode='lines',
                    line=dict(color='rgba(0,0,0,0.6)', width=1.5),
                    hoverinfo='skip', showlegend=False,
                ))

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

    st.plotly_chart(fig, width="stretch", config={'displayModeBar': False})

    # Stats
    ifm_flat = data_slice['ifm'].values.flatten()
    ifm_flat = ifm_flat[~np.isnan(ifm_flat)]
    pcts = [
        ("Faible (≤10)", (ifm_flat <= 10).mean()*100, "#2e7d32", "#e8f5e9"),
        ("Modéré (10–30)", ((ifm_flat > 10) & (ifm_flat <= 30)).mean()*100, "#f57f17", "#fff8e1"),
        ("Fort (30–50)", ((ifm_flat > 30) & (ifm_flat <= 50)).mean()*100, "#e65100", "#fff3e0"),
        ("Danger (50–80)", ((ifm_flat > 50) & (ifm_flat <= 80)).mean()*100, "#c62828", "#ffebee"),
        ("Exceptionnel (>80)", (ifm_flat > 80).mean()*100, "#880e4f", "#fce4ec"),
    ]

    cols = st.columns(5)
    for col, (lbl, pct, color, bg) in zip(cols, pcts):
        col.markdown(f"""
        <div style="background:{bg};border:1px solid {color}33;border-radius:5px;padding:10px 12px;text-align:center">
            <div style="font-size:0.65rem;font-weight:700;color:{color};text-transform:uppercase;letter-spacing:0.08em">{lbl}</div>
            <div style="font-size:1.4rem;font-weight:700;color:{color};margin-top:2px">{pct:.1f}%</div>
            <div style="background:{color};height:3px;border-radius:2px;margin-top:6px;opacity:0.5;width:{min(pct,100):.0f}%"></div>
        </div>
        """, unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
#  PAGE SÉRIES TEMPORELLES
# ══════════════════════════════════════════════════════════════
elif page == "📈  Séries temporelles":
    vline = selected_time

    if 'ifm' in ds:
        ifm_s, ifm_mn, ifm_mx, ifm_p90 = ds['ifm'].mean(dim=['lat','lon']).to_series(), ds['ifm'].min(dim=['lat','lon']).to_series(), ds['ifm'].max(dim=['lat','lon']).to_series(), ds['ifm'].quantile(0.9, dim=['lat','lon']).to_series()
        fig_ifm = go.Figure()
        fig_ifm.add_trace(go.Scatter(x=list(ifm_s.index)+list(ifm_s.index[::-1]), y=list(ifm_mx.values)+list(ifm_mn.values[::-1]), fill='toself', fillcolor='rgba(192,57,43,0.08)', line=dict(width=0), name='Min/Max', hoverinfo='skip'))
        fig_ifm.add_trace(go.Scatter(x=ifm_p90.index, y=ifm_p90.values, line=dict(color='rgba(192,57,43,0.35)', width=1, dash='dot'), name='P90'))
        fig_ifm.add_trace(go.Scatter(x=ifm_s.index, y=ifm_s.values, line=dict(color='#c0392b', width=2.5), name='Moyenne', hovertemplate='<b>%{x|%d/%m %H:00}</b><br>IFM : %{y:.1f}<extra></extra>'))
        fig_ifm.add_hline(y=50, line_color='rgba(180,0,0,0.4)', line_dash='dash', line_width=1, annotation_text='Seuil danger (50)', annotation_font=dict(size=10, color='#c0392b'))
        fig_ifm.add_hline(y=30, line_color='rgba(230,120,0,0.3)', line_dash='dot', line_width=1)
        fig_ifm.add_vline(x=vline, line_color='rgba(0,0,0,0.25)', line_width=1)
        fig_ifm.update_layout(**clean_layout(height=280, title=dict(text='Indice Forêt Météo', font=dict(size=13, family='Source Sans 3'), x=0), yaxis=dict(title='IFM', range=[0, None])))
        st.plotly_chart(fig_ifm, width="stretch", config={'displayModeBar': False})

    col_a, col_b = st.columns(2)
    with col_a:
        if 'temp' in ds and 'hr' in ds:
            fig_th = make_subplots(specs=[[{"secondary_y": True}]])
            temp_s, hr_s = ds['temp'].mean(dim=['lat','lon']).to_series(), ds['hr'].mean(dim=['lat','lon']).to_series()
            fig_th.add_trace(go.Scatter(x=temp_s.index, y=temp_s.values, line=dict(color='#e65100', width=2), name='Temp (°C)'), secondary_y=False)
            fig_th.add_trace(go.Scatter(x=hr_s.index, y=hr_s.values, line=dict(color='#1565c0', width=1.5, dash='dot'), name='HR (%)'), secondary_y=True)
            fig_th.add_vline(x=vline, line_color='rgba(0,0,0,0.2)', line_width=1)
            fig_th.update_layout(**clean_layout(height=250, title=dict(text='Température & Humidité', font=dict(size=12, family='Source Sans 3'), x=0)))
            fig_th.update_yaxes(title_text='°C', secondary_y=False, gridcolor='#ebebeb')
            fig_th.update_yaxes(title_text='HR (%)', secondary_y=True, showgrid=False)
            st.plotly_chart(fig_th, width="stretch", config={'displayModeBar': False})

    with col_b:
        if 'wind' in ds:
            wind_s, wind_mx = ds['wind'].mean(dim=['lat','lon']).to_series(), ds['wind'].max(dim=['lat','lon']).to_series()
            fig_w = go.Figure()
            fig_w.add_trace(go.Scatter(x=wind_s.index, y=wind_mx.values, fill='tozeroy', fillcolor='rgba(21,101,192,0.06)', line=dict(width=0), name='Max', hoverinfo='skip'))
            fig_w.add_trace(go.Scatter(x=wind_s.index, y=wind_s.values, line=dict(color='#1565c0', width=2), name='Vent moy (km/h)'))
            fig_w.add_vline(x=vline, line_color='rgba(0,0,0,0.2)', line_width=1)
            fig_w.update_layout(**clean_layout(height=250, title=dict(text='Vent (km/h)', font=dict(size=12, family='Source Sans 3'), x=0), yaxis=dict(title='km/h')))
            st.plotly_chart(fig_w, width="stretch", config={'displayModeBar': False})

    st.markdown('<div class="section-title">Tableau des échéances</div>', unsafe_allow_html=True)
    display_cols = [c for c in ['ifm', 'temp', 'wind', 'hr', 'rain'] if c in df_mean.columns]
    df_disp = df_mean[display_cols].copy().round(1)
    df_disp.index = df_disp.index.strftime('%a %d/%m · %H:00')
    df_disp.columns = [c.upper() for c in df_disp.columns]
    st.dataframe(df_disp, width="stretch", height=280)

# ══════════════════════════════════════════════════════════════
#  PAGE GRAPHIQUES
# ══════════════════════════════════════════════════════════════
elif page == "📊  Graphiques":
    vars_plot = ['ifm', 'temp', 'wind', 'hr', 'rain']
    existing  = [v for v in vars_plot if v in ds]

    fig_all = make_subplots(rows=len(existing), cols=1, shared_xaxes=True, vertical_spacing=0.06, subplot_titles=[v.upper() for v in existing])

    for i, var in enumerate(existing, start=1):
        series = ds[var].mean(dim=['lat','lon']).to_series()
        fig_all.add_trace(go.Scatter(x=series.index, y=series.values, line=dict(color='#c0392b', width=2), name=var.upper(), hovertemplate='%{x|%d/%m %H:00}<br>%{y:.1f}<extra></extra>'), row=i, col=1)
        fig_all.add_vline(x=selected_time, line_color='rgba(0,0,0,0.25)', line_width=1, row=i, col=1)

    fig_all.update_layout(height=200*len(existing), showlegend=False, margin=dict(l=10, r=10, t=30, b=10), paper_bgcolor='#fff', plot_bgcolor='#fafafa', font=dict(family='Source Sans 3', size=11))
    fig_all.update_xaxes(showgrid=True, gridcolor='#ebebeb')
    fig_all.update_yaxes(showgrid=True, gridcolor='#ebebeb')
    st.plotly_chart(fig_all, width="stretch", config={'displayModeBar': False})

st.markdown(f'<div style="margin-top:1.5rem;padding:6px 0;border-top:1px solid var(--border);font-size:0.65rem;color:var(--muted);display:flex;justify-content:space-between"><span>IFM · AROME 1.3 km · Météo-France</span><span>Généré le {now_utc}</span></div>', unsafe_allow_html=True)
