// Vérification automatisée des commandes, des déplacements et des collisions
// (ordinateur + téléphone émulé). Usage : node scripts/verifier.mjs [url]
import { chromium, devices } from 'playwright-core';
import fs from 'node:fs';

const url = process.argv[2] || 'http://localhost:5173/';
const exe = fs.readdirSync('/opt/pw-browsers').filter((d) => d.startsWith('chromium-')).map((d) => `/opt/pw-browsers/${d}/chrome-linux/chrome`).find((p) => fs.existsSync(p));
const browser = await chromium.launch({ executablePath: exe, args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
const results = [];
const ok = (name, pass, detail = '') => { results.push({ test: name, ok: !!pass, detail }); console.log(pass ? 'OK  ' : 'ÉCHEC', name, detail); };

async function load(ctxOpts) {
  const ctx = await browser.newContext(ctxOpts);
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await page.goto(url + '?capture=1&piece=chambre');
  await page.waitForFunction(() => window.__visite?.ready, null, { timeout: 600000 });
  await page.waitForTimeout(800);
  return { ctx, page, errors };
}
const state = (page) => page.evaluate(() => { const n = window.__visite.nav; return { x: n.pos.x, z: n.pos.y, yaw: n.yaw, pitch: n.pitch, mode: n.mode, room: n.currentRoom() }; });
const hold = async (page, key, ms) => {
  await page.evaluate(() => (window.__visite.paused = true));
  await page.keyboard.down(key);
  await page.evaluate((s) => window.__visite.simulate(s), ms / 1000);
  await page.keyboard.up(key);
  await page.evaluate(() => (window.__visite.paused = false));
};
const tap = async (page, sel, ms) => {
  await page.evaluate(() => (window.__visite.paused = true));
  await page.dispatchEvent(sel, 'pointerdown', { pointerId: 7, isPrimary: true, pointerType: 'touch' });
  await page.evaluate((s) => window.__visite.simulate(s), ms / 1000);
  await page.dispatchEvent(sel, 'pointerup', { pointerId: 7, isPrimary: true, pointerType: 'touch' });
  await page.evaluate(() => (window.__visite.paused = false));
};

// ------------------------------------------------------------- ordinateur
{
  const { ctx, page, errors } = await load({ viewport: { width: 1280, height: 800 } });
  await page.evaluate(() => window.__visite.nav.goTo([4.4, 4.2], [6.8, 5.0]));
  let a = await state(page);
  await hold(page, 'ArrowLeft', 700);
  let b = await state(page);
  ok('Flèche gauche : rotation sur place vers la gauche', b.yaw > a.yaw + 0.3 && Math.hypot(b.x - a.x, b.z - a.z) < 1e-6, `Δlacet=${(b.yaw - a.yaw).toFixed(2)} rad, déplacement=${Math.hypot(b.x - a.x, b.z - a.z).toFixed(3)} m`);
  a = b;
  await hold(page, 'ArrowRight', 700);
  b = await state(page);
  ok('Flèche droite : rotation sur place vers la droite', b.yaw < a.yaw - 0.3 && Math.hypot(b.x - a.x, b.z - a.z) < 1e-6, `Δlacet=${(b.yaw - a.yaw).toFixed(2)} rad`);
  a = b;
  await hold(page, 'ArrowUp', 800);
  b = await state(page);
  const fwd = [-Math.sin(a.yaw), -Math.cos(a.yaw)];
  const d = (b.x - a.x) * fwd[0] + (b.z - a.z) * fwd[1];
  ok('Flèche haut : avance dans la direction du regard', d > 0.3, `avancée=${d.toFixed(2)} m`);
  a = b;
  await hold(page, 'ArrowDown', 800);
  b = await state(page);
  ok('Flèche bas : recule', (b.x - a.x) * fwd[0] + (b.z - a.z) * fwd[1] < -0.3);
  // collision : foncer vers la façade (fenêtres de la chambre) pendant 6 s
  await page.evaluate(() => window.__visite.nav.goTo([5.6, 5.2], [9.0, 6.4]));
  await hold(page, 'ArrowUp', 6000);
  b = await state(page);
  ok('Collision : impossible de traverser la façade / les fenêtres', b.room === 'chambre', `position finale (${b.x.toFixed(2)}, ${b.z.toFixed(2)}) pièce=${b.room}`);
  // collision meuble : foncer dans le lit
  await page.evaluate(() => window.__visite.nav.goTo([5.9, 5.8], [4.2, 4.6]));
  await hold(page, 'ArrowUp', 5000);
  b = await state(page);
  const inBed = await page.evaluate(([x, z]) => {
    const ob = window.__visite.apt.obstacles.find((o) => /mandal/.test(o.name));
    if (!ob) return null;
    let inside = false; const p = ob.poly;
    for (let i = 0, j = p.length - 1; i < p.length; j = i++) { const [xi, zi] = p[i], [xj, zj] = p[j]; if ((zi > z) !== (zj > z) && x < ((xj - xi) * (z - zi)) / (zj - zi) + xi) inside = !inside; }
    return inside;
  }, [b.x, b.z]);
  ok('Collision : impossible de traverser le lit', inBed === false, `position finale (${b.x.toFixed(2)}, ${b.z.toFixed(2)})`);
  // traversée de porte (chambre -> dégagement)
  await page.evaluate(() => window.__visite.nav.goTo([3.2, 5.9], [1.6, 5.95]));
  await hold(page, 'ArrowUp', 2200);
  b = await state(page);
  ok('Passage des portes : chambre -> dégagement', b.room === 'sas', `pièce=${b.room}`);
  // glisser à la souris
  a = await state(page);
  await page.mouse.move(640, 400); await page.mouse.down(); await page.mouse.move(840, 350, { steps: 8 }); await page.mouse.up();
  b = await state(page);
  ok('Glisser : regarder autour de soi', Math.abs(b.yaw - a.yaw) > 0.2 && Math.abs(b.pitch - a.pitch) > 0.02 && Math.hypot(b.x - a.x, b.z - a.z) < 1e-6);
  // recentrer
  await page.click('#recentrer');
  b = await state(page);
  ok('Recentrer : regard remis à l’horizontale', Math.abs(b.pitch) < 1e-6);
  // pièces
  for (const [id, label] of [['Séjour', 'sejour'], ['Cuisine', 'cuisine'], ['Salle de bain', 'sdb'], ['Chambre', 'chambre'], ['Dégagement', 'sas']]) {
    await page.click(`#pieces button:text-is("${id}")`);
    b = await state(page);
    ok(`Accès direct : ${id}`, b.room === label, `pièce=${b.room}`);
  }
  // mini-plan : clic dans le séjour
  const box = await page.locator('#miniplan').boundingBox();
  const target = await page.evaluate(() => { const m = window.__visite; return null; });
  await page.evaluate(() => window.__visite.nav.goTo([3.25, 5.95], [6.7, 4.2]));
  const pt = await page.evaluate(() => { const mm = document.getElementById('miniplan'); return null; });
  // vue d'ensemble
  await page.click('[data-vue="coupe"]');
  b = await state(page);
  ok('Vue d’ensemble en coupe', b.mode === 'coupe');
  await page.click('[data-vue="visite"]');
  for (const m of ['soir', 'nuit', 'jour']) {
    await page.click(`[data-mode="${m}"]`);
    await page.waitForTimeout(500);
    const cur = await page.evaluate(() => window.__visite.apt.mode);
    ok(`Mode d’éclairage : ${m}`, cur === m);
  }
  ok('Aucune erreur JavaScript (ordinateur)', errors.length === 0, errors.join(' | '));
  await ctx.close();
}

// ------------------------------------------------------------- téléphone
{
  const { ctx, page, errors } = await load({ ...devices['Pixel 7'] });
  const visible = await page.locator('#tactile').isVisible();
  ok('Téléphone : boutons tactiles affichés', visible);
  await page.evaluate(() => window.__visite.nav.goTo([4.4, 4.2], [6.8, 5.0]));
  let a = await state(page);
  const btn = page.locator('#tactile [data-t="avant"]');
  const bb = await btn.boundingBox();
  await tap(page, '#tactile [data-t="avant"]', 900);
  let b = await state(page);
  ok('Téléphone : bouton ▲ avance', Math.hypot(b.x - a.x, b.z - a.z) > 0.3, `${Math.hypot(b.x - a.x, b.z - a.z).toFixed(2)} m`);
  a = b;
  await tap(page, '#tactile [data-t="gauche"]', 700);
  b = await state(page);
  ok('Téléphone : bouton ↺ tourne à gauche sur place', b.yaw > a.yaw + 0.3 && Math.hypot(b.x - a.x, b.z - a.z) < 1e-6);
  // glisser au doigt
  a = b;
  const cdp = await ctx.newCDPSession(page);
  await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x: 200, y: 300 }] });
  for (let i = 1; i <= 8; i++) await cdp.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x: 200 + i * 15, y: 300 }] });
  await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
  await page.waitForTimeout(200);
  b = await state(page);
  ok('Téléphone : glisser au doigt pour regarder', Math.abs(b.yaw - a.yaw) > 0.1, `Δlacet=${(b.yaw - a.yaw).toFixed(2)}`);
  const noScroll = await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth);
  ok('Téléphone : pas de défilement horizontal', noScroll);
  await page.screenshot({ path: '../docs/captures/telephone_chambre.jpg', type: 'jpeg', quality: 85 });
  ok('Aucune erreur JavaScript (téléphone)', errors.length === 0, errors.join(' | '));
  await ctx.close();
}
fs.writeFileSync('../docs/verification.json', JSON.stringify(results, null, 1));
console.log(`${results.filter((r) => r.ok).length}/${results.length} vérifications réussies`);
await browser.close();
