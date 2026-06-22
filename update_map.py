import os
import re
import requests
from bs4 import BeautifulSoup
import folium
import time

PILOT_ID = "TheoLap"
TRACKS_DIR = "traces"
os.makedirs(TRACKS_DIR, exist_ok=True)

headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
flight_links = []

# 1. Scan de toutes les pages de recherche du pilote (par paquets de 50 vols)
page = 0
while True:
    print(f"🚀 Scan de la page de recherche {page} pour le pilote {PILOT_ID}...")
    # On utilise la version internationale 'en' pour figer la structure des liens en '/flights/detail:'
    url_search = f"https://www.xcontest.org/world/en/flights-search/?filter[pilot]={PILOT_ID}&list[start]={page*50}"
    
    try:
        response = requests.get(url_search, headers=headers, timeout=15)
        if response.status_code != 200:
            print(f"⚠️ Fin de recherche ou erreur (Code {response.status_code})")
            break
            
        soup = BeautifulSoup(response.text, "html.parser")
        page_links = []
        
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if f"/flights/detail:{PILOT_ID}" in href:
                full_url = "https://www.xcontest.org" + href if href.startswith("/") else href
                if full_url not in flight_links and full_url not in page_links:
                    page_links.append(full_url)
        
        if not page_links:
            print("🏁 Plus aucun vol trouvé sur cette page. Fin du scan des pages.")
            break
            
        flight_links.extend(page_links)
        page += 1
        time.sleep(1) # Petite pause réglementaire pour XContest
    except Exception as e:
        print(f"❌ Erreur lors du scan : {e}")
        break

print(f"📊 Total de vols uniques détectés sur ton profil : {len(flight_links)}")

# 2. Téléchargement des fichiers IGC manquants
vols_telecharges = 0
for url in flight_links:
    # Extrait la date et l'heure pour nommer le fichier proprement
    match = re.search(r"detail:[\w.-]+/([\d.]+)/([\d:]+)", url)
    if match:
        date_str = match.group(1)
        time_str = match.group(2).replace(":", "-")
        filename = f"{date_str}_{time_str}.igc"
        filepath = os.path.join(TRACKS_DIR, filename)
        
        if not os.path.exists(filepath):
            print(f"📥 Téléchargement de la trace du {date_str} à {match.group(2)}...")
            dl_url = f"https://www.xcontest.org/world/en/flights/detail:{PILOT_ID}/{date_str}/{match.group(2)}/download/igc"
            try:
                r = requests.get(dl_url, headers=headers, timeout=15)
                # Vérification que le fichier reçu est bien une trace GPS (commence souvent par A ou contient les balises)
                if r.status_code == 200 and ("A" in r.text[:5] or "XCONTEST" in r.text[:100] or "B" in r.text[:200]):
                    with open(filepath, "w", encoding="utf-8", errors="ignore") as f:
                        f.write(r.text)
                    vols_telecharges += 1
                    time.sleep(1.5) # Pause pour ne pas se faire bloquer par XContest
                else:
                    print(f"⚠️ Impossible de récupérer l'IGC pour ce vol (Droits ou format bloqué)")
            except Exception as e:
                print(f"❌ Erreur de téléchargement : {e}")

print(f"✅ Opération téléchargement terminée. {vols_telecharges} nouvelles traces ajoutées au dossier.")

# 3. Lecture et extraction des coordonnées GPS de chaque fichier IGC
vols_par_annee = {}
for filename in os.listdir(TRACKS_DIR):
    if not filename.endswith(".igc"): 
        continue
        
    # Extraction de l'année depuis le nom du fichier (ex: 24.05.2025_11-30.igc -> 2025)
    parts = filename.split("_")[0].split(".")
    annee = parts[-1] if len(parts) == 3 else "Inconnu"
    
    filepath = os.path.join(TRACKS_DIR, filename)
    points = []
    
    with open(filepath, "r", errors="ignore") as f:
        for line in f:
            if line.startswith("B"): # Ligne de positionnement GPS valide dans un fichier IGC
                try:
                    lat = float(line[7:9]) + (float(line[9:14]) / 1000) / 60.0
                    if line[14] == "S": lat = -lat
                    lon = float(line[15:18]) + (float(line[18:23]) / 1000) / 60.0
                    if line[23] == "W": lon = -lon
                    points.append([lat, lon])
                except: 
                    continue
                    
    if points:
        if annee not in vols_par_annee: 
            vols_par_annee[annee] = []
        vols_par_annee[annee].append(points)

print(f"🗺️ Années de vol prêtes pour la carte : {list(vols_par_annee.keys())}")

# 4. Construction et rendu de la carte
if not vols_par_annee:
    print("❌ Aucun point GPS n'a pu être extrait. La carte sera vide.")
    # On crée une carte vide centrée sur les Alpes par défaut
    m = folium.Map(location=[45.5, 6.5], zoom_start=8)
else:
    # Centrage automatique de la carte sur ton tout premier point GPS trouvé
    premiere_annee = list(vols_par_annee.keys())[0]
    start_coord = vols_par_annee[premiere_annee][0][0]
    
    m = folium.Map(location=start_coord, zoom_start=9, tiles=None)

# Fond de carte Relief topographique style XContest
folium.TileLayer(
    tiles="https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png", 
    attr="OpenTopoMap", 
    name="Relief Topo"
).add_to(m)

# Injection des traces par calques d'années
for annee in sorted(vols_par_annee.keys(), reverse=True):
    group = folium.FeatureGroup(name=f"Vols {annee}", show=True)
    for trace in vols_par_annee[annee]:
        # Opacity=0.25 et weight=2 pour donner cet effet de surbrillance/heatmap aux zones répétées
        folium.PolyLine(trace, color="red", weight=2, opacity=0.25).add_to(group)
    group.add_to(m)

# Ajout de la petite boîte de filtres d'affichage
folium.LayerControl(collapsed=False).add_to(m)

# Sauvegarde finale de la page internet
m.save("index.html")
print("✅ Le fichier 'index.html' a été généré avec succès !")
