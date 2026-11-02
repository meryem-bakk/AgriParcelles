-- tables techniques de SpatiaLite (une seule fois, base vide)
SELECT InitSpatialMetadata(1);
CREATE TABLE parcelles (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 num_parcelle TEXT NOT NULL UNIQUE,
 agriculteur TEXT NOT NULL,
 culture TEXT NOT NULL,
 superficie_ha REAL, -- calculée par le serveur
 production_t REAL CHECK (production_t >= 0),
 date_saisie TEXT DEFAULT CURRENT_TIMESTAMP
);
-- colonne géométrique : polygones en WGS84 (EPSG:4326), obligatoire
SELECT AddGeometryColumn('parcelles', 'geom', 4326, 'POLYGON', 'XY', 1);
SELECT CreateSpatialIndex('parcelles', 'geom');