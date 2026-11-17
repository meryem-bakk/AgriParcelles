/*
 * map.js — F1 : carte plein écran, fonds Terrain et Satellite,
 * échelle graphique, coordonnées du curseur.
 * F3 : navigation, boutons « Vue Maroc » et « Vue région ».
 * F4 : positionnement par coordonnées WGS84.
 * Chargé en premier : les autres scripts utilisent les variables définies ici.
 */

// Vue initiale : Maroc (centre ≈ 31,8° N ; 7,1° O), zoom 6.
// Attention : Leaflet attend [latitude, longitude].
const CENTRE_MAROC = [31.8, -7.1];
const ZOOM_MAROC = 6;

// ---------- Fonds de carte (tuiles XYZ, sans clé API) ----------

// Terrain : OpenTopoMap (relief et toponymie), tuiles disponibles jusqu'au zoom 17
const fondTerrain = L.tileLayer("https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png", {
    subdomains: "abc",
    maxZoom: 17,
    attribution: 'Données : &copy; <a href="https://www.openstreetmap.org/copyright">contributeurs OpenStreetMap</a>, SRTM | Style : &copy; <a href="https://opentopomap.org">OpenTopoMap</a> (CC-BY-SA)'
});

// Terrain (variante) : Esri World Topo Map, sans clé API. Ordre {z}/{y}/{x}.
// Le guide indique un fond Terrain ESRI en section 3, mais OpenTopoMap en F1 :
// les deux sont proposés dans le contrôle de couches.
const fondTerrainEsri = L.tileLayer(
    "https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}", {
    maxZoom: 19,
    attribution: "Tuiles &copy; Esri — Source : Esri et la communauté des utilisateurs SIG"
});

// Satellite : Esri World Imagery.
// Attention : les services ArcGIS utilisent l'ordre {z}/{y}/{x}, et non {z}/{x}/{y}.
const fondSatellite = L.tileLayer(
    "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", {
    maxZoom: 19,
    maxNativeZoom: 18,   // au-delà du zoom 18, les tuiles du zoom 18 sont agrandies
    attribution: "Tuiles &copy; Esri — Source : Esri, Maxar, Earthstar Geographics et la communauté des utilisateurs SIG"
});

// ---------- Carte ----------
const map = L.map("map", {
    center: CENTRE_MAROC,
    zoom: ZOOM_MAROC,
    layers: [fondTerrain],   // fond affiché au démarrage

    // F3 : navigation. Ces options sont actives par défaut dans Leaflet ;
    // elles sont écrites ici pour montrer explicitement ce qui les contrôle.
    zoomControl: true,       // boutons + et −
    scrollWheelZoom: true,   // zoom avec la molette
    dragging: true           // déplacement en glissant la carte
});

// ---------- Contrôle de couches ----------
// Les fonds sont des "baseLayers" : un seul visible à la fois (boutons radio).
// La couche parcelles y sera ajoutée en F2 comme "overlay" (case à cocher).
const controleCouches = L.control.layers(
    { "Terrain (OpenTopoMap)": fondTerrain, "Terrain (Esri)": fondTerrainEsri, "Satellite": fondSatellite },
    {},
    { collapsed: false }   // contrôle toujours ouvert
).addTo(map);

// ---------- Échelle graphique (mètres / kilomètres) ----------
L.control.scale({ imperial: false }).addTo(map);

// ---------- Coordonnées du curseur ----------
let divCoords;   // élément HTML qui affiche les coordonnées

const controleCoords = L.control({ position: "bottomleft" });
controleCoords.onAdd = function () {
    // Leaflet appelle cette fonction pour créer l'élément HTML du contrôle
    divCoords = L.DomUtil.create("div", "coords-control");
    divCoords.innerHTML = "Lat : — | Lon : —";
    return divCoords;
};
controleCoords.addTo(map);

// À chaque mouvement de la souris sur la carte : afficher lat/lon à 5 décimales
map.on("mousemove", function (e) {
    const p = e.latlng.wrap();   // ramène la longitude entre -180 et 180
    divCoords.innerHTML = "Lat : " + p.lat.toFixed(5) + " | Lon : " + p.lng.toFixed(5);
});

// Quand la souris quitte la carte : effacer l'affichage
map.on("mouseout", function () {
    divCoords.innerHTML = "Lat : — | Lon : —";
});

// ---------- F3 : bouton « Vue Maroc » ----------
const controleVueMaroc = L.control({ position: "topleft" });   // sous les boutons + / −

controleVueMaroc.onAdd = function () {
    const bouton = L.DomUtil.create("button", "bouton-carte");
    bouton.type = "button";
    bouton.textContent = "Vue Maroc";
    bouton.title = "Revenir à la vue initiale";

    // Un clic sur le bouton ne doit pas être transmis à la carte
    // (sinon un double-clic sur le bouton zoomerait la carte)
    L.DomEvent.disableClickPropagation(bouton);

    // Au clic : revenir au centre et au zoom de départ, définis en haut du fichier
    L.DomEvent.on(bouton, "click", function () {
        map.setView(CENTRE_MAROC, ZOOM_MAROC);
    });

    return bouton;
};

controleVueMaroc.addTo(map);

// ---------- Bouton « Vue région » : Basse Moulouya (zone Z8 du groupe 5) ----------
// Emprise APPROXIMATIVE de la région agricole de la Basse Moulouya
// (plaines des Triffa, de Zebra, de Bou Areg et de Garet), en degrés WGS84.
// Rectangle à ajuster si le professeur précise d'autres limites.
const EMPRISE_REGION = L.latLngBounds(
    [34.75, -3.10],   // coin sud-ouest [latitude, longitude]
    [35.18, -2.18]    // coin nord-est
);

// Contour de la région, affichable depuis le contrôle de couches
const coucheRegion = L.rectangle(EMPRISE_REGION, {
    color: "#ff4081",
    weight: 2,
    dashArray: "6 6",       // pointillés
    fill: false,
    interactive: false      // ne bloque pas les clics sur les parcelles (F2, F6)
});
controleCouches.addOverlay(coucheRegion, "Région Basse Moulouya");

// Rayon de 10 km autour du point de départ de la zone Z8 (annexe A du guide) :
// les 15 parcelles du projet doivent se trouver dans ce cercle
const coucheRayon10km = L.circle([34.92, -2.32], {
    radius: 10000,          // en mètres
    color: "#00bcd4",
    weight: 2,
    dashArray: "4 4",
    fill: false,
    interactive: false
});
controleCouches.addOverlay(coucheRayon10km, "Zone Z8 : rayon de 10 km");

// Le bouton, placé sous « Vue Maroc »
const controleVueRegion = L.control({ position: "topleft" });
controleVueRegion.onAdd = function () {
    const bouton = L.DomUtil.create("button", "bouton-carte");
    bouton.type = "button";
    bouton.textContent = "Vue région";
    bouton.title = "Basse Moulouya (Berkane, Nador, Saïdia)";

    L.DomEvent.disableClickPropagation(bouton);
    L.DomEvent.on(bouton, "click", function () {
        map.fitBounds(EMPRISE_REGION);   // cadrer toute la région à l'écran
        coucheRegion.addTo(map);         // et afficher son contour
    });
    return bouton;
};
controleVueRegion.addTo(map);

// ---------- F4 : positionnement par coordonnées WGS84 ----------

// Emprise du Maroc imposée par le guide (degrés décimaux, EPSG:4326)
const LIMITES = { xMin: -17.5, xMax: -0.9, yMin: 20.5, yMax: 36.1 };
const ZOOM_ALLER = 17;

let marqueurPosition = null;   // marqueur du dernier point (un seul à la fois)

// Panneau de saisie, placé sous le contrôle de couches
const controlePosition = L.control({ position: "topright" });
controlePosition.onAdd = function () {
    const div = L.DomUtil.create("div", "panneau-carte");
    div.innerHTML =
        '<form id="form-position" novalidate>' +
        '  <div class="panneau-titre">Aller à des coordonnées (WGS84)</div>' +
        '  <label>Longitude (X)' +
        '    <input type="text" id="saisie-x" placeholder="ex. -5.93" inputmode="decimal">' +
        '  </label>' +
        '  <label>Latitude (Y)' +
        '    <input type="text" id="saisie-y" placeholder="ex. 34.26" inputmode="decimal">' +
        '  </label>' +
        '  <button type="submit" class="bouton-carte">Aller</button>' +
        '  <div id="erreur-position" class="message-erreur"></div>' +
        '</form>';

    // Clics et molette dans le panneau ne doivent pas agir sur la carte
    L.DomEvent.disableClickPropagation(div);
    L.DomEvent.disableScrollPropagation(div);
    return div;
};
controlePosition.addTo(map);

// Convertit le texte saisi en nombre. Tolère les saisies copiées-collées :
// espaces et caractères invisibles retirés, virgule acceptée (-5,93),
// signe moins typographique « − » accepté comme le tiret « - ».
// Renvoie NaN ("Not a Number") si le texte n'est pas un nombre.
// Utilisée aussi par le formulaire de F5 (production).
function lireNombre(texte) {
    const t = texte
        .replace(/[\s​-‍⁠﻿]/g, "")   // espaces et caractères invisibles
        .replace(",", ".")
        .replace("−", "-");                         // signe moins typographique -> tiret
    if (t === "") return NaN;
    return Number(t);
}

// Vérifie les coordonnées. Renvoie un message d'erreur, ou "" si tout est valide.
function verifierCoordonnees(x, y) {
    if (Number.isNaN(x) || Number.isNaN(y)) {
        return "Saisissez des valeurs numériques (ex. X = -5.93 ; Y = 34.26).";
    }
    // Erreur fréquente : X et Y inversés (le guide le rappelle : X = longitude)
    const xDansPlageY = x >= LIMITES.yMin && x <= LIMITES.yMax;
    const yDansPlageX = y >= LIMITES.xMin && y <= LIMITES.xMax;
    if (xDansPlageY && yDansPlageX) {
        return "X et Y semblent inversés : X est la longitude (négative au Maroc), Y la latitude.";
    }
    if (x < LIMITES.xMin || x > LIMITES.xMax) {
        return "Longitude (X) hors du Maroc : elle doit être comprise entre -17,5 et -0,9.";
    }
    if (y < LIMITES.yMin || y > LIMITES.yMax) {
        return "Latitude (Y) hors du Maroc : elle doit être comprise entre 20,5 et 36,1.";
    }
    return "";
}

// Clic sur « Aller » (ou touche Entrée dans un champ)
document.getElementById("form-position").addEventListener("submit", function (e) {
    e.preventDefault();   // un formulaire recharge la page par défaut : on l'en empêche

    const x = lireNombre(document.getElementById("saisie-x").value);
    const y = lireNombre(document.getElementById("saisie-y").value);
    const zoneErreur = document.getElementById("erreur-position");

    // 1. Contrôle de saisie
    const erreur = verifierCoordonnees(x, y);
    zoneErreur.textContent = erreur;
    if (erreur) return;   // on s'arrête là si la saisie est invalide

    // Leaflet attend [latitude, longitude], c'est-à-dire [Y, X]
    const point = [y, x];

    // 2. Basculer sur le fond Satellite, en retirant le fond Terrain affiché (l'un ou l'autre)
    fondSatellite.addTo(map);
    [fondTerrain, fondTerrainEsri].forEach(function (fond) {
        if (map.hasLayer(fond)) {
            map.removeLayer(fond);
        }
    });

    // 3. Centrer la carte sur le point, au zoom 17
    map.setView(point, ZOOM_ALLER);

    // 4. Placer un marqueur, en remplaçant le précédent
    if (marqueurPosition) {
        map.removeLayer(marqueurPosition);
    }
    marqueurPosition = L.marker(point)
        .bindPopup("X = " + x.toFixed(5) + " ; Y = " + y.toFixed(5))
        .addTo(map);
});