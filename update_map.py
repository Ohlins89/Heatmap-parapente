import os
import requests
from bs4 import BeautifulSoup
import folium
import time

PILOT_ID = "TheoLap"
TRACKS_DIR = "traces"
os.makedirs(TRACKS_DIR, exist_ok=True)

# On ajoute un faux profil de navigateur plus complet pour tromper la sécurité
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5"
}

print(f"🚀 Tentative de connexion au profil public de {PILOT_ID}...")
url_profile = f"https://www.xcontest.org/world/en/pilots/detail:{PILOT_ID}"

flight_links = []
try:
    response = requests.get(url_profile, headers=headers, timeout=15)
    print(f"📢 Code réponse profil XContest : {response.status_code}")
    
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/flights/detail:" in href.lower() and PILOT_ID.lower() in href.lower():
                full_url = "https://www.xcontest.org" + href if href.startswith("/") else href
                if full_url not in flight_links:
                    flight_links.append(full_url)
    else:
         print("⚠️ Toujours bloqué par XContest sur le profil public.")
except Exception as e:
    print(f"❌ Erreur de connexion : {e}")

print(f"📊 Total de vols détectés sur la page : {len(flight_links)}")

# 2. Téléchargement des fichiers IGC
vols_telecharges = 0
for url in flight_links:
    url_clean = url.split("detail:")[-1]
    filename = url_clean.replace("/", "_").replace(":", "-") + ".igc"
    filepath = os.path.join(TRACKS_DIR, filename)
    
    if not os.path.exists(filepath):
        print(f"📥 Téléchargement de la trace : {filename}...")
        dl_url = f"{url}/download/igc"
        try:
            r = requests.get(dl_url, headers=headers, timeout=15)
            # Si XContest bloque aussi le téléchargement des IGC, on aura une erreur ici
            if r.status_code == 200 and ("A" in r.text[:5] or "B" in r.text[:200] or "XCONTEST" in r.text[:100]):
                with open(filepath, "w", encoding="utf-8", errors="ignore") as f:
                    f.write(r.text)
                vols_telecharges += 1
                time.sleep(2) # Pause un peu plus longue pour rassurer XContest
            else:
                print(f"⚠️ Fichier refusé (Code {r.status_code}).")
        except Exception as e:
            print(f"❌ Erreur de téléchargement : {e}")

print(f"✅ Opération terminée. {vols_telecharges} nouvelles traces téléchargées.")

# 3. Lecture des IGC et création de la carte
vols_par_annee = {}
for filename in os.listdir(TRACKS_DIR):
    if not filename.endswith(".igc"): 
        continue
    try:
        parts = filename.split("_")[1].split(".")
        annee = parts[-1]
    except:
        annee = "Autre"
        
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
                except: 
                    continue
                    
    if points:
        if annee not in vols_par_annee: 
            vols_par_annee[annee] = []
        vols_par_annee[annee].append(points)

if not vols_par_annee:
    print("❌ Aucun point GPS n'a pu être extrait.")
    m = folium.Map(location=[45.5, 6.5], zoom_start=8)
else:
    premiere_annee = list(vols_par_annee.keys())[0]
    start_coord = vols_par_annee[premiere_annee][0][0]
    m = folium.Map(location=start_coord, zoom_start=9, tiles=None)

folium.TileLayer("https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png", attr="OpenTopoMap", name="Relief Topo").add_to(m)

for annee in sorted(vols_par_annee.keys(), reverse=True):
    group = folium.FeatureGroup(name=f"Vols {annee}", show=True)
    for trace in vols_par_annee[annee]:
        folium.PolyLine(trace, color="red", weight=2, opacity=0.25).add_to(group)
    group.add_to(m)

folium.LayerControl(collapsed=False).add_to(m)
m.save("index.html")
print("✅ Le fichier 'index.html' a été généré avec succès !")
