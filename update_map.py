import os
import re
import folium

TRACKS_DIR = "traces"
os.makedirs(TRACKS_DIR, exist_ok=True)

print("📂 Lecture des fichiers locaux...")
vols_par_annee = {}
fichiers_trouves = 0

for filename in os.listdir(TRACKS_DIR):
    # On ignore tout ce qui n'est pas un fichier IGC
    if not filename.lower().endswith(".igc"): 
        continue
        
    fichiers_trouves += 1
    
    # Recherche de l'année dans le nom du fichier (ex: 2023, 2024...)
    match = re.search(r'(20\d{2})', filename)
    annee = match.group(1) if match else "Autre"
        
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

print(f"📊 {fichiers_trouves} fichiers .igc trouvés dans le dossier 'traces'.")

if not vols_par_annee:
    print("❌ Aucun point GPS n'a pu être extrait. La carte sera vide.")
    m = folium.Map(location=[45.5, 6.5], zoom_start=8)
else:
    # On centre sur le premier point de la première année disponible
    premiere_annee = list(vols_par_annee.keys())[0]
    start_coord = vols_par_annee[premiere_annee][0][0]
    m = folium.Map(location=start_coord, zoom_start=9, tiles=None)

# Ajout du fond de carte Topo
folium.TileLayer("https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png", attr="OpenTopoMap", name="Relief Topo").add_to(m)

# Ajout des traces avec classement par année
for annee in sorted(vols_par_annee.keys(), reverse=True):
    group = folium.FeatureGroup(name=f"Vols {annee}", show=True)
    for trace in vols_par_annee[annee]:
        folium.PolyLine(trace, color="blue", weight=4, opacity=0.6).add_to(group)
    group.add_to(m)

# Menu de contrôle en haut à droite
folium.LayerControl(collapsed=False).add_to(m)
m.save("index.html")
print("✅ Le fichier 'index.html' a été généré avec succès avec tes traces locales !")
