"""
graphes_ndvi.py : dessine la courbe NDVI de chaque parcelle sur la campagne 2025-2026.

Entrées : data/series_ndvi.csv        (produit par extraire_series.py)
          data/propositions_ndvi.csv  (produit par analyse_series.py, facultatif)
Sorties : data/graphes/<num>.svg      une image par parcelle (rapport, diapos)
          data/graphes/index.html     toutes les courbes sur une page

Uniquement la bibliothèque standard : une image SVG est un simple fichier texte
(des lignes, des points, des textes), que l'on écrit nous-mêmes.
"""
import csv
import os
from datetime import date
from html import escape

DOSSIER = os.path.dirname(os.path.abspath(__file__))
ENTREE = os.path.join(DOSSIER, "data", "series_ndvi.csv")
PROPOSITIONS = os.path.join(DOSSIER, "data", "propositions_ndvi.csv")
SORTIE = os.path.join(DOSSIER, "data", "graphes")

DEBUT = date(2025, 9, 1)
FIN = date(2026, 8, 31)
LARGEUR, HAUTEUR = 480, 270              # taille d'un graphe, en pixels
GAUCHE, DROITE, HAUT, BAS = 42, 14, 50, 28   # marges autour de la zone de tracé
MOIS = ["S", "O", "N", "D", "J", "F", "M", "A", "M", "J", "J", "A"]   # septembre à août
VERT, ROUGE, GRIS = "#2E6B3F", "#B03A2E", "#6B7280"
COULEUR_ACCORD = {"oui": VERT, "non": ROUGE, "?": GRIS}


def x_px(jour):
    """Position horizontale d'une date sur le graphe."""
    return GAUCHE + (jour - DEBUT).days / (FIN - DEBUT).days * (LARGEUR - GAUCHE - DROITE)


def y_px(ndvi):
    """Position verticale d'un NDVI (axe de 0 à 1 ; le SVG compte les y vers le bas)."""
    ndvi = min(max(ndvi, 0.0), 1.0)
    return HAUTEUR - BAS - ndvi * (HAUTEUR - HAUT - BAS)


def graphe_svg(num, saisie, points, proposition, accord):
    """Texte SVG du graphe d'une parcelle. points : liste triée de (date, ndvi)."""
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{LARGEUR}" height="{HAUTEUR}" '
         f'viewBox="0 0 {LARGEUR} {HAUTEUR}" font-family="Arial, sans-serif">',
         f'<rect width="{LARGEUR}" height="{HAUTEUR}" fill="white"/>',
         f'<text x="{GAUCHE}" y="20" font-size="15" font-weight="bold">{escape(num)} : {escape(saisie)}</text>']
    if proposition:
        s.append(f'<text x="{GAUCHE}" y="38" font-size="12" fill="{COULEUR_ACCORD.get(accord, GRIS)}">'
                 f'NDVI : {escape(proposition)} (accord : {escape(accord)})</text>')

    # Lignes horizontales aux seuils de la grille d'interprétation du guide
    for v in (0.2, 0.4, 0.6, 0.8):
        y = y_px(v)
        s.append(f'<line x1="{GAUCHE}" y1="{y:.1f}" x2="{LARGEUR - DROITE}" y2="{y:.1f}" stroke="#E5E7EB"/>')
        s.append(f'<text x="{GAUCHE - 6}" y="{y + 4:.1f}" font-size="11" fill="{GRIS}" text-anchor="end">{v:.1f}</text>')

    # Initiale de chaque mois, au 15 du mois
    for i, lettre in enumerate(MOIS):
        annee, mois = (2025, 9 + i) if i < 4 else (2026, i - 3)
        s.append(f'<text x="{x_px(date(annee, mois, 15)):.1f}" y="{HAUTEUR - 8}" font-size="11" '
                 f'fill="{GRIS}" text-anchor="middle">{lettre}</text>')
    s.append(f'<line x1="{GAUCHE}" y1="{y_px(0):.1f}" x2="{LARGEUR - DROITE}" y2="{y_px(0):.1f}" stroke="{GRIS}"/>')

    # La courbe : une ligne qui relie les dates, et un point par image Sentinel-2
    trace = " ".join(f"{x_px(d):.1f},{y_px(v):.1f}" for d, v in points)
    s.append(f'<polyline points="{trace}" fill="none" stroke="{VERT}" stroke-width="2"/>')
    for d, v in points:
        s.append(f'<circle cx="{x_px(d):.1f}" cy="{y_px(v):.1f}" r="2.2" fill="{VERT}"/>')
    s.append("</svg>")
    return "\n".join(s)


# 1. Lecture des séries (dates sans NDVI sautées) et, s'il existe, du fichier des propositions
series = {}
with open(ENTREE, newline="", encoding="utf-8") as f:
    for ligne in csv.DictReader(f):
        if ligne["ndvi"].strip():
            p = series.setdefault(ligne["num"], {"culture": ligne["culture"], "points": []})
            p["points"].append((date.fromisoformat(ligne["date"][:10]), float(ligne["ndvi"])))

propositions = {}
if os.path.exists(PROPOSITIONS):
    with open(PROPOSITIONS, newline="", encoding="utf-8") as f:
        propositions = {ligne["num"]: ligne for ligne in csv.DictReader(f)}

# 2. Un fichier SVG par parcelle, et la même image dans la page index.html
os.makedirs(SORTIE, exist_ok=True)
page = ['<!doctype html><html lang="fr"><head><meta charset="utf-8">',
        "<title>Courbes NDVI 2025-2026</title>",
        "<style>body{font-family:Arial,sans-serif;margin:24px;background:#fff}"
        "div{display:flex;flex-wrap:wrap;gap:12px}svg{border:1px solid #E5E7EB}</style>",
        "</head><body><h1>Courbes NDVI de nos parcelles, campagne 2025-2026</h1><div>"]
for num in sorted(series):
    prop = propositions.get(num, {})
    svg = graphe_svg(num, series[num]["culture"], sorted(series[num]["points"]),
                     prop.get("proposition", ""), prop.get("accord", ""))
    with open(os.path.join(SORTIE, f"{num}.svg"), "w", encoding="utf-8") as f:
        f.write(svg)
    page.append(svg)
    print(f"{num} : {len(series[num]['points'])} dates")
page.append("</div></body></html>")

with open(os.path.join(SORTIE, "index.html"), "w", encoding="utf-8") as f:
    f.write("\n".join(page))
print(f"\nGraphes enregistrés dans {SORTIE} (ouvrir index.html)")