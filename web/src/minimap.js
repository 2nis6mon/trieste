// Mini-plan : dessiné à partir de plan.json et obstacles.json (même géométrie
// que la scène 3D) ; affiche la position et l'orientation du visiteur.
const ROOM_COLORS = {
  chambre: '#e9dcc7', sdb: '#dde3e3', sas: '#e6dfd3', cuisine: '#ecd9c4', sejour: '#efe4d2',
};

export class Minimap {
  constructor(canvas, apt, nav) {
    this.c = canvas;
    this.apt = apt;
    this.nav = nav;
    const xs = [], zs = [];
    for (const w of apt.plan.walls) for (const [x, z] of w.poly) { xs.push(x); zs.push(z); }
    this.box = { x0: Math.min(...xs) - 0.2, x1: Math.max(...xs) + 0.2, z0: Math.min(...zs) - 0.2, z1: Math.max(...zs) + 0.2 };
    canvas.addEventListener('click', (e) => {
      const r = canvas.getBoundingClientRect();
      const [x, z] = this.toPlan(e.clientX - r.left, e.clientY - r.top);
      if (nav.isFree(x, z)) {
        nav.setMode('visite');
        nav.pos.set(x, z);
      }
    });
    this.resize();
    addEventListener('resize', () => this.resize());
  }

  resize() {
    const dpr = Math.min(2, devicePixelRatio || 1);
    const w = this.c.clientWidth, h = this.c.clientHeight;
    this.c.width = w * dpr;
    this.c.height = h * dpr;
    this.dpr = dpr;
    const bw = this.box.x1 - this.box.x0, bh = this.box.z1 - this.box.z0;
    this.s = Math.min(w / bw, h / bh);
    this.ox = (w - bw * this.s) / 2;
    this.oy = (h - bh * this.s) / 2;
  }

  toPx(x, z) { return [this.ox + (x - this.box.x0) * this.s, this.oy + (z - this.box.z0) * this.s]; }
  toPlan(px, py) { return [(px - this.ox) / this.s + this.box.x0, (py - this.oy) / this.s + this.box.z0]; }

  poly(ctx, pts) {
    ctx.beginPath();
    pts.forEach(([x, z], i) => { const [a, b] = this.toPx(x, z); i ? ctx.lineTo(a, b) : ctx.moveTo(a, b); });
    ctx.closePath();
  }

  draw() {
    const ctx = this.c.getContext('2d');
    ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    ctx.clearRect(0, 0, this.c.width, this.c.height);
    const plan = this.apt.plan;
    this.poly(ctx, plan.terrace.poly);
    ctx.fillStyle = '#c9c6c0';
    ctx.fill();
    for (const id of ['sejour', 'cuisine', 'chambre', 'sdb', 'sas']) {
      const r = plan.rooms.find((x) => x.id === id);
      this.poly(ctx, r.poly);
      ctx.fillStyle = ROOM_COLORS[id];
      ctx.fill();
    }
    ctx.fillStyle = 'rgba(120,110,100,0.45)';
    for (const ob of this.apt.obstacles) { this.poly(ctx, ob.poly); ctx.fill(); }
    for (const o of plan.openings) {
      this.poly(ctx, o.quad);
      ctx.fillStyle = o.type === 'window' || o.type === 'door_glazed' ? '#9ec3d6' : '#f3eee6';
      ctx.fill();
    }
    ctx.fillStyle = '#26221f';
    for (const w of plan.walls) { this.poly(ctx, w.poly); ctx.fill(); }
    // visiteur
    const [px, py] = this.toPx(this.nav.pos.x, this.nav.pos.y);
    const yaw = this.nav.yaw;
    const dx = -Math.sin(yaw), dz = -Math.cos(yaw);
    const fov = 0.55;
    ctx.fillStyle = 'rgba(214,110,62,0.28)';
    ctx.beginPath();
    ctx.moveTo(px, py);
    for (const a of [-fov, fov]) {
      const c = Math.cos(a), s = Math.sin(a);
      ctx.lineTo(px + (dx * c - dz * s) * 34, py + (dx * s + dz * c) * 34);
    }
    ctx.closePath();
    ctx.fill();
    ctx.fillStyle = '#d0602f';
    ctx.strokeStyle = '#fff';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.arc(px, py, 5, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
  }
}
