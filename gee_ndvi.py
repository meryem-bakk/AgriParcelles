"""
gee_ndvi.py — F6 : NDVI moyen Sentinel-2 d'une parcelle, calculé sur Google Earth Engine.

Traitement imposé par le guide :
  1. collection COPERNICUS/S2_SR_HARMONIZED filtrée sur la parcelle et les dates
  2. scènes avec CLOUDY_PIXEL_PERCENTAGE < 30
  3. masque SCL : on ne garde que les classes 4 (végétation) et 5 (sol nu)
  4. NDVI = normalizedDifference(['B8', 'B4'])
  5. moyenne temporelle, puis moyenne spatiale (reduceRegion, pixels de 10 m)

L'identifiant du projet Google Cloud est lu dans la variable d'environnement
GEE_PROJECT : il n'apparaît jamais dans le code (règle de sécurité du guide).
"""
import os

import ee

COLLECTION = "COPERNICUS/S2_SR_HARMONIZED"   # Sentinel-2 niveau 2A (réflectance de surface)
SEUIL_NUAGES = 30                            # % maximal de pixels nuageux par scène
ECHELLE = 10                                 # résolution des bandes B4 et B8, en mètres

_gee_initialise = False   # la connexion à GEE n'est faite qu'une fois par processus


class AucuneImageError(Exception):
    """Aucune image ou aucun pixel exploitable sur la parcelle pour la période."""


def initialiser_gee():
    """Se connecte à Earth Engine au premier calcul seulement."""
    global _gee_initialise
    if _gee_initialise:
        return
    projet = os.environ.get("GEE_PROJECT")
    if not projet:
        raise RuntimeError("Variable d'environnement GEE_PROJECT absente : "
                           "définissez l'identifiant du projet Google Cloud.")
    ee.Initialize(project=projet)
    _gee_initialise = True


def masquer_scl(image):
    """Étape 3 : ne garder que les pixels classés végétation (4) ou sol nu (5).
    Nuages, ombres, eau, neige… sont masqués, pixel par pixel."""
    scl = image.select("SCL")
    masque = scl.eq(4).Or(scl.eq(5))
    return image.updateMask(masque)


def ndvi_image(image):
    """Étape 4 : NDVI = (B8 - B4) / (B8 + B4), B8 = proche infrarouge, B4 = rouge."""
    return image.normalizedDifference(["B8", "B4"]).rename("NDVI")


def calculer_ndvi(geometrie_geojson, debut, fin):
    """NDVI moyen d'une parcelle entre deux dates ('AAAA-MM-JJ').
    Renvoie {"ndvi_moyen": ..., "nb_images": ...}.
    Lève AucuneImageError s'il n'y a aucune image ou aucun pixel exploitable."""
    initialiser_gee()

    parcelle = ee.Geometry(geometrie_geojson)   # GeoJSON lu dans SpatiaLite
    # filterDate exclut la date de fin : on avance d'un jour pour l'inclure
    fin_incluse = ee.Date(fin).advance(1, "day")

    # Étapes 1 et 2 : images qui couvrent la parcelle, sur la période, peu nuageuses
    collection = (
        ee.ImageCollection(COLLECTION)
        .filterBounds(parcelle)
        .filterDate(debut, fin_incluse)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", SEUIL_NUAGES))
    )

    nb_images = collection.size().getInfo()   # 1er échange avec les serveurs de Google
    if nb_images == 0:
        raise AucuneImageError("Aucune image Sentinel-2 peu nuageuse sur cette période.")

    # Étapes 3, 4, 5 : masque SCL, NDVI de chaque image, moyenne temporelle pixel par pixel
    ndvi_temporel = collection.map(masquer_scl).map(ndvi_image).mean()

    # Étape 5 (suite) : moyenne spatiale sur la parcelle, pixels de 10 m
    resultat = ndvi_temporel.reduceRegion(ee.Reducer.mean(), parcelle, ECHELLE).getInfo()

    ndvi_moyen = resultat.get("NDVI")
    if ndvi_moyen is None:
        raise AucuneImageError("Aucun pixel exploitable sur la parcelle "
                               "(nuages ou ombres à chaque passage).")

    return {"ndvi_moyen": ndvi_moyen, "nb_images": nb_images}


# Test en ligne de commande : python gee_ndvi.py <numéro de parcelle> <début> <fin>
if __name__ == "__main__":
    import json
    import sys

    from db import get_connection

    num, debut, fin = sys.argv[1], sys.argv[2], sys.argv[3]

    conn = get_connection()
    try:
        ligne = conn.execute(
            "SELECT AsGeoJSON(geom) FROM parcelles WHERE num_parcelle = ?", (num,)
        ).fetchone()
    finally:
        conn.close()

    if ligne is None:
        sys.exit(f"Parcelle « {num} » introuvable dans la base.")

    print(calculer_ndvi(json.loads(ligne[0]), debut, fin))