document.addEventListener('DOMContentLoaded', () => {
  const params = new URLSearchParams(window.location.search);
  const currentStation = params.get('station') || 'all';
  const filterSelect = document.getElementById('filterSelect');
  const toggleBtn = document.getElementById('toggleUsers');
  const usersSection = document.getElementById('usersSection');

  let usersLoaded = false;

  const loadStats = () => {
    const st = currentStation;
    const flt = filterSelect.value;
    loadSummary(st, flt);
    loadRanking(st, flt);
    loadHabitsGeneral(st, flt);
    loadLoyalty(st, flt);
    if (!usersSection.classList.contains('hidden')) {
      loadDrivers(st, flt);
    }
  };

  filterSelect.addEventListener('change', loadStats);

  toggleBtn.addEventListener('click', () => {
    const hidden = usersSection.classList.toggle('hidden');
    usersSection.setAttribute('aria-hidden', hidden ? 'true' : 'false');
    toggleBtn.textContent = hidden ? 'Ver conductores' : 'Ocultar conductores';
    if (!hidden && !usersLoaded) {
      usersLoaded = true;
      loadDrivers(currentStation, filterSelect.value);
    } else if (!hidden) {
      loadDrivers(currentStation, filterSelect.value);
    }
  });

  // Cargar estadísticas inicialmente
  loadStats();
});

// ========= Conductores: listado paginado =========
let currentUsers = [];
let currentPage = 1;
const usersPerPage = 12;

async function loadDrivers(station, filter){
  try{
    const res = await fetch(`/api/stats/users/${encodeURIComponent(station)}?filter=${encodeURIComponent(filter)}`);
    const data = await res.json();
    renderUsers(data.usuarios || []);
  }catch(e){ console.error(e); }
}

function renderUsers(users){
  currentUsers = users;
  currentPage = 1;
  showPage(currentPage);
  setupPagination();
}

function showPage(page){
  const container = document.getElementById('conductoresContainer');
  container.innerHTML = '';
  const start = (page-1) * usersPerPage;
  const pageUsers = currentUsers.slice(start, start + usersPerPage);
  pageUsers.forEach(u => {
    const card = document.createElement('div');
    card.className = 'user-card';
    const tipo = mapVehicleType(u.category);
    const modelo = u.model ? u.model : '-';
    card.innerHTML = `
      <h4>${u.user_name || u.user_code}</h4>
      <p><strong>Cargas:</strong> ${u.total_cargas ?? 0}</p>
      <p><strong>Energía:</strong> ${u.total_energy_Wh ?? 0} Wh</p>
      <p><strong>Modelo:</strong> ${modelo}</p>
      <p><strong>Tipo:</strong> ${tipo}</p>`;
    container.appendChild(card);
  });
  document.getElementById('pageInfo').textContent = `Página ${page} de ${Math.max(1, Math.ceil(currentUsers.length / usersPerPage))}`;
}

function setupPagination(){
  document.getElementById('prevPage').onclick = () => {
    if(currentPage > 1){ currentPage--; showPage(currentPage); }
  };
  document.getElementById('nextPage').onclick = () => {
    if(currentPage < Math.ceil(currentUsers.length / usersPerPage)){
      currentPage++; showPage(currentPage);
    }
  };
}

function mapVehicleType(category){
  if(!category) return '-';
  const c = String(category).toUpperCase();
  if(c === 'EV') return 'EV';
  if(c === 'PHEV') return 'PHEV';
  return '-';
}

// ========= Ranking =========
async function loadRanking(station, filter){
  try{
    const res = await fetch(`/api/stats/drivers/ranking?station=${encodeURIComponent(station)}&filter=${encodeURIComponent(filter)}&limit=10`);
    const data = await res.json();
    const canvas = document.getElementById('rankingChart');
    const labels = data.items.map(it => (it.user_name || it.user_code || ''));
    const values = data.items.map(it => it.total_cargas || 0);
    // KPI: top conductor
    if (data.items[0]) {
      document.getElementById('kpiTopDriver').textContent = `${(data.items[0].user_name || data.items[0].user_code || '').slice(0,24)} • ${data.items[0].total_cargas}`;
    } else {
      document.getElementById('kpiTopDriver').textContent = '-';
    }
    // Horizontal bars responsive: width from parent, height by rows
    const parentW = canvas.parentElement ? canvas.parentElement.clientWidth : 520;
    const width = Math.max(320, Math.min(920, parentW - 16));
    const height = Math.max(220, Math.min(520, 28 * labels.length + 40));
    setupCanvas(canvas, width, height, Math.max(1, window.devicePixelRatio||1));
    drawHBar(canvas, labels, values, '#ff9800');
  }catch(e){ console.error(e); }
}

// ========= Hábitos (hora del día) =========
async function loadHabitsGeneral(station, filter){
  try{
    const res = await fetch(`/api/stats/habits/general?station=${encodeURIComponent(station)}&filter=${encodeURIComponent(filter)}`);
    const data = await res.json();
    const canvas = document.getElementById('habitsGeneral');
    const parentW = canvas.parentElement ? canvas.parentElement.clientWidth : 600;
    // ancho seguro para móvil sin desbordar
    const width = Math.max(260, parentW - 24);
    setupCanvas(canvas, width, 140, Math.max(1, window.devicePixelRatio||1));
    drawHeatStrip(canvas, data.histogram || new Array(24).fill(0));
  }catch(e){ console.error(e); }
}

// ========= Fidelidad =========
async function loadLoyalty(station, filter){
  try{
    const res = await fetch(`/api/stats/drivers/loyalty?station=${encodeURIComponent(station)}&filter=${encodeURIComponent(filter)}`);
    const data = await res.json();
    const canvas = document.getElementById('loyaltyChart');
    const dpr = Math.max(1, window.devicePixelRatio||1);
    const parentW = canvas.parentElement ? canvas.parentElement.clientWidth : 360;
    const width = Math.max(260, parentW - 24);
    setupCanvas(canvas, width, 240, dpr);
    drawDonut(canvas, data.recurrentes||0, (data.recurrentes||0) + (data.nuevos||0));
  }catch(e){ console.error(e); }
}

// ========= Alertas =========
// ========= Canvas helpers =========
function setupCanvas(canvas, cssW, cssH, dpr){
  canvas.style.width = cssW + 'px';
  canvas.style.height = cssH + 'px';
  canvas.width = Math.floor(cssW * dpr);
  canvas.height = Math.floor(cssH * dpr);
  const ctx = canvas.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return ctx;
}

function drawBars(canvas, labels, data, colors){
  const dpr = Math.max(1, window.devicePixelRatio||1);
  const ctx = canvas.getContext('2d');
  const W = parseInt(canvas.style.width)||400; const H = parseInt(canvas.style.height)||220;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0,0,W,H);
  const left=44,right=12,top=16,bottom=44; const chartW=W-left-right, chartH=H-top-bottom;
  const maxVal=Math.max(1, ...data);
  const steps=4; const stepVal=Math.ceil(maxVal/steps); const maxAxis=stepVal*steps;
  ctx.strokeStyle='#333'; ctx.lineWidth=1; ctx.font='12px sans-serif'; ctx.fillStyle='#aaa'; ctx.textAlign='right';
  for(let i=0;i<=steps;i++){
    const y=top+chartH-(i/steps)*chartH; ctx.beginPath(); ctx.moveTo(left,y); ctx.lineTo(W-right,y); ctx.stroke(); ctx.fillText(String(Math.round((i*maxAxis)/steps)), left-8, y+4);
  }
  const groupW=chartW/labels.length; const barW=Math.min(26, groupW*0.7); ctx.textAlign='center';
  labels.forEach((lab,i)=>{
    const xC=left+i*groupW+groupW/2; const v=data[i]||0; const h=(v/maxAxis)*chartH; const x=xC-barW/2; const y=top+chartH-h; ctx.fillStyle=colors[i%colors.length]; ctx.fillRect(x,y,barW,h); ctx.fillStyle='#ccc'; ctx.fillText(lab,xC,H-16);
  });
}

// Donut simple
function drawDonut(canvas, value, total){
  const dpr = Math.max(1, window.devicePixelRatio||1);
  const ctx = canvas.getContext('2d');
  const W = parseInt(canvas.style.width)||320; const H = parseInt(canvas.style.height)||240;
  ctx.setTransform(dpr,0,0,dpr,0,0);
  ctx.clearRect(0,0,W,H);
  const cx=W/2, cy=H/2, r=Math.min(W,H)/3; const pct= total>0? Math.min(1,value/total):0;
  ctx.beginPath(); ctx.arc(cx,cy,r,0,Math.PI*2); ctx.strokeStyle='#333'; ctx.lineWidth=22; ctx.stroke();
  ctx.beginPath(); ctx.arc(cx,cy,r,-Math.PI/2,-Math.PI/2+Math.PI*2*pct); ctx.strokeStyle='#8BC34A'; ctx.lineWidth=22; ctx.stroke();
  ctx.font='16px sans-serif'; ctx.fillStyle='#ddd'; ctx.textAlign='center'; ctx.fillText(`${Math.round(pct*100)}% recurrentes`, cx, cy+6);
}

// Horizontal bars (clean labels)
function drawHBar(canvas, labels, data, color){
  const dpr = Math.max(1, window.devicePixelRatio||1);
  const ctx = canvas.getContext('2d');
  const parentW = canvas.parentElement ? canvas.parentElement.clientWidth : 520;
  const W = Math.max(320, Math.min(parentW - 16, 920));
  canvas.style.width = W + 'px';
  const H = parseInt(canvas.style.height)||260;
  ctx.setTransform(dpr,0,0,dpr,0,0);
  ctx.clearRect(0,0,W,H);
  // Dynamic left margin: smaller on narrow screens to avoid clipping
  const right=24,top=8,bottom=8;
  const left = Math.min(140, Math.max(80, Math.floor(W * 0.22)));
  const chartW=W-left-right; const rowH= (H-top-bottom)/Math.max(1, labels.length);
  const endPad = 28; // reserva al extremo derecho para que la barra no toque el borde
  const barMaxW = Math.max(40, chartW - endPad);
  const maxVal = Math.max(1, ...data);
  ctx.font='12px sans-serif';
  labels.forEach((lab,i)=>{
    const v = data[i]||0; const y = top + i*rowH + rowH*0.2; const h = Math.max(10, rowH*0.6);
    // ancho de barra con margen al final para no sobresalir
    const w = Math.max(2, Math.min(barMaxW, Math.round((v/maxVal) * barMaxW)));
    // Label (left)
    ctx.textAlign='right'; ctx.fillStyle='#ddd';
    const maxChars = W < 380 ? 14 : (W < 480 ? 18 : 22);
    const label = lab.length>maxChars ? lab.slice(0,maxChars-3) + '…' : lab;
    ctx.fillText(label, left-8, y + h - 2);
    // Bar with rounded corners
    ctx.fillStyle=color;
    const r = Math.min(8, h/2);
    roundRect(ctx, left, y, w, h, r); ctx.fill();
    // Value pill (si la barra es corta, mostrar al final, fuera pero dentro del área)
    const pillW = 28, pillH = 16; const py = y + (h - pillH)/2;
    let px = left + w - pillW - 6; // por defecto, dentro del final de la barra
    let inside = true;
    if (w < pillW + 12){
      // barra muy corta: ubicar la píldora justo después de la barra, sin salir del chart
      px = left + Math.min(barMaxW - pillW, w + 6);
      inside = false;
    }
    // Dibujar píldora y texto
    ctx.fillStyle = inside ? 'rgba(0,0,0,0.35)' : 'rgba(0,0,0,0.25)';
    roundRect(ctx, px, py, pillW, pillH, 8); ctx.fill();
    ctx.fillStyle='#ff9800'; ctx.textAlign='center'; ctx.font='11px sans-serif';
    ctx.fillText(String(v), px + pillW/2, py + pillH - 4);
  });
}

// Compact hourly heat strip (0..23)
function drawHeatStrip(canvas, hist){
  const dpr = Math.max(1, window.devicePixelRatio||1);
  const ctx = canvas.getContext('2d');
  const W = parseInt(canvas.style.width)||420; const H = parseInt(canvas.style.height)||60;
  ctx.setTransform(dpr,0,0,dpr,0,0);
  ctx.clearRect(0,0,W,H);
  const cols = 24; const gap=2; const pad=10; const cellW = (W - pad*2 - gap*(cols-1)) / cols; const cellH = H - pad*2 - 10;
  const max = Math.max(1, ...hist);
  for(let i=0;i<cols;i++){
    const v = hist[i]||0; const intensity = v/max; const x = pad + i*(cellW+gap); const y = pad;
    const base = 0.15 + 0.75*intensity;
    ctx.fillStyle = `rgba(255,152,0,${base})`;
    ctx.fillRect(x,y,cellW,cellH);
  }
  // Minimal ticks 0, 6, 12, 18, 23
  ctx.fillStyle='#888'; ctx.font='10px sans-serif'; ctx.textAlign='center';
  ;[0,6,12,18,23].forEach(i=>{ const x = pad + i*(cellW+gap) + cellW/2; ctx.fillText(String(i), x, H-2); });
}

// helper to draw rounded rectangles
function roundRect(ctx, x, y, w, h, r){
  ctx.beginPath();
  ctx.moveTo(x+r, y);
  ctx.arcTo(x+w, y, x+w, y+h, r);
  ctx.arcTo(x+w, y+h, x, y+h, r);
  ctx.arcTo(x, y+h, x, y, r);
  ctx.arcTo(x, y, x+w, y, r);
  ctx.closePath();
}

// Summary KPIs
async function loadSummary(station, filter){
  try{
    const res = await fetch(`/api/stats/drivers/summary?station=${encodeURIComponent(station)}&filter=${encodeURIComponent(filter)}&threshold=2.5`);
    const data = await res.json();
    document.getElementById('kpiDrivers').textContent = data.total_drivers ?? 0;
    document.getElementById('kpiCharges').textContent = data.total_charges ?? 0;
    document.getElementById('kpiAvg').textContent = (data.avg_charges_per_driver ?? 0).toFixed(1);
  }catch(e){ console.error(e); }
}
