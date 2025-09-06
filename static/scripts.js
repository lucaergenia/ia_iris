document.addEventListener("DOMContentLoaded", () => {
  // Auth: fetch user and wire logout
  bootstrapAuth();
  const stationSelect = document.getElementById("stationSelect");
  const filterSelect = document.getElementById("filterSelect");
  const navToggle = document.getElementById("navToggle");
  const navMenu = document.getElementById("navMenu");
  const filtersToggle = document.getElementById('filtersToggle');
  const filtersDrawer = document.getElementById('filtersDrawer');
  const filtersClose = document.getElementById('filtersClose');
  const userBtn = document.getElementById('userBtn');
  const userMenu = document.getElementById('userMenu');
  const btnUnclassified = document.getElementById("btnUnclassified");
  const panelUnc = document.getElementById("unclassifiedPanel");
  const listUnc = document.getElementById("unclassifiedList");
  const closeUnc = document.getElementById("closeUnclassified");
  const openStreaming = document.getElementById("openStreaming");
  const modal = document.getElementById("streamModal");
  const modalImg = document.getElementById("rtspModalImg");
  const closeBtn = document.getElementById("closeStreaming");
  const backdrop = document.getElementById("streamBackdrop");
  const resizeBtn = document.getElementById("resizeStreaming");
  const fullscreenBtn = document.getElementById("fullscreenStreaming");

  loadStationData(stationSelect.value, filterSelect.value);

  stationSelect.addEventListener("change", () => {
    loadStationData(stationSelect.value, filterSelect.value);
  });

  filterSelect.addEventListener("change", () => {
    loadStationData(stationSelect.value, filterSelect.value);
  });

  // Auto-actualización no intrusiva cada 60s
  setInterval(() => {
    loadStationData(stationSelect.value, filterSelect.value).catch(() => {});
  }, 60000);

  // Unclassified UI
  if (btnUnclassified && panelUnc && listUnc) {
    const toggle = async () => {
      const opening = panelUnc.classList.contains('hidden');
      if (opening) {
        await renderUnclassified(listUnc, stationSelect.value, filterSelect.value);
        panelUnc.classList.remove('hidden');
        panelUnc.setAttribute('aria-hidden','false');
      } else {
        panelUnc.classList.add('hidden');
        panelUnc.setAttribute('aria-hidden','true');
      }
    };
    btnUnclassified.addEventListener('click', toggle);
    closeUnc && closeUnc.addEventListener('click', () => {
      panelUnc.classList.add('hidden');
      panelUnc.setAttribute('aria-hidden','true');
    });
    // refrescar contenido si cambian filtros mientras está abierto
    const refreshIfOpen = () => {
      if (!panelUnc.classList.contains('hidden')) {
        renderUnclassified(listUnc, stationSelect.value, filterSelect.value).catch(()=>{});
      }
    };
    stationSelect.addEventListener('change', refreshIfOpen);
    filterSelect.addEventListener('change', refreshIfOpen);
  }

  // Nav dropdown
  if (navToggle && navMenu){
    const close = () => { navMenu.classList.add('hidden'); navToggle.setAttribute('aria-expanded','false'); };
    const open = () => { navMenu.classList.remove('hidden'); navToggle.setAttribute('aria-expanded','true'); };
    navToggle.addEventListener('click', () => {
      if (navMenu.classList.contains('hidden')) open(); else close();
    });
    document.addEventListener('click', (e) => {
      if (!navMenu.contains(e.target) && e.target !== navToggle){ close(); }
    });
  }

  // User dropdown
  if (userBtn && userMenu){
    const close = () => { userMenu.classList.add('hidden'); userBtn.setAttribute('aria-expanded','false'); };
    const open = () => { userMenu.classList.remove('hidden'); userBtn.setAttribute('aria-expanded','true'); };
    userBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      if (userMenu.classList.contains('hidden')) open(); else close();
    });
    document.addEventListener('click', (e) => {
      if (!userMenu.contains(e.target) && e.target !== userBtn) close();
    });
  }

  // Filters drawer
  if (filtersToggle && filtersDrawer){
    const openF = () => { filtersDrawer.classList.remove('hidden'); filtersDrawer.setAttribute('aria-hidden','false'); filtersToggle.setAttribute('aria-expanded','true'); };
    const closeF = () => { filtersDrawer.classList.add('hidden'); filtersDrawer.setAttribute('aria-hidden','true'); filtersToggle.setAttribute('aria-expanded','false'); };
    filtersToggle.addEventListener('click', () => {
      const opened = !filtersDrawer.classList.contains('hidden');
      if (opened) closeF(); else openF();
    });
    filtersClose && filtersClose.addEventListener('click', closeF);
    document.addEventListener('click', (e)=>{
      if (filtersDrawer.classList.contains('hidden')) return;
      if (!filtersDrawer.contains(e.target) && e.target !== filtersToggle) closeF();
    });
    // Aplicar y cerrar al cambiar (opcional deja abierto)
    stationSelect.addEventListener('change', () => closeF());
    filterSelect.addEventListener('change', () => closeF());
  }
});

async function bootstrapAuth(){
  try{
    const res = await fetch('/api/stats/auth/me');
    if(res.status === 401){
      window.location.href = '/login.html';
      return;
    }
    const me = await res.json();
    const userName = document.getElementById('userName');
    if(userName) userName.textContent = me.name || me.email; // legacy element if present
    const fullName = document.getElementById('userFullName');
    const userEmail = document.getElementById('userEmail');
    if(fullName) fullName.textContent = me.name || '-';
    if(userEmail) userEmail.textContent = me.email || '';
    const btn = document.getElementById('logoutBtn');
    if(btn){
      btn.addEventListener('click', async ()=>{
        await fetch('/api/stats/auth/logout', { method: 'POST' });
        window.location.href = '/login.html';
      });
    }
  }catch(e){
    window.location.href = '/login.html';
  }
}

async function renderUnclassified(ul, station, filter){
  const url = new URL('/api/stats/unclassified-models', window.location.origin);
  url.searchParams.set('station', station || 'all');
  url.searchParams.set('filter', filter || 'total');
  const res = await fetch(url);
  if(!res.ok){
    ul.innerHTML = '<li>Error cargando no clasificados</li>';
    return;
  }
  const data = await res.json();
  const items = data.items || [];
  ul.innerHTML = items.length
    ? items.map(it => `<li>${escapeHtml((it.brand||'-') + ' ' + (it.model||'-'))} — ${it.count}</li>`).join('')
    : '<li>No hay modelos sin clasificar</li>';
}

function escapeHtml(s){
  return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','\'':'&#39;'}[c]));
}

async function loadStationData(station, filter) {
  try {
    const statsRes = await fetch(`/api/stats/last?station=${encodeURIComponent(station)}&filter=${encodeURIComponent(filter)}`);
    if (!statsRes.ok) throw new Error(`❌ Error al obtener datos de ${station} con filtro ${filter}`);
    const stats = await statsRes.json();
    renderStats(stats);
    drawCharts(stats);
  } catch (error) {
    console.error(error);
  }
}

function renderStats(stats) {
  document.getElementById("totalCargas").textContent = stats.total_cargas ?? 0;
  document.getElementById("totalUsuarios").textContent = stats.total_usuarios ?? 0;
  document.getElementById("totalEnergia").textContent = stats.total_energy_Wh ?? 0;

  // ✅ Nuevas tarjetas de vehículos
  document.getElementById("cochesHibridos").textContent = stats.coches_hibridos ?? 0;
  document.getElementById("cochesElectricos").textContent = stats.coches_electricos ?? 0;
  document.getElementById("cochesTotales").textContent = stats.coches_totales ?? 0;
}

/* ==== Gráficas en dashboard ==== */
function drawCharts(stats) {
  const barsCU = document.getElementById('barsCU');
  const barsEnergy = document.getElementById('barsEnergy');
  const pie = document.getElementById('pieCanvas');
  if ((!barsCU && !barsEnergy) || !pie) return;

  const dpr = Math.max(1, window.devicePixelRatio || 1);
  if (barsCU) {
    const barsCard1 = barsCU.parentElement;
    const barsW1 = Math.max(360, Math.min(1200, (barsCard1.clientWidth || 900) - 32));
    const barsH1 = Math.max(380, Math.round(barsW1 * 0.6));
    const ctx1 = setupCanvas(barsCU, barsW1, barsH1, dpr);
    drawBarChartWithGrid(
      ctx1,
      ["Cargas", "Usuarios"],
      [stats.total_cargas || 0, stats.total_usuarios || 0],
      ["#ff9800", "#4CAF50"]
    );
  }
  if (barsEnergy) {
    const barsCard2 = barsEnergy.parentElement;
    const barsW2 = Math.max(360, Math.min(1200, (barsCard2.clientWidth || 900) - 32));
    const barsH2 = Math.max(380, Math.round(barsW2 * 0.6));
    const ctx2 = setupCanvas(barsEnergy, barsW2, barsH2, dpr);
    drawBarChartWithGrid(
      ctx2,
      ["Energía (Wh)"],
      [stats.total_energy_Wh || 0],
      ["#03A9F4"]
    );
  }
  const pieCard = pie.parentElement;
  const pieW = Math.max(360, Math.min(800, (pieCard.clientWidth || 420) - 32));
  const pieH = Math.max(360, Math.round(pieW * 0.75));
  const pieCtx = setupCanvas(pie, pieW, pieH, dpr);
  drawPieChart(
    pieCtx,
    [stats.coches_electricos || 0, stats.coches_hibridos || 0],
    ["#03A9F4", "#8BC34A"],
    ["EV", "PHEV"]
  );
}

async function loadEnergyData(station, filter){
  try{
    const params = new URLSearchParams({ station, filter });
    const summaryRes = await fetch(`/api/stats/energy/summary?${params.toString()}`);
    if (summaryRes.ok){
      const summary = await summaryRes.json();
      const el = document.getElementById('co2Evitado');
      if (el) el.textContent = summary.co2_avoided_kg ?? 0;
    }

    // Elegir periodo por filtro por defecto
    let period = 'month';
    if (filter === 'mes') period = 'day';
    if (filter === 'diario' || filter === 'dia') period = 'hour';
    const seriesParams = new URLSearchParams({ station, filter, period });
    const seriesRes = await fetch(`/api/stats/energy/series?${seriesParams.toString()}`);
    if (seriesRes.ok){
      const { series } = await seriesRes.json();
      drawEnergySeries(series || [], period);
    }
  } catch(e){
    console.warn('Sostenibilidad no disponible:', e);
  }
}

function drawEnergySeries(series, period){
  const canvas = document.getElementById('energySeries');
  if (!canvas) return;
  const dpr = Math.max(1, window.devicePixelRatio || 1);
  const card = canvas.parentElement;
  const W = Math.max(360, Math.min(1200, (card.clientWidth || 900) - 32));
  const H = Math.max(380, Math.round(W * 0.6));
  const ctx = setupCanvas(canvas, W, H, dpr);

  // Preparar labels compactos y datos (limitar a 30 puntos para legibilidad)
  let data = series || [];
  if (data.length > 30) data = data.slice(-30);
  const labels = data.map(d => formatPeriodLabel(d.period_start, period));
  const values = data.map(d => d.energy_Wh || 0);
  drawBarChartWithGrid(ctx, labels, values, ["#66BB6A"]);
}

function formatPeriodLabel(iso, period){
  try{
    const d = new Date(iso);
    if (period === 'hour'){
      return d.toLocaleTimeString([], {hour: '2-digit'});
    }
    if (period === 'day'){
      return d.toLocaleDateString([], {month: 'short', day: '2-digit'});
    }
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

  // y grid and axis
  const steps = 5;
  const stepVal = niceStep(maxVal / steps);
  const maxAxis = stepVal * steps;
  ctx.strokeStyle = '#333';
  ctx.lineWidth = 1;
  ctx.font = '12px sans-serif';
  ctx.fillStyle = '#aaa';
  ctx.textAlign = 'right';
  for (let i = 0; i <= steps; i++) {
    const y = top + chartH - (i / steps) * chartH;
    ctx.beginPath();
    ctx.moveTo(left, y);
    ctx.lineTo(W - right, y);
    ctx.stroke();
    ctx.fillText(formatAbbr((i * maxAxis) / steps), left - 8, y + 4);
  }

  const groupWidth = chartW / labels.length;
  const barWidth = Math.min(80, groupWidth * 0.5);

  // x labels and bars
  ctx.textAlign = 'center';
  labels.forEach((lab, i) => {
    const xCenter = left + i * groupWidth + groupWidth / 2;
    // label
    ctx.fillStyle = '#ccc';
    ctx.fillText(lab, xCenter, H - 16);
    // bar
    const val = data[i];
    const h = (val / maxAxis) * chartH;
    const x = xCenter - barWidth / 2;
    const y = top + chartH - h;
    ctx.fillStyle = colors[i % colors.length];
    ctx.fillRect(x, y, barWidth, h);
    // value label
    ctx.fillStyle = '#ddd';
    ctx.fillText(formatAbbr(val), xCenter, Math.max(top + 12, y - 6));
  });
}

function niceStep(raw) {
  const pow10 = Math.pow(10, Math.floor(Math.log10(raw||1)));
  const norm = raw / pow10;
  let step;
  if (norm <= 1) step = 1; else if (norm <= 2) step = 2; else if (norm <= 5) step = 5; else step = 10;
  return step * pow10;
}

function drawPieChart(ctx, data, colors, labels) {
  const W = ctx.canvas.clientWidth || parseInt(ctx.canvas.style.width) || 360;
  const H = ctx.canvas.clientHeight || parseInt(ctx.canvas.style.height) || 300;
  ctx.clearRect(0, 0, W, H);

  const total = data.reduce((a, b) => a + b, 0) || 1;
  const cx = W / 2;
  const cy = H / 2 - 10;
  const r = Math.min(W, H) / 3;
  let start = -Math.PI / 2;
  data.forEach((val, i) => {
    const angle = (val / total) * Math.PI * 2;
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.arc(cx, cy, r, start, start + angle);
    ctx.closePath();
    ctx.fillStyle = colors[i % colors.length];
    ctx.fill();
    start += angle;
  });

  // legend
  const items = labels.map((lab, i) => ({ name: `${lab}: ${data[i]}`, color: colors[i] }));
  ctx.font = '12px sans-serif';
  ctx.textAlign = 'left';
  let totalWidth = 0;
  const box = 12, gap = 8, itemGap = 16;
  items.forEach(it => { totalWidth += box + gap + ctx.measureText(it.name).width + itemGap; });
  let x = Math.max(10, (W - totalWidth) / 2);
  const y = H - 16;
  items.forEach(it => {
    ctx.fillStyle = it.color;
    ctx.fillRect(x, y - 10, box, box);
    ctx.fillStyle = '#ccc';
    ctx.fillText(it.name, x + box + gap, y);
    x += box + gap + ctx.measureText(it.name).width + itemGap;
  });
}

function formatAbbr(n) {
  const abs = Math.abs(n);
  if (abs >= 1_000_000) return (n / 1_000_000).toFixed(1).replace(/\.0$/, '') + 'M';
  if (abs >= 1_000) return (n / 1_000).toFixed(1).replace(/\.0$/, '') + 'K';
  return String(n);
}
