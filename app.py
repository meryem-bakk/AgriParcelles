"""
app.py — Serveur Flask d'AgriParcelles : page principale et API REST en JSON.
Lancement : python app.py, puis http://127.0.0.1:5000
"""
import json
import math
import sqlite3
from datetime import date

import ee
from flask import Flask, Response, jsonify, render_template, request

from db import get_connection
from extraire_series import nettoyer, serie_gee
from gee_ndvi import AucuneImageError, calculer_ndvi, carte_ndvi_png, initialiser_gee
from profils_ndvi import GRILLE, MIN_DATES, comparer, lire_serie_fichier

# Flask sert automatiquement le contenu du dossier static/ sous l'adresse /static/...
app = Flask(__name__)
app.json.ensure_ascii = False   # garder les accents lisibles dans le JSON

# Liste imposée par le guide (F5). Le serveur la vérifie lui-même :
# on ne se fie jamais aux seuls contrôles du navigateur.
CULTURES = [
    "Blé dur", "Blé tendre", "Orge", "Maïs", "Betterave sucrière", "Olivier",
    "Agrumes", "Maraîchage", "Luzerne", "Jachère", "Autre",
]

# Colonnes renvoyées pour une parcelle (géométrie convertie en texte GeoJSON)
COLONNES = """id, num_parcelle, agriculteur, culture, superficie_ha,
              production_t, date_saisie, AsGeoJSON(geom) AS geometrie"""


# ---------- Fonctions utilitaires ----------

def erreur(code, message):
    """Réponse d'erreur uniforme : {"erreur": "..."} avec le code HTTP."""
    return jsonify({"erreur": message}), code


def ligne_vers_feature(ligne):
    """Transforme une ligne de la table en Feature GeoJSON."""
    proprietes = dict(ligne)                               # grâce à row_factory
    geometrie = json.loads(proprietes.pop("geometrie"))    # texte -> objet
    return {"type": "Feature", "geometry": geometrie, "properties": proprietes}


def lire_polygone(donnees):
    """Extrait la géométrie envoyée par le navigateur.
    Renvoie le texte GeoJSON, ou None si ce n'est pas un polygone."""
    geometrie = donnees.get("geometrie")
    if not isinstance(geometrie, dict) or geometrie.get("type") != "Polygon":
        return None
    return json.dumps(geometrie)


def analyser_geometrie(conn, geojson_texte):
    """Traitement imposé par le guide : convertit le GeoJSON en géométrie WGS84,
    vérifie sa validité et calcule sa superficie sur l'ellipsoïde.
    Renvoie (valide, superficie_ha)."""
    ligne = conn.execute(
        """
        SELECT ST_IsValid(g)          AS valide,
               ST_Area(g, 1) / 10000  AS superficie_ha
        FROM (SELECT SetSRID(GeomFromGeoJSON(?), 4326) AS g)
        """,
        (geojson_texte,),
    ).fetchone()
    return ligne["valide"] == 1, ligne["superficie_ha"]


# Règles de dates imposées par le guide (F6)
DATE_MIN = date(2019, 1, 1)
ECART_MIN_JOURS = 10


def verifier_dates(debut_txt, fin_txt):
    """Contrôle les dates du calcul NDVI. Renvoie un message d'erreur, ou "" si tout va bien."""
    try:
        debut = date.fromisoformat(debut_txt)
        fin = date.fromisoformat(fin_txt)
    except (TypeError, ValueError):
        return "Dates invalides : format attendu AAAA-MM-JJ."
    if debut < DATE_MIN:
        return "La date de début doit être le 01/01/2019 ou après."
    if fin > date.today():
        return "La date de fin ne peut pas dépasser la date du jour."
    if debut >= fin:
        return "La date de début doit précéder la date de fin."
    if (fin - debut).days < ECART_MIN_JOURS:
        return "L'écart entre les deux dates doit être d'au moins 10 jours."
    return ""


def geometrie_parcelle(num):
    """Géométrie GeoJSON d'une parcelle, lue dans SpatiaLite, ou None si elle n'existe pas."""
    conn = get_connection()
    try:
        ligne = conn.execute(
            "SELECT AsGeoJSON(geom) AS geometrie FROM parcelles WHERE num_parcelle = ?",
            (num,),
        ).fetchone()
    finally:
        conn.close()
    return json.loads(ligne["geometrie"]) if ligne else None


def verifier_attributs(donnees):
    """Extension (modification d'une parcelle) : mêmes contrôles que F5 sur les attributs.
    Renvoie (num, agriculteur, culture, production) et "", ou None et le message d'erreur."""
    num = str(donnees.get("num_parcelle") or "").strip()
    agriculteur = str(donnees.get("agriculteur") or "").strip()
    culture = donnees.get("culture")
    if not num:
        return None, "Le numéro de parcelle est obligatoire."
    if not agriculteur:
        return None, "Le nom de l'agriculteur est obligatoire."
    if culture not in CULTURES:
        return None, "Culture inconnue."
    try:
        production = float(donnees.get("production_t"))
    except (TypeError, ValueError):
        return None, "La production doit être un nombre."
    # isfinite refuse aussi NaN et l'infini, que le JSON de Python accepte
    if not math.isfinite(production) or production < 0:
        return None, "La production doit être un nombre positif ou nul."
    return (num, agriculteur, culture, production), ""


# ---------- Routes ----------

@app.route("/")
def index():
    """Page principale : la carte (static/index.html)."""
    return app.send_static_file("index.html")


@app.route("/api/parcelles", methods=["GET"])
def lister_parcelles():
    """F2 — Renvoie toutes les parcelles au format GeoJSON (FeatureCollection)."""
    conn = get_connection()
    try:
        lignes = conn.execute(
            "SELECT " + COLONNES + " FROM parcelles ORDER BY num_parcelle"
        ).fetchall()
    finally:
        conn.close()   # une connexion par requête, toujours refermée

    features = [ligne_vers_feature(ligne) for ligne in lignes]
    return jsonify({"type": "FeatureCollection", "features": features})


@app.route("/api/superficie", methods=["POST"])
def calculer_superficie():
    """F5 — Superficie d'un polygone dessiné, affichée dans le formulaire
    avant l'enregistrement. Rien n'est écrit dans la base."""
    donnees = request.get_json(silent=True) or {}
    geojson_texte = lire_polygone(donnees)
    if geojson_texte is None:
        return erreur(400, "Un polygone GeoJSON est attendu.")

    conn = get_connection()
    try:
        valide, superficie = analyser_geometrie(conn, geojson_texte)
    finally:
        conn.close()

    if not valide:
        return erreur(422, "Géométrie invalide : redessinez la parcelle.")
    return jsonify({"superficie_ha": superficie})


@app.route("/api/parcelles", methods=["POST"])
def creer_parcelle():
    """F5 — Enregistre une nouvelle parcelle et renvoie l'enregistrement créé."""
    donnees = request.get_json(silent=True) or {}

    # 1. Contrôler les attributs (le serveur refait tous les contrôles)
    num = str(donnees.get("num_parcelle") or "").strip()
    agriculteur = str(donnees.get("agriculteur") or "").strip()
    culture = donnees.get("culture")
    if not num:
        return erreur(400, "Le numéro de parcelle est obligatoire.")
    if not agriculteur:
        return erreur(400, "Le nom de l'agriculteur est obligatoire.")
    if culture not in CULTURES:
        return erreur(400, "Culture inconnue.")
    try:
        production = float(donnees.get("production_t"))
    except (TypeError, ValueError):
        return erreur(400, "La production doit être un nombre.")
    if production < 0:
        return erreur(400, "La production doit être positive ou nulle.")

    geojson_texte = lire_polygone(donnees)
    if geojson_texte is None:
        return erreur(400, "Un polygone GeoJSON est attendu.")

    conn = get_connection()
    try:
        # 2. Convertir la géométrie, vérifier sa validité, calculer la superficie
        valide, superficie = analyser_geometrie(conn, geojson_texte)
        if not valide:
            return erreur(422, "Géométrie invalide : redessinez la parcelle.")

        # 3. Insérer la parcelle
        try:
            curseur = conn.execute(
                """
                INSERT INTO parcelles (num_parcelle, agriculteur, culture,
                                       superficie_ha, production_t, geom)
                VALUES (?, ?, ?, ?, ?, SetSRID(GeomFromGeoJSON(?), 4326))
                """,
                (num, agriculteur, culture, superficie, production, geojson_texte),
            )
            conn.commit()
        except sqlite3.IntegrityError as e:
            # La contrainte UNIQUE du schéma refuse un numéro déjà utilisé
            if "UNIQUE" in str(e):
                return erreur(409, f"Le numéro de parcelle « {num} » existe déjà.")
            return erreur(422, f"Parcelle refusée par la base : {e}")

        # 4. Relire l'enregistrement créé (avec son id et sa date de saisie)
        ligne = conn.execute(
            "SELECT " + COLONNES + " FROM parcelles WHERE id = ?",
            (curseur.lastrowid,),
        ).fetchone()
    finally:
        conn.close()

    return jsonify(ligne_vers_feature(ligne)), 201


@app.route("/api/parcelles/<int:id_parcelle>", methods=["PUT"])
def modifier_parcelle(id_parcelle):
    """Extension — Modifie les attributs d'une parcelle (numéro, agriculteur, culture,
    production). La géométrie, donc la superficie, ne change pas."""
    attributs, message = verifier_attributs(request.get_json(silent=True) or {})
    if message:
        return erreur(400, message)
    num, agriculteur, culture, production = attributs

    conn = get_connection()
    try:
        try:
            modifiees = conn.execute(
                """
                UPDATE parcelles
                SET num_parcelle = ?, agriculteur = ?, culture = ?, production_t = ?
                WHERE id = ?
                """,
                (num, agriculteur, culture, production, id_parcelle),
            ).rowcount
            conn.commit()
        except sqlite3.IntegrityError as e:
            # Même contrainte UNIQUE qu'en F5 : numéro déjà pris par une autre parcelle
            if "UNIQUE" in str(e):
                return erreur(409, f"Le numéro de parcelle « {num} » existe déjà.")
            return erreur(422, f"Modification refusée par la base : {e}")
        if modifiees == 0:
            return erreur(404, f"Parcelle n° {id_parcelle} introuvable.")

        ligne = conn.execute(
            "SELECT " + COLONNES + " FROM parcelles WHERE id = ?", (id_parcelle,)
        ).fetchone()
    finally:
        conn.close()

    return jsonify(ligne_vers_feature(ligne))


@app.route("/api/parcelles/<int:id_parcelle>", methods=["DELETE"])
def supprimer_parcelle(id_parcelle):
    """Extension — Supprime une parcelle. L'index spatial est mis à jour
    automatiquement par SpatiaLite."""
    conn = get_connection()
    try:
        supprimees = conn.execute(
            "DELETE FROM parcelles WHERE id = ?", (id_parcelle,)
        ).rowcount
        conn.commit()
    finally:
        conn.close()

    if supprimees == 0:
        return erreur(404, f"Parcelle n° {id_parcelle} introuvable.")
    return jsonify({"supprimee": id_parcelle})


@app.route("/ndvi")
def page_ndvi():
    """F6 — Page chargée dans l'iframe : formulaire de calcul du NDVI."""
    num = request.args.get("num", "").strip()
    if not num:
        return "Paramètre num manquant dans l'adresse.", 400
    # Flask remplit le modèle templates/ndvi.html ; {{ num }} y est échappé automatiquement
    return render_template("ndvi.html", num=num)


@app.route("/api/ndvi", methods=["GET"])
def api_ndvi():
    """F6 — NDVI moyen Sentinel-2 d'une parcelle, par le traitement GEE imposé."""
    num = request.args.get("num", "").strip()
    debut = request.args.get("debut", "")
    fin = request.args.get("fin", "")

    # 1. Contrôle des dates (le serveur refait les contrôles du navigateur)
    message = verifier_dates(debut, fin)
    if message:
        return erreur(400, message)

    # 2. Géométrie de la parcelle, lue dans SpatiaLite
    geometrie = geometrie_parcelle(num)
    if geometrie is None:
        return erreur(404, f"Parcelle « {num} » introuvable.")

    # 3. Calcul sur Google Earth Engine
    try:
        resultat = calculer_ndvi(geometrie, debut, fin)
    except AucuneImageError as e:
        return erreur(422, str(e))                      # exigé par le guide
    except RuntimeError as e:
        return erreur(500, f"Configuration GEE manquante : {e}")
    except ee.EEException as e:
        return erreur(502, f"Erreur de Google Earth Engine : {e}")

    # 4. Réponse JSON au format imposé
    return jsonify({
        "num_parcelle": num,
        "debut": debut,
        "fin": fin,
        "ndvi_moyen": resultat["ndvi_moyen"],
        "nb_images": resultat["nb_images"],
    })


@app.route("/api/ndvi/carte", methods=["GET"])
def api_ndvi_carte():
    """F6 (option du guide) — Carte des classes de NDVI sur la parcelle, en image PNG.
    Flask télécharge lui-même l'image auprès de GEE : le navigateur ne voit jamais
    une adresse Google (qui contient l'identifiant du projet)."""
    num = request.args.get("num", "").strip()
    debut = request.args.get("debut", "")
    fin = request.args.get("fin", "")

    message = verifier_dates(debut, fin)
    if message:
        return erreur(400, message)

    geometrie = geometrie_parcelle(num)
    if geometrie is None:
        return erreur(404, f"Parcelle « {num} » introuvable.")

    try:
        png = carte_ndvi_png(geometrie, debut, fin)
    except AucuneImageError as e:
        return erreur(422, str(e))
    except RuntimeError as e:
        return erreur(500, f"Configuration GEE manquante : {e}")
    except (ee.EEException, OSError) as e:    # OSError : échec du téléchargement de l'image
        return erreur(502, f"Erreur de Google Earth Engine : {e}")

    return Response(png, mimetype="image/png")


@app.route("/ndvi/cycle")
def page_cycle():
    """Extension — Page chargée dans l'iframe de F6 : courbe NDVI de la campagne
    2025-2026 comparée aux profils de référence des cultures."""
    num = request.args.get("num", "").strip()
    if not num:
        return "Paramètre num manquant dans l'adresse.", 400
    return render_template("cycle.html", num=num)


@app.route("/api/ndvi/serie", methods=["GET"])
def api_ndvi_serie():
    """Extension — Série NDVI d'une parcelle sur la campagne 2025-2026, comparée aux
    profils de référence (profils_ndvi.py). La série est lue dans data/series_ndvi.csv,
    produit par extraire_series.py ; une parcelle absente du fichier (ajoutée depuis)
    est calculée sur GEE, avec le même traitement."""
    num = request.args.get("num", "").strip()

    conn = get_connection()
    try:
        ligne = conn.execute(
            "SELECT culture, AsGeoJSON(geom) AS geometrie FROM parcelles WHERE num_parcelle = ?",
            (num,),
        ).fetchone()
    finally:
        conn.close()
    if ligne is None:
        return erreur(404, f"Parcelle « {num} » introuvable.")

    points = lire_serie_fichier(num)
    source = "fichier"
    if not points:
        try:
            initialiser_gee()
            lignes = nettoyer(serie_gee(json.loads(ligne["geometrie"])))
        except RuntimeError as e:
            return erreur(500, f"Configuration GEE manquante : {e}")
        except ee.EEException as e:
            return erreur(502, f"Erreur de Google Earth Engine : {e}")
        points = [(date.fromisoformat(jour), ndvi) for jour, ndvi, _ in lignes if ndvi != ""]
        source = "gee"

    if len(points) < MIN_DATES:
        return erreur(422, "Trop peu d'images sans nuages sur la campagne pour tracer la courbe.")

    resultat = comparer(points, ligne["culture"])
    return jsonify({
        "num_parcelle": num,
        "culture": ligne["culture"],
        "source": source,
        "dates": [d.isoformat() for d, _ in points],
        "ndvi": [round(v, 3) for _, v in points],
        "grille": [d.isoformat() for d in GRILLE],
        "courbe": resultat["courbe"],
        "profils": resultat["profils"],
        "profil_saisie": resultat["profil_saisie"],
        "verdict": resultat["verdict"],
    })


if __name__ == "__main__":
    app.run(debug=True)