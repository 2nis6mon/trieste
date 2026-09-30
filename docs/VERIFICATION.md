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

## Géométrie

- Étanchéité des murs : lancer de rayons tous les 10 cm sur le pourtour de
  chaque pièce, à 0,3 / 1,2 / 2,0 / 2,62 m : **0 trou**.
- Implantation de la chambre contrôlée en 2D (`docs/implantation-chambre.png`) :
  meubles dans la pièce, débattements de la porte et des portes du placard libres.

## Limites connues

- Les captures sont produites en rendu logiciel ; sur une vraie carte
  graphique le rendu est identique mais fluide.
- Pas de test sur un iPhone réel (émulation Chromium uniquement).
- Bruit résiduel de précalcul (marbrures légères) sur les grandes surfaces
  blanches (façades du placard, tableaux des fenêtres), réduit par les
  portails de lumière mais encore visible de près.
- La salle de bain (pièce aveugle) reste assez sombre en mode jour.
