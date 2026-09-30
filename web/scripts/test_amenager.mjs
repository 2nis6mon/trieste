// Test du mode « Aménager » : sélection et déplacement d'un meuble à la souris.
import { chromium } from 'playwright-core';
import fs from 'node:fs';
const out = process.argv[2] || '/tmp/amenager.jpg';
const exe = fs.readdirSync('/opt/pw-browsers').filter((d) => d.startsWith('chromium-')).map((d) => `/opt/pw-browsers/${d}/chrome-linux/chrome`).find((p) => fs.existsSync(p));
const b = await chromium.launch({ executablePath: exe, args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
const p = await b.newPage({ viewport: { width: 1280, height: 800 } });
const logs = [];
p.on('pageerror', (e) => logs.push('ERREUR ' + e.message));
await p.goto((process.env.URL || 'http://localhost:5173/') + '?capture=1');
await p.waitForFunction(() => window.__visite?.ready, null, { timeout: 600000 });
await p.evaluate(() => { try { localStorage.clear(); } catch (e) {} });
await p.click('[data-vue="coupe"]');
await p.waitForTimeout(3000);
await p.click('#btn-amenager');
// position écran du lit
const s = await p.evaluate(() => {
  const v = window.__visite; const g = v.mob.pieces.lit.group;
  const w = g.position.clone(); w.y = 0.5; w.project(v.camera);
  return { x: (w.x + 1) / 2 * innerWidth, y: (1 - w.y) / 2 * innerHeight, avant: [g.position.x, g.position.z] };
});
await p.mouse.move(s.x, s.y);
await p.mouse.down();
for (let i = 1; i <= 5; i++) { await p.mouse.move(s.x + i * 12, s.y + i * 6); await p.waitForTimeout(200); }
await p.mouse.up();
await p.click('#amenager [data-rot="90"]');
const apres = await p.evaluate(() => {
  const v = window.__visite; const pc = v.mob.pieces.lit;
  return { sel: document.querySelector('#amenager .nom').textContent, x: pc.x, z: pc.z, r: pc.r, etat: v.mob.state() };
});
await p.waitForTimeout(3000);
await p.screenshot({ path: out, type: 'jpeg', quality: 85, timeout: 180000 });
console.log(JSON.stringify({ avant: s.avant, apres }), logs.join('\n'));
await b.close();
