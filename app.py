import os
import json
import tempfile
import requests
import time
from datetime import datetime, UTC

import numpy as np
import pandas as pd
import xarray as xr
import streamlit as st
import folium
from streamlit_folium import st_folium
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import matplotlib
import matplotlib.cm as cm
import matplotlib.colors as mcolors

# ═════════════════════════════════════════════════════════════
#  CONFIGURATION & CSS "PYROCAST"
# ═════════════════════════════════════════════════════════════
st.set_page_config(
    layout="wide",
    page_title="PyroCast · AROME",
    page_icon="🔥",
    initial_sidebar_state="expanded"
)

css_code = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');

:root {
    --bg-app: #f4f6f9;
    --card-bg: #ffffff;
    --border: #e2e8f0;
    --text-main: #0f172a;
    --text-muted: #64748b;
    --accent: #ef4444; 
}

.stApp { background: var(--bg-app) !important; font-family: 'Inter', sans-serif !important; }
[data-testid="stSidebar"] { background: var(--card-bg) !important; border-right: 1px solid var(--border) !important; box-shadow: 2px 0 12px rgba(0,0,0,0.03) !important; }

/* Dashboard Metrics Top */
.metrics-row { display: flex; gap: 1rem; margin-bottom: 1rem; }
.metric-card {
    flex: 1; background: var(--card-bg); border: 1px solid var(--border); border-radius: 12px;
    padding: 16px 20px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    border-top: 4px solid var(--accent); transition: transform 0.2s ease;
}
.metric-card:hover { transform: translateY(-2px); }
.metric-label { font-size: 0.75rem; font-weight: 700; text-transform: uppercase; color: var(--text-muted); margin-bottom: 4px; letter-spacing: 0.05em; }
.metric-val { font-size: 2rem; font-weight: 800; color: var(--text-main); line-height: 1.1;}
.metric-unit { font-size: 1rem; color: #94a3b8; font-weight: 500; margin-left: 4px; }

.section-title { font-size: 0.8rem; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: var(--text-muted); border-bottom: 2px solid var(--border); padding-bottom: 6px; margin: 1.5rem 0 1rem; }

/* Animation Loading */
.fire-container {display:flex; justify-content:center; align-items:center; height:150px; gap:5px}
.flame {width:20px; height:40px; background:linear-gradient(to top,#ef4444,#f59e0b,#fbbf24); border-radius:50% 50% 50% 50%/60% 60% 40% 40%; animation:flicker 0.3s infinite alternate; box-shadow:0 0 20px #ef4444}
.flame:nth-child(2) {animation-delay:0.1s} .flame:nth-child(3) {animation-delay:0.2s}
@keyframes flicker { 0% {transform:scaleY(1) translateY(0); opacity:1} 50% {transform:scaleY(1.2) translateY(-5px); opacity:0.8} 100% {transform:scaleY(0.9) translateY(2px); opacity:1} }

/* Table Pandas styling */
[data-testid="stDataFrame"] { border-radius: 8px; overflow: hidden; border: 1px solid var(--border); }
</style>
"""
st.markdown(css_code, unsafe_allow_html=True)

# ═════════════════════════════════════════════════════════════
#  CHARGEMENT DONNÉES
# ═════════════════════════════════════════════════════════════
def open_nc(path):
    for engine in ["netcdf4", "h5netcdf", "scipy"]:
        try: return xr.open_dataset(path, engine=engine)
        except Exception: continue
    raise RuntimeError("Aucun engine xarray disponible")

@st.cache_data(ttl=3600, show_spinner=False)
def load_netcdf():
    REPO, BRANCH, NCFILE = "Matthieu-Lacroix/AROME1.3km_IFM_Horaire", "main", "arome_fwi_complet.nc"
    token = st.secrets.get("GITHUB_TOKEN", os.environ.get("GITHUB_TOKEN"))
    auth = {"Authorization": f"token {token}"} if token else {}
    def stream(url, h):
        tmp = tempfile.NamedTemporaryFile(suffix=".nc", delete=False)
        r = requests.get(url, headers=h, stream=True, timeout=300)
        r.raise_for_status()
        for c in r.iter_content(512 * 1024): tmp.write(c)
        tmp.flush(); tmp.close()
        return tmp.name
    for lp in [f"/mount/src/{REPO.split('/')[-1].lower()}/{NCFILE}", os.path.join(os.path.dirname(os.path.abspath(__file__)), NCFILE)]:
        if os.path.exists(lp) and os.path.getsize(lp) > 1000:
            try: return open_nc(lp)
            except Exception: pass
    mu = f"https://api.github.com/repos/{REPO}/contents/{NCFILE}?ref={BRANCH}"
    mr = requests.get(mu, headers={**auth, "Accept": "application/vnd.github.v3+json"}, timeout=20)
    mr.raise_for_status()
    m = mr.json()
    dl, sz = m.get("download_url"), m.get("size", 0)
    if not dl or sz < 500:
        lu = f"https://media.githubusercontent.com/media/{REPO}/{BRANCH}/{NCFILE}"
        tp = stream(lu, {**auth, "Accept": "application/octet-stream"})
    else:
        tp = stream(dl, {**auth, "Accept": "application/octet-stream"})
    ds = open_nc(tp); os.unlink(tp); return ds

@st.cache_data(ttl=3600, show_spinner=False)
def load_geojson():
    REPO, BRANCH, GEO = "Matthieu-Lacroix/AROME1.3km_IFM_Horaire", "main", "dep.geojson"
    token = st.secrets.get("GITHUB_TOKEN", os.environ.get("GITHUB_TOKEN"))
    auth = {"Authorization": f"token {token}"} if token else {}
    for lp in [f"/mount/src/{REPO.split('/')[-1].lower()}/{GEO}", os.path.join(os.path.dirname(os.path.abspath(__file__)), GEO)]:
        if os.path.exists(lp):
            try:
                with open(lp, 'r') as f: return json.load(f)
            except Exception: pass
    ru = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/{GEO}"
    r = requests.get(ru, headers=auth, timeout=30)
    r.raise_for_status()
    return r.json()

if 'ds' not in st.session_state:
    ld = st.empty()
    with ld.container():
        st.markdown('<div class="fire-container"><div class="flame"></div><div class="flame"></div><div class="flame"></div></div><h3 style="text-align:center; color:#ef4444;">Connexion AROME...</h3>', unsafe_allow_html=True)
    st.session_state.ds = load_netcdf()
    st.session_state.geojson = load_geojson()
    ld.empty()

ds = st.session_state.ds
geojson = st.session_state.geojson

# ═════════════════════════════════════════════════════════════
#  FONCTIONS RASTER ET LÉGENDE SPÉCIFIQUE
# ═════════════════════════════════════════════════════════════
LAT = next(c for c in ["latitude", "lat", "LAT", "y", "Y"] if c in ds.coords or c in ds.dims)
LON = next(c for c in ["longitude", "lon", "LON", "long", "LONG", "x", "X"] if c in ds.coords or c in ds.dims)

def create_raster_overlay(data_arr, var_key):
    data = data_arr.values.astype(np.float32)
    data = np.where(np.isfinite(data), data, np.nan)
    valid_mask = ~np.isnan(data)
    if not np.any(valid_mask): return None, None
    
    if var_key == "ifm":
        # Classification stricte de l'IFM
        colors = ['#22c55e', '#eab308', '#f97316', '#e11d48', '#7f1d1d'] # Vert, Jaune, Orange, Rose/Rouge, Rouge Foncé
        bounds = [0, 5.2, 11.2, 21.3, 38, max(np.nanmax(data), 50)]
        cmap = mcolors.ListedColormap(colors)
        norm = mcolors.BoundaryNorm(bounds, cmap.N)
        
        rgba = cmap(norm(data))
        vrange = (0, bounds[-1])
    else:
        # Variables continues standards
        cmap_name = {"temp": "RdYlBu_r", "wind": "Blues", "hr": "GnBu"}.get(var_key, "viridis")
        vmin, vmax = np.nanpercentile(data, [2, 98])
        if vmin >= vmax: vmin, vmax = 0, 1
        norm_data = np.clip((data - vmin) / (vmax - vmin), 0, 1)
        try: cmap = matplotlib.colormaps.get_cmap(cmap_name)
        except AttributeError: cmap = cm.get_cmap(cmap_name)
        rgba = cmap(norm_data)
        vrange = (vmin, vmax)
        
    rgba[..., 3] = np.where(valid_mask, 0.75, 0) # Opacité ajustée pour la visibilité des fonds
    img = (np.clip(rgba, 0, 1) * 255).astype(np.uint8)
    return np.flipud(img), vrange

def render_dynamic_legend(var_key, vmin, vmax, var_name, unit):
    if var_key == "ifm":
        html = f"""
        <div style="background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; margin-top: 10px;">
            <div style="font-size: 0.75rem; font-weight: 700; color: #64748b; margin-bottom: 8px; text-transform: uppercase;">Niveaux de Danger IFM</div>
            <div style="display: flex; height: 16px; border-radius: 4px; overflow: hidden; margin-bottom: 4px;">
                <div style="flex: 1; background: #22c55e;" title="Faible (0-5.2)"></div>
                <div style="flex: 1; background: #eab308;" title="Modéré (5.2-11.2)"></div>
                <div style="flex: 1; background: #f97316;" title="Élevé (11.2-21.3)"></div>
                <div style="flex: 1; background: #e11d48;" title="Très Élevé (21.3-38)"></div>
                <div style="flex: 1; background: #7f1d1d;" title="Extrême (>38)"></div>
            </div>
            <div style="display: flex; justify-content: space-between; font-size: 0.7rem; color: #0f172a; font-weight: 600;">
                <span style="flex:1; text-align:left;">0</span>
                <span style="flex:1; text-align:center;">5.2</span>
                <span style="flex:1; text-align:center;">11.2</span>
                <span style="flex:1; text-align:center;">21.3</span>
                <span style="flex:1; text-align:right;">38+</span>
            </div>
        </div>
        """
    else:
        css_gradients = {
            "temp": "linear-gradient(to right, #313695, #74add1, #e0f3f8, #fee090, #f46d43, #a50026)",
            "wind": "linear-gradient(to right, #f7fbff, #c6dbef, #6baed6, #2171b5, #08306b)",
            "hr": "linear-gradient(to right, #f7fcf0, #ccece6, #7bccc4, #2b8cbe, #084081)"
        }
        grad = css_gradients.get(var_key, "linear-gradient(to right, #eee, #333)")
        html = f"""
        <div style="background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; margin-top: 10px;">
            <div style="font-size: 0.75rem; font-weight: 700; color: #64748b; margin-bottom: 8px; text-transform: uppercase;">{var_name} ({unit})</div>
            <div style="width: 100%; height: 12px; background: {grad}; border-radius: 4px;"></div>
            <div style="display: flex; justify-content: space-between; font-size: 0.8rem; font-weight: 600; color: #0f172a; margin-top: 6px;">
                <span>{vmin:.1f}</span>
                <span>{vmax:.1f}</span>
            </div>
        </div>
        """
    st.markdown(html, unsafe_allow_html=True)

# ═════════════════════════════════════════════════════════════
#  STATE & SIDEBAR
# ═════════════════════════════════════════════════════════════
time_coords = pd.to_datetime(ds.time.values)
n_steps = len(time_coords)
time_labels = [t.strftime('%a %d/%m - %H:00 UTC') for t in time_coords]

# Valeurs par défaut centrées sur le Rhône (Lat ~45.8, Lon ~4.6)
if 'step_idx' not in st.session_state: st.session_state.step_idx = 0
if 'lat_target' not in st.session_state: st.session_state.lat_target = 45.8
if 'lon_target' not in st.session_state: st.session_state.lon_target = 4.6
if 'variable' not in st.session_state: st.session_state.variable = 'ifm'
if 'is_playing' not in st.session_state: st.session_state.is_playing = False

with st.sidebar:
    st.markdown("<h2 style='color:#0f172a; font-weight:900; letter-spacing:-0.05em;'>🔥 PyroCast</h2>", unsafe_allow_html=True)
    st.caption("Intelligence Géospatiale | AROME 1.3km")
    
    st.markdown('<div class="section-title">Mode d\'analyse</div>', unsafe_allow_html=True)
    page_choisie = st.radio("Menu", ["🗺️ Cartographie", "📈 Météogramme & Data"], label_visibility="collapsed")

    st.markdown('<div class="section-title">Variable superposée</div>', unsafe_allow_html=True)
    var_choice = st.selectbox("var", ["Indice Forêt Météo", "Température", "Vitesse du Vent", "Humidité Relative"], label_visibility="collapsed")
    var_map = {"Indice Forêt Météo": "ifm", "Température": "temp", "Vitesse du Vent": "wind", "Humidité Relative": "hr"}
    st.session_state.variable = var_map[var_choice]
    
    st.markdown('<div class="section-title">Curseur Temporel</div>', unsafe_allow_html=True)
    selected_time_label = st.select_slider("Échéance", options=time_labels, value=time_labels[st.session_state.step_idx], label_visibility="collapsed")
    if time_labels.index(selected_time_label) != st.session_state.step_idx:
        st.session_state.step_idx = time_labels.index(selected_time_label)
        st.session_state.is_playing = False 
        st.rerun()

    st.markdown(f"**Heure affichée :** {time_labels[st.session_state.step_idx]}")
    st.caption(f"H+{st.session_state.step_idx} depuis exécution du run")
    
    cols = st.columns(5)
    if cols[0].button("⏮", width="stretch"): st.session_state.step_idx = 0; st.session_state.is_playing = False; st.rerun()
    if cols[1].button("◀", width="stretch"): st.session_state.step_idx = max(0, st.session_state.step_idx - 1); st.session_state.is_playing = False; st.rerun()
    play_icon = "⏸" if st.session_state.is_playing else "▶️"
    if cols[2].button(play_icon, width="stretch", type="primary"): st.session_state.is_playing = not st.session_state.is_playing; st.rerun()
    if cols[3].button("▶", width="stretch"): st.session_state.step_idx = min(n_steps - 1, st.session_state.step_idx + 1); st.session_state.is_playing = False; st.rerun()
    if cols[4].button("⏭", width="stretch"): st.session_state.step_idx = n_steps - 1; st.session_state.is_playing = False; st.rerun()

data_slice = ds.isel(time=st.session_state.step_idx)
var_key = st.session_state.variable
units_cfg = {"ifm": "Index", "temp": "°C", "wind": "km/h", "hr": "%"}
img, vrange = create_raster_overlay(data_slice[var_key], var_key)

# ═════════════════════════════════════════════════════════════
#  AFFICHAGE PRINCIPAL
# ═════════════════════════════════════════════════════════════

if page_choisie == "🗺️ Cartographie":
    
    # --- MÉTÉRIQUES EN HAUT (HEADS-UP) ---
    local_data = data_slice.sel({LAT: st.session_state.lat_target, LON: st.session_state.lon_target}, method="nearest")
    def get_val(var): return float(local_data[var].values) if var in local_data else 0.0

    # Déterminer la couleur de la carte IFM selon le seuil
    ifm_val = get_val('ifm')
    ifm_color = "#22c55e" if ifm_val <= 5.2 else "#eab308" if ifm_val <= 11.2 else "#f97316" if ifm_val <= 21.3 else "#e11d48" if ifm_val <= 38 else "#7f1d1d"

    cols = st.columns(4)
    metrics = [
        ("🔥 Risque IFM",  ifm_val, "", ifm_color),
        ("🌡️ Température", get_val('temp'), "°C", "#3b82f6"),
        ("💨 Vent", get_val('wind'), "km/h", "#10b981"),
        ("💧 Humidité",   get_val('hr'), "%", "#8b5cf6")
    ]
    
    for col, (lbl, val, unit, color) in zip(cols, metrics):
        col.markdown(f"""
        <div class="metric-card" style="border-top-color: {color};">
            <div class="metric-label">{lbl}</div>
            <div class="metric-val">{val:.1f}<span class="metric-unit">{unit}</span></div>
        </div>
        """, unsafe_allow_html=True)
        
    st.markdown("<br>", unsafe_allow_html=True) # Espacement

    # --- CARTE FOLIUM (RÉSOLUTION AGRANDIE & COUCHES) ---
    # Centrage sur le département du Rhône par défaut
    m = folium.Map(location=[45.8, 4.6], zoom_start=9, tiles=None)
    
    # Basemaps additionnels
    folium.TileLayer('CartoDB positron', name='Minimaliste (CartoDB)', control=True).add_to(m)
    folium.TileLayer('OpenStreetMap', name='Topographique (OSM)', control=True).add_to(m)
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri', name='Satellite (Esri)', control=True
    ).add_to(m)
    
    # Calque de données
    if img is not None:
        lats, lons = ds[LAT].values, ds[LON].values
        bounds = [[float(lats.min()), float(lons.min())], [float(lats.max()), float(lons.max())]]
        folium.raster_layers.ImageOverlay(
            image=img, bounds=bounds, opacity=0.85, 
            interactive=True, cross_origin=False, name=f'Modèle ({var_choice})'
        ).add_to(m)
        
    # Contour départements
    for feat in geojson.get('features', []):
        geom = feat.get('geometry', {})
        coords_list = [geom['coordinates']] if geom.get('type') == 'Polygon' else geom.get('coordinates', []) if geom.get('type') == 'MultiPolygon' else []
        for poly in coords_list:
            for ring in poly:
                folium.PolyLine(locations=list(zip([c[1] for c in ring], [c[0] for c in ring])), color='#1e293b', opacity=0.6, weight=1.5).add_to(m)

    # Curseur de sélection
    folium.Marker(
        location=[st.session_state.lat_target, st.session_state.lon_target],
        icon=folium.Icon(color="black", icon="crosshairs", prefix='fa')
    ).add_to(m)
    
    # Ajout du contrôle des calques
    folium.LayerControl(position='topright').add_to(m)
    
    # Rendu : carte plus haute (750px)
    map_data = st_folium(m, use_container_width=True, height=750, returned_objects=["last_clicked"])
    
    # Légende Dynamique en bas
    if img is not None and vrange is not None:
        render_dynamic_legend(var_key, vrange[0], vrange[1], var_choice, units_cfg[var_key])
    
    if map_data and map_data.get("last_clicked"):
        st.session_state.lat_target = map_data["last_clicked"]["lat"]
        st.session_state.lon_target = map_data["last_clicked"]["lng"]
        st.session_state.is_playing = False
        st.rerun()

elif page_choisie == "📈 Météogramme & Data":
    
    st.markdown(f"### Météogramme Station : {st.session_state.lat_target:.4f}°N, {st.session_state.lon_target:.4f}°E")
    
    try:
        ts = ds.sel({LAT: st.session_state.lat_target, LON: st.session_state.lon_target}, method="nearest")
        df = pd.DataFrame({
            "Date": time_labels,
            "IFM": ts['ifm'].values if 'ifm' in ts else [0] * n_steps,
            "Temp": ts['temp'].values if 'temp' in ts else [0] * n_steps,
            "Vent": ts['wind'].values if 'wind' in ts else [0] * n_steps,
            "HR": ts['hr'].values if 'hr' in ts else [0] * n_steps,
        })
        
        # --- NOUVEAU MÉTÉOGRAMME (1 colonne, 4 lignes, axe temporel partagé) ---
        fig = make_subplots(
            rows=4, cols=1, 
            shared_xaxes=True, 
            vertical_spacing=0.04,
            subplot_titles=("IFM (Risque Incendie)", "Température (°C)", "Vitesse du Vent (km/h)", "Humidité Relative (%)")
        )
        
        fig.add_trace(go.Scatter(x=df['Date'], y=df['IFM'], mode='lines', line=dict(color='#ef4444', width=2, shape='spline'), fill='tozeroy', fillcolor='rgba(239, 68, 68, 0.1)', name='IFM'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df['Date'], y=df['Temp'], mode='lines', line=dict(color='#f59e0b', width=2, shape='spline'), fill='tozeroy', fillcolor='rgba(245, 158, 11, 0.1)', name='Temp'), row=2, col=1)
        fig.add_trace(go.Scatter(x=df['Date'], y=df['Vent'], mode='lines', line=dict(color='#3b82f6', width=2, shape='spline'), fill='tozeroy', fillcolor='rgba(59, 130, 246, 0.1)', name='Vent'), row=3, col=1)
        fig.add_trace(go.Scatter(x=df['Date'], y=df['HR'], mode='lines', line=dict(color='#10b981', width=2, shape='spline'), fill='tozeroy', fillcolor='rgba(16, 185, 129, 0.1)', name='HR'), row=4, col=1)
        
        fig.add_vline(x=time_labels[st.session_state.step_idx], line_color='rgba(15, 23, 42, 0.6)', line_width=2, line_dash="dash")
        
        fig.update_layout(
            height=900, 
            showlegend=False, 
            plot_bgcolor='rgba(0,0,0,0)', 
            paper_bgcolor='rgba(0,0,0,0)',
            hovermode="x unified",
            font=dict(family='Inter', size=11, color='#475569'),
            margin=dict(l=10, r=10, t=40, b=10)
        )
        
        # Quadrillage
        fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='#f1f5f9', zeroline=False)
        fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='#f1f5f9', zeroline=False)
        
        st.plotly_chart(fig, use_container_width=True)
        
        # --- TABLEAU AMÉLIORÉ ---
        st.markdown("### Extraction Data (Séries Temporelles)")
        # Mise en évidence des pics maximum par colonne (rouge pâle) et des minimums en HR (bleu pâle)
        styled_df = df.style.highlight_max(axis=0, subset=['IFM', 'Temp', 'Vent'], color='#fecaca') \
                            .highlight_min(axis=0, subset=['HR'], color='#bfdbfe') \
                            .format({"IFM": "{:.1f}", "Temp": "{:.1f}", "Vent": "{:.1f}", "HR": "{:.1f}"})
                            
        st.dataframe(styled_df, use_container_width=True, height=400)
            
    except Exception as e:
        st.error(f"Erreur d'analyse météogramme : {e}")

# ═════════════════════════════════════════════════════════════
#  MOTEUR TEMPOREL
# ═════════════════════════════════════════════════════════════
if st.session_state.is_playing:
    if st.session_state.step_idx < n_steps - 1:
        time.sleep(1.0)
        st.session_state.step_idx += 1
        st.rerun()
    else:
        st.session_state.is_playing = False
        st.rerun()
