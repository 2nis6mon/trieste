// Navigation : visite à hauteur d'œil (flèches, glisser, boutons tactiles,
// collisions) et vue d'ensemble en coupe (orbite).
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

export const EYE = 1.6;
const RADIUS = 0.22;
const SPEED = 1.3;           // m/s
const TURN = Math.PI / 2.2;  // rad/s

export class Navigation {
  constructor(camera, dom, apt) {
    this.camera = camera;
    this.dom = dom;
    this.apt = apt;
    this.mode = 'visite';
    this.pos = new THREE.Vector2(3.25, 5.95); // plan (x, z)
    this.yaw = 0;
    this.pitch = 0;
    this.keys = new Set();
    this.hold = { fwd: 0, turn: 0 };
    this.segments = [];
    this.buildColliders();
    this.orbit = new OrbitControls(camera, dom);
    this.orbit.enabled = false;
    this.orbit.enableDamping = true;
    this.orbit.maxPolarAngle = Math.PI * 0.47;
    this.orbit.minDistance = 4;
    this.orbit.maxDistance = 30;
    this.bindInputs();
  }

  // ------------------------------------------------------------ collisions
  buildColliders() {
    const segs = [];
    const addPoly = (poly) => {
      for (let i = 0; i < poly.length; i++) {
        const a = poly[i], b = poly[(i + 1) % poly.length];
        segs.push([a[0], a[1], b[0], b[1]]);
      }
    };
    for (const w of this.apt.plan.walls) addPoly(w.poly);
    for (const o of this.apt.plan.openings) {
      // fenêtres, porte-fenêtre et porte palière (fermées) sont infranchissables
      if (['window', 'door_glazed', 'door_entry'].includes(o.type)) addPoly(o.quad);
    }
    for (const ob of this.apt.obstacles) if (ob.top > 0.2) addPoly(ob.poly);
    this.segments = segs;
  }

  resolve(p) {
    for (let it = 0; it < 4; it++) {
      let moved = false;
      for (const [ax, az, bx, bz] of this.segments) {
        const dx = bx - ax, dz = bz - az;
        const L2 = dx * dx + dz * dz || 1e-9;
        let t = ((p.x - ax) * dx + (p.y - az) * dz) / L2;
        t = Math.max(0, Math.min(1, t));
        const cx = ax + t * dx, cz = az + t * dz;
        let nx = p.x - cx, nz = p.y - cz;
        const d = Math.hypot(nx, nz);
        if (d < RADIUS) {
          if (d < 1e-6) { nx = -dz; nz = dx; } else { nx /= d; nz /= d; }
          const push = RADIUS - (d < 1e-6 ? 0 : d);
          p.x += nx * push;
          p.y += nz * push;
          moved = true;
        }
      }
      if (!moved) break;
    }
    return p;
  }

  isFree(x, z) {
    const inside = this.apt.plan.rooms.some((r) => pointInPoly(x, z, r.poly));
    if (!inside) return false;
    for (const [ax, az, bx, bz] of this.segments) {
      if (distSeg(x, z, ax, az, bx, bz) < RADIUS * 0.95) return false;
    }
    for (const ob of this.apt.obstacles) if (ob.top > 0.2 && pointInPoly(x, z, ob.poly)) return false;
    return true;
  }

  // ------------------------------------------------------------ modes
  goTo(pos, look) {
    this.setMode('visite');
    this.pos.set(pos[0], pos[1]);
    this.yaw = Math.atan2(-(look[0] - pos[0]), -(look[1] - pos[1]));
    this.pitch = -0.04;
    this.resolve(this.pos);
  }

  setMode(m) {
    if (m === this.mode) return;
    this.mode = m;
    this.orbit.enabled = m === 'coupe';
    this.apt.setCutaway(m === 'coupe');
    if (m === 'coupe') {
      this.camera.fov = 45;
      this.camera.updateProjectionMatrix();
      this.orbit.target.set(4.5, 0.4, 7.0);
      this.camera.position.set(4.5 - 1.5, 10.5, 7.0 + 6.5);
      this.orbit.update();
    }
    this.onMode?.(m);
  }

  recenter() {
    if (this.mode === 'coupe') {
      this.orbit.target.set(4.5, 0.4, 7.0);
      this.camera.position.set(2.0, 13.5, 16.0);
      this.orbit.update();
    } else {
      this.pitch = 0;
    }
  }

  // ------------------------------------------------------------ entrées
  bindInputs() {
    addEventListener('keydown', (e) => {
      if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(e.key)) {
        e.preventDefault();
        this.keys.add(e.key);
      }
    });
    addEventListener('keyup', (e) => this.keys.delete(e.key));
    addEventListener('blur', () => this.keys.clear());
    let drag = null;
    this.dom.addEventListener('pointerdown', (e) => {
      if (this.mode !== 'visite') return;
      drag = { x: e.clientX, y: e.clientY, id: e.pointerId };
      try { this.dom.setPointerCapture(e.pointerId); } catch (err) { /* pointeur synthétique */ }
    });
    this.dom.addEventListener('pointermove', (e) => {
      if (!drag || e.pointerId !== drag.id) return;
      const k = (this.camera.fov * Math.PI / 180) / this.dom.clientHeight;
      this.yaw += (e.clientX - drag.x) * k;
      this.pitch += (e.clientY - drag.y) * k;
      this.pitch = Math.max(-1.3, Math.min(1.3, this.pitch));
      drag.x = e.clientX;
      drag.y = e.clientY;
    });
    const end = () => (drag = null);
    this.dom.addEventListener('pointerup', end);
    this.dom.addEventListener('pointercancel', end);
  }

  update(dt) {
    if (this.mode === 'coupe') {
      this.orbit.update();
      return;
    }
    let fwd = this.hold.fwd, turn = this.hold.turn;
    if (this.keys.has('ArrowUp')) fwd += 1;
    if (this.keys.has('ArrowDown')) fwd -= 1;
    // flèche gauche : tourner à gauche sur place ; droite : à droite
    if (this.keys.has('ArrowLeft')) turn += 1;
    if (this.keys.has('ArrowRight')) turn -= 1;
    this.yaw += turn * TURN * dt;
    if (fwd) {
      const step = dt * SPEED * fwd;
      // sous-pas pour ne jamais traverser une cloison fine
      const n = Math.ceil(Math.abs(step) / 0.05);
      for (let i = 0; i < n; i++) {
        this.pos.x += -Math.sin(this.yaw) * step / n;
        this.pos.y += -Math.cos(this.yaw) * step / n;
        this.resolve(this.pos);
      }
    }
    // champ de vision réaliste : ~72° horizontal en paysage, 60° vertical en portrait
    const aspect = this.camera.aspect;
    const vfov = aspect >= 1 ? 2 * Math.atan(Math.tan((72 * Math.PI) / 360) / aspect) * 180 / Math.PI : 62;
    if (Math.abs(this.camera.fov - vfov) > 0.01) {
      this.camera.fov = vfov;
      this.camera.updateProjectionMatrix();
    }
    this.camera.position.set(this.pos.x, EYE, this.pos.y);
    this.camera.rotation.set(0, 0, 0);
    this.camera.rotateY(this.yaw);
    this.camera.rotateX(-this.pitch);
  }

  currentRoom() {
    const order = ['cuisine', 'chambre', 'sdb', 'sas', 'sejour'];
    for (const id of order) {
      const r = this.apt.plan.rooms.find((x) => x.id === id);
      if (r && pointInPoly(this.pos.x, this.pos.y, r.poly)) return id;
    }
    return null;
  }
}

export function pointInPoly(x, z, poly) {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, zi] = poly[i], [xj, zj] = poly[j];
    if ((zi > z) !== (zj > z) && x < ((xj - xi) * (z - zi)) / (zj - zi) + xi) inside = !inside;
  }
  return inside;
}

function distSeg(px, pz, ax, az, bx, bz) {
  const dx = bx - ax, dz = bz - az;
  const L2 = dx * dx + dz * dz || 1e-9;
  let t = ((px - ax) * dx + (pz - az) * dz) / L2;
  t = Math.max(0, Math.min(1, t));
  return Math.hypot(px - (ax + t * dx), pz - (az + t * dz));
}
