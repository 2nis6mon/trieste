import * as THREE from 'three';
import { EffectComposer } from 'three/examples/jsm/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/examples/jsm/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/examples/jsm/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/examples/jsm/postprocessing/OutputPass.js';
import { ShaderPass } from 'three/examples/jsm/postprocessing/ShaderPass.js';
import { Apartment, MODES, ROOMS } from './scene.js';
import { Navigation } from './navigation.js';
import { Minimap } from './minimap.js';

const REFERENCES = [
  { f: 'rendu-chambre', t: 'Chambre — rendu d’ambiance', v: 'chambre', pos: [3.0, 6.1], look: [6.6, 4.0] },
  { f: 'chantier-chambre', t: 'Chambre — capture du chantier', v: 'chambre', pos: [4.4, 4.2], look: [7.2, 5.6] },
  { f: 'rendu-sejour-fenetre', t: 'Séjour vers la fenêtre — rendu', v: 'sejour', pos: [3.0, 9.6], look: [7.9, 9.4] },
  { f: 'chantier-sejour', t: 'Séjour — capture du chantier', v: 'sejour', pos: [3.4, 9.7], look: [7.9, 9.4] },
  { f: 'rendu-sejour', t: 'Séjour vers l’entrée — rendu (à corriger)', v: 'sejour', pos: [6.8, 10.3], look: [1.0, 9.0] },
  { f: 'rendu-cuisine', t: 'Cuisine — rendu (implantation IKEA)', v: 'cuisine', pos: [4.1, 7.95], look: [4.6, 6.6] },
  { f: 'chantier-cuisine', t: 'Cuisine — capture du chantier', v: 'cuisine', pos: [3.0, 7.4], look: [6.6, 7.2] },
  { f: 'rendu-salle-de-bain', t: 'Salle de bain — rendu', v: 'sdb', pos: [2.72, 4.45], look: [4.4, 2.2] },
  { f: 'chantier-salle-de-bain', t: 'Salle de bain — capture', v: 'sdb', pos: [2.72, 4.45], look: [4.4, 2.2] },
  { f: 'rendu-buanderie', t: 'Buanderie — rendu', v: 'sas', pos: [2.2, 6.0], look: [1.1, 5.1] },
  { f: 'chantier-buanderie', t: 'Buanderie — raccordements réels', v: 'sas', pos: [2.2, 6.0], look: [1.1, 5.1] },
  { f: 'chantier-porte-terrasse', t: 'Porte de la terrasse — capture', v: 'sejour', pos: [7.1, 8.6], look: [7.1, 7.4] },
  { f: 'chantier-entree', t: 'Porte d’entrée — capture', v: 'sejour', pos: [2.2, 8.4], look: [1.7, 10.3] },
  { f: 'plan-sans-mobilier', t: 'Plan sans mobilier (géométrie)', v: null },
  { f: 'plan-cote', t: 'Plan coté (dimensions)', v: null },
];

const canvas = document.getElementById('vue');
const touch = matchMedia('(pointer: coarse)').matches;
if (touch) document.body.classList.add('tactile');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: 'high-performance', preserveDrawingBuffer: false });
renderer.setPixelRatio(Math.min(devicePixelRatio, touch ? 1.6 : 2));
renderer.toneMapping = THREE.AgXToneMapping;
renderer.outputColorSpace = THREE.SRGBColorSpace;

const camera = new THREE.PerspectiveCamera(50, 1, 0.05, 900);
const apt = new Apartment(renderer);
let nav, map, composer, bloom, grade;

function resize() {
  const w = innerWidth, h = innerHeight;
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  composer?.setSize(w, h);
}

async function start() {
  const bar = document.getElementById('progression');
  await apt.load((p) => (bar.style.width = `${Math.round(p * 100)}%`));
  nav = new Navigation(camera, canvas, apt);
  map = new Minimap(document.getElementById('miniplan'), apt, nav);
  composer = new EffectComposer(renderer, new THREE.WebGLRenderTarget(1, 1, { type: THREE.HalfFloatType, samples: 4 }));
  composer.addPass(new RenderPass(apt.scene, camera));
  bloom = new UnrealBloomPass(new THREE.Vector2(256, 256), 0.18, 0.4, 1.0);
  bloom.enabled = false;
  composer.addPass(bloom);
  // balance des blancs (espace linéaire, avant le mappage tonal)
  grade = new ShaderPass({
    uniforms: { tDiffuse: { value: null }, balance: { value: new THREE.Vector3(1, 1, 1) } },
    vertexShader: 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }',
    fragmentShader: 'uniform sampler2D tDiffuse; uniform vec3 balance; varying vec2 vUv; void main(){ vec4 c = texture2D(tDiffuse, vUv); gl_FragColor = vec4(c.rgb * balance, c.a); }',
  });
  composer.addPass(grade);
  composer.addPass(new OutputPass());
  resize();
  addEventListener('resize', resize);
  setupUI();
  const params = new URLSearchParams(location.search);
  const room = ROOMS[params.get('piece')] || ROOMS.chambre;
  nav.goTo(room.pos, room.look);
  if (params.get('mode')) await setMode(params.get('mode'), params.get('plafonniers') === '1');
  if (params.get('vue') === 'coupe') nav.setMode('coupe');
  const ch = document.getElementById('chargement');
  ch.style.opacity = 0;
  setTimeout(() => ch.remove(), 700);
  window.__visite = {
    apt, nav, camera, renderer, setMode, ready: true,
    // simulation déterministe (tests automatisés, indépendante de la cadence d'affichage)
    simulate: (seconds, step = 1 / 60) => { for (let t = 0; t < seconds; t += step) nav.update(step); },
    paused: false,
  };
  let last = performance.now();
  renderer.setAnimationLoop((t) => {
    const dt = Math.min(0.25, (t - last) / 1000);
    last = t;
    if (!window.__visite.paused) nav.update(dt);
    if (apt.balance) grade.uniforms.balance.value.set(...apt.balance);
    composer.render();
    map.draw();
    const r = nav.currentRoom();
    document.getElementById('piece-courante').textContent = nav.mode === 'coupe' ? 'Vue d’ensemble' : (ROOMS[r]?.name || '');
  });
}

async function setMode(mode, ceiling = false) {
  if (!MODES[mode]) return;
  document.querySelectorAll('[data-mode]').forEach((b) => b.classList.toggle('actif', b.dataset.mode === mode));
  const lab = document.getElementById('plafonniers');
  lab.hidden = mode !== 'nuit';
  lab.querySelector('input').checked = ceiling;
  await apt.setMode(mode, ceiling);
  if (bloom) bloom.enabled = mode === 'nuit';
}

function setupUI() {
  document.querySelectorAll('[data-mode]').forEach((b) => b.addEventListener('click', () => setMode(b.dataset.mode)));
  document.querySelector('#plafonniers input').addEventListener('change', (e) => setMode('nuit', e.target.checked));
  document.querySelectorAll('[data-vue]').forEach((b) => b.addEventListener('click', () => nav.setMode(b.dataset.vue)));
  nav.onMode = (m) => document.querySelectorAll('[data-vue]').forEach((b) => b.classList.toggle('actif', b.dataset.vue === m));
  const pieces = document.getElementById('pieces');
  for (const [id, r] of Object.entries(ROOMS)) {
    const b = document.createElement('button');
    b.textContent = r.name;
    b.addEventListener('click', () => nav.goTo(r.pos, r.look));
    pieces.appendChild(b);
  }
  document.getElementById('recentrer').addEventListener('click', () => nav.recenter());
  // boutons tactiles : maintenir appuyé
  const holdMap = { avant: ['fwd', 1], arriere: ['fwd', -1], gauche: ['turn', 1], droite: ['turn', -1] };
  document.querySelectorAll('#tactile [data-t]').forEach((b) => {
    const [k, v] = holdMap[b.dataset.t];
    const on = (e) => { e.preventDefault(); nav.hold[k] = v; try { b.setPointerCapture(e.pointerId); } catch (err) { /* pointeur synthétique */ } };
    const off = () => (nav.hold[k] = 0);
    b.addEventListener('pointerdown', on);
    b.addEventListener('pointerup', off);
    b.addEventListener('pointercancel', off);
    b.addEventListener('lostpointercapture', off);
  });
  const toggle = (id, show) => (document.getElementById(id).hidden = !show);
  document.getElementById('btn-aide').addEventListener('click', () => toggle('aide', true));
  document.getElementById('btn-photos').addEventListener('click', () => toggle('photos', true));
  document.querySelectorAll('.panneau .fermer').forEach((b) => b.addEventListener('click', () => (b.closest('.panneau').hidden = true)));
  const grid = document.getElementById('grille');
  const cmp = document.getElementById('comparaison');
  for (const r of REFERENCES) {
    const fig = document.createElement('figure');
    fig.innerHTML = `<img loading="lazy" src="references/${r.f}.webp" alt="${r.t}"><figcaption>${r.t}</figcaption>`;
    fig.addEventListener('click', () => {
      cmp.querySelector('img').src = `references/${r.f}.webp`;
      cmp.querySelector('figcaption').textContent = r.t;
      cmp.hidden = false;
      toggle('photos', false);
      if (r.pos) nav.goTo(r.pos, r.look);
    });
    grid.appendChild(fig);
  }
  cmp.querySelector('.fermer').addEventListener('click', () => (cmp.hidden = true));
  let vu = false;
  try { vu = !!localStorage.getItem('aide-vue'); localStorage.setItem('aide-vue', '1'); } catch (e) { /* stockage indisponible */ }
  if (!vu && !new URLSearchParams(location.search).has('capture')) toggle('aide', true);
}

start().catch((e) => {
  document.getElementById('etat').textContent = 'Erreur de chargement : ' + e.message;
  console.error(e);
});
