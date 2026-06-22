import os
import re
import requests
from bs4 import BeautifulSoup
import folium

# 1. Configuration
PILOT_ID = "TheoLap"
XCONTEST_URL = f"https://www.xcontest.org/world/fr/pilotes/details:{PILOT_ID}"
TRACKS_DIR = "traces"
os.makedirs(TRACKS_DIR, exist_ok=True)

print("🚀 Recherche des vols sur XContest...")
response = requests.get(XCONTEST_URL, headers={"User-Agent": "Mozilla/5.0"})
soup = BeautifulSoup(response.text, "html.parser")

# Trouver tous les liens de vols du pilote
flight_links = []
for a in soup.find_all("a", href=True):
    if f"/flights/detail:{PILOT_ID}/" in a["href"]:
        full_url = "https://www.xcontest.org" + a["href"]
        if full_url not in flight_links:
            flight_links.append(full_url)

print(f"📊 {len(flight_links)} vols trouvés sur le profil.")

# 2. Téléchargement des fichiers IGC manquants
for url in flight_links:
    # Extrait la date et l'heure pour nommer le fichier
    match = re.search(r"detail:.*?/(.*?)/(.*?)$", url)
    if match:
        date_str, time_str = match.group(1), match.group(2).replace(":", "-")
        filename = f"{date_str}_{time_str}.igc"
        filepath = os.path.join(TRACKS_DIR, filename)
        
        if not os.path.exists(filepath):
            print(f"📥 Téléchargement du vol du {date_str}...")
            # Sur XContest, ajouter /download/igc à l'URL du vol permet souvent de l'avoir en direct
            dl_url = f"{url}/download/igc"
            r = requests.get(dl_url, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200 and "[IGC]" in r.text[:100]: # Vérification rapide du format
                with open(filepath, "w", encoding="utf-8", errors="ignore") as f:
                    f.write(r.text)

# 3. Lecture et parsing des coordonnées GPS des IGC
print("🗺️ Traitement des traces GPS...")
vols_par_annee = {}

for filename in os.listdir(TRACKS_DIR):
    if not filename.endswith(".igc"):
        continue
    annee = filename.split(".")[2].split("_")[0] if "_" in filename else "Inconnu" # Format DD.MM.YYYY
    if len(annee) == 4 and annee.isdigit():
        pass
    else:
        annee = filename.split("_")[0].split(".")[-1] # Sécurité selon format
        
    filepath = os.path.join(TRACKS_DIR, filename)
    points = []
    
    with open(filepath, "r", errors="ignore") as f:
        for line in f:
            if line.startswith("B"): # Ligne de point GPS standard en IGC
                try:
                    lat_deg = float(line[7:9])
                    lat_min = float(line[9:14]) / 1000
                    lat = lat_deg + lat_min / 60.0
                    if line[14] == "S": lat = -lat
                    
                    lon_deg = float(line[15:18])
                    lon_min = float(line[18:23]) / 1000
                    lon = lon_deg + lon_min / 60.0
                    if line[23] == "W": lon = -lon
                    
                    points.append([lat, lon])
                except:
                    continue
                    
    if points:
        if annee not in vols_par_annee:
            vols_par_annee[annee] = []
        vols_par_annee[annee].append(points)

# 4. Création de la carte Folium
print("🎨 Génération de la carte interactive...")
# Centrage initial (Alpes par défaut, s'adaptera au premier point trouvé)
start_coord = [45.5, 6.5]
for annee in vols_par_annee:
    if vols_par_annee[annee]:
        start_coord = vols_par_annee[annee][0][0]
        break

m = folium.Map(location=start_coord, zoom_start=10, tiles=None)

# Fond de carte Relief (OpenTopoMap) proche du style XContest
folium.TileLayer(
    tiles="https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
    attr="OpenTopoMap",
    name="Relief Topo"
).add_to(m)

# Ajouter les traces par année (Calques filtrables)
for annee in sorted(vols_par_annee.keys(), reverse=True):
    group = folium.FeatureGroup(name=f"Vols {annee}", show=True)
    for trace in vols_par_annee[annee]:
        # Ligne fine (weight=2) et semi-transparente (opacity=0.3) pour l'effet heatmap cumulatif
        folium.PolyLine(trace, color="red", weight=2, opacity=0.3).add_to(group)
    group.add_to(m)

# Ajouter le contrôleur de filtres en haut à droite
folium.LayerControl(collapsed=False).add_to(m)

# Sauvegarde de la page web finale
m.save("index.html")
print("✅ Carte 'index.html' générée avec succès !")
