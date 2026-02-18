import streamlit as st
import xarray as xr
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import json, os, tempfile
from datetime import datetime, UTC
import folium
from streamlit_folium import st_folium
import matplotlib.pyplot as plt
import matplotlib.cm as cm

st.set_page_config(
    layout="wide",
    page_title="IFM · AROME 1.3km",
    page_icon="🔥",
    initial_sidebar_state="expanded"
)

# ═════════════════════════════════════════════════════════════
#  CSS
# ═════════════════════════════════════════════════════════════
st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@300;400;600;700&display=swap" rel="stylesheet">
<style>
:root {--bg:#f4f5f7;--white:#fff;--border:#dde1e7;--text:#1c2333;--muted:#6b7280;--accent:#c0392b;}
html,body,[class*="css"]{font-family:'Source Sans 3',sans-serif!important;background:var(--bg)!important;}
#MainMenu,footer,header,[data-testid="stToolbar"],[data-testid="stDecoration"]{display:none!important}
.block-container{padding:1rem!important;}
[data-testid="stSidebar"]{background:linear-gradient(180deg,#fff 0%,#f8f9fa 100%)!important;border-right:1px solid var(--border)!important;box-shadow:4px 0 10px rgba(0,0,0,0.05)!important}

.fire-container{display:flex;justify-content:center;align-items:center;height:200px;gap:5px}
.flame{width:20px;height:40px;background:linear-gradient(to top,#ff4500,#ffa500,#ffff00);border-radius:50% 50% 50% 50%/60% 60% 40% 40%;animation:flicker 0.3s infinite alternate;box-shadow:0 0 20px #ff4500}
.flame:nth-child(2){animation-delay:0.1s}.flame:nth-child(3){animation-delay:0.2s}
.flame:nth-child(4){animation-delay:0.15s}.flame:nth-child(5){animation-delay:0.25s}
@keyframes flicker{0%{transform:scaleY(1) translateY(0);opacity:1}50%{transform:scaleY(1.2) translateY(-5px);opacity:0.8}100%{transform:scaleY(0.9) translateY(2px);opacity:1}}
.loading-text{text-align:center;margin-top:20px;font-size:18px;color:#ff6347;font-weight:bold}

.metric-card{background:var(--white);border:1px solid var(--border);border-radius:8px;padding:16px;margin:8px 0;border-left:4px solid var(--accent)}
.metric-label{font-size:0.7rem;font-weight:600;text-transform:uppercase;color:var(--muted);margin-bottom:4px}
.metric-val{font-size:1.6rem;font-weight:700;color:var(--text)}
.section-title{font-size:0.75rem;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;color:var(--muted);border-bottom:1px solid var(--border);padding-bottom:4px;margin:1rem 0 0.6rem}
</style>
""", unsafe_allow_html=True)

# ═════════════════════════════════════════════════════════════
#  CHARGEMENT
# ═════════════════════════════════════════════════════════════

def open_nc(path):
    for engine in ["netcdf4", "h5netcdf", "scipy"]:
        try:
            return xr.open_dataset(path, engine=engine)
        except Exception:
            continue
    raise RuntimeError("Aucun engine xarray disponible")

@st.cache_data(ttl=3600, show_spinner=False)
def load_netcdf():
    REPO, BRANCH, NCFILE = "Matthieu-Lacroix/AROME1.3km_IFM_Horaire", "main", "arome_fwi_complet.nc"
    token = None
    try:
        token = st.secrets["GITHUB_TOKEN"]
    except Exception:
        pass
    if not token:
        token = os.environ.get("GITHUB_TOKEN")
    auth = {"Authorization": f"token {token}"} if token else {}

    def stream(url, h):
        tmp = tempfile.NamedTemporaryFile(suffix=".nc", delete=False)
        r = requests.get(url, headers=h, stream=True, timeout=300)
        r.raise_for_status()
        for c in r.iter_content(512 * 1024):
            tmp.write(c)
        tmp.flush()
        tmp.close()
        return tmp.name

    for lp in [
        f"/mount/src/{REPO.split('/')[-1].lower()}/{NCFILE}",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), NCFILE)
    ]:
        if os.path.exists(lp) and os.path.getsize(lp) > 1000:
            try:
                return open_nc(lp)
            except Exception:
                pass

    mu = f"https://api.github.com/repos/{REPO}/contents/{NCFILE}?ref={BRANCH}"
    mr = requests.get(mu, headers={**auth, "Accept": "application/vnd.github.v3+json"}, timeout=20)
    mr.raise_for_status()
    m = mr.json()
    dl, sz = m.get("download_url"), m.get("size", 0)
    if not dl or sz < 500:
        lu = f"https://media.githubusercontent.com/media/{REPO}/{BRANCH}/{NCFILE}"
        tp = stream(lu, {**auth, "Accept": "application/octet-stream"})
        ds = open_nc(tp)
        os.unlink(tp)
        return ds
    tp = stream(dl, {**auth, "Accept": "application/octet-stream"})
    ds = open_nc(tp)
    os.unlink(tp)
    return ds

@st.cache_data(ttl=3600, show_spinner=False)
def load_geojson():
    REPO, BRANCH, GEO = "Matthieu-Lacroix/AROME1.3km_IFM_Horaire", "main", "dep.geojson"
    token = None
    try:
        token = st.secrets["GITHUB_TOKEN"]
    except Exception:
        pass
    if not token:
        token = os.environ.get("GITHUB_TOKEN")
    auth = {"Authorization": f"token {token}"} if token else {}
    for lp in [
        f"/mount/src/{REPO.split('/')[-1].lower()}/{GEO}",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), GEO)
    ]:
        if os.path.exists(lp):
            try:
                with open(lp, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
    ru = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/{GEO}"
    r = requests.get(ru, headers=auth, timeout=30)
    r.raise_for_status()
    return r.json()

# Écran de chargement
if 'ds' not in st.session_state:
    ld = st.empty()
    with ld.container():
        st.markdown("""
        <div class="fire-container">
            <div class="flame"></div><div class="flame"></div><div class="flame"></div>
            <div class="flame"></div><div class="flame"></div>
        </div>
        <div class="loading-text">🔥 Chargement des données météo... 🔥</div>
        """, unsafe_allow_html=True)
    st.session_state.ds = load_netcdf()
    st.session_state.geojson = load_geojson()
    ld.empty()

ds = st.session_state.ds
geojson = st.session_state.geojson

# ═════════════════════════════════════════════════════════════
#  DÉTECTION AUTOMATIQUE DES NOMS DE COORDONNÉES
# ═════════════════════════════════════════════════════════════

def _find_coord(ds, candidates):
    """Trouve le nom réel d'une coordonnée parmi plusieurs candidats possibles."""
    for c in candidates:
        if c in ds.coords or c in ds.dims:
            return c
    available = list(ds.coords) + list(ds.dims)
    raise KeyError(
        f"Aucune coordonnée trouvée parmi {candidates}. "
        f"Coordonnées disponibles dans le fichier : {available}"
    )

LAT = _find_coord(ds, ["latitude", "lat", "LAT", "y", "Y"])
LON = _find_coord(ds, ["longitude", "lon", "LON", "long", "LONG", "x", "X"])

# ═════════════════════════════════════════════════════════════
#  SESSION STATE
# ═════════════════════════════════════════════════════════════
if 'step_idx' not in st.session_state:
    st.session_state.step_idx = 0
if 'lat_target' not in st.session_state:
    st.session_state.lat_target = 45.0
if 'lon_target' not in st.session_state:
    st.session_state.lon_target = 5.0
if 'variable' not in st.session_state:
    st.session_state.variable = 'ifm'

time_coords = pd.to_datetime(ds.time.values)
n_steps = len(time_coords)

# ═════════════════════════════════════════════════════════════
#  SIDEBAR
# ═════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("### 🔥 IFM · AROME 1.3km")
    st.caption("Prévision numérique haute résolution")
    st.markdown('<div style="height:1px;background:#ddd;margin:12px 0"></div>', unsafe_allow_html=True)

    st.markdown('<div class="section-title">Variable</div>', unsafe_allow_html=True)
    var_choice = st.selectbox("var", ["IFM", "Température", "Vent", "Humidité"], label_visibility="collapsed")
    var_map = {"IFM": "ifm", "Température": "temp", "Vent": "wind", "Humidité": "hr"}
    st.session_state.variable = var_map[var_choice]

    st.markdown('<div class="section-title">Échéance</div>', unsafe_allow_html=True)
    new_idx = st.slider("Échéance", 0, n_steps - 1, st.session_state.step_idx, label_visibility="collapsed")
    if new_idx != st.session_state.step_idx:
        st.session_state.step_idx = new_idx

    sel_time = time_coords[st.session_state.step_idx]
    st.markdown(f"**{sel_time.strftime('%a %d/%m · %H:00 UTC')}**")
    st.caption(f"+{st.session_state.step_idx}h depuis le run")

    cols = st.columns(5)
    if cols[0].button("⏮", use_container_width=True, key="first"):
        st.session_state.step_idx = 0
        st.rerun()
    if cols[1].button("◀", use_container_width=True, key="prev"):
        st.session_state.step_idx = max(0, st.session_state.step_idx - 1)
        st.rerun()
    cols[2].button("▶", use_container_width=True, key="play")  # placeholder
    if cols[3].button("▶", use_container_width=True, key="next"):
        st.session_state.step_idx = min(n_steps - 1, st.session_state.step_idx + 1)
        st.rerun()
    if cols[4].button("⏭", use_container_width=True, key="last"):
        st.session_state.step_idx = n_steps - 1
        st.rerun()

# ═════════════════════════════════════════════════════════════
#  CARTE LEAFLET INTERACTIVE
# ═════════════════════════════════════════════════════════════

def create_raster_overlay(data_arr, cmap_name='RdYlGn_r'):
    """Convertit un DataArray xarray en image RGBA pour overlay Folium."""
    data = data_arr.values.astype(np.float32)
    data = np.where(np.isfinite(data), data, np.nan)
    valid_mask = ~np.isnan(data)
    if not np.any(valid_mask):
        return None, None
    vmin, vmax = np.nanpercentile(data, [2, 98])
    if not np.isfinite(vmin) or not np.isfinite(vmax) or vmin >= vmax:
        vmin, vmax = 0, 1
    norm_data = np.clip((data - vmin) / (vmax - vmin), 0, 1)
    norm_data = np.nan_to_num(norm_data, nan=0.0)
    cmap = cm.get_cmap(cmap_name)
    rgba = cmap(norm_data)
    rgba[..., 3] = np.where(valid_mask, 0.7, 0)
    img = (np.clip(rgba, 0, 1) * 255).astype(np.uint8)
    return np.flipud(img), (vmin, vmax)

data_slice = ds.isel(time=st.session_state.step_idx)
var_key = st.session_state.variable

cmap_cfg = {"ifm": "RdYlGn_r", "temp": "RdYlBu_r", "wind": "Blues", "hr": "GnBu"}
cmap_name = cmap_cfg.get(var_key, "RdYlGn_r")

img, vrange = create_raster_overlay(data_slice[var_key], cmap_name)

# Utilisation de LAT/LON détectés automatiquement
lats = ds[LAT].values
lons = ds[LON].values
center_lat = (float(lats.min()) + float(lats.max())) / 2
center_lon = (float(lons.min()) + float(lons.max())) / 2

m = folium.Map(location=[center_lat, center_lon], zoom_start=8, tiles="OpenStreetMap")

if img is not None:
    bounds = [
        [float(lats.min()), float(lons.min())],
        [float(lats.max()), float(lons.max())]
    ]
    folium.raster_layers.ImageOverlay(
        image=img, bounds=bounds, opacity=1.0,
        interactive=True, cross_origin=False, zindex=1
    ).add_to(m)

# Départements GeoJSON
for feat in geojson.get('features', []):
    geom = feat.get('geometry', {})
    if geom.get('type') == 'Polygon':
        coords_list = [geom['coordinates']]
    elif geom.get('type') == 'MultiPolygon':
        coords_list = geom['coordinates']
    else:
        continue
    for poly in coords_list:
        for ring in poly:
            lons_d = [c[0] for c in ring]
            lats_d = [c[1] for c in ring]
            folium.PolyLine(
                locations=list(zip(lats_d, lons_d)),
                color='rgba(0,0,0,0.6)', weight=1.5
            ).add_to(m)

# Marqueur cible
folium.Marker(
    location=[st.session_state.lat_target, st.session_state.lon_target],
    popup="Point actif",
    icon=folium.Icon(color="red", icon="crosshairs", prefix='fa')
).add_to(m)

map_data = st_folium(m, width="100%", height=650, returned_objects=["last_clicked"])

# Gestion clic
if map_data and map_data.get("last_clicked"):
    clicked = map_data["last_clicked"]
    st.session_state.lat_target = clicked["lat"]
    st.session_state.lon_target = clicked["lng"]
    st.rerun()

# ═════════════════════════════════════════════════════════════
#  MÉTRIQUES POINT ACTIF
# ═════════════════════════════════════════════════════════════

def safe_mean(var):
    return float(data_slice[var].mean()) if var in data_slice else 0.0

st.markdown('<div class="section-title">📍 Métriques Point Actif</div>', unsafe_allow_html=True)
st.caption(f"Coordonnées : {st.session_state.lat_target:.4f}°N, {st.session_state.lon_target:.4f}°E")

cols = st.columns(4)
metrics = [
    ("🔥 IFM",  safe_mean('ifm'),  ""),
    ("🌡️ Temp", safe_mean('temp'), "°C"),
    ("💨 Vent",  safe_mean('wind'), "km/h"),
    ("💧 HR",   safe_mean('hr'),   "%"),
]
for col, (lbl, val, unit) in zip(cols, metrics):
    col.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">{lbl}</div>
        <div class="metric-val">{val:.1f}<span style="font-size:0.9rem;color:#999">{unit}</span></div>
    </div>
    """, unsafe_allow_html=True)

# ═════════════════════════════════════════════════════════════
#  GRAPHIQUES TEMPORELS
# ═════════════════════════════════════════════════════════════

st.markdown('<div class="section-title">📈 Séries Temporelles</div>', unsafe_allow_html=True)

try:
    # Sélection du point le plus proche avec les noms de coordonnées détectés
    ts = ds.sel({LAT: st.session_state.lat_target, LON: st.session_state.lon_target}, method="nearest")

    df = pd.DataFrame({
        "H+":  range(n_steps),
        "IFM": ts['ifm'].values  if 'ifm'  in ts else [0] * n_steps,
        "Temp":ts['temp'].values if 'temp' in ts else [0] * n_steps,
        "Vent":ts['wind'].values if 'wind' in ts else [0] * n_steps,
        "HR":  ts['hr'].values   if 'hr'   in ts else [0] * n_steps,
    })

    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=("IFM", "Température", "Vent", "Humidité"),
        vertical_spacing=0.12
    )
    fig.add_trace(go.Scatter(x=df['H+'], y=df['IFM'],  fill='tozeroy',
        fillcolor='rgba(192,57,43,0.1)', line=dict(color='#c0392b', width=2), name='IFM'),  row=1, col=1)
    fig.add_trace(go.Scatter(x=df['H+'], y=df['Temp'], line=dict(color='#e65100', width=2), name='Temp'), row=1, col=2)
    fig.add_trace(go.Scatter(x=df['H+'], y=df['Vent'], line=dict(color='#1565c0', width=2), name='Vent'), row=2, col=1)
    fig.add_trace(go.Scatter(x=df['H+'], y=df['HR'],   line=dict(color='#43a047', width=2), name='HR'),   row=2, col=2)

    fig.add_vline(x=st.session_state.step_idx, line_color='rgba(0,0,0,0.3)', line_width=1)
    fig.update_layout(
        height=600, showlegend=False, template="plotly_white",
        font=dict(family='Source Sans 3', size=11)
    )
    fig.update_xaxes(showgrid=True, gridcolor='#ebebeb')
    fig.update_yaxes(showgrid=True, gridcolor='#ebebeb')

    st.plotly_chart(fig, use_container_width=True)

    # Tableau
    st.markdown('<div class="section-title">Tableau des échéances</div>', unsafe_allow_html=True)
    df_disp = df.copy().round(1)
    st.dataframe(df_disp, use_container_width=True, height=250)

except Exception as e:
    st.error(f"Erreur graphiques : {e}")
