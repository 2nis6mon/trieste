// Éclairage temps réel des meubles : soleil (position calculée à Trieste,
// mêmes valeurs que le précalcul) et lampes de l'appartement (lampes.json).
// Les murs, sols et plafonds gardent leur éclairage précalculé ; ces lumières
// n'agissent que sur les meubles (voir patchShaders).
import * as THREE from 'three';

const UP_AZ = 70.9; // azimut du haut du plan (plan cadastral)
const SUN_COLOR = { jour: [1.0, 0.975, 0.93], soir: [1.0, 0.7, 0.43] };
// Conversion puissance Blender (W) -> intensité three.js (cd, unités cohérentes
// avec les lightmaps) ; calée visuellement sur le précalcul.
const K_POINT = 1 / (4 * Math.PI);
const K_AREA = 1 / Math.PI;
// Lampes d'appoint : Eclisse (sphère à ouverture : une partie de la lumière
// reste dans la coque), Nessino (dôme opale), Tolomeo (diffuseur ouvert)
const GAIN = { lampe_chevet_1_lum: 0.45, lampe_chevet_2_lum: 0.45, lampe_tv_lum: 0.55 };
// Toutes les sources : 2700 K (vu avec une balance des blancs d'intérieur à 4000 K)
export const K2700 = [1.0, 0.63, 0.25];

export class Eclairage {
  constructor(apt) {
    this.apt = apt;
    this.scene = apt.scene;
    this.sun = new THREE.DirectionalLight(0xffffff, 0);
    this.sun.castShadow = true;
    this.sun.shadow.mapSize.set(2048, 2048);
    const c = this.sun.shadow.camera;
    c.left = -8; c.right = 8; c.top = 8; c.bottom = -8; c.near = 1; c.far = 60;
    this.sun.shadow.bias = -0.0008;
    this.sun.shadow.normalBias = 0.05;
    this.sun.target.position.set(4.6, 1.0, 7.2);
    this.scene.add(this.sun, this.sun.target);
    this.lamps = [];
    for (const l of apt.lamps) {
      let light;
      const col = new THREE.Color(...K2700);
      if (l.type === 'POINT') {
        light = new THREE.PointLight(col, l.power * K_POINT * (GAIN[l.name] || 1), 6, 2);
        light.shadow.mapSize.set(512, 512);
        light.shadow.bias = -0.002;
        light.shadow.radius = 4;
      } else {
        // plafonniers, spot, rubans LED : lumière dirigée vers le bas
        light = new THREE.SpotLight(col, l.power * K_AREA, 8, Math.PI * 0.46, 1.0, 2);
        light.shadow.mapSize.set(1024, 1024);
        light.shadow.bias = -0.002;
        light.shadow.radius = 4;
        const tgt = new THREE.Object3D();
        tgt.position.set(l.pos[0], 0, l.pos[2]);
        this.scene.add(tgt);
        light.target = tgt;
      }
      light.shadow.camera.near = 0.02; // le globe de la lampe est à quelques cm de l'ampoule
      light.position.set(l.pos[0], l.pos[1] + (l.type === 'POINT' ? 0 : -0.03), l.pos[2]);
      light.visible = false;
      light.userData = { ...l };
      this.scene.add(light);
      this.lamps.push(light);
    }
    this.buildOccluders(apt.plan);
    this.mode = 'jour';
    this.ceiling = false;
    this.room = null;
    this.coupe = false;
  }

  setCoupe(on) {
    if (on === this.coupe) return;
    this.coupe = on;
    this.setMode(this.mode, this.ceiling);
  }

  // Volumes d'ombre pleins (invisibles) : murs du plan extrudés, allèges et
  // impostes des baies, dalle haute. Ils remplacent la coque de l'architecture
  // pour les ombres (ses micro-joints laissaient passer de fins traits de soleil).
  buildOccluders(plan) {
    const mat = new THREE.MeshBasicMaterial({ colorWrite: false, depthWrite: false });
    const H = 2.70;
    const add = (poly, y0, y1) => {
      const sh = new THREE.Shape(poly.map(([x, z]) => new THREE.Vector2(x, -z)));
      const g = new THREE.ExtrudeGeometry(sh, { depth: y1 - y0, bevelEnabled: false });
      g.rotateX(-Math.PI / 2);
      g.translate(0, y0, 0);
      const m = new THREE.Mesh(g, mat);
      m.castShadow = true;
      m.userData.occluder = true;
      this.scene.add(m);
    };
    for (const w of plan.walls) add(w.poly, 0, H);
    for (const o of plan.openings) {
      if (o.type === 'passage') { add(o.quad, o.head ?? 2.1, H); continue; }
      if (o.sill > 0.01) add(o.quad, 0, o.sill);
      add(o.quad, o.head ?? 2.1, H);
      if (o.type === 'door_entry') add(o.quad, 0, H); // porte palière fermée
    }
    let x0 = 1e9, z0 = 1e9, x1 = -1e9, z1 = -1e9;
    for (const w of plan.walls) for (const [x, z] of w.poly) { x0 = Math.min(x0, x); x1 = Math.max(x1, x); z0 = Math.min(z0, z); z1 = Math.max(z1, z); }
    add([[x0, z0], [x1, z0], [x1, z1], [x0, z1]], H, H + 0.3);
  }

  lampByName(name) {
    return this.lamps.find((l) => l.userData.name === name);
  }

  setMode(mode, ceiling) {
    this.mode = mode;
    this.ceiling = ceiling;
    const info = this.apt.manifest[mode]?.info;
    const night = mode === 'nuit';
    if (!night && info?.az != null) {
      const th = THREE.MathUtils.degToRad(info.az - UP_AZ);
      const el = THREE.MathUtils.degToRad(info.el);
      const d = new THREE.Vector3(Math.sin(th) * Math.cos(el), Math.sin(el), -Math.cos(th) * Math.cos(el));
      this.sun.position.copy(this.sun.target.position).addScaledVector(d, 30);
      // vue en coupe : plafonds et hauts de murs masqués, le soleil entrerait partout
      this.sun.intensity = info.sun_strength * (this.coupe ? 0.12 : 1);
      this.sun.color.setRGB(...(SUN_COLOR[mode] || SUN_COLOR.jour));
      this.sun.visible = true;
    } else {
      this.sun.visible = false;
    }
    for (const l of this.lamps) {
      const g = l.userData.group;
      const blind = ['sdb', 'sas'].includes(l.userData.room);
      l.visible = (night && (g === 'appoint' || g === 'integre' || (g === 'plafonnier' && ceiling))) ||
        (!night && blind && g === 'plafonnier');
    }
    this.updateShadows(this.room, true);
  }

  // Ombres des lampes : seulement dans la pièce où l'on se trouve (coût GPU)
  updateShadows(room, force = false) {
    if (room === this.room && !force) return;
    this.room = room;
    for (const l of this.lamps) {
      const on = l.visible && l.userData.room === room && l.userData.group !== 'integre';
      if (l.castShadow !== on) l.castShadow = on;
    }
  }
}
