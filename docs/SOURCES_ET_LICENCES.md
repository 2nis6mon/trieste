# Sources et licences

## Modèles 3D

Tous les modèles (architecture, menuiseries, mobilier, textiles, plantes,
cour) sont **créés pour ce projet** par les scripts de `pipeline/blender/` :
aucun modèle tiers n'est utilisé. Les textiles (couette, oreillers, coussins)
sont obtenus par simulation de tissu dans Blender.

Les noms IKEA (MANDAL, NORDKISA, PAX, FORSAND, NÅLBJÖRNBÄR, ASPUDDEN, BILLSBRO,
EKBACKEN, NISSAFORS, METOD) servent de références d'aspect et de dimensions ;
les objets sont des reconstitutions, pas des fichiers IKEA.

## Textures

Toutes les textures de `web/public/textures/` sont **générées par
`pipeline/textures/gen_textures.py`** (bruit spectral, dessin vectoriel) :
parquet, enduit, bouleau, chêne, bambou, lin, motif floral, tissus, tapis
tricotés, éponge, cannage, carrelage, dallage, stratifié terracotta, métal
brossé, façades de la cour (jour et nuit), affiches, feuillages, grès. Elles
relèvent de la même licence que le projet. Aucune banque d'images n'a été
utilisée (inaccessibles depuis l'environnement de production).

## Éclairage

Lightmaps de `web/public/lightmaps/` : calculées par Blender Cycles à partir
de la scène (ciel physique « multiple scattering », position du soleil de
Trieste calculée par les formules NOAA), débruitées par OpenImageDenoise.

## Logiciels

| Logiciel | Licence | Usage |
|---|---|---|
| three.js 0.186 | MIT | rendu web (embarqué) |
| Vite 7 | MIT | construction du site (développement) |
| Blender 5.0 (`bpy`) | GPL-3.0 | modélisation, simulation, précalcul (outil, non distribué) |
| numpy, Pillow, SciPy, Shapely, OpenCV, mapbox-earcut | BSD / MIT-CMU / Apache-2.0 | outils de génération |
| Playwright | Apache-2.0 | captures et tests automatisés |

## Documents du propriétaire

- `references/plan-sans-mobilier.jpg`, `references/plan-cote.png` : plans
  fournis (export Floorplanner).
- `web/public/references/` : rendus d'ambiance et captures de la vidéo de
  chantier fournis par le propriétaire (sans personne visible).
- Le plan cadastral (PDF) n'a servi qu'à lire l'orientation (rose des vents) :
  il contient des données personnelles et **n'est pas inclus** dans le dépôt,
  pas plus que la vidéo ni l'adresse.
