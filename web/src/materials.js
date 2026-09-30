// Bibliothèque de matériaux (web/public/data/materials.json, partagée avec Blender)
// et adaptation du shader three.js à l'éclairage précalculé.
import * as THREE from 'three';

const LOG_K = 1024.0; // doit correspondre à pipeline/blender/bake.py

// ---------------------------------------------------------------------------
// Patch global des shaders :
//  - lightmap encodée en logarithmique 8 bits : L = s ((1+K)^v - 1) / K
//  - avec une lightmap, l'éclairement diffus vient uniquement de la lightmap
//    (la sonde de la pièce ne sert qu'aux reflets) : pas de double comptage ;
//  - occlusion spéculaire : les reflets de la sonde sont atténués là où la
//    lightmap est plus sombre que la sonde (sous le lit, derrière un meuble…).
// ---------------------------------------------------------------------------
let patched = false;
export function patchShaders() {
  if (patched) return;
  patched = true;
  let c = THREE.ShaderChunk.lights_fragment_maps;
  c = c.replace(
    'vec3 lightMapIrradiance = lightMapTexel.rgb * lightMapIntensity;',
    `vec3 lightMapIrradiance = ( pow( vec3( ${(LOG_K + 1).toFixed(1)} ), lightMapTexel.rgb ) - 1.0 ) * ( lightMapIntensity / ${LOG_K.toFixed(1)} );`
  );
  c = c.replace('irradiance += lightMapIrradiance;', `iblIrradiance += lightMapIrradiance;
		#if defined( USE_ENVMAP ) && defined( ENVMAP_TYPE_CUBE_UV )
			float lmL = dot( lightMapIrradiance, vec3( 0.2126, 0.7152, 0.0722 ) );
			float prL = dot( getIBLIrradiance( geometryNormal ), vec3( 0.2126, 0.7152, 0.0722 ) );
			lmOcclusion = clamp( lmL / max( prL, 1e-5 ), 0.05, 1.0 );
		#endif`);
  c = c.replace(
    'iblIrradiance += getIBLIrradiance( geometryNormal );',
    `#ifndef USE_LIGHTMAP
			iblIrradiance += getIBLIrradiance( geometryNormal );
			#endif`
  );
  c = 'float lmOcclusion = 1.0;\n' + c;
  c = c.replace(/radiance \+= iblRadiance;/, 'radiance += iblRadiance * lmOcclusion;');
  THREE.ShaderChunk.lights_fragment_maps = c;
  // Les surfaces précalculées (murs, sols, plafonds) contiennent déjà la
  // lumière directe : les lampes temps réel n'éclairent que les meubles.
  let b = THREE.ShaderChunk.lights_fragment_begin;
  for (const k of ['NUM_POINT_LIGHTS', 'NUM_SPOT_LIGHTS', 'NUM_DIR_LIGHTS']) {
    b = b.replace(`#if ( ${k} > 0 ) && defined( RE_Direct )`, `#if ( ${k} > 0 ) && defined( RE_Direct ) && !defined( USE_LIGHTMAP )`);
  }
  b = b.replace('#if ( NUM_RECT_AREA_LIGHTS > 0 ) && defined( RE_Direct_RectArea )',
    '#if ( NUM_RECT_AREA_LIGHTS > 0 ) && defined( RE_Direct_RectArea ) && !defined( USE_LIGHTMAP )');
  THREE.ShaderChunk.lights_fragment_begin = b;
}

// ---------------------------------------------------------------------------
const texLoader = new THREE.TextureLoader();
const texCache = new Map();

function loadTex(name, srgb) {
  const key = name + (srgb ? ':s' : ':l');
  if (!texCache.has(key)) {
    const t = texLoader.load(`textures/${name}.webp`);
    t.wrapS = t.wrapT = THREE.RepeatWrapping;
    t.colorSpace = srgb ? THREE.SRGBColorSpace : THREE.NoColorSpace;
    t.anisotropy = 8;
    texCache.set(key, t);
  }
  return texCache.get(key);
}

function tex(name, srgb, repeat) {
  const base = loadTex(name, srgb);
  if (!repeat) return base;
  const t = base.clone(); // partage l'image source
  t.repeat.set(repeat, repeat);
  t.needsUpdate = true;
  return t;
}

export class MaterialLibrary {
  constructor(specs) {
    this.specs = specs;
    this.cache = new Map();
    this.lampMaterials = [];
    this.facadeMaterials = [];
  }

  // Un matériau par (nom, atlas de lightmap, pièce) : la lightmap et la sonde
  // d'environnement sont propres à chaque combinaison.
  get(name, { lightMap = null, lightMapIntensity = 1, envMap = null, room = '' } = {}) {
    const key = `${name}|${lightMap ? lightMap.uuid : '-'}|${room}`;
    if (this.cache.has(key)) return this.cache.get(key);
    const m = this.build(name);
    if (lightMap && m.userData.lit === 'lightmap') {
      m.lightMap = lightMap;
      m.lightMapIntensity = lightMapIntensity;
    }
    if (envMap) m.envMap = envMap;
    m.userData.room = room;
    this.cache.set(key, m);
    return m;
  }

  build(name) {
    const s = this.specs[name] || { color: '#ff00ff' };
    const lit = s.lit || 'lightmap';
    const rep = s.uv === 'unit' ? null : 1 / (s.size || 1);
    const p = {
      color: new THREE.Color(s.color || '#ffffff'),
      roughness: s.roughness ?? 0.5,
      metalness: s.metalness ?? 0,
    };
    if (s.map) p.map = tex(s.map, true, rep);
    if (s.normalMap) {
      p.normalMap = tex(s.normalMap, false, s.normalSize ? 1 / s.normalSize : rep);
      const k = s.normalScale ?? 1;
      p.normalScale = new THREE.Vector2(k, k);
    }
    if (s.roughnessMap) p.roughnessMap = tex(s.roughnessMap, false, rep);
    if (s.sheen) {
      p.sheen = s.sheen;
      p.sheenColor = new THREE.Color(s.sheenColor || '#ffffff');
      p.sheenRoughness = s.sheenRoughness ?? 0.6;
    }
    if (s.clearcoat) {
      p.clearcoat = s.clearcoat;
      p.clearcoatRoughness = s.clearcoatRoughness ?? 0.1;
    }
    if (s.alphaTest) {
      p.alphaTest = s.alphaTest;
    }
    if (s.side === 'double') p.side = THREE.DoubleSide;
    let m;
    if (lit === 'glass') {
      m = new THREE.MeshPhysicalMaterial({
        color: p.color, roughness: s.roughness ?? 0.02, metalness: 0, transparent: true,
        opacity: s.opacity ?? 0.1, depthWrite: false, side: THREE.DoubleSide, envMapIntensity: 1.0,
      });
      m.userData.lit = 'glass';
      return m;
    }
    if (s.transparent) {
      p.transparent = true;
      p.opacity = s.transparent;
    }
    if (s.emissive) {
      p.emissive = new THREE.Color(s.emissive);
      p.emissiveIntensity = 0;
    }
    if (s.emissiveMap) {
      p.emissiveMap = tex(s.emissiveMap, true, null);
      p.emissive = new THREE.Color('#ffffff');
      p.emissiveIntensity = 0;
    }
    m = new THREE.MeshPhysicalMaterial(p);
    m.name = name;
    m.userData.lit = lit;
    if (lit === 'lamp') this.lampMaterials.push(m);
    if (s.emissiveMap) this.facadeMaterials.push(m);
    return m;
  }

  static loadLightmap(url) {
    const t = texLoader.load(url);
    t.flipY = false;
    t.colorSpace = THREE.NoColorSpace;
    t.channel = 1;
    t.generateMipmaps = true;
    t.minFilter = THREE.LinearMipmapLinearFilter;
    t.magFilter = THREE.LinearFilter;
    return t;
  }
}
