"""
init_db.py — Crée data/agriparcelles.sqlite à partir de sql/schema.sql.
À lancer une seule fois : python init_db.py
"""
import os

from db import BASE_DIR, DB_PATH, get_connection

SCHEMA_PATH = os.path.join(BASE_DIR, "sql", "schema.sql")


def init_db():
    # 1. Ne jamais écraser une base existante : elle contiendra
    #    les parcelles digitalisées. Un fichier vide (0 octet) n'est pas
    #    encore une base : on peut l'initialiser.
    if os.path.exists(DB_PATH) and os.path.getsize(DB_PATH) > 0:
        print("La base existe déjà :", DB_PATH)
        print("Supprimez-la manuellement pour la recréer (les parcelles seront perdues).")
        return

    # 2. Créer le dossier data/ s'il n'existe pas encore
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    # 3. Lire le script SQL imposé par le guide
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        schema = f.read()

    # 4. Ouvrir la connexion : crée le fichier vide et charge SpatiaLite
    conn = get_connection()
    try:
        # 5. Exécuter toutes les instructions du script, dans l'ordre
        conn.executescript(schema)

        # 6. Vérifier le résultat dans la table technique geometry_columns
        ligne = conn.execute(
            "SELECT f_geometry_column, geometry_type, srid, spatial_index_enabled "
            "FROM geometry_columns WHERE f_table_name = 'parcelles'"
        ).fetchone()
        if ligne is None:
            raise RuntimeError("La colonne géométrique 'geom' n'a pas été créée.")

        print("Table parcelles créée")
        print("  colonne       :", ligne["f_geometry_column"])
        print("  type          :", ligne["geometry_type"], "(3 = POLYGON XY)")
        print("  SRID          :", ligne["srid"])
        print("  index spatial :", "oui" if ligne["spatial_index_enabled"] == 1 else "non")
    except Exception:
        # En cas d'échec, supprimer la base incomplète pour pouvoir relancer
        conn.close()
        os.remove(DB_PATH)
        raise

    conn.close()
    print("Base créée :", DB_PATH)


if __name__ == "__main__":
    init_db()