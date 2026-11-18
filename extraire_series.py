"""
extraire_series.py : série NDVI Sentinel-2 de chaque parcelle de la base, sur la
campagne 2025-2026 (une valeur par passage du satellite), calculée sur Google
Earth Engine. Produit data/series_ndvi.csv, lu ensuite par analyse_series.py.

Même traitement que F6 (on réutilise les fonctions de gee_ndvi.py) :
collection S2_SR_HARMONIZED, scènes à moins de 30 % de nuages, masque SCL
(classes 4 et 5), NDVI = (B8 - B4) / (B8 + B4), pixels de 10 m.
Seule différence : pas de moyenne dans le temps, on garde une valeur par date.

Lancement, depuis le dossier du projet, avec GEE_PROJECT défini comme pour
l'application :   python extraire_series.py
"""
import csv
import json
import os

import ee

from db import BASE_DIR, get_connection
from gee_ndvi import COLLECTION, ECHELLE, SEUIL_NUAGES, initialiser_gee, masquer_scl, ndvi_image

DEBUT = "2025-09-01"
FIN = "2026-09-01"            # filterDate exclut la date de fin : la campagne s'arrête au 31 août
SORTIE = os.path.join(BASE_DIR, "data", "series_ndvi.csv")
PART_VISIBLE_MIN = 0.5        # une date compte si au moins la moitié de la parcelle est visible


def serie_gee(geometrie_geojson):
    """Interroge GEE pour une parcelle. Renvoie une liste (date, ndvi, pixels) :
    ndvi vaut None quand tous les pixels sont masqués (nuages, ombres)."""
    parcelle = ee.Geometry(geometrie_geojson)
    collection = (
        ee.ImageCollection(COLLECTION)
        .filterBounds(parcelle)
        .filterDate(DEBUT, FIN)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", SEUIL_NUAGES))
    )
    # Deux calculs en un passage : la moyenne du NDVI et le nombre de pixels non masqués
    reducteur = ee.Reducer.mean().combine(ee.Reducer.count(), sharedInputs=True)

    def valeur_du_jour(image):
        """NDVI moyen de la parcelle sur une seule image."""
        stats = ndvi_image(masquer_scl(image)).reduceRegion(reducteur, parcelle, ECHELLE)
        return ee.Feature(None, {
            "date": image.date().format("YYYY-MM-dd"),
            "ndvi": stats.get("NDVI_mean"),
            "pixels": stats.get("NDVI_count"),
        })

    # Un seul échange avec les serveurs de Google par parcelle
    resultat = ee.FeatureCollection(collection.map(valeur_du_jour)).getInfo()
    return [(f["properties"]["date"], f["properties"].get("ndvi"), f["properties"].get("pixels") or 0)
            for f in resultat["features"]]


def nettoyer(points):
    """Une seule valeur par date : quand deux images du même jour couvrent la parcelle
    (deux tuiles Sentinel-2), on garde celle qui en voit le plus de pixels.
    Le NDVI est laissé vide si moins de la moitié de la parcelle est visible :
    une moyenne sur quelques pixels entre deux nuages n'est pas fiable."""
    par_date = {}
    for jour, ndvi, pixels in points:
        if jour not in par_date or pixels > par_date[jour][1]:
            par_date[jour] = (ndvi, pixels)

    pixels_max = max((pixels for _, pixels in par_date.values()), default=0)
    lignes = []
    for jour in sorted(par_date):
        ndvi, pixels = par_date[jour]
        if ndvi is None or pixels < PART_VISIBLE_MIN * pixels_max:
            lignes.append((jour, "", pixels))
        else:
            lignes.append((jour, round(ndvi, 4), pixels))
    return lignes


def main():
    initialiser_gee()

    conn = get_connection()
    try:
        parcelles = conn.execute(
            "SELECT num_parcelle, culture, AsGeoJSON(geom) AS geojson "
            "FROM parcelles ORDER BY num_parcelle"
        ).fetchall()
    finally:
        conn.close()

    with open(SORTIE, "w", newline="", encoding="utf-8") as f:
        ecrivain = csv.writer(f)
        ecrivain.writerow(["num", "date", "ndvi", "pixels", "culture"])
        for p in parcelles:
            lignes = nettoyer(serie_gee(json.loads(p["geojson"])))
            utiles = sum(1 for _, ndvi, _ in lignes if ndvi != "")
            print(f"{p['num_parcelle']} : {len(lignes)} dates, {utiles} utilisables")
            for jour, ndvi, pixels in lignes:
                ecrivain.writerow([p["num_parcelle"], jour, ndvi, pixels, p["culture"]])

    print(f"\nSérie enregistrée dans {SORTIE}")


if __name__ == "__main__":
    main()