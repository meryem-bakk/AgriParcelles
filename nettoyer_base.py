"""
nettoyer_base.py — Outil temporaire (ne fait pas partie du projet rendu).
  python nettoyer_base.py                  -> liste toutes les parcelles
  python nettoyer_base.py mimi Test1 ...   -> supprime ces parcelles, après confirmation
"""
import sys

from db import get_connection

conn = get_connection()
try:
    if len(sys.argv) == 1:
        # Sans argument : afficher la liste pour repérer les parcelles de test
        for ligne in conn.execute(
            "SELECT id, num_parcelle, culture, ROUND(superficie_ha, 2) AS ha "
            "FROM parcelles ORDER BY id"
        ):
            print(f'{ligne["id"]:>3}  {ligne["num_parcelle"]:<15} {ligne["culture"]:<20} {ligne["ha"]} ha')
    else:
        nums = sys.argv[1:]
        if input(f"Supprimer {', '.join(nums)} ? (o/n) ").lower() == "o":
            for num in nums:
                n = conn.execute("DELETE FROM parcelles WHERE num_parcelle = ?", (num,)).rowcount
                print(num, ":", "supprimée" if n else "introuvable")
            # Table vide : remettre le compteur d'identifiants à zéro
            if conn.execute("SELECT COUNT(*) FROM parcelles").fetchone()[0] == 0:
                conn.execute("DELETE FROM sqlite_sequence WHERE name = 'parcelles'")
            conn.commit()
finally:
    conn.close()
    