"""
corriger_cultures.py — Outil temporaire (ne fait pas partie du projet rendu),
comme nettoyer_base.py. Corrige la culture et la production des parcelles
d'après leur courbe NDVI (data/graphes/index.html, data/propositions_ndvi.csv).

  python corriger_cultures.py   -> affiche les changements, les applique après confirmation

Une seule personne du binôme le lance, puis envoie la base sur GitHub.
"""
import sys

from app import CULTURES          # même liste que le formulaire (imposée par le guide)
from db import get_connection

# numéro : (culture retenue, production en tonnes, ce que montre la courbe NDVI)
# Production du maraîchage : environ 30 t/ha (ordre de grandeur, à ajuster)
CORRECTIONS = {
    "Z8-P03": ("Maraîchage", 89.0,
               "sol nu jusqu'à fin février, vert jusqu'à fin mai puis récolté d'un coup"),
    "Z8-P05": ("Maraîchage", 65.0,
               "sol nu en automne et en été (pas une luzerne), pic fin avril"),
    "Z8-P06": ("Jachère", 0.0,
               "NDVI jamais au-dessus de 0,32 : rien n'a vraiment poussé"),
    "Z8-P08": ("Maraîchage", 70.0,
               "vert de juin à août : pas une betterave, récoltée avant l'été"),
    "Z8-P15": ("Blé dur", 18.0,
               "pic mi-février puis sec en été, même courbe que le blé dur de P04"),
    # Z8-P07 reste en Jachère, sauf si son graphe montre une vraie cloche comme P04 :
    # dans ce cas, enlever le # de la ligne suivante.
    # "Z8-P07": ("Orge", 3.0, "pic début mars : céréale pluviale plutôt que jachère"),
}

for num, (culture, _, _) in CORRECTIONS.items():
    if culture not in CULTURES:
        sys.exit(f"{num} : « {culture} » n'est pas dans la liste des cultures du guide.")

conn = get_connection()
try:
    for num, (culture, production, raison) in CORRECTIONS.items():
        avant = conn.execute(
            "SELECT culture, production_t FROM parcelles WHERE num_parcelle = ?", (num,)
        ).fetchone()
        if avant is None:
            sys.exit(f"{num} : parcelle introuvable, rien n'a été modifié.")
        print(f"{num} : {avant['culture']} ({avant['production_t']} t) -> "
              f"{culture} ({production} t)\n         {raison}")

    if input("\nAppliquer ces corrections ? (o/n) ").lower() == "o":
        for num, (culture, production, _) in CORRECTIONS.items():
            conn.execute(
                "UPDATE parcelles SET culture = ?, production_t = ? WHERE num_parcelle = ?",
                (culture, production, num),
            )
        conn.commit()
        print("Corrections enregistrées.")
    else:
        print("Rien n'a été modifié.")
finally:
    conn.close()