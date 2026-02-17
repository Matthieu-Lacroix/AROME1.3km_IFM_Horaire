import streamlit as st
import xarray as xr
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import io
from datetime import datetime

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(layout="wide", page_title="IFM AROME 1.3km", page_icon="🔥")

# --- CSS PERSONNALISÉ (STYLE SCIENTIFIQUE PRO) ---
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] {
        height: 50px; white-space: pre-wrap; background-color: #ffffff;
        border-radius: 4px 4px 0px 0px; gap: 1px; padding-top: 10px;
    }
    .stTabs [aria-selected="true"] { background-color: #e1f5fe; border-bottom: 3px solid #0288d1; }
    div[data-testid="stMetricValue"] { font-size: 24px; color: #0288d1; }
    </style>
    """, unsafe_allow_html=True)

# --- CHARGEMENT DES DONNÉES (CACHE) ---
@st.cache_data(ttl=3600)
def load_data():
    # Remplacez par votre URL brute GitHub
    url = "https://raw.githubusercontent.com/VOTRE_USER/VOTRE_REPO/main/arome_fwi_complet.nc"
    response = requests.get(url)
    if response.status_code == 200:
        # Utilisation de BytesIO pour lire le NetCDF en mémoire
        ds = xr.open_dataset(io.BytesIO(response.content), engine="netcdf4")
        return ds
    return None

ds = load_data()

if ds is None:
    st.error("Impossible de charger le fichier NetCDF. Vérifiez l'URL ou le workflow GitHub.")
    st.stop()

# --- SIDEBAR & NAVIGATION ---
st.sidebar.header("⏱️ Contrôle Temporel")
time_coords = pd.to_datetime(ds.time.values)
selected_time = st.sidebar.select_slider(
    "Échéance de prévision",
    options=time_coords,
    format_func=lambda x: x.strftime("%d/%m %H:00")
)

st.sidebar.markdown("---")
st.sidebar.metric("Run AROME", ds.attrs.get('run_date', 'Inconnu'))
st.sidebar.info(f"Région : {ds.attrs.get('region', 'France')}")

# --- TABS ---
tab1, tab2 = st.tabs(["🗺️ Cartographie IFM", "📈 Analyse des Variables"])

# --- ONGLET 1 : CARTE ---
with tab1:
    st.subheader(f"Indice Forêt Météo - {selected_time.strftime('%d %B %Y à %H:00 UTC')}")
    
    # Extraction de la tranche temporelle
    data_slice = ds.sel(time=selected_time)
    
    # Création de la carte avec Plotly (très fluide pour les grilles)
    # On utilise imshow pour la rapidité sur du 1.3km
    fig_map = px.imshow(
        data_slice['ifm'],
        labels=dict(color="Indice IFM"),
        x=ds.lon, y=ds.lat,
        color_continuous_scale="YlOrRd",
        origin='lower',
        aspect="equal"
    )
    
    fig_map.update_layout(
        margin={"r":0,"t":0,"l":0,"b":0},
        height=700,
        coloraxis_colorbar=dict(title="IFM"),
        # Ajout d'un fond de carte si nécessaire, mais imshow est plus rapide pur
    )
    
    st.plotly_chart(fig_map, use_container_width=True, config={'displayModeBar': False})

# --- ONGLET 2 : GRAPHIQUES ---
with tab2:
    st.subheader("Évolution temporelle sur la région (Moyenne spatiale)")
    
    # Calcul des moyennes spatiales pour le graphique
    ds_mean = ds.mean(dim=['lat', 'lon'])
    df_mean = ds_mean.to_dataframe()
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Graphique IFM et Température
        fig_fwi = go.Figure()
        fig_fwi.add_trace(go.Scatter(x=df_mean.index, y=df_mean['ifm'], name="IFM", line=dict(color='firebrick', width=3)))
        fig_fwi.update_layout(title="Évolution de l'IFM", xaxis_title="Temps", yaxis_title="Indice")
        st.plotly_chart(fig_fwi, use_container_width=True)
        
    with col2:
        # Graphique Vent et Précipitations
        fig_meteo = go.Figure()
        fig_meteo.add_trace(go.Scatter(x=df_mean.index, y=df_mean['temp'], name="Temp (°C)", line=dict(color='orange')))
        fig_meteo.add_trace(go.Scatter(x=df_mean.index, y=df_mean['wind'], name="Vent (km/h)", line=dict(color='royalblue')))
        fig_meteo.update_layout(title="Température et Vent", xaxis_title="Temps")
        st.plotly_chart(fig_meteo, use_container_width=True)

    st.markdown("---")
    st.dataframe(df_mean[['ifm', 'temp', 'wind', 'hr', 'rain']].style.background_gradient(cmap='YlOrRd'))