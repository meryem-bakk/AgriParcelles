/*
 * mapserver.js — Bonus : couche WMS servie par MapServer (MS4W).
 * Couleur par culture, étiquettes et légende sont calculées côté serveur.
 * Utilise map et controleCouches (map.js).
 */

// AGRIPARCELLES est un alias défini dans C:\ms4w\ms4w.conf :
// le chemin du fichier .map n'apparaît pas dans l'adresse.
const URL_WMS = "http://localhost:8080/cgi-bin/mapserv.exe?map=AGRIPARCELLES";

// Leaflet demande à MapServer des images de 256 × 256 pixels (protocole WMS)
const coucheWms = L.tileLayer.wms(URL_WMS, {
    layers: "parcelles,etiquettes",
    format: "image/png",
    transparent: true,       // fond transparent : on voit le fond de carte
    version: "1.3.0",
    maxZoom: 19,
    attribution: "Parcelles par culture : MapServer (WMS)"
});
controleCouches.addOverlay(coucheWms, "Parcelles par culture (MapServer)");

// Légende produite par MapServer (requête GetLegendGraphic)
const URL_LEGENDE = URL_WMS +
    "&SERVICE=WMS&VERSION=1.3.0&REQUEST=GetLegendGraphic" +
    "&LAYER=parcelles&FORMAT=image/png&SLD_VERSION=1.1.0";

const controleLegende = L.control({ position: "bottomright" });
controleLegende.onAdd = function () {
    const div = L.DomUtil.create("div", "legende-wms");
    div.innerHTML = '<div class="panneau-titre">Cultures</div>' +
                    '<img src="' + URL_LEGENDE + '" alt="Légende des cultures">';
    return div;
};

// La légende n'est affichée que lorsque la couche WMS est cochée
map.on("overlayadd", function (e) {
    if (e.layer === coucheWms) controleLegende.addTo(map);
});
map.on("overlayremove", function (e) {
    if (e.layer === coucheWms) controleLegende.remove();
});