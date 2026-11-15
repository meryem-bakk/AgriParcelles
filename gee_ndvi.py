"""
gee_ndvi.py — F6 : NDVI moyen Sentinel-2 d'une parcelle, calculé sur Google Earth Engine.

Traitement imposé par le guide :
  1. collection COPERNICUS/S2_SR_HARMONIZED filtrée sur la parcelle et les dates
  2. scènes avec CLOUDY_PIXEL_PERCENTAGE < 30
  3. masque SCL : on ne garde que les classes 4 (végétation) et 5 (sol nu)
  4. NDVI = normalizedDifference(['B8', 'B4'])
  5. moyenne temporelle, puis moyenne spatiale (reduceRegion, pixels de 10 m)
Option prévue par le guide : carte détaillée du NDVI sur la parcelle (carte_ndvi_png).

L'identifiant du projet Google Cloud est lu dans la variable d'environnement
GEE_PROJECT : il n'apparaît jamais dans le code (règle de sécurité du guide).
"""
import os
import urllib.request

import ee

COLLECTION = "COPERNICUS/S2_SR_HARMONIZED"   # Sentinel-2 niveau 2A (réflectance de surface)
SEUIL_NUAGES = 30                            # % maximal de pixels nuageux par scène
ECHELLE = 10                                 # résolution des bandes B4 et B8, en mètres

# Couleurs de la carte NDVI, une par classe de la grille d'interprétation du guide :
# < 0,2 sol nu ; 0,2–0,4 faible ; 0,4–0,6 modérée ; > 0,6 dense
PALETTE_CLASSES = ["a6611a", "dfc27d", "a6d96a", "1a9641"]

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


def preparer_ndvi(parcelle, debut, fin):
    """Étapes 1 à 5 (partie temporelle), communes au NDVI moyen et à la carte.
    Renvoie (nombre d'images, image du NDVI moyen dans le temps).
    Lève AucuneImageError s'il n'y a aucune image sur la période."""
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
    return nb_images, ndvi_temporel


def calculer_ndvi(geometrie_geojson, debut, fin):
    """NDVI moyen d'une parcelle entre deux dates ('AAAA-MM-JJ').
    Renvoie {"ndvi_moyen": ..., "nb_images": ...}.
    Lève AucuneImageError s'il n'y a aucune image ou aucun pixel exploitable."""
    initialiser_gee()
    parcelle = ee.Geometry(geometrie_geojson)   # GeoJSON lu dans SpatiaLite
    nb_images, ndvi_temporel = preparer_ndvi(parcelle, debut, fin)

    # Étape 5 (suite) : moyenne spatiale sur la parcelle, pixels de 10 m
    resultat = ndvi_temporel.reduceRegion(ee.Reducer.mean(), parcelle, ECHELLE).getInfo()

    ndvi_moyen = resultat.get("NDVI")
    if ndvi_moyen is None:
        raise AucuneImageError("Aucun pixel exploitable sur la parcelle "
                               "(nuages ou ombres à chaque passage).")

    return {"ndvi_moyen": ndvi_moyen, "nb_images": nb_images}


def carte_ndvi_png(geometrie_geojson, debut, fin):
    """Option du guide : carte détaillée du NDVI sur la parcelle, en image PNG.
    Chaque pixel de 10 m prend la couleur de sa classe d'interprétation ;
    hors de la parcelle et sur les pixels masqués (SCL), l'image est transparente.
    Renvoie les octets de l'image."""
    initialiser_gee()
    parcelle = ee.Geometry(geometrie_geojson)
    _, ndvi_temporel = preparer_ndvi(parcelle, debut, fin)

    # Classe de chaque pixel : chaque comparaison vaut 0 ou 1, leur somme donne
    # 0 (< 0,2), 1 (0,2–0,4), 2 (0,4–0,6) ou 3 (> 0,6)
    classes = ndvi_temporel.gte(0.2).add(ndvi_temporel.gte(0.4)).add(ndvi_temporel.gt(0.6))

    # GEE fabrique l'image et renvoie son adresse, qui n'est connue que du serveur Flask
    url = classes.clip(parcelle).getThumbURL({
        "region": parcelle,
        "dimensions": 512,          # 512 pixels sur le plus grand côté
        "crs": "EPSG:3857",         # même projection que Leaflet
        "format": "png",
        "min": 0,
        "max": 3,
        "palette": PALETTE_CLASSES,
    })
    # Flask télécharge l'image lui-même : l'adresse Google (qui contient l'identifiant
    # du projet) n'est jamais transmise au navigateur
    with urllib.request.urlopen(url, timeout=60) as reponse:
        return reponse.read()


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