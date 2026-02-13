#!/usr/bin/env python3
"""
Calcul automatique IFM (Indice Forêt Météo) depuis AROME
Export CSV uniquement - Version GitHub Actions
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

CLIENT_ID = os.getenv('MF_CLIENT_ID')
CLIENT_SECRET = os.getenv('MF_CLIENT_SECRET')

if not CLIENT_ID or not CLIENT_SECRET:
    print("❌ ERREUR: Variables d'environnement MF_CLIENT_ID et MF_CLIENT_SECRET requises")
    sys.exit(1)
    
TOKEN_URL = "https://portail-api.meteofrance.fr/token"
BASE_URL = "https://public-api.meteofrance.fr/public/arome/1.0/wcs/MF-NWP-HIGHRES-AROME-001-FRANCE-WCS"

ZONE = {'lat': (44.0, 46.5), 'long': (2.5, 7.5), 'name': 'Auvergne-Rhône-Alpes'}
MAX_HOURS = 36
SUBSAMPLE = 3
FFMC_INIT, DMC_INIT, DC_INIT = 85.0, 6.0, 15.0

SEUILS_IFM = {
    'Faible': (0, 5.2),
    'Modéré': (5.2, 11.2),
    'Élevé': (11.2, 21.3),
    'Très élevé': (21.3, 38.0),
    'Extrême': (38.0, 999)
}

# ==================== FONCTIONS ====================

def get_latest_run():
    """Détecte le dernier run AROME disponible"""
    now = datetime.now(timezone.utc) - timedelta(hours=4)
    run_hour = (now.hour // 3) * 3
    return now.replace(hour=run_hour, minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:00:00Z")

def get_token():
    """Authentification OAuth2"""
    creds = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    r = requests.post(TOKEN_URL, data={'grant_type': 'client_credentials'},
                     headers={'Authorization': f'Basic {creds}'}, timeout=30)
    return r.json().get('access_token') if r.status_code == 200 else None

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
    """Calcule le Fine Fuel Moisture Code"""
    # Effet pluie
    mo = 147.2 * (101.0 - prev) / (59.5 + prev)
    mr = mo + 42.5 * r * np.exp(-100.0/(251.0-mo)) * (1-np.exp(-6.93/r))
    mr = np.where(r > 1.5, mr + 0.0015 * (mo-150.0)**2 * np.sqrt(r), mr)
    prev = np.where(r > 0.5, 59.5 * (250.0 - np.minimum(mr, 250.0)) / (147.2 + np.minimum(mr, 250.0)), prev)
    
    # Séchage
    mo = 147.2 * (101.0 - prev) / (59.5 + prev)
    ed = np.where(mo > 150, 
                  0.942 * rh**0.679 + 11.0*np.exp((rh-100)/10) + 0.18*(21.1-t)*(1-np.exp(-0.115*rh)),
                  0.618 * rh**0.753 + 10.0*np.exp((rh-100)/10) + 0.18*(21.1-t)*(1-np.exp(-0.115*rh)))
    ew = 0.618 * rh**0.753 + 10.0*np.exp((rh-100)/10) + 0.18*(21.1-t)*(1-np.exp(-0.115*rh))
    
    ko = 0.424*(1-((100-rh)/100)**1.7) + 0.0694*np.sqrt(w)*(1-((100-rh)/100)**8)
    m = np.where(mo > ed, 
                 ed + (mo-ed) * 10**(-ko * 0.581*np.exp(0.0365*t)),
                 ew - (ew-mo) * 10**(-ko * 0.581*np.exp(0.0365*t)))
    
    return np.clip(59.5 * (250.0 - m) / (147.2 + m), 0, 101)

def calc_isi(w, ffmc):
    """Initial Spread Index"""
    mo = 147.2 * (101.0 - ffmc) / (59.5 + ffmc)
    ff = 19.115 * np.exp(-0.1386*mo) * (1 + mo**5.31/49300000.0)
    return ff * np.exp(0.05039*w)

def calc_bui(dmc, dc):
    """Buildup Index"""
    return np.where(dmc <= 0.4*dc, 
                    0.8*dmc*dc/(dmc+0.4*dc),
                    dmc - (1-0.8*dc/(dmc+0.4*dc))*(0.92+(0.0114*dmc)**1.7))

def calc_fwi(isi, bui):
    """Fire Weather Index"""
    fD = np.where(bui <= 80, 0.626*bui**0.809 + 2.0, 1000.0/(25.0 + 108.64*np.exp(-0.023*bui)))
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
        print(f"Erreur chargement H+{hour}: {e}")
        return None

# ==================== MAIN ====================

def main():
    print(f"Démarrage calcul IFM - {datetime.now().isoformat()}")
    
    # Détection run
    DATE_RUN = get_latest_run()
    print(f"Run détecté: {DATE_RUN}")
    
    # Authentification
    token = get_token()
    if not token:
        raise Exception("Échec authentification")
    print("Token: OK")
    
    # Téléchargement
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
                print(f"  Téléchargé: {f.name}")
    print(f"Total fichiers: {len(files)}")
    
    # Calcul IFM
    run_dt = datetime.strptime(DATE_RUN, "%Y-%m-%dT%H:%M:%SZ")
    results = []
    
    d0 = load_hour_data(0)
    if not d0:
        raise Exception("Impossible de charger données initiales")
    
    ffmc = np.full(d0[0].shape, FFMC_INIT)
    dmc = np.full(d0[0].shape, DMC_INIT)
    dc = np.full(d0[0].shape, DC_INIT)
    
    for h in range(MAX_HOURS + 1):
        print(f"Calcul H+{h}...")
        d = load_hour_data(h)
        if not d: 
            continue
            
        ta, ha, wa, ra, lats, lons = d
        fdt = run_dt + timedelta(hours=h)
        
        # Calcul indices
        ffmc = calc_ffmc(ta, ha, wa, ra, ffmc)
        isi = calc_isi(wa, ffmc)
        bui = calc_bui(dmc, dc)
        fwi = calc_fwi(isi, bui)
        
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
                    'isi': round(isi[i,j], 2),
                    'bui': round(bui[i,j], 2),
                    'ifm': round(fwi[i,j], 2),
                    'danger': class_ifm(fwi[i,j])
                })
    
    # Export CSV
    df = pd.DataFrame(results)
    csv_file = f"ifm_{DATE_RUN.replace(':', '').replace('-', '')}.csv"
    df.to_csv(csv_file, index=False, float_format='%.2f')
    
    print(f"\n{'='*50}")
    print(f"RÉSULTATS")
    print(f"{'='*50}")
    print(f"Points calculés: {len(df)}")
    print(f"Échéances: {df['echeance_h'].nunique()}")
    print(f"IFM moyen: {df['ifm'].mean():.2f}")
    print(f"IFM max: {df['ifm'].max():.2f}")
    print(f"Danger max: {df.loc[df['ifm'].idxmax(), 'danger']}")
    print(f"Fichier: {csv_file}")
    
    # Stats par niveau
    print(f"\nRépartition danger:")
    for niveau, count in df[df['echeance_h'] == df['echeance_h'].max()]['danger'].value_counts().items():
        print(f"  {niveau}: {count} points")
    
    return csv_file

if __name__ == "__main__":
    main()

