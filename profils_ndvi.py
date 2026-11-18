"""
profils_ndvi.py — Comparaison de la courbe NDVI d'une parcelle (campagne
septembre 2025 - août 2026) avec les profils de référence des cultures de la zone.

Un profil de référence est la courbe NDVI attendue pour une culture, construite
à partir de son calendrier cultural (semis, pic de végétation, récolte) et des
niveaux de la grille d'interprétation du guide (< 0,2 sol nu ; > 0,6 dense).
Ce sont des courbes théoriques, pas des mesures : elles servent à vérifier que
la courbe de la parcelle suit bien le cycle phénologique de la culture saisie.

Uniquement la bibliothèque standard de Python.
"""
import csv
import os
from datetime import date, timedelta
from math import sqrt
from statistics import median

from db import BASE_DIR

FICHIER_SERIES = os.path.join(BASE_DIR, "data", "series_ndvi.csv")   # extraire_series.py

DEBUT = date(2025, 9, 1)
FIN = date(2026, 8, 31)
GRILLE = [DEBUT + timedelta(days=j) for j in range(0, (FIN - DEBUT).days + 1, 10)]
MIN_DATES = 10          # en dessous, la courbe de la parcelle n'est pas fiable

# Lecture de l'écart moyen (en NDVI) entre la courbe de la parcelle et un profil
ECART_BON = 0.10        # moins d'une demi-classe de la grille du guide (classes de 0,2)
ECART_MOYEN = 0.15      # au-delà : la courbe ne suit pas ce profil
ECART_PROCHE = 0.02     # deux profils à moins de 0,02 l'un de l'autre : on ne peut pas trancher

# Points clés de chaque profil : ("MM-JJ", NDVI). Entre deux points, la courbe est
# une droite. Septembre à décembre sont en 2025, janvier à août en 2026.
# "cultures" : les cultures de la liste du guide que ce profil représente.
PROFILS = [
    {"nom": "Agrumes", "cultures": ["Agrumes"],
     "cycle": "Verger irrigué à feuillage persistant : vert toute l'année.",
     "points": [("09-01", 0.62), ("01-15", 0.66), ("03-15", 0.70), ("05-15", 0.66), ("08-31", 0.62)]},
    {"nom": "Olivier", "cultures": ["Olivier"],
     "cycle": "Arbres espacés, sol visible entre eux : NDVI moyen toute l'année, "
              "un peu plus haut en hiver avec l'herbe sous les arbres.",
     "points": [("09-01", 0.36), ("12-15", 0.40), ("02-15", 0.46), ("04-15", 0.44),
                ("06-15", 0.38), ("08-31", 0.35)]},
    {"nom": "Luzerne", "cultures": ["Luzerne"],
     "cycle": "Fourrage irrigué pluriannuel : vert toute l'année, pousse ralentie en hiver. "
              "Chaque coupe fait chuter le NDVI quelques jours (dates variables, non dessinées).",
     "points": [("09-01", 0.62), ("12-15", 0.52), ("02-15", 0.58), ("04-15", 0.70), ("08-31", 0.64)]},
    {"nom": "Céréale d'hiver", "cultures": ["Blé dur", "Blé tendre", "Orge"],
     "cycle": "Semis en novembre-décembre, pic à l'épiaison (février-mars), "
              "jaunissement en avril-mai, récolte en mai-juin.",
     "points": [("09-01", 0.16), ("11-30", 0.17), ("01-10", 0.35), ("02-20", 0.78), ("03-20", 0.80),
                ("04-20", 0.55), ("05-15", 0.28), ("06-10", 0.18), ("08-31", 0.15)]},
    {"nom": "Betterave sucrière", "cultures": ["Betterave sucrière"],
     "cycle": "Semis à partir de mi-septembre, le sol est couvert dès l'hiver, "
              "pic en mars-avril, arrachage en mai-juin.",
     "points": [("09-01", 0.15), ("10-15", 0.17), ("11-30", 0.35), ("01-15", 0.62), ("03-01", 0.80),
                ("04-30", 0.80), ("05-31", 0.50), ("06-30", 0.18), ("08-31", 0.15)]},
    {"nom": "Maraîchage de printemps", "cultures": ["Maraîchage"],
     "cycle": "Pomme de terre de saison par exemple : plantation en janvier-février, "
              "pic en avril-mai, récolte en mai-juin. Sol nu le reste de l'année.",
     "points": [("09-01", 0.18), ("02-10", 0.20), ("03-15", 0.40), ("04-20", 0.78), ("05-20", 0.80),
                ("06-05", 0.45), ("06-20", 0.18), ("08-31", 0.17)]},
    {"nom": "Culture d'été", "cultures": ["Maïs", "Maraîchage"],
     "cycle": "Maïs ou maraîchage d'été : semis en avril-mai, pic en juillet-août, récolte en "
              "septembre-octobre. En septembre, on voit encore la culture de l'été précédent.",
     "points": [("09-01", 0.55), ("10-10", 0.25), ("11-01", 0.18), ("04-15", 0.18), ("05-20", 0.40),
                ("07-01", 0.75), ("08-15", 0.80), ("08-31", 0.78)]},
    {"nom": "Jachère", "cultures": ["Jachère"],
     "cycle": "Pas de culture : sol nu, avec un peu d'herbe spontanée après les pluies d'hiver.",
     "points": [("09-01", 0.14), ("12-01", 0.16), ("02-15", 0.26), ("04-15", 0.22),
                ("05-31", 0.15), ("08-31", 0.13)]},
]


def interpoler(x, xs, ys):
    """Interpolation linéaire entre deux points connus ; valeur du bord en dehors."""
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    for i in range(1, len(xs)):
        if x <= xs[i]:
            t = (x - xs[i - 1]) / (xs[i] - xs[i - 1])
            return ys[i - 1] + t * (ys[i] - ys[i - 1])


def mediane_glissante(valeurs):
    """Médiane sur 3 points centrés (2 aux bords) : enlève une valeur isolée due à un nuage."""
    return [median(valeurs[max(0, i - 1):i + 2]) for i in range(len(valeurs))]


def jour_campagne(mm_jj):
    """'MM-JJ' -> nombre de jours depuis le 1er septembre 2025."""
    mois, jour = int(mm_jj[:2]), int(mm_jj[3:])
    annee = 2025 if mois >= 9 else 2026
    return (date(annee, mois, jour) - DEBUT).days


def courbe_profil(profil):
    """Valeurs d'un profil de référence sur la grille de 10 jours."""
    xs = [jour_campagne(p[0]) for p in profil["points"]]
    ys = [p[1] for p in profil["points"]]
    return [round(interpoler((d - DEBUT).days, xs, ys), 3) for d in GRILLE]


def courbe_parcelle(points):
    """Courbe de la parcelle sur la même grille, lissée. points : liste triée de (date, ndvi)."""
    xs = [(d - DEBUT).days for d, _ in points]
    ys = [v for _, v in points]
    return mediane_glissante([interpoler((d - DEBUT).days, xs, ys) for d in GRILLE])


def ecart(courbe_a, courbe_b):
    """Écart moyen entre deux courbes (racine de la moyenne des carrés des différences),
    en unités de NDVI : 0 si elles sont identiques."""
    return sqrt(sum((a - b) ** 2 for a, b in zip(courbe_a, courbe_b)) / len(courbe_a))


def lire_serie_fichier(num):
    """Série d'une parcelle dans data/series_ndvi.csv : liste triée de (date, ndvi),
    vide si le fichier n'existe pas ou ne contient pas cette parcelle."""
    if not os.path.exists(FICHIER_SERIES):
        return []
    with open(FICHIER_SERIES, newline="", encoding="utf-8") as f:
        return sorted((date.fromisoformat(l["date"][:10]), float(l["ndvi"]))
                      for l in csv.DictReader(f) if l["num"] == num and l["ndvi"].strip())


def correspondance(valeur_ecart):
    """Lecture de l'écart en trois niveaux."""
    if valeur_ecart < ECART_BON:
        return "bonne"
    if valeur_ecart < ECART_MOYEN:
        return "moyenne"
    return "faible"


def verdict(profils, profil_saisie, culture_saisie):
    """Phrase de conclusion. profils est déjà classé du plus proche au plus éloigné."""
    meilleur, second = profils[0], profils[1]
    if profil_saisie is None:
        texte = (f"Culture saisie « {culture_saisie} » : pas de profil de référence. "
                 f"Le profil le plus proche est « {meilleur['nom']} ».")
    elif profil_saisie["nom"] == meilleur["nom"]:
        texte = f"La courbe confirme la culture saisie : son profil « {meilleur['nom']} » est le plus proche."
        if second["ecart"] - meilleur["ecart"] < ECART_PROCHE:
            texte += f" Mais « {second['nom']} » est presque aussi proche : la courbe seule ne permet pas de trancher."
    elif profil_saisie["ecart"] - meilleur["ecart"] < ECART_PROCHE:
        texte = (f"Le profil de la culture saisie (« {profil_saisie['nom']} ») est presque aussi proche "
                 f"que le plus proche (« {meilleur['nom']} ») : la courbe ne permet pas de trancher.")
    else:
        texte = (f"Attention : le profil le plus proche est « {meilleur['nom']} », "
                 f"pas celui de la culture saisie (« {profil_saisie['nom']} »).")
    ecart_txt = f"{meilleur['ecart']:.2f}".replace(".", ",")
    if meilleur["ecart"] >= ECART_MOYEN:
        texte += f" Aucun profil ne correspond bien (écart minimal {ecart_txt}) : à confirmer sur le terrain."
    elif meilleur["ecart"] >= ECART_BON:
        texte += f" La correspondance reste moyenne (écart {ecart_txt})."
    return texte


def comparer(points, culture_saisie):
    """Compare la courbe d'une parcelle à tous les profils.
    Renvoie la courbe lissée, les profils classés du plus proche au plus éloigné,
    le nom du profil de la culture saisie (le plus proche s'il y en a deux) et une conclusion."""
    courbe = courbe_parcelle(points)
    profils = []
    for p in PROFILS:
        valeurs = courbe_profil(p)
        e = ecart(courbe, valeurs)
        profils.append({"nom": p["nom"], "cultures": p["cultures"], "cycle": p["cycle"],
                        "valeurs": valeurs, "ecart": round(e, 3), "correspondance": correspondance(e)})
    profils.sort(key=lambda p: p["ecart"])

    profil_saisie = next((p for p in profils if culture_saisie in p["cultures"]), None)
    return {"courbe": [round(v, 3) for v in courbe], "profils": profils,
            "profil_saisie": profil_saisie["nom"] if profil_saisie else None,
            "verdict": verdict(profils, profil_saisie, culture_saisie)}
