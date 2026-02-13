#!/usr/bin/env python3
"""
Calcul automatique IFM (Indice Forêt Météo) depuis AROME
Export CSV uniquement - Version GitHub Actions
Région: Auvergne-Rhône-Alpes, France
"""

import os
import sys
import requests
import numpy as np
import pandas as pd
import xarray as xr
from datetime import datetime, timedelta, timezone
from pathlib import Path
import base64
import warnings
warnings.filterwarnings('ignore')

# ==================== CONFIGURATION ====================

# Récupération depuis variables d'environnement
CLIENT_ID = os.getenv('MF_CLIENT_ID')
CLIENT_SECRET = os.getenv('MF_CLIENT_SECRET')

# Validation
if not CLIENT_ID or not CLIENT_SECRET:
    print("❌ ERREUR: Variables d'environnement MF_CLIENT_ID et MF_CLIENT_SECRET requises")
    print("   Configurez-les dans GitHub Settings > Secrets and variables > Actions")
    sys.exit(1)

TOKEN_URL = "https://portail-api.meteofrance.fr/token"
BASE_URL = "https://public-api.meteofrance.fr/public/arome/1.0/wcs/MF-NWP-HIGHRES-AROME-001-FRANCE-WCS"

ZONE = {'lat': (44.0, 46.5), 'long': (2.5, 7.5), 'name': 'Auvergne-Rhône-Alpes'}
MAX_HOURS = 36
SUBSAMPLE = 3

# Valeurs initiales adaptées pour la France (printemps/été)
# Ces valeurs seront ajustées automatiquement selon la saison
FFMC_INIT, DMC_INIT, DC_INIT = 85.0, 6.0, 15.0

SEUILS_IFM = {
    'Faible': (0, 5.2),
    'Modéré': (5.2, 11.2),
    'Élevé': (11.2, 21.3),
    'Très élevé': (21.3, 38.0),
    'Extrême': (38.0, 999)
}

# Tableaux pour calculs DMC et DC (latitude 45°N - France métropole)
# Day Length factors pour DMC
DAY_LENGTH_45N = np.array([12.6, 12.0, 11.4, 10.9, 10.5, 10.2, 10.4, 10.9, 11.4, 12.0, 12.6, 13.0])

# Day factors pour DC
DAY_FACTOR_45N = np.array([-1.6, -1.6, -1.6, 0.9, 3.8, 5.8, 6.4, 5.0, 2.4, 0.4, -1.6, -1.6])

# ==================== FONCTIONS ====================

def get_seasonal_init(month):
    """
    Retourne des valeurs initiales adaptées à la saison en France
    Basé sur les statistiques climatiques d'Auvergne-Rhône-Alpes
    """
    # Hiver (Dec-Feb): humide, faible risque
    if month in [12, 1, 2]:
        return 75.0, 3.0, 10.0
    # Printemps (Mar-May): montée progressive
    elif month in [3, 4, 5]:
        return 82.0, 8.0, 25.0
    # Été (Jun-Aug): risque maximal
    elif month in [6, 7, 8]:
        return 87.0, 15.0, 100.0
    # Automne (Sep-Nov): décroissance
    else:
        return 80.0, 10.0, 50.0

def get_latest_run():
    """Détecte le dernier run AROME disponible"""
    now = datetime.now(timezone.utc) - timedelta(hours=4)
    run_hour = (now.hour // 3) * 3
    return now.replace(hour=run_hour, minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:00:00Z")

def get_token():
    """Authentification OAuth2"""
    print(f"🔐 Tentative d'authentification...")
    print(f"   URL: {TOKEN_URL}")
    print(f"   Client ID: {CLIENT_ID[:8]}..." if CLIENT_ID else "   ❌ Client ID manquant")
    
    if not CLIENT_ID or not CLIENT_SECRET:
        raise ValueError("CLIENT_ID et CLIENT_SECRET doivent être définis")
    
    creds = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    
    try:
        r = requests.post(
            TOKEN_URL, 
            data={'grant_type': 'client_credentials'},
            headers={'Authorization': f'Basic {creds}'}, 
            timeout=30
        )
        
        print(f"   Status: {r.status_code}")
        
        if r.status_code == 200:
            token = r.json().get('access_token')
            print(f"   ✓ Token obtenu ({len(token) if token else 0} caractères)")
            return token
        else:
            print(f"   ❌ Erreur: {r.text}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Erreur réseau: {e}")
        return None

def download_var(var, cfg, hour, date_run, token):
    """Télécharge une variable AROME"""
    run_dt = datetime.strptime(date_run, "%Y-%m-%dT%H:%M:%SZ")
    
    if cfg['type'] == 'instant':
        t = (run_dt + timedelta(hours=hour)).strftime('%Y-%m-%dT%H:%M:%SZ')
        subsets = [f'time({t})', f'lat({ZONE["lat"][0]},{ZONE["lat"][1]})', f'long({ZONE["long"][0]},{ZONE["long"][1]})']
        if cfg.get('height'): subsets.insert(1, f'height({cfg["height"]})')
        cid = f'{var}___{date_run}'
    else:
        if hour == 0: return None
        t = (run_dt + timedelta(hours=hour)).strftime('%Y-%m-%dT%H:%M:%SZ')
        subsets = [f'time({t})', f'lat({ZONE["lat"][0]},{ZONE["lat"][1]})', f'long({ZONE["long"][0]},{ZONE["long"][1]})']
        cid = f'{var}___{date_run}_PT1H'
    
    r = requests.get(f'{BASE_URL}/GetCoverage',
                    params={'service': 'WCS', 'version': '2.0.1', 'coverageid': cid,
                            'subset': subsets, 'format': 'application/wmo-grib'},
                    headers={'Authorization': f'Bearer {token}'}, timeout=60)
    
    if r.status_code == 200:
        f = Path('data_grib') / f"{cfg['short_name']}_H{hour:03d}.grib"
        f.parent.mkdir(exist_ok=True)
        f.write_bytes(r.content)
        return f
    return None

def calc_ffmc(t, rh, w, r, prev):
    """
    Calcule le Fine Fuel Moisture Code
    t: température (°C)
    rh: humidité relative (%)
    w: vitesse du vent (km/h)
    r: pluie (mm)
    prev: FFMC précédent
    """
    # Effet de la pluie
    mo = 147.2 * (101.0 - prev) / (59.5 + prev)
    
    # Pluie > 0.5mm
    mr = mo + 42.5 * r * np.exp(-100.0/(251.0-mo)) * (1.0 - np.exp(-6.93/r))
    mr = np.where(r > 1.5, mr + 0.0015 * (mo - 150.0)**2 * np.sqrt(r), mr)
    prev = np.where(r > 0.5, 59.5 * (250.0 - np.minimum(mr, 250.0)) / (147.2 + np.minimum(mr, 250.0)), prev)
    
    # Séchage
    mo = 147.2 * (101.0 - prev) / (59.5 + prev)
    
    # Équilibre drying/wetting
    ed = np.where(mo > 150,
                  0.942 * rh**0.679 + 11.0*np.exp((rh-100.0)/10.0) + 0.18*(21.1-t)*(1.0-np.exp(-0.115*rh)),
                  0.618 * rh**0.753 + 10.0*np.exp((rh-100.0)/10.0) + 0.18*(21.1-t)*(1.0-np.exp(-0.115*rh)))
    
    ew = 0.618 * rh**0.753 + 10.0*np.exp((rh-100.0)/10.0) + 0.18*(21.1-t)*(1.0-np.exp(-0.115*rh))
    
    # Taux de séchage
    ko = 0.424*(1.0 - ((100.0-rh)/100.0)**1.7) + 0.0694*np.sqrt(w)*(1.0 - ((100.0-rh)/100.0)**8)
    kd = ko * 0.581 * np.exp(0.0365*t)
    
    # Moisture final
    m = np.where(mo > ed,
                 ed + (mo - ed) * 10**(-kd),
                 ew - (ew - mo) * 10**(-kd))
    
    return np.clip(59.5 * (250.0 - m) / (147.2 + m), 0, 101)

def calc_dmc(t, rh, r, prev, month):
    """
    Calcule le Duff Moisture Code
    t: température (°C)
    rh: humidité relative (%)
    r: pluie (mm)
    prev: DMC précédent
    month: mois (1-12)
    """
    # Effet de la pluie (re > 0 seulement si r > 1.5mm)
    re = 0.92 * r - 1.27
    
    # Moisture content
    Mo = 20.0 + np.exp(5.6348 - prev/43.43)
    
    # Slope variable
    b = np.where(prev <= 33,
                 100.0 / (0.5 + 0.3 * prev),
                 np.where(prev <= 65,
                         14.0 - 1.3 * np.log(prev),
                         6.2 * np.log(prev) - 17.2))
    
    # Moisture after rain
    Mr = Mo + 1000.0 * re / (48.77 + b * re)
    Pr = 244.72 - 43.43 * np.log(Mr - 20.0)
    
    # Appliquer effet pluie seulement si r > 1.5mm
    prev_wet = np.where(r > 1.5, Pr, prev)
    
    # Séchage
    K = 1.894 * (t + 1.1) * (100.0 - rh) * DAY_LENGTH_45N[month-1] * 1e-6
    
    return np.clip(prev_wet + 100.0 * K, 0, 400)

def calc_dc(t, r, prev, month):
    """
    Calcule le Drought Code
    t: température (°C)
    r: pluie (mm)
    prev: DC précédent
    month: mois (1-12)
    """
    # Effet de la pluie (seulement si r > 2.8mm)
    Qr = 800.0 * np.exp(-prev/400.0)
    Dr = prev - 400.0 * np.log(1.0 + 3.937 * r / Qr)
    Dr = np.where(r > 2.8, Dr, prev)
    
    # Potentiel d'évapotranspiration
    V = np.where(t < -2.8, 
                 DAY_FACTOR_45N[month-1],
                 0.36 * (t + 2.8) + DAY_FACTOR_45N[month-1])
    V = np.maximum(V, 0)
    
    return np.clip(Dr + 0.5 * V, 0, 1000)

def calc_isi(w, ffmc):
    """
    Calcule l'Initial Spread Index
    w: vitesse du vent (km/h)
    ffmc: Fine Fuel Moisture Code
    """
    mo = 147.2 * (101.0 - ffmc) / (59.5 + ffmc)
    ff = 19.115 * np.exp(-0.1386*mo) * (1.0 + mo**5.31/49300000.0)
    return ff * np.exp(0.05039*w)

def calc_bui(dmc, dc):
    """
    Calcule le Buildup Index
    dmc: Duff Moisture Code
    dc: Drought Code
    """
    return np.where(dmc <= 0.4*dc,
                    0.8*dmc*dc/(dmc+0.4*dc),
                    dmc - (1.0-0.8*dc/(dmc+0.4*dc))*(0.92+(0.0114*dmc)**1.7))

def calc_fwi(isi, bui):
    """
    Calcule le Fire Weather Index
    isi: Initial Spread Index
    bui: Buildup Index
    """
    fD = np.where(bui <= 80, 
                  0.626*bui**0.809 + 2.0, 
                  1000.0/(25.0 + 108.64*np.exp(-0.023*bui)))
    B = 0.1 * isi * fD
    return np.where(B > 1, np.exp(2.72 * (0.434*np.log(B))**0.647), B)

def class_ifm(fwi):
    """Classifie le niveau de danger IFM"""
    for niveau, (mini, maxi) in SEUILS_IFM.items():
        if mini <= fwi < maxi:
            return niveau
    return 'Extrême'

def load_hour_data(hour):
    """Charge les données GRIB pour une échéance"""
    try:
        t = xr.open_dataset(Path('data_grib')/f'temp_H{hour:03d}.grib', engine='cfgrib').isel(
            latitude=slice(None,None,SUBSAMPLE), longitude=slice(None,None,SUBSAMPLE))
        rh = xr.open_dataset(Path('data_grib')/f'hr_H{hour:03d}.grib', engine='cfgrib').isel(
            latitude=slice(None,None,SUBSAMPLE), longitude=slice(None,None,SUBSAMPLE))
        w = xr.open_dataset(Path('data_grib')/f'wind_H{hour:03d}.grib', engine='cfgrib').isel(
            latitude=slice(None,None,SUBSAMPLE), longitude=slice(None,None,SUBSAMPLE))
        
        ta = t.to_array().values[0]
        if np.mean(ta) > 100: ta -= 273.15
        ha = rh.to_array().values[0]
        wa = w.to_array().values[0] * 3.6 * 1.15  # m/s -> km/h
        
        rain_file = Path('data_grib')/f'rain_H{hour:03d}.grib'
        ra = xr.open_dataset(rain_file, engine='cfgrib').isel(
            latitude=slice(None,None,SUBSAMPLE), longitude=slice(None,None,SUBSAMPLE)).to_array().values[0] \
            if hour > 0 and rain_file.exists() else np.zeros_like(ta)
        
        return ta, ha, wa, ra, t.latitude.values, t.longitude.values
    except Exception as e:
        print(f"⚠️  Erreur chargement H+{hour}: {e}")
        return None

# ==================== MAIN ====================

def main():
    print(f"🔥 Démarrage calcul IFM - {datetime.now().isoformat()}")
    print(f"📍 Région: {ZONE['name']}")
    
    # Détection run
    DATE_RUN = get_latest_run()
    run_dt = datetime.strptime(DATE_RUN, "%Y-%m-%dT%H:%M:%SZ")
    print(f"📅 Run détecté: {DATE_RUN}")
    print(f"🌍 Mois: {run_dt.strftime('%B %Y')}")
    
    # Valeurs initiales adaptées à la saison
    ffmc_init, dmc_init, dc_init = get_seasonal_init(run_dt.month)
    print(f"🔧 Valeurs initiales: FFMC={ffmc_init}, DMC={dmc_init}, DC={dc_init}")
    
    # Authentification
    token = get_token()
    if not token:
        raise Exception("Échec authentification")
    print("✓ Token: OK\n")
    
    # Téléchargement
    print("📥 Téléchargement données AROME...")
    VARS = {
        'TEMPERATURE__SPECIFIC_HEIGHT_LEVEL_ABOVE_GROUND': {'short_name': 'temp', 'height': 2, 'type': 'instant'},
        'RELATIVE_HUMIDITY__SPECIFIC_HEIGHT_LEVEL_ABOVE_GROUND': {'short_name': 'hr', 'height': 2, 'type': 'instant'},
        'WIND_SPEED__SPECIFIC_HEIGHT_LEVEL_ABOVE_GROUND': {'short_name': 'wind', 'height': 10, 'type': 'instant'},
        'TOTAL_PRECIPITATION__GROUND_OR_WATER_SURFACE': {'short_name': 'rain', 'height': None, 'type': 'cumul'}
    }
    
    files = {}
    for h in range(MAX_HOURS + 1):
        for v, c in VARS.items():
            f = download_var(v, c, h, DATE_RUN, token)
            if f:
                files[f"{c['short_name']}_H{h:03d}"] = f
                print(f"  ✓ H+{h:02d}: {c['short_name']}")
    print(f"✓ Total fichiers téléchargés: {len(files)}\n")
    
    # Calcul IFM
    print("🧮 Calcul des indices FWI...")
    results = []
    
    d0 = load_hour_data(0)
    if not d0:
        raise Exception("Impossible de charger données initiales")
    
    # Initialisation des codes avec valeurs saisonnières
    ffmc = np.full(d0[0].shape, ffmc_init)
    dmc = np.full(d0[0].shape, dmc_init)
    dc = np.full(d0[0].shape, dc_init)
    
    for h in range(MAX_HOURS + 1):
        print(f"  Calcul H+{h:02d}...", end=' ')
        d = load_hour_data(h)
        if not d:
            print("❌ Données manquantes")
            continue
        
        ta, ha, wa, ra, lats, lons = d
        fdt = run_dt + timedelta(hours=h)
        month = fdt.month
        
        # Calcul des indices dans l'ordre correct
        ffmc = calc_ffmc(ta, ha, wa, ra, ffmc)
        dmc = calc_dmc(ta, ha, ra, dmc, month)
        dc = calc_dc(ta, ra, dc, month)
        
        isi = calc_isi(wa, ffmc)
        bui = calc_bui(dmc, dc)
        fwi = calc_fwi(isi, bui)
        
        # Statistiques de l'échéance
        print(f"IFM moyen={np.mean(fwi):.2f}, max={np.max(fwi):.2f}")
        
        # Stockage résultats
        for i in range(len(lats)):
            for j in range(len(lons)):
                results.append({
                    'run_date': DATE_RUN,
                    'echeance_h': h,
                    'date_prevision': fdt.isoformat(),
                    'latitude': round(lats[i], 4),
                    'longitude': round(lons[j], 4),
                    'temperature_c': round(ta[i,j], 1),
                    'humidite_percent': round(ha[i,j], 1),
                    'vent_kmh': round(wa[i,j], 1),
                    'pluie_mm': round(ra[i,j], 2),
                    'ffmc': round(ffmc[i,j], 2),
                    'dmc': round(dmc[i,j], 2),
                    'dc': round(dc[i,j], 2),
                    'isi': round(isi[i,j], 2),
                    'bui': round(bui[i,j], 2),
                    'ifm': round(fwi[i,j], 2),
                    'danger': class_ifm(fwi[i,j])
                })
    
    # Export CSV
    df = pd.DataFrame(results)
    csv_file = f"ifm_{DATE_RUN.replace(':', '').replace('-', '')}.csv"
    df.to_csv(csv_file, index=False, float_format='%.2f')
    
    print(f"\n{'='*60}")
    print(f"📊 RÉSULTATS")
    print(f"{'='*60}")
    print(f"Points calculés: {len(df):,}")
    print(f"Échéances: {df['echeance_h'].nunique()}")
    print(f"Période: {df['date_prevision'].min()} → {df['date_prevision'].max()}")
    print(f"\n🔥 Indices FWI moyens (dernière échéance):")
    last_h = df[df['echeance_h'] == df['echeance_h'].max()]
    print(f"   FFMC: {last_h['ffmc'].mean():.2f}")
    print(f"   DMC:  {last_h['dmc'].mean():.2f}")
    print(f"   DC:   {last_h['dc'].mean():.2f}")
    print(f"   ISI:  {last_h['isi'].mean():.2f}")
    print(f"   BUI:  {last_h['bui'].mean():.2f}")
    print(f"   IFM:  {last_h['ifm'].mean():.2f} (max: {last_h['ifm'].max():.2f})")
    print(f"\n⚠️  Danger maximal: {df.loc[df['ifm'].idxmax(), 'danger']}")
    print(f"📁 Fichier: {csv_file}")
    
    # Stats par niveau de danger
    print(f"\n📈 Répartition danger (dernière échéance):")
    for niveau in ['Faible', 'Modéré', 'Élevé', 'Très élevé', 'Extrême']:
        count = (last_h['danger'] == niveau).sum()
        pct = 100 * count / len(last_h)
        if count > 0:
            print(f"   {niveau:12s}: {count:4d} points ({pct:5.1f}%)")
    
    print(f"{'='*60}\n")
    
    return csv_file

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ ERREUR FATALE: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
