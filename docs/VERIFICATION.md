# Vérifications

Tests automatisés : `web/scripts/verifier.mjs` (Chromium sans écran, rendu
logiciel SwiftShader). Résultat brut : `docs/verification.json`.
**25 / 25 vérifications réussies** sur la maquette finale.

La logique de déplacement est testée par simulation déterministe
(`window.__visite.simulate(secondes)`), indépendamment de la cadence
d'affichage, très lente en rendu logiciel.

## Ordinateur (1280 × 800)

| Vérification | Résultat |
|---|---|
| ← : rotation sur place vers la gauche | OK (1,00 rad en 0,7 s, déplacement nul) |
| → : rotation sur place vers la droite | OK |
| ↑ : avance dans la direction du regard | OK (0,95 m en 0,8 s) |
| ↓ : recule | OK |
| Collision façade / fenêtres (6 s contre la façade) | OK, reste dans la chambre |
| Collision meuble (5 s contre le lit) | OK, hors de l'emprise du lit |
| Passage des portes (chambre → dégagement) | OK |
| Glisser à la souris pour regarder | OK |
| Recentrer (regard à l'horizontale) | OK |
| Accès direct : séjour, cuisine, salle de bain, chambre, dégagement | OK |
| Vue d'ensemble en coupe | OK |
| Modes jour / fin de journée / nuit | OK |
| Aucune erreur JavaScript | OK |

## Téléphone (Pixel 7 émulé, écran tactile)

| Vérification | Résultat |
|---|---|
| Boutons tactiles affichés | OK |
| ▲ avance (maintenu 0,9 s) | OK (1,11 m) |
| ↺ tourne à gauche sur place | OK |
| Glisser au doigt pour regarder | OK |
| Pas de défilement horizontal | OK |
| Aucune erreur JavaScript | OK |

## Mode « Aménager » (`web/scripts/test_amenager.mjs`)

| Vérification | Résultat |
|---|---|
| Clic sur un meuble dans la vue d'ensemble : sélection | OK (« Lit MANDAL 160×200 ») |
| Glisser à la souris : déplacement | OK (0,71 m / 0,73 m) |
| Bouton ↺ 90° : rotation | OK (π/2) |
| Implantation mémorisée et copiable (JSON) | OK |

## Géométrie

- Étanchéité des murs : lancer de rayons tous les 10 cm sur le pourtour de
  chaque pièce, à 0,3 / 1,2 / 2,0 / 2,62 m : **0 trou**.
- Implantation de la chambre contrôlée en 2D (`docs/implantation-chambre.png`) :
  meubles dans la pièce, débattements de la porte et des portes du placard libres.

## Limites connues

- Les captures sont produites en rendu logiciel ; sur une vraie carte
  graphique le rendu est identique mais fluide.
- Pas de test sur un iPhone réel (émulation Chromium uniquement).
- Meubles, murs, tableaux et niches sont éclairés en temps réel (unis, sans
  marbrures) ; seuls sols, plafonds, faïence et extérieur gardent le
  précalcul. Les murs perdent donc les dégradés de lumière indirecte fine.
- Les lampes qu'on déplace gardent leur halo précalculé au sol et au plafond
  à l'ancienne place (leur lumière directe, elle, suit la lampe).
- En rendu logiciel (tests), les ombres des lampes de nuit ralentissent
  fortement l'affichage ; sur une vraie carte graphique c'est fluide.
- La salle de bain (pièce aveugle) reste assez sombre en mode jour.
