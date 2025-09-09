document.addEventListener('DOMContentLoaded', () => {
  bootstrapAuth();
  const params = new URLSearchParams(window.location.search);
  const currentStation = params.get('station') || 'all';
  const filterSelect = document.getElementById('filterSelect');
  const filtersToggle = document.getElementById('filtersToggle');
  const filtersDrawer = document.getElementById('filtersDrawer');
  const filtersClose = document.getElementById('filtersClose');

  const load = () => loadSustainability(currentStation, filterSelect.value);
  load();
  filterSelect.addEventListener('change', load);
  setInterval(() => load().catch(()=>{}), 60000);

  // Filters drawer
  if (filtersToggle && filtersDrawer){
    const openF = () => { filtersDrawer.classList.remove('hidden'); filtersDrawer.setAttribute('aria-hidden','false'); filtersToggle.setAttribute('aria-expanded','true'); };
    const closeF = () => { filtersDrawer.classList.add('hidden'); filtersDrawer.setAttribute('aria-hidden','true'); filtersToggle.setAttribute('aria-expanded','false'); };
    filtersToggle.addEventListener('click', () => { const opened = !filtersDrawer.classList.contains('hidden'); if (opened) closeF(); else openF(); });
    filtersClose && filtersClose.addEventListener('click', closeF);
    document.addEventListener('click', (e)=>{ if (filtersDrawer.classList.contains('hidden')) return; if (!filtersDrawer.contains(e.target) && e.target !== filtersToggle) closeF(); });
    filterSelect.addEventListener('change', () => closeF());
  }
});

async function bootstrapAuth(){
  try{
    const res = await fetch('/api/stats/auth/me');
    if(res.status === 401){ window.location.href = '/login.html'; return; }
    const me = await res.json();
    const fullName = document.getElementById('userFullName');
    const userEmail = document.getElementById('userEmail');
    if(fullName) fullName.textContent = me.name || '-';
    if(userEmail) userEmail.textContent = me.email || '';
    const btn = document.getElementById('logoutBtn');
    if(btn){ btn.addEventListener('click', async ()=>{ await fetch('/api/stats/auth/logout', { method: 'POST' }); window.location.href = '/login.html'; }); }
  }catch(e){ window.location.href = '/login.html'; }
}

async function loadSustainability(station, filter){
  try{
    // Summary
    const params = new URLSearchParams({ station, filter });
    const summaryRes = await fetch(`/api/stats/energy/summary?${params.toString()}`);
    if (summaryRes.ok){
      const s = await summaryRes.json();
      setText('totalKWh', s.energy_kWh ?? 0);
      setText('co2Red', s.co2_grid_kg ?? 0);
      setText('co2ICE', s.co2_ice_equiv_kg ?? 0);
      setText('co2Evitado', s.co2_avoided_kg ?? 0);
      const a = s.assumptions || {};

      // Store assumptions and draw assumption charts
      window.__assumptions = {
        grid: Number(a.GRID_CO2_KG_PER_KWH || 0.2),
        eff: Number(a.EV_KM_PER_KWH || 6.0),
        ice: Number(a.ICE_CO2_KG_PER_KM || 0.17),
      };
      drawComp100km(window.__assumptions);
      drawSensGrid(window.__assumptions);
      drawSensEff(window.__assumptions);
    }

    // Series
    let period = 'month';
    if (filter === 'mes') period = 'day';
    if (filter === 'diario' || filter === 'dia') period = 'hour';
    const seriesParams = new URLSearchParams({ station, filter, period });
    const seriesRes = await fetch(`/api/stats/energy/series?${seriesParams.toString()}`);
    if (seriesRes.ok){
      const { series } = await seriesRes.json();
      drawEnergySeries(series || [], period);
    }
  }catch(e){ console.warn('Error cargando sostenibilidad', e); }
}

function setText(id, val){ const el = document.getElementById(id); if (el) el.textContent = val; }

function drawEnergySeries(series, period){
  const canvas = document.getElementById('energySeries');
  if (!canvas) return;
  const dpr = Math.max(1, window.devicePixelRatio || 1);
  const card = canvas.parentElement;
  const W = Math.max(360, Math.min(1200, (card.clientWidth || 900) - 32));
  const H = Math.max(380, Math.round(W * 0.6));
  const ctx = setupCanvas(canvas, W, H, dpr);
  let data = series || [];
  if (data.length > 30) data = data.slice(-30);
  const labels = data.map(d => formatPeriodLabel(d.period_start, period));
  const values = data.map(d => d.energy_Wh || 0);
  drawBarChartWithGrid(ctx, labels, values, ['#66BB6A']);
}

// ===== Assumptions visuals =====
function evKgPer100km(gridFactor, evEff){
  return (100 / Math.max(0.1, evEff)) * gridFactor;
}
function iceKgPer100km(iceFactor){
  return 100 * iceFactor;
}
function avoidedPer100km(gridFactor, evEff, iceFactor){
  return iceKgPer100km(iceFactor) - evKgPer100km(gridFactor, evEff);
}

function drawComp100km(a){
  const canvas = document.getElementById('comp100km'); if (!canvas) return;
  const dpr = Math.max(1, window.devicePixelRatio || 1);
  const card = canvas.parentElement; const W = Math.max(360, Math.min(800, (card.clientWidth || 700) - 32));
  const H = Math.max(320, Math.round(W * 0.55));
  const ctx = setupCanvas(canvas, W, H, dpr);
  const ev = evKgPer100km(a.grid, a.eff);
  const ice = iceKgPer100km(a.ice);
  drawBarChartWithGrid(ctx, ['EV (red)', 'ICE'], [ev, ice], ['#03A9F4', '#8BC34A']);
}

function drawSensGrid(a){
  const canvas = document.getElementById('sensGrid'); if (!canvas) return;
  const dpr = Math.max(1, window.devicePixelRatio || 1);
  const card = canvas.parentElement; const W = Math.max(360, Math.min(800, (card.clientWidth || 700) - 32));
  const H = Math.max(320, Math.round(W * 0.55));
  const ctx = setupCanvas(canvas, W, H, dpr);
  const xs = []; const ys = [];
  for (let g = 0.0; g <= 0.8 + 1e-6; g += 0.04){ xs.push(Number(g.toFixed(2))); ys.push(avoidedPer100km(g, a.eff, a.ice)); }
  drawLineChartWithGrid(ctx, xs, ys, '#FFA726', a.grid, (x)=>x.toFixed(2));
}

function drawSensEff(a){
  const canvas = document.getElementById('sensEff'); if (!canvas) return;
  const dpr = Math.max(1, window.devicePixelRatio || 1);
  const card = canvas.parentElement; const W = Math.max(360, Math.min(800, (card.clientWidth || 700) - 32));
  const H = Math.max(320, Math.round(W * 0.55));
  const ctx = setupCanvas(canvas, W, H, dpr);
  const xs = []; const ys = [];
  for (let e = 4.0; e <= 8.0 + 1e-6; e += 0.2){ xs.push(Number(e.toFixed(1))); ys.push(avoidedPer100km(a.grid, e, a.ice)); }
  drawLineChartWithGrid(ctx, xs, ys, '#42A5F5', a.eff, (x)=>x.toFixed(1));
}


function drawLineChartWithGrid(ctx, xs, ys, color, markX, formatX){
  const W = ctx.canvas.clientWidth || parseInt(ctx.canvas.style.width) || 800;
  const H = ctx.canvas.clientHeight || parseInt(ctx.canvas.style.height) || 320;
  ctx.clearRect(0, 0, W, H);
  const left = 56, right = 16, top = 24, bottom = 44;
  const chartW = W - left - right;
  const chartH = H - top - bottom;
  const yMin = Math.min(0, ...ys);
  const yMax = Math.max(1, ...ys);
  const yRange = yMax - yMin || 1;
  const steps = 5;
  const stepVal = niceStep(yRange / steps);
  const axisMax = Math.ceil(yMax / stepVal) * stepVal;
  const axisMin = Math.floor(yMin / stepVal) * stepVal;
  const axisRange = axisMax - axisMin || stepVal;
  // y grid
  ctx.strokeStyle = '#333'; ctx.lineWidth = 1; ctx.font = '12px sans-serif'; ctx.fillStyle = '#aaa'; ctx.textAlign = 'right';
  for (let v = axisMin; v <= axisMax + 1e-9; v += stepVal){
    const y = top + chartH - ((v - axisMin) / axisRange) * chartH;
    ctx.beginPath(); ctx.moveTo(left, y); ctx.lineTo(W - right, y); ctx.stroke();
    ctx.fillText(formatAbbr(v), left - 8, y + 4);
  }
  // x ticks (limit to ~6 labels)
  ctx.textAlign = 'center'; ctx.fillStyle = '#ccc';
  const n = xs.length; const maxLabels = 6; const step = Math.max(1, Math.floor(n / maxLabels));
  xs.forEach((xVal, i) => {
    if (i % step !== 0 && i !== n-1) return;
    const x = left + (i / (n - 1 || 1)) * chartW;
    ctx.fillText(formatX ? formatX(xVal) : String(xVal), x, H - 16);
  });
  // line
  ctx.strokeStyle = color; ctx.lineWidth = 2; ctx.beginPath();
  ys.forEach((yVal, i) => {
    const x = left + (i / (n - 1 || 1)) * chartW;
    const y = top + chartH - ((yVal - axisMin) / axisRange) * chartH;
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  });
  ctx.stroke();
  // mark current
  if (markX !== undefined && markX !== null){
    // find closest index
    let idx = 0; let best = Infinity;
    xs.forEach((v, i)=>{ const d = Math.abs(v - markX); if (d < best){ best = d; idx = i; } });
    const x = left + (idx / (n - 1 || 1)) * chartW;
    const y = top + chartH - ((ys[idx] - axisMin) / axisRange) * chartH;
    ctx.fillStyle = color; ctx.beginPath(); ctx.arc(x, y, 4, 0, Math.PI*2); ctx.fill();
  }
}

function formatPeriodLabel(iso, period){
  try{
    const d = new Date(iso);
    if (period === 'hour') return d.toLocaleTimeString([], {hour: '2-digit'});
    if (period === 'day') return d.toLocaleDateString([], {month: 'short', day: '2-digit'});
    return d.toLocaleDateString([], {year: '2-digit', month: 'short'});
  }catch{ return ''; }
}

function setupCanvas(canvas, cssW, cssH, dpr) {
  canvas.style.width = cssW + 'px';
  canvas.style.height = cssH + 'px';
  canvas.width = Math.floor(cssW * dpr);
  canvas.height = Math.floor(cssH * dpr);
  const ctx = canvas.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return ctx;
}

function drawBarChartWithGrid(ctx, labels, data, colors) {
  const W = ctx.canvas.clientWidth || parseInt(ctx.canvas.style.width) || 900;
  const H = ctx.canvas.clientHeight || parseInt(ctx.canvas.style.height) || 320;
  ctx.clearRect(0, 0, W, H);
  const left = 56, right = 16, top = 24, bottom = 44;
  const chartW = W - left - right;
  const chartH = H - top - bottom;
  const maxVal = Math.max(1, ...data);
  const steps = 5;
  const stepVal = niceStep(maxVal / steps);
  const maxAxis = stepVal * steps;
  ctx.strokeStyle = '#333'; ctx.lineWidth = 1; ctx.font = '12px sans-serif'; ctx.fillStyle = '#aaa'; ctx.textAlign = 'right';
  for (let i = 0; i <= steps; i++) {
    const y = top + chartH - (i / steps) * chartH;
    ctx.beginPath(); ctx.moveTo(left, y); ctx.lineTo(W - right, y); ctx.stroke();
    ctx.fillText(formatAbbr((i * maxAxis) / steps), left - 8, y + 4);
  }
  const groupWidth = chartW / labels.length;
  const barWidth = Math.min(80, groupWidth * 0.5);
  ctx.textAlign = 'center';
  labels.forEach((lab, i) => {
    const xCenter = left + i * groupWidth + groupWidth / 2;
    ctx.fillStyle = '#ccc'; ctx.fillText(lab, xCenter, H - 16);
    const val = data[i]; const h = (val / maxAxis) * chartH;
    const x = xCenter - barWidth / 2; const y = top + chartH - h;
    ctx.fillStyle = colors[i % colors.length]; ctx.fillRect(x, y, barWidth, h);
    ctx.fillStyle = '#ddd'; ctx.fillText(formatAbbr(val), xCenter, Math.max(top + 12, y - 6));
  });
}

function niceStep(raw) {
  const pow10 = Math.pow(10, Math.floor(Math.log10(raw||1)));
  const norm = raw / pow10;
  let step;
  if (norm <= 1) step = 1; else if (norm <= 2) step = 2; else if (norm <= 5) step = 5; else step = 10;
  return step * pow10;
}

function formatAbbr(n) {
  const abs = Math.abs(n);
  if (abs >= 1_000_000) return (n / 1_000_000).toFixed(1).replace(/\.0$/, '') + 'M';
  if (abs >= 1_000) return (n / 1_000).toFixed(1).replace(/\.0$/, '') + 'K';
  return String(n);
}
