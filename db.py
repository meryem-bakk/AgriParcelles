"""
db.py — Connexion à la base SpatiaLite d'AgriParcelles.

init_db.py et app.py obtiennent leur connexion par get_connection(),
pour que le chargement de SpatiaLite soit écrit à un seul endroit.
"""
import os
import sqlite3

# Dossier du projet (celui qui contient ce fichier), quel que soit
# le dossier depuis lequel on lance Python
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Chemin de la base imposé par le guide
DB_PATH = os.path.join(BASE_DIR, "data", "agriparcelles.sqlite")

# Dossier des DLL SpatiaLite : variable d'environnement SPATIALITE_DIR
# si elle est définie (utile si l'autre membre du binôme l'a installé
# ailleurs), sinon chemin par défaut.
SPATIALITE_DIR = os.environ.get(
    "SPATIALITE_DIR", r"C:\spatialite\mod_spatialite-5.1.0-win-amd64"
)

# SQLite charge mod_spatialite.dll avec la recherche Windows classique,
# qui consulte le PATH pour trouver ses dépendances (GEOS, PROJ...).
# On place donc ce dossier en tête du PATH, pour ce processus uniquement.
os.environ["PATH"] = SPATIALITE_DIR + os.pathsep + os.environ["PATH"]


def get_connection(db_path=DB_PATH):
    """Ouvre une connexion SQLite et y charge l'extension SpatiaLite."""
    conn = sqlite3.connect(db_path)

    # Les lignes renvoyées se lisent par nom de colonne :
    # ligne["culture"] au lieu de ligne[3]. Pratique pour produire du JSON.
    conn.row_factory = sqlite3.Row

    # Charger SpatiaLite, puis interdire tout autre chargement d'extension
    conn.enable_load_extension(True)
    conn.load_extension(os.path.join(SPATIALITE_DIR, "mod_spatialite"))
    conn.enable_load_extension(False)

    return conn


# Test rapide : python db.py
if __name__ == "__main__":
    conn = get_connection(":memory:")
    version = conn.execute("SELECT spatialite_version()").fetchone()[0]
    print("Connexion OK — SpatiaLite", version)
    conn.close()