// Captures d'écran et tests de navigation automatisés (Chromium sans écran).
// Usage : node scripts/captures.mjs [url] [dossier]
//   ex. : npx vite preview --port 4173 & node scripts/captures.mjs http://localhost:4173/ ../docs/captures
import { chromium } from 'playwright-core';
import fs from 'node:fs';
import path from 'node:path';

const url = process.argv[2] || 'http://localhost:5173/';
const out = process.argv[3] || '../docs/captures';
const only = process.argv[4] ? process.argv[4].split(',') : null;
fs.mkdirSync(out, { recursive: true });

const exe = process.env.CHROMIUM || fs.readdirSync('/opt/pw-browsers').filter((d) => d.startsWith('chromium-')).map((d) => `/opt/pw-browsers/${d}/chrome-linux/chrome`).find((p) => fs.existsSync(p));
const browser = await chromium.launch({
  executablePath: exe,
  args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'],
});

async function open(page, q) {
  const logs = [];
  page.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') logs.push(m.text()); });
  page.on('pageerror', (e) => logs.push('ERREUR ' + e.message));
  await page.goto(url + '?capture=1&' + q, { waitUntil: 'load' });
  await page.waitForFunction(() => window.__visite?.ready, null, { timeout: 600000 });
  await page.addStyleTag({ content: '#haut,#pieces,#plan,#recentrer,#tactile,#aide{display:none!important}' });
  await page.waitForTimeout(1500);
  return logs;
}

async function shot(page, name, setup) {
  if (setup) await page.evaluate(setup);
  await page.waitForTimeout(2500);
  await page.screenshot({ path: path.join(out, name + '.jpg'), type: 'jpeg', quality: 88 });
  console.log('capture', name);
}

const VIEWS = {
  chambre_porte: [[3.0, 6.1], [6.6, 4.0]],
  chambre_lit: [[6.3, 5.5], [3.6, 4.0]],
  chambre_fenetres: [[4.1, 4.1], [7.0, 5.8]],
  sejour_fenetre: [[3.0, 9.6], [7.9, 9.4]],
  sejour_entree: [[6.8, 10.3], [1.0, 9.0]],
  cuisine: [[2.75, 7.85], [5.4, 6.75]],
  salle_de_bain: [[2.72, 4.45], [4.4, 2.2]],
  buanderie: [[2.55, 6.25], [1.05, 5.0]],
};

const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
const logs = await open(page, 'piece=chambre');
for (const mode of ['jour', 'soir', 'nuit']) {
  await page.evaluate((m) => window.__visite.setMode(m), mode);
  await page.waitForTimeout(1500);
  for (const [name, [p, l]] of Object.entries(VIEWS)) {
    if (only && !only.includes(name)) continue;
    await shot(page, `${name}_${mode}`, `window.__visite.nav.goTo(${JSON.stringify(p)}, ${JSON.stringify(l)})`);
  }
}
await shot(page, 'vue_ensemble_jour', `window.__visite.setMode('jour').then(()=>window.__visite.nav.setMode('coupe'))`);
await shot(page, 'chambre_lit_nuit_plafonniers', `window.__visite.nav.setMode('visite'); window.__visite.setMode('nuit', true).then(()=>window.__visite.nav.goTo([6.3,5.5],[3.6,4.0]))`);
console.log('messages console :', logs.slice(0, 20));
await browser.close();
