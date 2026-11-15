/*
 * ndvi.js — F6 (interface) : mode sélection, surbrillance de la parcelle choisie,
 * fenêtre flottante déplaçable contenant l'iframe /ndvi?num=<numéro>,
 * et carte détaillée du NDVI sur la parcelle (option prévue par le guide).
 * Utilise map (map.js), coucheParcelles, contenuPopup et annulerDessin (parcelles.js).
 */

// Style de la parcelle sélectionnée : se distingue du jaune des autres parcelles
const STYLE_SELECTION = {
    color: "#00e5ff",       // contour cyan
    weight: 4,
    fillColor: "#00e5ff",
    fillOpacity: 0.3
};

let modeSelection = false;         // vrai pendant qu'on attend un clic sur une parcelle
let parcelleSelectionnee = null;   // parcelle actuellement en surbrillance

const fenetreNdvi = document.getElementById("fenetre-ndvi");
const enteteNdvi = document.getElementById("entete-ndvi");
const titreNdvi = document.getElementById("titre-ndvi");
const iframeNdvi = document.getElementById("iframe-ndvi");
let boutonSelection;   // créé par le contrôle ci-dessous

// ---------- Bouton « Sélectionner une parcelle » ----------
const controleSelection = L.control({ position: "topleft" });
controleSelection.onAdd = function () {
    boutonSelection = L.DomUtil.create("button", "bouton-carte");
    boutonSelection.type = "button";
    boutonSelection.textContent = "Sélectionner une parcelle";
    L.DomEvent.disableClickPropagation(boutonSelection);
    L.DomEvent.on(boutonSelection, "click", function () {
        // Un second clic sur le bouton annule le mode sélection
        if (modeSelection) {
            quitterModeSelection();
        } else {
            entrerModeSelection();
        }
    });
    return boutonSelection;
};
controleSelection.addTo(map);

// ---------- 1. Entrer et sortir du mode sélection ----------
function entrerModeSelection() {
    annulerDessin();   // pas de dessin F5 en même temps (fonction de parcelles.js)
    modeSelection = true;
    L.DomUtil.addClass(map.getContainer(), "mode-selection");   // curseur en croix (CSS)
    boutonSelection.textContent = "Annuler la sélection";
    // Pendant la sélection, un clic sur une parcelle ne doit pas ouvrir sa popup
    coucheParcelles.eachLayer(function (couche) {
        couche.unbindPopup();
    });
}

function quitterModeSelection() {
    modeSelection = false;
    L.DomUtil.removeClass(map.getContainer(), "mode-selection");
    boutonSelection.textContent = "Sélectionner une parcelle";
    // On remet les popups de F2
    coucheParcelles.eachLayer(function (couche) {
        couche.bindPopup(contenuPopup(couche.feature.properties));
    });
}

// Commencer un dessin (F5) fait quitter le mode sélection
map.on("pm:drawstart", function () {
    if (modeSelection) {
        quitterModeSelection();
    }
});

// ---------- 2. Clic sur une parcelle ----------
// Le clic sur une parcelle remonte jusqu'à la couche qui la contient
coucheParcelles.on("click", function (e) {
    if (!modeSelection) return;   // hors mode sélection : la popup de F2 s'ouvre normalement
    const parcelle = e.layer;     // la parcelle cliquée
    retirerCarteNdvi();           // la carte NDVI de la parcelle précédente disparaît
    quitterModeSelection();
    mettreEnSurbrillance(parcelle);
    ouvrirFenetreNdvi(parcelle.feature.properties.num_parcelle);
});

function mettreEnSurbrillance(parcelle) {
    retirerSurbrillance();               // une seule parcelle en surbrillance à la fois
    parcelleSelectionnee = parcelle;
    parcelle.setStyle(STYLE_SELECTION);
    parcelle.bringToFront();             // passe au-dessus des parcelles voisines
}

function retirerSurbrillance() {
    if (parcelleSelectionnee) {
        coucheParcelles.resetStyle(parcelleSelectionnee);   // retour au style jaune de F2
        parcelleSelectionnee = null;
    }
}

// ---------- 3. Ouvrir et fermer la fenêtre flottante ----------
function ouvrirFenetreNdvi(num) {
    titreNdvi.textContent = "NDVI — parcelle " + num;   // textContent : jamais interprété comme du HTML
    // encodeURIComponent : le numéro peut contenir des espaces, des accents ou un « # »
    iframeNdvi.src = "/ndvi?num=" + encodeURIComponent(num);

    if (fenetreNdvi.hidden) {
        // Première ouverture : la fenêtre apparaît centrée en haut de l'écran
        fenetreNdvi.hidden = false;
        fenetreNdvi.style.left = Math.max(10, (window.innerWidth - fenetreNdvi.offsetWidth) / 2) + "px";
        fenetreNdvi.style.top = "60px";
    }
}

function fermerFenetreNdvi() {
    fenetreNdvi.hidden = true;
    iframeNdvi.src = "about:blank";   // vide l'iframe (arrête un éventuel chargement)
    retirerCarteNdvi();
    retirerSurbrillance();
}

document.getElementById("fermer-ndvi").addEventListener("click", fermerFenetreNdvi);

// ---------- 4. Déplacer la fenêtre en glissant sa barre de titre ----------
let enDeplacement = false;
let decalageX = 0;   // position du pointeur par rapport au coin de la fenêtre
let decalageY = 0;

enteteNdvi.addEventListener("pointerdown", function (e) {
    if (e.target.closest("#fermer-ndvi")) return;   // le bouton × ne déplace pas la fenêtre
    enDeplacement = true;
    decalageX = e.clientX - fenetreNdvi.offsetLeft;
    decalageY = e.clientY - fenetreNdvi.offsetTop;
    enteteNdvi.setPointerCapture(e.pointerId);   // la barre reçoit tous les mouvements du pointeur
    iframeNdvi.style.pointerEvents = "none";     // sinon l'iframe « capte » les mouvements au passage
});

enteteNdvi.addEventListener("pointermove", function (e) {
    if (!enDeplacement) return;
    fenetreNdvi.style.left = (e.clientX - decalageX) + "px";
    fenetreNdvi.style.top = Math.max(0, e.clientY - decalageY) + "px";   // la barre reste visible
});

function finDeplacement() {
    enDeplacement = false;
    iframeNdvi.style.pointerEvents = "";
}
enteteNdvi.addEventListener("pointerup", finDeplacement);
enteteNdvi.addEventListener("pointercancel", finDeplacement);

// ---------- 5. Carte NDVI de la parcelle (option prévue par le guide) ----------
// Mêmes classes et mêmes couleurs que PALETTE_CLASSES dans gee_ndvi.py
const CLASSES_NDVI = [
    { couleur: "#a6611a", texte: "< 0,2 : sol nu ou végétation très faible" },
    { couleur: "#dfc27d", texte: "0,2 – 0,4 : végétation faible" },
    { couleur: "#a6d96a", texte: "0,4 – 0,6 : végétation modérée" },
    { couleur: "#1a9641", texte: "> 0,6 : végétation dense" }
];

let carteNdvi = null;   // image actuellement posée sur la carte

const controleLegendeNdvi = L.control({ position: "bottomright" });
controleLegendeNdvi.onAdd = function () {
    const div = L.DomUtil.create("div", "legende-wms");   // même cadre que la légende MapServer
    let html = '<div class="panneau-titre">NDVI moyen</div>';
    CLASSES_NDVI.forEach(function (c) {
        html += '<div><span class="pastille" style="background:' + c.couleur + '"></span>' + c.texte + "</div>";
    });
    div.innerHTML = html;
    return div;
};

// Déclarée avec « function » (et non const) : elle devient une propriété de window,
// ce qui permet à l'iframe de l'appeler avec window.parent.afficherCarteNdvi(...)
function afficherCarteNdvi(num, debut, fin) {
    retirerCarteNdvi();
    if (!parcelleSelectionnee) return;

    const url = "/api/ndvi/carte?" + new URLSearchParams({ num: num, debut: debut, fin: fin });
    const emprise = parcelleSelectionnee.getBounds();

    // L'image (calculée par GEE) est posée exactement sur l'emprise de la parcelle
    carteNdvi = L.imageOverlay(url, emprise, {
        opacity: 0.9,
        interactive: false,
        className: "carte-ndvi"   // pixels nets, sans lissage (voir style.css)
    }).addTo(map);
    carteNdvi.on("error", function () {
        alert("La carte NDVI n'a pas pu être produite pour cette période.");
        retirerCarteNdvi();
    });

    controleLegendeNdvi.addTo(map);
    map.fitBounds(emprise, { maxZoom: 18 });   // zoomer sur la parcelle
}

function retirerCarteNdvi() {
    if (carteNdvi) {
        map.removeLayer(carteNdvi);
        carteNdvi = null;
    }
    controleLegendeNdvi.remove();   // sans effet si la légende n'est pas affichée
}