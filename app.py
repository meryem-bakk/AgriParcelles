"""
app.py — Serveur Flask d'AgriParcelles : page principale et API REST en JSON.
Lancement : python app.py, puis http://127.0.0.1:5000
"""
import json
import sqlite3

from flask import Flask, jsonify, request

from db import get_connection

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


if __name__ == "__main__":
    app.run(debug=True)