// Meubles déplaçables : groupes (meubles.json), implantation (position et
// rotation de chaque meuble) et mode « Aménager » de la vue d'ensemble.
// L'implantation est gardée dans le navigateur et peut être copiée (JSON).
import * as THREE from 'three';

const CLE = 'trieste-implantation-v1';
const sanitize = (n) => n.replace(/\s/g, '_').replace(/[[\]./:]/g, '');

export class Mobilier {
  constructor(apt, eclairage, defs, defaut = {}) {
    this.apt = apt;
    this.ecl = eclairage;
    this.pieces = {};
    this.defaut = defaut;
    const root = apt.root;
    for (const [id, def] of Object.entries(defs.meubles)) {
      const nodes = def.objets.map((n) => root.getObjectByName(sanitize(n))).filter(Boolean);
      if (!nodes.length) continue;
      // pivot : centre de l'emprise de l'objet ancre
      const box = new THREE.Box3().setFromObject(nodes[0]);
      const c = box.getCenter(new THREE.Vector3());
      const g = new THREE.Group();
      g.name = 'meuble_' + id;
      g.position.set(c.x, 0, c.z);
      apt.scene.add(g);
      g.updateMatrixWorld(true);
      for (const n of nodes) g.attach(n);
      for (const ln of def.lumieres || []) {
        const l = eclairage.lampByName(ln);
        if (l) g.attach(l);
      }
      const names = new Set(def.objets);
      const obstacles = apt.obstacles.filter((o) => names.has(o.name));
      for (const o of obstacles) o.poly0 = o.poly.map((p) => [...p]);
      const meshes = [];
      g.traverse((o) => { if (o.isMesh) { o.userData.meuble = id; meshes.push(o); } });
      this.pieces[id] = { id, def, group: g, pivot: [c.x, c.z], obstacles, meshes, x: 0, z: 0, r: 0 };
    }
    this.load();
  }

  load() {
    let saved = {};
    try { saved = JSON.parse(localStorage.getItem(CLE) || '{}'); } catch (e) { /* stockage indisponible */ }
    for (const p of Object.values(this.pieces)) {
      const t = saved[p.id] || this.defaut[p.id] || { x: 0, z: 0, r: 0 };
      this.set(p.id, t.x, t.z, t.r, false);
    }
    this.onChange?.();
  }

  save() {
    try { localStorage.setItem(CLE, JSON.stringify(this.state())); } catch (e) { /* stockage indisponible */ }
  }

  state() {
    const s = {};
    for (const p of Object.values(this.pieces)) {
      if (Math.abs(p.x) > 1e-3 || Math.abs(p.z) > 1e-3 || Math.abs(p.r) > 1e-3) {
        s[p.id] = { x: +p.x.toFixed(3), z: +p.z.toFixed(3), r: +p.r.toFixed(4) };
      }
    }
    return s;
  }

  set(id, x, z, r, persist = true) {
    const p = this.pieces[id];
    if (!p) return;
    p.x = x; p.z = z; p.r = r;
    p.group.position.set(p.pivot[0] + x, 0, p.pivot[1] + z);
    p.group.rotation.y = r;
    p.group.updateMatrixWorld(true);
    const cs = Math.cos(r), sn = Math.sin(r);
    for (const o of p.obstacles) {
      o.poly = o.poly0.map(([px, pz]) => {
        const dx = px - p.pivot[0], dz = pz - p.pivot[1];
        return [p.pivot[0] + x + dx * cs + dz * sn, p.pivot[1] + z - dx * sn + dz * cs];
      });
    }
    if (persist) { this.save(); this.onChange?.(); }
  }

  reset() {
    try { localStorage.removeItem(CLE); } catch (e) { /* stockage indisponible */ }
    for (const p of Object.values(this.pieces)) {
      const t = this.defaut[p.id] || { x: 0, z: 0, r: 0 };
      this.set(p.id, t.x, t.z, t.r, false);
    }
    this.onChange?.();
  }

  get meshes() {
    return Object.values(this.pieces).flatMap((p) => p.meshes);
  }
}

// ---------------------------------------------------------------------------
// Mode « Aménager » : cliquer un meuble, le faire glisser, le tourner.
export class Editeur {
  constructor(mob, camera, dom, nav, panel) {
    this.mob = mob;
    this.camera = camera;
    this.dom = dom;
    this.nav = nav;
    this.panel = panel;
    this.actif = false;
    this.sel = null;
    this.ray = new THREE.Raycaster();
    this.box = new THREE.BoxHelper(undefined, 0xe0a458);
    this.box.visible = false;
    this.box.material.depthTest = false;
    this.box.renderOrder = 10;
    mob.apt.scene.add(this.box);
    this.fillList();
    this.bind();
  }

  setActif(on) {
    this.actif = on;
    if (!on) this.dom.style.cursor = '';
    this.panel.hidden = !on;
    if (!on) this.select(null);
    this.dom.classList.toggle('amenager', on);
  }

  pick(e) {
    const r = this.dom.getBoundingClientRect();
    const v = new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
    this.ray.setFromCamera(v, this.camera);
    return this.ray;
  }

  select(id) {
    this.sel = id;
    const p = id && this.mob.pieces[id];
    this.box.visible = !!p;
    if (p) this.box.setFromObject(p.group);
    this.panel.querySelector('.nom').textContent = p ? p.def.label : 'Cliquez sur un meuble (ou choisissez-le dans la liste)';
    this.panel.querySelectorAll('[data-rot], [data-dep]').forEach((b) => (b.disabled = !p));
    const liste = this.panel.querySelector('select');
    if (liste) liste.value = id || '';
  }

  // Déplacement par pas (boutons flèches) : dx, dz en mètres, axes du plan
  nudge(dx, dz) {
    const p = this.sel && this.mob.pieces[this.sel];
    if (!p) return;
    this.mob.set(p.id, p.x + dx, p.z + dz, p.r);
    this.box.setFromObject(p.group);
  }

  fillList() {
    const liste = this.panel.querySelector('select');
    if (!liste) return;
    const noms = { chambre: 'Chambre', sejour: 'Séjour', cuisine: 'Cuisine' };
    liste.innerHTML = '<option value="">— Choisir un meuble —</option>' + Object.values(this.mob.pieces)
      .map((p) => `<option value="${p.id}">${noms[p.def.room] || ''} · ${p.def.label}</option>`).join('');
    liste.addEventListener('change', () => this.select(liste.value || null));
  }

  rotate(deg) {
    const p = this.sel && this.mob.pieces[this.sel];
    if (!p) return;
    this.mob.set(p.id, p.x, p.z, p.r + THREE.MathUtils.degToRad(deg));
    this.box.setFromObject(p.group);
  }

  bind() {
    const plane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
    let drag = null;
    this.dom.addEventListener('pointerdown', (e) => {
      if (!this.actif) return;
      const ray = this.pick(e);
      const hit = ray.intersectObjects(this.mob.meshes, false)[0];
      if (!hit) { this.select(null); return; }
      const id = hit.object.userData.meuble;
      this.select(id);
      const p = this.mob.pieces[id];
      const pt = new THREE.Vector3();
      ray.ray.intersectPlane(plane, pt);
      drag = { id, start: pt.clone(), x: p.x, z: p.z, pid: e.pointerId };
      this.nav.orbit.enabled = false;
      try { this.dom.setPointerCapture(e.pointerId); } catch (err) { /* pointeur synthétique */ }
      e.stopImmediatePropagation();
    }, true);
    this.dom.addEventListener('pointermove', (e) => {
      if (this.actif && !drag && e.pointerType === 'mouse') {
        // survol : curseur « main » au-dessus d'un meuble
        const over = this.pick(e).intersectObjects(this.mob.meshes, false).length > 0;
        this.dom.style.cursor = over ? 'grab' : '';
      }
      if (!drag || e.pointerId !== drag.pid) return;
      this.dom.style.cursor = 'grabbing';
      const pt = new THREE.Vector3();
      if (!this.pick(e).ray.intersectPlane(plane, pt)) return;
      const p = this.mob.pieces[drag.id];
      this.mob.set(drag.id, drag.x + pt.x - drag.start.x, drag.z + pt.z - drag.start.z, p.r);
      this.box.setFromObject(p.group);
    });
    const end = () => {
      if (!drag) return;
      drag = null;
      this.nav.orbit.enabled = this.nav.mode === 'coupe';
    };
    this.dom.addEventListener('pointerup', end);
    this.dom.addEventListener('pointercancel', end);
    addEventListener('keydown', (e) => {
      if (!this.actif || !this.sel) return;
      if (e.key === 'q' || e.key === 'Q') this.rotate(15);
      if (e.key === 'e' || e.key === 'E') this.rotate(-15);
    });
  }
}
