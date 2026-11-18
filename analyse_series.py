"""
analyse_series.py : propose une famille de cultures à partir de la série NDVI
de chaque parcelle, sur une campagne (septembre 2025 à août 2026).
Sert à vérifier la culture saisie dans la base.

Entrée  : data/series_ndvi.csv  (colonnes num, date, ndvi, culture)
Sortie  : data/propositions_ndvi.csv

Uniquement la bibliothèque standard de Python (csv, datetime, statistics),
pour rester dans la pile imposée par le guide.
"""
import csv
from datetime import date, timedelta
from statistics import mean, median

ENTREE = "data/series_ndvi.csv"
SORTIE = "data/propositions_ndvi.csv"

DEBUT = date(2025, 9, 1)
FIN = date(2026, 8, 31)
PAS = 10                       # une valeur tous les 10 jours

# Seuils de la règle de décision : à ajuster sur nos 15 parcelles connues
AMP_PERENNE = 0.45             # en dessous : peu de variation dans l'année
MOY_PERENNE = 0.40             # au-dessus : végétation présente toute l'année
AMP_CEREALE = 0.45             # au-dessus : un vrai cycle de culture
AUTOMNE_SOL_NU = 0.30          # en dessous : sol nu de septembre à novembre
MOY_SOL_NU = 0.30              # en dessous : jachère ou sol nu

GRILLE = [DEBUT + timedelta(days=j) for j in range(0, (FIN - DEBUT).days + 1, PAS)]


def interpoler(x, xs, ys):
    """Interpolation linéaire (comme numpy.interp) : valeur du bord en dehors des données."""
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    for i in range(1, len(xs)):
        if x <= xs[i]:
            t = (x - xs[i - 1]) / (xs[i] - xs[i - 1])
            return ys[i - 1] + t * (ys[i] - ys[i - 1])


def mediane_glissante(valeurs):
    """Médiane sur 3 points centrés (2 aux bords) : enlève les valeurs isolées dues aux nuages."""
    return [median(valeurs[max(0, i - 1):i + 2]) for i in range(len(valeurs))]


# 1. Lecture du fichier, regroupé par parcelle
series = {}
with open(ENTREE, newline="", encoding="utf-8") as f:
    for ligne in csv.DictReader(f):
        if not ligne["ndvi"].strip():              # image masquée : pas de valeur
            continue
        p = series.setdefault(ligne["num"], {"culture": ligne["culture"], "points": []})
        p["points"].append((date.fromisoformat(ligne["date"][:10]), float(ligne["ndvi"])))

# 2. Analyse de chaque parcelle
resultats = []
for num in sorted(series):
    points = sorted(series[num]["points"])
    if len(points) < 2:
        print(f"{num} : moins de 2 dates, parcelle ignorée")
        continue
    jours = [(d - DEBUT).days for d, _ in points]
    ndvi = [v for _, v in points]

    y = [interpoler((d - DEBUT).days, jours, ndvi) for d in GRILLE]
    y = mediane_glissante(y)

    moy = mean(y)
    amp = max(y) - min(y)
    pic = GRILLE[y.index(max(y))]
    automne = mean(y[:9])                           # 1er septembre au 20 novembre

    # Règle de décision, testée dans cet ordre (la culture d'hiver avant le sol nu).
    # Le NDVI seul ne sépare pas le blé de la betterave, ni les agrumes de la luzerne :
    # on propose une famille, pas une culture.
    if amp < AMP_PERENNE and moy >= MOY_PERENNE:
        famille = "Vert toute l'année (agrumes, olivier, luzerne)"
    elif amp >= AMP_CEREALE and automne < AUTOMNE_SOL_NU and pic.month in (2, 3, 4):
        famille = "Culture d'hiver (céréale, betterave)"
    elif moy < MOY_SOL_NU:
        famille = "Jachère / sol nu"
    else:
        famille = "À vérifier sur l'image"

    resultats.append({"num": num, "saisie": series[num]["culture"],
                      "ndvi_moy": round(moy, 2), "amplitude": round(amp, 2),
                      "pic": pic.strftime("%d/%m"), "proposition": famille})

# 3. Affichage et enregistrement
print(f"{'num':8} {'saisie':20} {'moy':>5} {'ampl':>5} {'pic':>6}  proposition")
for r in resultats:
    print(f"{r['num']:8} {r['saisie']:20} {r['ndvi_moy']:5.2f} {r['amplitude']:5.2f} {r['pic']:>6}  {r['proposition']}")

with open(SORTIE, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["num", "saisie", "ndvi_moy", "amplitude", "pic", "proposition"])
    w.writeheader()
    w.writerows(resultats)
print(f"\nRésultats enregistrés dans {SORTIE}")