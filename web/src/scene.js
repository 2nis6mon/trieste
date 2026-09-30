// Chargement de la maquette, éclairage précalculé par mode, sondes de pièce.
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { Reflector } from 'three/examples/jsm/objects/Reflector.js';
import { DRACOLoader } from 'three/examples/jsm/loaders/DRACOLoader.js';
import { MaterialLibrary, patchShaders } from './materials.js';

export const MODES = {
  jour: { label: 'Jour', exposure: 1.0, sky: [[0.42, 0.62, 0.92], [0.86, 0.9, 0.95]], skyIntensity: 3.2 },
  soir: { label: 'Fin de journée', exposure: 1.35, sky: [[0.36, 0.44, 0.66], [1.0, 0.72, 0.52]], skyIntensity: 1.6 },
  nuit: { label: 'Nuit', exposure: 2.2, sky: [[0.004, 0.007, 0.016], [0.05, 0.035, 0.028]], skyIntensity: 0.25 },
};

// Pièces : point de vue par défaut (plan, m) et nom affiché
export const ROOMS = {
  chambre: { name: 'Chambre', pos: [3.25, 5.95], look: [6.7, 4.2] },
  sejour: { name: 'Séjour', pos: [3.1, 9.9], look: [7.9, 9.3] },
  cuisine: { name: 'Cuisine', pos: [3.0, 7.55], look: [6.3, 7.1] },
  sdb: { name: 'Salle de bain', pos: [2.72, 4.45], look: [4.4, 2.2] },
  sas: { name: 'Dégagement', pos: [2.05, 5.95], look: [1.0, 5.05] },
  entree: { name: 'Entrée', pos: [1.75, 9.4], look: [4.5, 8.6] },
};

export class Apartment {
  constructor(renderer) {
    this.renderer = renderer;
    this.scene = new THREE.Scene();
    this.root = new THREE.Group();
    this.scene.add(this.root);
    this.meshes = [];
    this.lightmaps = {};
    this.probes = {};
    this.mode = 'jour';
    this.ceiling = false;
    patchShaders();
  }

  async load(onProgress) {
    const get = (u) => fetch(u).then((r) => r.json());
    const [plan, specs, manifest, obstacles, lamps] = await Promise.all([
      get('data/plan.json'), get('data/materials.json'), get('lightmaps/manifest.json'),
      get('data/obstacles.json').catch(() => []), get('data/lampes.json').catch(() => []),
    ]);
    this.plan = plan;
    this.manifest = manifest;
    this.obstacles = obstacles;
    this.lamps = lamps;
    this.lib = new MaterialLibrary(specs);
    const draco = new DRACOLoader().setDecoderPath('draco/');
    const gltf = await new GLTFLoader().setDRACOLoader(draco).loadAsync('models/appartement.glb', (e) => {
      if (e.total) onProgress?.(e.loaded / e.total);
    });
    this.root.add(gltf.scene);
    gltf.scene.traverse((o) => {
      if (!o.isMesh) return;
      // les propriétés Blender sont sur le nœud parent (objet) ou le maillage
      let ud = o.userData;
      let p = o;
      while (p && !p.userData.lit) p = p.parent;
      if (p) ud = p.userData;
      o.userData = { ...ud, meshName: o.name };
      const mname = (o.material?.name || '').replace(/\.\d+$/, '');
      o.userData.matName = mname;
      this.meshes.push(o);
    });
    this.applyMaterials();
    this.buildMirrors();
    this.buildSky();
    this.buildCaps();
    await this.setMode('jour');
  }

  applyMaterials() {
    for (const o of this.meshes) {
      const ud = o.userData;
      const spec = this.lib.specs[ud.matName];
      const room = ud.room || '';
      const atlas = spec && (spec.lit || 'lightmap') === 'lightmap' ? ud.atlas || '' : '';
      const key = `${ud.matName}|${atlas}|${room}`;
      let m = this.lib.cache.get(key);
      if (!m) {
        m = this.lib.build(ud.matName);
        m.userData.atlas = atlas;
        m.userData.room = room;
        this.lib.cache.set(key, m);
      }
      o.material = m;
      if (m.userData.lit === 'glass') o.renderOrder = 2;
    }
  }

  // Miroir de la salle de bain : vrai reflet (rendu plan), léger voile chaud
  buildMirrors() {
    for (const o of [...this.meshes]) {
      if (this.lib.specs[o.userData.matName]?.lit !== 'mirror') continue;
      // le Reflector attend un plan orienté +Z local : on reconstruit un disque
      o.updateWorldMatrix(true, false);
      const g = o.geometry;
      g.computeBoundingBox();
      const c = g.boundingBox.getCenter(new THREE.Vector3()).applyMatrix4(o.matrixWorld);
      const size = g.boundingBox.getSize(new THREE.Vector3());
      const radius = Math.max(size.x, size.y, size.z) / 2;
      const n = new THREE.Vector3().fromBufferAttribute(g.attributes.normal, 0).transformDirection(o.matrixWorld);
      const r = new Reflector(new THREE.CircleGeometry(radius, 72), {
        textureWidth: 1024, textureHeight: 1024, color: 0xd8d6d0, clipBias: 0.003, multisample: 4,
      });
      r.position.copy(c);
      r.lookAt(c.clone().add(n));
      r.userData = { ...o.userData, lit: 'mirror' };
      o.parent.remove(o);
      this.scene.add(r);
      this.meshes = this.meshes.filter((m) => m !== o);
    }
  }

  async setMode(mode, ceiling = this.ceiling) {
    this.mode = mode;
    this.ceiling = ceiling && mode === 'nuit';
    const tag = this.ceiling ? 'nuit_plafonniers' : mode;
    const man = this.manifest[tag] || this.manifest[mode] || Object.values(this.manifest)[0];
    const loads = [];
    for (const [atlas, a] of Object.entries(man.atlas)) {
      const key = `${tag}/${atlas}`;
      if (!this.lightmaps[key]) {
        const t = MaterialLibrary.loadLightmap(a.file);
        this.lightmaps[key] = { tex: t, intensity: a.intensity };
        loads.push(new Promise((res) => {
          const img = new Image();
          img.onload = img.onerror = res;
          img.src = a.file;
        }));
      }
    }
    await Promise.all(loads);
    for (const m of this.lib.cache.values()) {
      const at = m.userData.atlas;
      if (!at) continue;
      const lm = this.lightmaps[`${tag}/${at}`];
      if (!lm) continue;
      m.lightMap = lm.tex;
      m.lightMapIntensity = lm.intensity * Math.PI;
      m.needsUpdate = true;
    }
    const night = mode === 'nuit';
    for (const m of this.lib.cache.values()) {
      const n = m.name;
      if (m.userData.lit === 'lamp') {
        const on = night && (n !== 'plafonnier_diffuseur' || this.ceiling);
        m.emissiveIntensity = on ? (n === 'plafonnier_diffuseur' ? 3.0 : 5.0) : 0.0;
      }
      if (m.emissiveMap) m.emissiveIntensity = night ? 1.2 : 0.0;
    }
    const cfg = MODES[mode];
    this.renderer.toneMappingExposure = cfg.exposure;
    this.sky.material.uniforms.zenith.value.setRGB(...cfg.sky[0]).multiplyScalar(cfg.skyIntensity);
    this.sky.material.uniforms.horizon.value.setRGB(...cfg.sky[1]).multiplyScalar(cfg.skyIntensity);
    await new Promise((r) => requestAnimationFrame(r));
    this.captureProbes();
  }

  roomCenter(id) {
    const r = this.plan.rooms.find((x) => x.id === id);
    let x = 0, z = 0;
    for (const [a, b] of r.poly) { x += a; z += b; }
    return [x / r.poly.length, z / r.poly.length];
  }

  // Sondes d'environnement : captures cubiques de la pièce déjà éclairée
  captureProbes() {
    const pmrem = new THREE.PMREMGenerator(this.renderer);
    const glass = this.meshes.filter((o) => o.material.userData.lit === 'glass');
    glass.forEach((o) => (o.visible = false));
    const centers = {
      chambre: [4.9, 4.9], sdb: [3.55, 3.2], sas: [1.85, 5.65], cuisine: [4.3, 7.4], sejour: [4.6, 9.6],
    };
    const exposure = this.renderer.toneMappingExposure;
    for (const [room, c] of Object.entries(centers)) {
      const rt = new THREE.WebGLCubeRenderTarget(128, { type: THREE.HalfFloatType });
      const cam = new THREE.CubeCamera(0.05, 80, rt);
      cam.position.set(c[0], 1.35, c[1]);
      this.scene.add(cam);
      cam.update(this.renderer, this.scene);
      this.scene.remove(cam);
      if (this.probes[room]) this.probes[room].dispose();
      this.probes[room] = pmrem.fromCubemap(rt.texture).texture;
      rt.dispose();
    }
    this.renderer.toneMappingExposure = exposure;
    glass.forEach((o) => (o.visible = true));
    pmrem.dispose();
    const alias = { terrasse: 'sejour', exterieur: 'sejour', all: 'sejour', '': 'sejour' };
    for (const m of this.lib.cache.values()) {
      const r = this.probes[m.userData.room] ? m.userData.room : alias[m.userData.room] || 'sejour';
      m.envMap = this.probes[r];
      m.envMapIntensity = m.userData.lit === 'glass' ? 1.0 : 1.0;
      m.needsUpdate = true;
    }
  }

  buildSky() {
    const g = new THREE.SphereGeometry(400, 32, 16);
    const m = new THREE.ShaderMaterial({
      side: THREE.BackSide, depthWrite: false,
      uniforms: { zenith: { value: new THREE.Color() }, horizon: { value: new THREE.Color() } },
      vertexShader: `varying vec3 vDir; void main(){ vDir = normalize(position); gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }`,
      fragmentShader: `uniform vec3 zenith; uniform vec3 horizon; varying vec3 vDir;
        void main(){ float h = clamp(vDir.y, 0.0, 1.0); vec3 c = mix(horizon, zenith, pow(h, 0.55));
        gl_FragColor = vec4(c, 1.0);
        #include <tonemapping_fragment>
        #include <colorspace_fragment>
        }`,
    });
    this.sky = new THREE.Mesh(g, m);
    this.sky.frustumCulled = false;
    this.scene.add(this.sky);
  }

  // Poché des murs pour la vue en coupe
  buildCaps() {
    this.caps = new THREE.Group();
    const mat = new THREE.MeshBasicMaterial({ color: 0x2a2826 });
    for (const w of this.plan.walls) {
      const s = new THREE.Shape(w.poly.map(([x, z]) => new THREE.Vector2(x, -z)));
      const g = new THREE.ShapeGeometry(s);
      g.rotateX(-Math.PI / 2);
      const mesh = new THREE.Mesh(g, mat);
      this.caps.add(mesh);
    }
    this.caps.visible = false;
    this.scene.add(this.caps);
  }

  setCutaway(on, height = 1.25) {
    const plane = new THREE.Plane(new THREE.Vector3(0, -1, 0), height);
    this.renderer.localClippingEnabled = on;
    this.caps.visible = on;
    this.caps.position.y = height + 0.002;
    for (const o of this.meshes) {
      const ud = o.userData;
      const archi = ud.atlas === 'archi' || ud.lit === 'glass' || /^(murs|faience|fenetre|vitrage|porte|plinthe)/.test(ud.meshName || '');
      if (ud.kind === 'plafond' || /^plafon/.test(ud.meshName || '')) { o.visible = !on; continue; }
      if (ud.room === 'exterieur') { o.visible = !on; continue; }
      if (archi) {
        o.material.clippingPlanes = on ? [plane] : null;
        o.material.clipShadows = true;
        o.material.needsUpdate = true;
      }
    }
  }
}
