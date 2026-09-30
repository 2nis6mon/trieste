// Capture ponctuelle : node scripts/vue.mjs sortie.jpg x z lx lz [tangage] [mode] [plafonniers]
import { chromium } from 'playwright-core';
import fs from 'node:fs';
const [out, x, z, lx, lz, pitch = '-0.04', mode = 'jour', pl = '0'] = process.argv.slice(2);
const exe = process.env.CHROMIUM || fs.readdirSync('/opt/pw-browsers').filter((d) => d.startsWith('chromium-')).map((d) => `/opt/pw-browsers/${d}/chrome-linux/chrome`).find((p) => fs.existsSync(p));
const b = await chromium.launch({ executablePath: exe, args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
const p = await b.newPage({ viewport: { width: 1280, height: 800 } });
const logs = [];
p.on('pageerror', (e) => logs.push('ERREUR ' + e.message));
p.on('console', (m) => { if (m.type() === 'error') logs.push(m.text()); });
await p.goto(`${process.env.URL || 'http://localhost:5173/'}?capture=1&mode=${mode}&plafonniers=${pl}`);
await p.waitForFunction(() => window.__visite?.ready, null, { timeout: 600000 });
await p.addStyleTag({ content: '#haut,#pieces,#plan,#recentrer,#tactile,#aide{display:none!important}' });
await p.evaluate(([x, z, lx, lz, pt]) => { const v = window.__visite; v.nav.goTo([x, z], [lx, lz]); v.nav.pitch = pt; }, [+x, +z, +lx, +lz, +pitch]);
await p.waitForTimeout(4000);
await p.screenshot({ path: out, type: 'jpeg', quality: 88, timeout: 180000 });
console.log(logs.join('\n') || 'ok');
await b.close();
