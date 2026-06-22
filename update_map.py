import os
import re
import requests
from bs4 import BeautifulSoup
import folium

PILOT_ID = "TheoLap"
# Utilisation de la page de recherche des vols qui est plus complète
XCONTEST_URL = f"https://www.xcontest.org/world/fr/pilotes/details:{PILOT_ID}"
TRACKS_DIR = "traces"
os.makedirs(TRACKS_DIR, exist_ok=True)

print(f"🚀 Connexion au profil XContest de {PILOT_ID}...")
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
response = requests.get(XCONTEST_URL, headers=headers)

print(f"📢 Code réponse XContest : {response.status_code}")

soup = BeautifulSoup(response.text, "html.parser")
flight_links = []

# Recherche approfondie des liens de vols
for a in soup.find_all("a", href=True):
    href = a["href"]
    if "/flights/detail:" in href:
        full_url = "https://www.xcontest.org" + href if href.startswith("/") else href
        if full_url not in flight_links:
            flight_links.append(full_url)

print(f"📊 Nombre de liens de vols détectés sur la page : {len(flight_links)}")

# Si aucun vol sur la page principale, on teste une URL alternative
if len(flight_links) == 0:
    print("⚠️ Aucun vol trouvé sur le profil principal, tentative via la recherche globale...")
    SEARCH_URL = f"https://www.xcontest.org/world/fr/vols-recherche/?filter[pilot]={PILOT_ID}"
    response = requests.get(SEARCH_URL, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")
    for a in soup.find_all("a", href=True):
        if "/flights/detail:" in a["href"]:
            full_url = "https://www.xcontest.org" + a["href"]
            if full_url not in flight_links:
                flight_links.append(full_url)
    print(f"📊 Après seconde tentative : {len(flight_links)} vols trouvés.")

# Téléchargement
vols_telecharges = 0
for url in flight_links[:10]: # On limite à 10 pour le premier test de sécurité
    match = re.search(r"detail:.*?/(.*?)/(.*?)$", url)
    if match:
        date_str, time_str = match.group(1), match.group(2).replace(":", "-")
        filename = f"{date_str}_{time_str}.igc"
        filepath = os.path.join(TRACKS_DIR, filename)
        
        if not os.path.exists(filepath):
            dl_url = f"{url}/download/igc"
            r = requests.get(dl_url, headers=headers)
            if r.status_code == 200:
                with open(filepath, "w", encoding="utf-8", errors="ignore") as f:
                    f.write(r.text)
                vols_telecharges += 1

print(f"📥 {vols_telecharges} nouveaux fichiers IGC téléchargés.")

# Lecture et tracé
vols_par_annee = {}
for filename in os.listdir(TRACKS_DIR):
    if not filename.endswith(".igc"): continue
    # Extraction de l'année (ex: 24.05.2025 -> 2025)
    parts = filename.split("_")[0].split(".")
    annee = parts[-1] if len(parts) == 3 else "Autre"
    
    filepath = os.path.join(TRACKS_DIR, filename)
    points = []
    with open(filepath, "r", errors="ignore") as f:
        for line in f:
            if line.startswith("B"):
                try:
                    lat = float(line[7:9]) + (float(line[9:14]) / 1000) / 60.0
                    if line[14] == "S": lat = -lat
                    lon = float(line[15:18]) + (float(line[18:23]) / 1000) / 60.0
                    if line[23] == "W": lon = -lon
                    points.append([lat, lon])
                except: continue
    if points:
        if annee not in vols_par_annee: vols_par_annee[annee] = []
        vols_par_annee[annee].append(points)

print(f"🗺️ Années lues dans le dossier : {list(vols_par_annee.keys())}")

# Génération de la carte
start_coord = [45.5, 6.5]
for annee in vols_par_annee:
    if vols_par_annee[annee]:
        start_coord = vols_par_annee[annee][0][0]
        break

m = folium.Map(location=start_coord, zoom_start=9, tiles=None)
folium.TileLayer(tiles="https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png", attr="OpenTopoMap", name="Relief Topo").add_to(m)

for annee in sorted(vols_par_annee.keys(), reverse=True):
    group = folium.FeatureGroup(name=f"Vols {annee}", show=True)
    for trace in vols_par_annee[annee]:
        folium.PolyLine(trace, color="red", weight=2, opacity=0.4).add_to(group)
    group.add_to(m)

folium.LayerControl(collapsed=False).add_to(m)
m.save("index.html")
print("✅ Fichier index.html mis à jour.")
