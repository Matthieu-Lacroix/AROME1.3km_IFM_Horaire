```markdown
# 🔥 Calcul Automatique IFM (Indice Forêt Météo)

[![CI](https://github.com/VOTRE_ORG/VOTRE_REPO/actions/workflows/ifm.yml/badge.svg)](https://github.com/VOTRE_ORG/VOTRE_REPO/actions/workflows/ifm.yml)

Pipeline automatisé de téléchargement des données météo AROME, calcul de l'Indice Forêt Météo (IFM/FWI) et export CSV pour analyse du risque feux de forêt.

## 📋 Description

Ce projet télécharge automatiquement les prévisions du modèle AROME de Météo-France, calcule l'**Indice Forêt Météo (IFM)** basé sur le système canadien Fire Weather Index (FWI), et génère des fichiers CSV exploitables dans QGIS, Lizmap ou tout autre outil SIG.

### Indices calculés

| Indice | Description | Utilisation |
|--------|-------------|-------------|
| **FFMC** | Fine Fuel Moisture Code | Humidité des litières superficielles |
| **ISI** | Initial Spread Index | Vitesse de propagation initiale |
| **BUI** | Buildup Index | Charge combustible totale |
| **IFM** | Indice Forêt Météo | Risque global d'incendie |

### Niveaux de danger

| Niveau | Seuil IFM | Couleur |
|--------|-----------|---------|
| Faible | 0 - 5.2 | 🟢 |
| Modéré | 5.2 - 11.2 | 🟡 |
| Élevé | 11.2 - 21.3 | 🟠 |
| Très élevé | 21.3 - 38.0 | 🔴 |
| Extrême | > 38.0 | ⚫ |

## 🚀 Installation

### Prérequis

- Python 3.10+
- Compte API Météo-France ([portail-api.meteofrance.fr](https://portail-api.meteofrance.fr))

### Dépendances

```bash
pip install requests numpy pandas xarray cfgrib netCDF4
```

## ⚙️ Configuration

### Variables d'environnement

```bash
export MF_CLIENT_ID="votre_client_id"
export MF_CLIENT_SECRET="votre_client_secret"
```

Ou modifier directement dans `calcul_ifm.py` :

```python
CLIENT_ID = "votre_client_id"
CLIENT_SECRET = "votre_secret"
```

### Paramètres de zone

Dans `calcul_ifm.py`, ajuster :

```python
ZONE = {
    'lat': (44.0, 46.5),    # Latitude min/max
    'long': (2.5, 7.5),     # Longitude min/max
    'name': 'Auvergne-Rhône-Alpes'
}
MAX_HOURS = 36              # Échéances (0 à 36h)
SUBSAMPLE = 3               # Résolution (1 = native, 3 = 1 point sur 3)
```

## 📊 Utilisation

### Exécution manuelle

```bash
python calcul_ifm.py
```

### Sortie

```
ifm_20260211T030000Z.csv
```

### Structure du CSV

| Colonne | Type | Description |
|---------|------|-------------|
| `run_date` | ISO 8601 | Date du run AROME |
| `echeance_h` | int | Heure de prévision (H+0, H+1...) |
| `date_prevision` | ISO 8601 | Date/heure prévue |
| `latitude` | float | Latitude WGS84 |
| `longitude` | float | Longitude WGS84 |
| `temperature_c` | float | Température à 2m (°C) |
| `humidite_percent` | float | Humidité relative (%) |
| `vent_kmh` | float | Vitesse vent à 10m (km/h) |
| `pluie_mm` | float | Précipitations cumulées (mm) |
| `ffmc` | float | Fine Fuel Moisture Code |
| `isi` | float | Initial Spread Index |
| `bui` | float | Buildup Index |
| `ifm` | float | Indice Forêt Météo |
| `danger` | string | Niveau de danger |

## 🤖 Automatisation GitHub Actions

Le workflow `.github/workflows/ifm.yml` exécute le calcul automatiquement :

- **Fréquence** : Toutes les 6 heures (3h30 après chaque run AROME)
- **Déclenchement manuel** : Possible via l'interface GitHub

### Secrets requis

Dans `Settings > Secrets and variables > Actions` :

| Secret | Valeur |
|--------|--------|
| `MF_CLIENT_ID` | Votre Client ID Météo-France |
| `MF_CLIENT_SECRET` | Votre Client Secret Météo-France |

### Artifacts

Les résultats sont :
- Téléchargés comme **Artifacts** (90 jours de conservation)
- Commités sur la branche principale (optionnel)

## 🗺️ Intégration SIG

### QGIS

1. Importer le CSV via `Couche > Ajouter une couche > Ajouter une couche de texte délimité`
2. X = `longitude`, Y = `latitude`
3. CRS = `EPSG:4326 - WGS 84`
4. Symboliser par champ `ifm` ou `danger`

### Lizmap

Pour publication web avec Lizmap :

```sql
-- Création table PostGIS (optionnel)
CREATE TABLE ifm_points (
    id SERIAL PRIMARY KEY,
    run_date TIMESTAMP,
    echeance_h INTEGER,
    date_prevision TIMESTAMP,
    geom GEOMETRY(POINT, 2154),  -- Lambert 93
    temperature_c FLOAT,
    humidite_percent FLOAT,
    vent_kmh FLOAT,
    pluie_mm FLOAT,
    ffmc FLOAT,
    isi FLOAT,
    bui FLOAT,
    ifm FLOAT,
    danger VARCHAR(20)
);

CREATE INDEX idx_ifm_geom ON ifm_points USING GIST(geom);
CREATE INDEX idx_ifm_run ON ifm_points(run_date);
CREATE INDEX idx_ifm_echeance ON ifm_points(echeance_h);
```

## 📁 Structure du projet

```
.
├── .github/
│   └── workflows/
│       └── ifm.yml          # Workflow GitHub Actions
├── calcul_ifm.py            # Script principal
├── README.md                # Ce fichier
└── data_grib/               # Dossier temporaire (créé automatiquement)
    ├── temp_H000.grib       # Données brutes AROME
    ├── hr_H000.grib
    ├── wind_H000.grib
    └── rain_H000.grib
```

## 🔧 Personnalisation

### Changer la zone géographique

```python
# Exemple : Corse
ZONE = {
    'lat': (41.3, 43.0),
    'long': (8.5, 9.6),
    'name': 'Corse'
}
```

### Modifier les échéances

```python
MAX_HOURS = 36  # Jusqu'à H+36
```

### Ajuster la résolution

```python
SUBSAMPLE = 1   # Pleine résolution AROME (~1.25 km)
SUBSAMPLE = 5   # Résolution réduite (~6 km, 25× plus rapide)
```

## ⚠️ Limitations

- **Données** : Nécessite une connexion API Météo-France (gratuite pour usage modéré)
- **Zone** : Limité à la couverture AROME France (métropole + Corse)
- **Échéances** : 42 heures maximum pour AROME haute résolution
- **Fréquence** : Runs disponibles toutes les 3h (00, 03, 06, 09, 12, 15, 18, 21 UTC)

## 📚 Références

- [Météo-France API](https://portail-api.meteofrance.fr/)
- [Fire Weather Index - Système canadien](https://cwfis.cfs.nrcan.gc.ca/background/summary/fwi)
- [AROME - Documentation](https://www.umr-cnrm.fr/spip.php?article120)

## 📝 Licence

MIT License - Voir [LICENSE](LICENSE)

## 🤝 Contribution

Les pull requests sont bienvenues. Pour les modifications majeures, ouvrir une issue d'abord.

---

**Développé pour le SDMIS et les services de prévention des feux de forêt.**
```

Fichier `LICENSE` (MIT) si besoin :

```text
MIT License

Copyright (c) 2026 SDMIS

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
```
