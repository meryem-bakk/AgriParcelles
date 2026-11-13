/*
 * ndvi.js — F6 (interface) : mode sélection, surbrillance de la parcelle choisie,
 * fenêtre flottante déplaçable contenant l'iframe /ndvi?num=<numéro>.
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