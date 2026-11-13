/*
 * parcelles.js — F2 : affichage de la couche parcelles depuis l'API.
 * Utilise map et controleCouches, définis dans map.js.
 */

// Style lisible sur le fond satellite : contour jaune, remplissage semi-transparent
const STYLE_PARCELLE = {
    color: "#ffff00",       // contour jaune
    weight: 2,
    fillColor: "#ffff00",
    fillOpacity: 0.2        // 20 % : on voit l'image satellite à travers
};

// Protège l'affichage : un texte saisi (ex. nom d'agriculteur) est affiché
// tel quel, jamais interprété comme du HTML
function echapper(texte) {
    const div = document.createElement("div");
    div.textContent = texte;
    return div.innerHTML;
}

// Construit le contenu de la popup avec tous les attributs de la parcelle
function contenuPopup(p) {
    return "<b>Parcelle " + echapper(p.num_parcelle) + "</b><br>" +
        "Identifiant : " + p.id + "<br>" +
        "Agriculteur : " + echapper(p.agriculteur) + "<br>" +
        "Culture : " + echapper(p.culture) + "<br>" +
        "Superficie : " + p.superficie_ha.toFixed(2) + " ha<br>" +
        "Production : " + p.production_t + " t<br>" +
        "Date de saisie : " + p.date_saisie;
}

// Couche GeoJSON, vide au départ, remplie par chargerParcelles()
const coucheParcelles = L.geoJSON(null, {
    style: STYLE_PARCELLE,
    onEachFeature: function (feature, layer) {
        // Appelée pour chaque parcelle : on lui attache sa popup
        layer.bindPopup(contenuPopup(feature.properties));
    }
}).addTo(map);

// Case à cocher dans le contrôle de couches pour masquer/afficher la couche
controleCouches.addOverlay(coucheParcelles, "Parcelles");

// Demande les parcelles à l'API et les affiche
async function chargerParcelles() {
    try {
        const reponse = await fetch("/api/parcelles");
        if (!reponse.ok) {
            throw new Error("erreur serveur " + reponse.status);
        }
        const geojson = await reponse.json();
        coucheParcelles.clearLayers();   // vider avant de recharger (utile en F5)
        coucheParcelles.addData(geojson);
    } catch (erreur) {
        console.error(erreur);
        alert("Impossible de charger les parcelles : " + erreur.message);
    }
}

chargerParcelles();

// =====================================================================
// F5 : digitalisation et enregistrement d'une parcelle
// =====================================================================

map.pm.setLang("fr");   // bulles d'aide de Geoman en français

let dessinEnCours = null;   // polygone terminé mais pas encore enregistré

// Éléments du formulaire (définis dans index.html)
const panneauParcelle = document.getElementById("panneau-parcelle");
const formParcelle = document.getElementById("form-parcelle");
const messageParcelle = document.getElementById("message-parcelle");
const champSuperficie = document.getElementById("champ-superficie");
const boutonEnregistrer = document.getElementById("bouton-enregistrer");

// ---------- Boutons « Nouvelle parcelle » et « Annuler » sur la carte ----------
const controleDessin = L.control({ position: "topleft" });
controleDessin.onAdd = function () {
    const div = L.DomUtil.create("div", "groupe-boutons");

    const boutonNouvelle = L.DomUtil.create("button", "bouton-carte", div);
    boutonNouvelle.type = "button";
    boutonNouvelle.textContent = "Nouvelle parcelle";

    const boutonAnnuler = L.DomUtil.create("button", "bouton-carte", div);
    boutonAnnuler.type = "button";
    boutonAnnuler.textContent = "Annuler";

    // Un clic sur ces boutons ne doit pas être pris pour un sommet du polygone
    L.DomEvent.disableClickPropagation(div);

    L.DomEvent.on(boutonNouvelle, "click", commencerDessin);
    L.DomEvent.on(boutonAnnuler, "click", annulerDessin);
    return div;
};
controleDessin.addTo(map);

// Le bouton « Annuler » du formulaire fait la même chose
document.getElementById("bouton-annuler-form").addEventListener("click", annulerDessin);

// ---------- 1. « Nouvelle parcelle » : activer l'outil de dessin ----------
function commencerDessin() {
    annulerDessin();   // repartir de zéro si un dessin était en cours
    map.pm.enableDraw("Polygon", {
        allowSelfIntersection: false   // refuse un contour qui se croise lui-même
    });
}

// ---------- 2. Fin du dessin : ouvrir le formulaire ----------
// Geoman déclenche "pm:create" quand on referme le polygone (clic sur le 1er sommet)
map.on("pm:create", function (e) {
    dessinEnCours = e.layer;
    ouvrirFormulaire();
});

async function ouvrirFormulaire() {
    formParcelle.reset();
    messageParcelle.textContent = "";
    panneauParcelle.hidden = false;
    document.getElementById("champ-num").focus();

    // Superficie : calculée par le serveur (SpatiaLite) à partir de la géométrie
    champSuperficie.value = "calcul…";
    try {
        const reponse = await fetch("/api/superficie", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ geometrie: dessinEnCours.toGeoJSON().geometry })
        });
        const resultat = await reponse.json();
        if (!reponse.ok) {
            throw new Error(resultat.erreur);
        }
        champSuperficie.value = resultat.superficie_ha.toFixed(2);
    } catch (erreur) {
        champSuperficie.value = "";
        messageParcelle.textContent = erreur.message;
    }
}

// ---------- 3. « Annuler » : effacer le dessin et fermer le formulaire ----------
function annulerDessin() {
    map.pm.disableDraw();               // interrompt un dessin non terminé
    if (dessinEnCours) {
        map.removeLayer(dessinEnCours); // efface un polygone terminé non enregistré
        dessinEnCours = null;
    }
    panneauParcelle.hidden = true;
}

// ---------- 4. « Enregistrer » : envoyer la parcelle au serveur ----------
formParcelle.addEventListener("submit", async function (e) {
    e.preventDefault();   // pas de rechargement de la page

    // Contrôles dans le navigateur (le serveur refait les siens)
    const num = document.getElementById("champ-num").value.trim();
    const agriculteur = document.getElementById("champ-agriculteur").value.trim();
    const culture = document.getElementById("champ-culture").value;
    const production = lireNombre(document.getElementById("champ-production").value);   // fonction de map.js (F4)

    let erreur = "";
    if (!num) {
        erreur = "Le numéro de parcelle est obligatoire.";
    } else if (!agriculteur) {
        erreur = "Le nom de l'agriculteur est obligatoire.";
    } else if (!culture) {
        erreur = "Choisissez une culture.";
    } else if (Number.isNaN(production) || production < 0) {
        erreur = "La production doit être un nombre positif ou nul (en tonnes).";
    }
    messageParcelle.textContent = erreur;
    if (erreur) return;

    boutonEnregistrer.disabled = true;   // évite un double envoi pendant la requête
    try {
        const reponse = await fetch("/api/parcelles", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                num_parcelle: num,
                agriculteur: agriculteur,
                culture: culture,
                production_t: production,
                geometrie: dessinEnCours.toGeoJSON().geometry
            })
        });
        const resultat = await reponse.json();

        if (!reponse.ok) {
            // 409 (numéro déjà utilisé), 400 ou 422 : on affiche le message du serveur.
            // Le dessin et la saisie restent en place pour corriger.
            messageParcelle.textContent = resultat.erreur;
            return;
        }

        // 201 : le serveur renvoie la parcelle créée (une Feature GeoJSON)
        map.removeLayer(dessinEnCours);      // retirer le dessin provisoire (bleu)
        dessinEnCours = null;
        panneauParcelle.hidden = true;
        coucheParcelles.addData(resultat);   // la parcelle apparaît aussitôt, en jaune
        // Bonus MapServer : redemander les images WMS pour y voir la nouvelle parcelle
        if (typeof coucheWms !== "undefined") {
            coucheWms.setParams({ maj: Date.now() });
        }
    } catch (err) {
        messageParcelle.textContent = "Erreur de communication avec le serveur : " + err.message;
    } finally {
        boutonEnregistrer.disabled = false;  // exécuté dans tous les cas
    }
});