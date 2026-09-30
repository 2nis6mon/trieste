// Prépare une version « page unique + fichiers associés » du site (dist/),
// pour une publication comme page web privée : CSS et JS intégrés dans la page,
// maquette, lightmaps, textures et photos servis comme fichiers voisins.
import fs from 'node:fs';
import path from 'node:path';

const dist = path.resolve('dist');
let html = fs.readFileSync(path.join(dist, 'index.html'), 'utf8');
// CSS intégré
html = html.replace(/<link rel="stylesheet"[^>]*href="\.\/(assets\/[^"]+\.css)"[^>]*>/g, (_, f) =>
  `<style>${fs.readFileSync(path.join(dist, f), 'utf8')}</style>`);
// JS intégré (module)
let js = '';
html = html.replace(/<script type="module"[^>]*src="\.\/(assets\/[^"]+\.js)"[^>]*><\/script>/g, (_, f) => {
  js = fs.readFileSync(path.join(dist, f), 'utf8');
  return '';
});
const title = html.match(/<title>[\s\S]*?<\/title>/)[0];
const style = (html.match(/<style>[\s\S]*?<\/style>/g) || []).join('\n');
const body = html.match(/<body>([\s\S]*)<\/body>/)[1];
const page = `${title}\n${style}\n${body}\n<script type="module">${js.replace(/<\/script>/g, '<\\/script>')}</script>\n`;
fs.writeFileSync(path.join(dist, 'visite.html'), page);
// liste des fichiers à publier à côté de la page
const files = {};
const walk = (d) => {
  for (const f of fs.readdirSync(d)) {
    const p = path.join(d, f);
    if (fs.statSync(p).isDirectory()) walk(p);
    else {
      const rel = path.relative(dist, p);
      if (rel.startsWith('assets/') || rel === 'index.html' || rel === 'visite.html' || rel.startsWith('draco/')) continue;
      files[rel] = p;
    }
  }
};
walk(dist);
fs.writeFileSync(path.join(dist, 'fichiers.json'), JSON.stringify(files, null, 1));
const total = Object.values(files).reduce((s, p) => s + fs.statSync(p).size, 0);
console.log('page', (page.length / 1e6).toFixed(2), 'Mo ;', Object.keys(files).length, 'fichiers,', (total / 1e6).toFixed(1), 'Mo');
