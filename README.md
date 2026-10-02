# Trieste — visite 3D de l'appartement

Visite libre, dans le navigateur (ordinateur et téléphone), de l'appartement du
5ᵉ étage à Trieste : vraie scène 3D modélisée (murs, menuiseries, mobilier),
matériaux physiques et **éclairage mixte**, à la manière d'Unreal Engine :
- murs, sols et plafonds : éclairage **précalculé** par tracé de chemins
  (Blender Cycles), calculé sans les meubles déplaçables ;
- meubles : éclairage **en temps réel** dans le navigateur (soleil calculé pour
  Trieste avec ombres, lampes avec ombres dans la pièce où l'on se trouve,
  lumière ambiante captée dans chaque pièce, ombres de contact).
Les meubles peuvent donc être déplacés sans recalcul. Aucun serveur de
calcul : le site est entièrement statique.

- Modes d'éclairage : **Jour** (21 juin, 13 h 30), **Fin de journée** (21 juin,
  19 h 36), **Nuit** (lampes d'appoint, chevets et éclairages intégrés
  allumés ; option *Plafonniers*).
- **Visite** à 1,60 m (murs et plafonds complets) et **vue d'ensemble** en
  coupe (murs coupés à 1,25 m).
- Commandes : glisser pour regarder ; ← / → tourner sur place ; ↑ / ↓
  avancer / reculer ; boutons tactiles équivalents ; collisions avec murs,
  fenêtres et meubles ; accès direct à chaque pièce ; mini-plan cliquable ;
  bouton *Recentrer* ; photos de référence superposables.
- **Aménager** (dans la vue d'ensemble) : cliquer un meuble, le faire glisser,
  le tourner (boutons ou touches Q / E). L'implantation est gardée dans le
  navigateur ; *Copier l'implantation* donne un JSON à coller dans
  `web/public/data/implantation.json` pour la rendre définitive pour tous.
  Liste des meubles déplaçables : `web/public/data/meubles.json`.

## Arborescence

| Dossier | Contenu |
|---|---|
| `web/` | Site (Vite + three.js). `web/public/` contient la maquette `models/appartement.glb`, les lightmaps `lightmaps/<mode>/*.webp`, les textures, le plan vectorisé `data/plan.json`, les emprises des meubles `data/obstacles.json` et les photos de référence. |
| `pipeline/plan/` | Vectorisation du plan sans mobilier → `plan.json` (échelle 74,4 px/m). |
| `pipeline/textures/` | Génération procédurale de toutes les textures (numpy). |
| `pipeline/layout.py` | Implantation du mobilier (repères muraux) + contrôle 2D. |
| `pipeline/blender/` | Construction de la scène (architecture, mobilier, tissus simulés), éclairage, précalcul, export glTF. |
| `references/` | Plans source (sans mobilier, coté). |
| `docs/` | Dimensions et hypothèses, sources et licences, vérifications, captures. |

## Lancer le site

```bash
cd web
npm install
npm run dev          # http://localhost:5173 (et adresse réseau pour tester sur téléphone)
npm run build        # site statique dans web/dist
npm run preview      # sert web/dist
```

Paramètres d'URL utiles : `?piece=chambre|sejour|cuisine|sdb|sas|entree`,
`&mode=jour|soir|nuit`, `&plafonniers=1`, `&vue=coupe`.

## Publier

Le site est statique (≈ 40 Mo) : n'importe quel hébergement de fichiers
convient (GitHub Pages, Netlify, OVH…), sans coût de calcul.

- **GitHub Pages** : le workflow `.github/workflows/pages.yml` construit et
  publie `web/dist` à chaque push sur `main`. Activer *Settings → Pages →
  Source : GitHub Actions*. Attention : sur un compte gratuit, Pages exige un
  dépôt public (les photos de référence et le plan deviennent alors publics).
- **Netlify / autre** : répertoire de build `web`, commande `npm run build`,
  dossier publié `web/dist`.

## Régénérer la maquette (optionnel)

Nécessite Python 3.11 et le module Blender (`pip install bpy==5.0.1 numpy pillow
scipy shapely mapbox-earcut opencv-python-headless`), ou Blender 5.0 installé.

```bash
python pipeline/plan/extract_plan.py            # plan -> plan.json
python pipeline/textures/gen_textures.py        # textures
cd pipeline/blender
python build.py scene                           # scène -> pipeline/cache/appartement.blend
SPP=160 python build.py bake jour soir nuit nuit+plafonniers   # ~2 h sur 4 cœurs CPU
SPP=384 python build.py bake-archi              # architecture seule, sans les meubles déplaçables
python percer_evier.py                          # perce le plan de travail + export GLB
python separer_tableaux.py                      # tableaux et niches en temps réel + export
python meubles_v2.py                            # mobilier v2 (PAX TONSTAD, Artemide, enfilade…) + export
python build.py export                          # -> web/public/models/appartement.glb
python build.py preview jour chambre_lit        # rendus Cycles de contrôle
```

Avec une carte graphique (Blender installé localement), le précalcul prend
quelques minutes : dans `build.py`, passer `scene.cycles.device = 'GPU'`.

Le fichier `pipeline/cache/appartement.blend` s'ouvre dans Blender 5.0 pour
modifier la scène à la main.

## Documentation

- [Dimensions, hypothèses et contradictions relevées](docs/DIMENSIONS.md)
- [Sources et licences](docs/SOURCES_ET_LICENCES.md)
- [Vérifications (ordinateur, mobile, collisions)](docs/VERIFICATION.md)
- Captures : `docs/captures/`
