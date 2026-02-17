EN COURS DE TEST NE PAS UTILISER ENCORE MERCI BEAUCOUP (17/02/2026)

🔥 Calcul Automatique IFM (Indice Forêt Météo) - AROME 1.3km





Pipeline automatisé de téléchargement des données météo AROME, calcul de l'Indice Forêt Météo (IFM/FWI) et export CSV + NetCDF pour analyse du risque feux de forêt en Auvergne-Rhône-Alpes.



📋 Description


Ce projet télécharge automatiquement les prévisions du modèle AROME 1.3km de Météo-France, calcule l'Indice Forêt Météo (IFM) basé sur le système canadien Fire Weather Index (FWI), et génère des fichiers exploitables dans QGIS, Lizmap ou tout autre outil SIG.


🔬 Indices FWI calculés


Le système FWI canadien calcule 6 indices complémentaires :




Indice
Nom complet
Description
Unité




FFMC
Fine Fuel Moisture Code
Humidité des combustibles fins (litière)
0-101


DMC
Duff Moisture Code
Humidité des combustibles moyens (humus)
0-400


DC
Drought Code
Sécheresse profonde du sol
0-1000


ISI
Initial Spread Index
Vitesse de propagation potentielle
0-∞


BUI
Buildup Index
Combustible disponible pour la combustion
0-∞


FWI
Fire Weather Index
Indice final de danger d'incendie
0-∞




⚠️ Niveaux de danger




Niveau
Seuil IFM
Couleur
Signification




Faible
0 - 5.2
🟢 Vert
Départs de feu peu probables


Modéré
5.2 - 11.2
🟡 Jaune
Départs possibles, propagation faible


Élevé
11.2 - 21.3
🟠 Orange
Départs probables, propagation modérée


Très élevé
21.3 - 38.0
🔴 Rouge
Départs fréquents, propagation rapide


Extrême
> 38.0
⚫ Violet
Conditions exceptionnelles





🚀 Installation


Prérequis


Python 3.10+
Compte API Météo-France : portail-api.meteofrance.fr
Bibliothèques système : libeccodes (pour lecture GRIB)


Installation locale


# Installation des dépendances système (Ubuntu/Debian)
sudo apt-get update
sudo apt-get install -y libeccodes0 libeccodes-dev

# Installation des dépendances Python
pip install requests numpy pandas xarray cfgrib netCDF4 rioxarray



Configuration GitHub Actions


Forkez ce dépôt
Ajoutez vos secrets dans Settings → Secrets and variables → Actions :

MF_CLIENT_ID : Votre identifiant API Météo-France
MF_CLIENT_SECRET : Votre clé secrète API


Le workflow s'exécutera automatiquement 4 fois par jour



⚙️ Configuration


Variables d'environnement


Pour une utilisation locale :


export MF_CLIENT_ID="votre_client_id"
export MF_CLIENT_SECRET="votre_client_secret"
python calcul_ifm.py



Paramètres de zone


Dans calcul_ifm.py, vous pouvez ajuster la zone d'étude :


ZONE = {
    'lat': (44.0, 46.5),    # Latitude min/max
    'long': (2.5, 7.5),     # Longitude min/max
    'name': 'Auvergne-Rhône-Alpes'
}



Valeurs initiales


Les valeurs initiales (FFMC, DMC, DC) sont automatiquement adaptées selon la saison :




Saison
FFMC
DMC
DC
Contexte




Hiver (Déc-Fév)
75
3
10
Humide, faible risque


Printemps (Mar-Mai)
82
8
25
Montée progressive


Été (Juin-Août)
87
15
100
Risque maximal


Automne (Sep-Nov)
80
10
50
Décroissance





📊 Données produites


📄 Fichiers CSV


Nom : ifm_YYYYMMDDTHHMMSSZ.csv


Colonnes :


run_date : Date du run AROME
echeance_h : Échéance de prévision (0-36h)
date_prevision : Date/heure de validité
latitude, longitude : Coordonnées (WGS84)
temperature_c : Température à 2m (°C)
humidite_percent : Humidité relative à 2m (%)
vent_kmh : Vent à 10m (km/h)
pluie_mm : Précipitations horaires (mm)
ffmc, dmc, dc : Codes d'humidité FWI
isi, bui : Indices de comportement FWI
ifm : Indice Forêt Météo final
danger : Niveau de danger (texte)


🗺️ Fichiers NetCDF (compatibles QGIS)


Archive : netcdf_fwi_YYYYMMDDTHHMMSSZ.zip


Format : CF-Conventions 1.8 (standard météorologique)

Projection : EPSG:4326 (WGS84)


Contenu de l'archive :




Variables principales (fichiers séparés pour optimisation) :


arome_ifm_horaire.nc : 🔥 Indice Forêt Météo (FWI)
arome_temp_horaire.nc : 🌡️ Température (°C)
arome_wind_horaire.nc : 💨 Vent (km/h)
arome_hr_horaire.nc : 💧 Humidité relative (%)
arome_rain_horaire.nc : 🌧️ Précipitations (mm)




Indices FWI complets :


arome_fwi_indices.nc : FFMC, DMC, DC, ISI, BUI




Cube spatio-temporel complet :


arome_fwi_complet.nc : Toutes les variables dans un seul fichier





🗺️ Utilisation dans QGIS


Méthode rapide : Glisser-Déposer


Téléchargez l'archive netcdf_fwi_*.zip depuis GitHub Actions
Décompressez le fichier
Glissez-déposez les fichiers .nc directement dans QGIS
Les dimensions spatio-temporelles sont détectées automatiquement ✨


Navigation temporelle




Ouvrez le Contrôleur Temporel :


Menu : Vue → Panneaux → Contrôleur temporel
Raccourci : Ctrl+Shift+T




Configurez l'animation :


QGIS détecte automatiquement la plage temporelle (36h)
Pas de temps : 1 heure
Cliquez sur ▶️ pour animer la propagation du risque




Pour une heure précise :


Utilisez le curseur temporel
Ou double-cliquez pour entrer une date/heure




🎨 Symbologie recommandée


Pour visualiser l'IFM avec les bonnes couleurs :


Propriétés de la couche → Symbologie
Choisissez Pseudo-couleur à bande unique
Configurez les classes :


Valeur min → Valeur max    Couleur        Étiquette
─────────────────────────────────────────────────────
0.0  →  5.2               #00FF00 (Vert)    Faible
5.2  → 11.2               #FFFF00 (Jaune)   Modéré
11.2 → 21.3               #FFA500 (Orange)  Élevé
21.3 → 38.0               #FF0000 (Rouge)   Très élevé
38.0 → 100.0              #8B00FF (Violet)  Extrême



Mode d'interpolation : Discret (pour des seuils nets)


💡 Astuces QGIS


Performances : Utilisez les fichiers séparés par variable (ex: arome_ifm_horaire.nc)
Analyse multi-critères : Chargez plusieurs variables et utilisez la Calculatrice Raster
Export d'images : Utilisez l'outil Atlas pour créer automatiquement des cartes pour chaque échéance
Partage web : Publiez les données sur Lizmap pour un accès web interactif



🔄 Automatisation (GitHub Actions)


Workflow configuré


Le script s'exécute automatiquement 4 fois par jour :




Heure UTC
Heure FR (hiver)
Heure FR (été)
Run AROME ciblé




03h30
04h30
05h30
Run 00h UTC


09h30
10h30
11h30
Run 06h UTC


15h30
16h30
17h30
Run 12h UTC


21h30
22h30
23h30
Run 18h UTC




Récupération des fichiers


Les fichiers sont disponibles de 2 façons :




GitHub Artifacts (30 jours de rétention) :


Allez dans Actions → Sélectionnez le dernier run
Téléchargez ifm-results-XXXXX




Commit dans le dépôt :


Les fichiers CSV et ZIP sont commitées automatiquement
Historique complet disponible dans le dépôt




Exécution manuelle


Depuis GitHub :


Allez dans Actions
Sélectionnez le workflow Calcul IFM AROME
Cliquez sur Run workflow



📐 Spécifications techniques


Zone d'étude


Région : Auvergne-Rhône-Alpes, France
Emprise géographique :

Latitude : 44.0°N - 46.5°N
Longitude : 2.5°E - 7.5°E


Résolution spatiale : ~1.3 km (grille AROME échantillonnée 1/3)
Résolution temporelle : 1 heure
Horizon prévisionnel : +36 heures


Données sources


Modèle : AROME 1.3km (Météo-France)
Variables téléchargées :

Température à 2m (°C)
Humidité relative à 2m (%)
Vitesse du vent à 10m (m/s → km/h)
Précipitations cumulées horaires (mm)




Calculs FWI


Système : Fire Weather Index canadien (Van Wagner, 1987)
Latitude de référence : 45°N (pour tables DMC/DC)
Facteur vent : Correction x1.15 pour conditions françaises
Valeurs initiales : Adaptées automatiquement selon la saison


Format NetCDF


Convention : CF-1.8 (Climate and Forecast Metadata)
Projection : EPSG:4326 (WGS84)
Compression : NETCDF4_CLASSIC (compatibilité maximale)
Dimensions : (time, lat, lon)
Coordonnées :

time : ISO 8601 avec attribut axis='T'
lat : degrees_north avec attribut axis='Y'
lon : degrees_east avec attribut axis='X'





📚 Références scientifiques


Van Wagner, C.E. (1987). Development and structure of the Canadian Forest Fire Weather Index System. Canadian Forestry Service Technical Report 35.
Dowdy, A.J. et al. (2009). Index sensitivity analysis applied to the Canadian Forest Fire Weather Index and the McArthur Forest Fire Danger Index. Meteorological Applications, 17(3), 298-312.
CF Conventions : http://cfconventions.org/
AROME : Seity, Y., et al. (2011). The AROME-France convective-scale operational model. Monthly Weather Review, 139(3), 976-991.



🛠️ Développement


Structure du projet


├── calcul_ifm.py              # Script principal
├── .github/
│   └── workflows/
│       └── calcul_ifm.yml     # Workflow GitHub Actions
├── README.md                  # Ce fichier
├── LICENSE                    # Licence du projet
└── outputs/                   # (créé automatiquement)
    ├── ifm_*.csv              # Résultats CSV
    ├── netcdf_*.zip           # Archives NetCDF
    └── export_netcdf/         # Fichiers NetCDF individuels



Contribution


Les contributions sont les bienvenues ! Pour contribuer :


Forkez le projet
Créez une branche (git checkout -b feature/amelioration)
Committez vos changements (git commit -am 'Ajout fonctionnalité X')
Pushez vers la branche (git push origin feature/amelioration)
Ouvrez une Pull Request


Tests locaux


# Exécution locale
export MF_CLIENT_ID="votre_id"
export MF_CLIENT_SECRET="votre_secret"
python calcul_ifm.py

# Vérification des sorties
ls -lh ifm_*.csv
ls -lh netcdf_*.zip




❓ FAQ


Pourquoi DMC et DC ne sont-ils pas constants ?


DMC (Duff Moisture Code) et DC (Drought Code) représentent l'humidité des couches profondes du sol. Contrairement à FFMC qui réagit rapidement, DMC et DC évoluent lentement sur plusieurs jours/semaines selon la température et les précipitations cumulées.


Quelle différence entre FFMC, DMC et DC ?


FFMC : Combustibles fins (feuilles mortes, herbe sèche) - réaction en quelques heures
DMC : Combustibles moyens (humus, petites branches) - réaction en quelques jours
DC : Combustibles profonds (sol, grosses branches) - réaction en plusieurs semaines


Les seuils de danger sont-ils valables partout en France ?


Les seuils utilisés (système canadien) sont une référence internationale. Pour une calibration locale optimale, il faudrait idéalement comparer avec les statistiques d'incendies historiques de votre région.


Puis-je utiliser ce code pour une autre région ?


Oui ! Il suffit de modifier les paramètres ZONE dans calcul_ifm.py. Attention :


Les tables DMC/DC sont calibrées pour 45°N (ajustez si nécessaire)
Les valeurs initiales saisonnières sont pour le climat français


Quelle est la précision de ces prévisions ?


La précision dépend de :


La qualité du modèle AROME (excellent à courte échéance)
L'échéance de prévision (diminue après 24h)
Les valeurs initiales FFMC/DMC/DC (estimées, sans historique terrain)


Pour un usage opérationnel, il est recommandé de calibrer les valeurs initiales avec des mesures terrain.



📝 Licence


Ce projet est sous licence MIT - voir le fichier LICENSE pour plus de détails.



📧 Contact & Support


Issues : GitHub Issues
Discussions : GitHub Discussions



🙏 Remerciements


Météo-France pour l'accès aux données AROME
Service Canadien des Forêts pour le développement du système FWI
Communauté QGIS pour les outils SIG open-source



Dernière mise à jour : Février 2026

Version : 2.0 (avec export NetCDF)


🗺️ Utilisation dans QGIS


Méthode 1 : Glisser-Déposer


Décompressez netcdf_fwi_YYYYMMDDTHHMMSSZ.zip
Glissez-déposez les fichiers .nc directement dans QGIS
Les dimensions temporelles sont détectées automatiquement


Méthode 2 : Menu classique


Dans QGIS : Couche → Ajouter une couche → Ajouter une couche raster
Sélectionnez un fichier .nc
QGIS détecte les dimensions temps/espace automatiquement


📅 Navigation temporelle




Une fois la couche chargée, ouvrez le Panneau Contrôleur Temporel :


Menu : Vue → Panneaux → Contrôleur temporel
Ou raccourci : Ctrl+Shift+T




Configurez l'animation :


Définissez la plage temporelle
Ajustez le pas de temps (1 heure par défaut)
Utilisez les boutons ▶️ pour animer




Pour une heure précise :


Utilisez le curseur temporel
Ou double-cliquez pour entrer une date/heure




🎨 Symbologie recommandée pour IFM


Palette de couleurs suggérée (dégradé) :

0.0 - 5.2   → Vert (#00FF00)      Faible
5.2 - 11.2  → Jaune (#FFFF00)     Modéré
11.2 - 21.3 → Orange (#FFA500)    Élevé
21.3 - 38.0 → Rouge (#FF0000)     Très élevé
38.0+       → Violet (#8B00FF)    Extrême



💡 Conseils QGIS


Pour de meilleures performances : Utilisez les fichiers séparés par variable
Pour l'analyse complète : Utilisez arome_fwi_complet.nc
Exportation d'images : Utilisez l'outil Atlas pour créer des cartes pour chaque échéance
Calculs raster : Utilisez la Calculatrice Raster pour combiner les indices


🔬 Indices FWI calculés


Le système FWI (Fire Weather Index) canadien calcule 6 indices :


Codes d'humidité


FFMC (Fine Fuel Moisture Code) : Humidité des combustibles fins (litière)
DMC (Duff Moisture Code) : Humidité des combustibles moyens (humus)
DC (Drought Code) : Sécheresse profonde (sol)


Indices de comportement


ISI (Initial Spread Index) : Vitesse de propagation potentielle
BUI (Buildup Index) : Combustible disponible
FWI (Fire Weather Index) : Indice final de danger


📈 Classification du danger




Niveau
FWI
Description




Faible
0.0 - 5.2
Départs de feu peu probables


Modéré
5.2 - 11.2
Départs possibles, propagation faible


Élevé
11.2 - 21.3
Départs probables, propagation modérée


Très élevé
21.3 - 38.0
Départs fréquents, propagation rapide


Extrême
38.0+
Conditions exceptionnelles




🌍 Zone couverte


Région : Auvergne-Rhône-Alpes
Emprise :

Latitude : 44.0°N - 46.5°N
Longitude : 2.5°E - 7.5°E


Résolution spatiale : ~1.3 km (échantillonnage 1/3)
Résolution temporelle : 1 heure
Horizon prévisionnel : +36 heures


🔄 Mise à jour


Les calculs sont lancés automatiquement 4 fois par jour :


03h30 UTC (05h30 heure française)
09h30 UTC (11h30 heure française)
15h30 UTC (17h30 heure française)
21h30 UTC (23h30 heure française)


Chaque calcul utilise les dernières données AROME disponibles (runs 00h, 06h, 12h, 18h UTC).


📚 Références


Système FWI : Van Wagner, C.E. (1987). Development and structure of the Canadian Forest Fire Weather Index System. Canadian Forestry Service Technical Report 35.
CF Conventions : http://cfconventions.org/
AROME : Modèle Météo-France à 1.3km de résolution


⚙️ Configuration technique


Modèle source : AROME 1.3km (Météo-France)
Variables météo : Température (2m), Humidité (2m), Vent (10m), Précipitations
Latitude de référence : 45°N (pour calculs DMC/DC)
Valeurs initiales : Adaptées automatiquement selon la saison


📝 Notes


Les valeurs initiales (FFMC, DMC, DC) sont ajustées selon le mois pour refléter les conditions climatiques moyennes
Le calcul utilise les formules officielles du système FWI canadien
Les fichiers NetCDF suivent les standards CF-1.8 pour une compatibilité maximale


🐛 Problèmes connus


Les fichiers NetCDF peuvent être volumineux (~50-100 MB selon le nombre d'échéances)
QGIS peut nécessiter quelques secondes pour charger les cubes temporels
Pour de très grandes séries temporelles, privilégiez les fichiers par variable


📧 Support


Pour toute question ou suggestion d'amélioration, ouvrez une issue sur GitHub.



Dernière mise à jour : Février 2026
