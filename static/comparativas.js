document.addEventListener('DOMContentLoaded', () => {
  const filterSelect = document.getElementById('filterComparatives');
  loadComparatives(filterSelect.value);

  filterSelect.addEventListener('change', () => {
    loadComparatives(filterSelect.value);
  });
});

async function loadComparatives(filter) {
  try {
    const [pRes, sRes] = await Promise.all([
      fetch(`/api/stats/last?station=${encodeURIComponent('Portobelo')}&filter=${encodeURIComponent(filter)}`),
      fetch(`/api/stats/last?station=${encodeURIComponent('Salvio')}&filter=${encodeURIComponent(filter)}`)
    ]);

    if (!pRes.ok || !sRes.ok) throw new Error('Error al cargar comparativas');

    const [pStats, sStats] = await Promise.all([pRes.json(), sRes.json()]);
    renderComparatives(pStats, sStats);
    drawCharts(pStats, sStats);
  } catch (e) {
    console.error(e);
  }
}

function renderComparatives(portobelo, salvio) {
  const container = document.getElementById('comparativesContainer');
  container.innerHTML = '';

  const cards = [
    { name: 'Portobelo', data: portobelo },
    { name: 'Salvio', data: salvio },
  ];

  cards.forEach(({ name, data }) => {
    const el = document.createElement('div');
    el.className = 'comparative-card';
    el.innerHTML = `
      <h3>${name}</h3>
      <ul>
        <li><strong>Total Cargas:</strong> ${data.total_cargas ?? 0}</li>
        <li><strong>Total Usuarios:</strong> ${data.total_usuarios ?? 0}</li>
        <li><strong>Energía (Wh):</strong> ${data.total_energy_Wh ?? 0}</li>
        <li><strong>Vehículos PHEV:</strong> ${data.coches_hibridos ?? 0}</li>
        <li><strong>Vehículos EV:</strong> ${data.coches_electricos ?? 0}</li>
        <li><strong>Vehículos Totales:</strong> ${data.coches_totales ?? 0}</li>
      </ul>
    `;
    container.appendChild(el);
  });
}

/* ==== Charts (no external libs) ==== */
function drawCharts(p, s) {
  const bars = document.getElementById('barsCanvas');
  const pPie = document.getElementById('piePorto');
  const sPie = document.getElementById('pieSalvio');
  if (!bars || !pPie || !sPie) return;

  // Responsivo + HiDPI
  const dpr = Math.max(1, window.devicePixelRatio || 1);
  const barsCard = bars.parentElement;
  const barsW = Math.max(480, Math.min(1000, barsCard.clientWidth - 32));
  const barsH = 360;
  const barsCtx = setupCanvas(bars, barsW, barsH, dpr);

  const labels = ['Cargas', 'Usuarios', 'Energía (Wh)'];
  const series = [
    [p.total_cargas || 0, p.total_usuarios || 0, p.total_energy_Wh || 0],
    [s.total_cargas || 0, s.total_usuarios || 0, s.total_energy_Wh || 0],
  ];
  drawGroupedBarChart(barsCtx, labels, series, ['#ff9800', '#03A9F4']);

  const piesRow = pPie.parentElement.parentElement;
  const pieW = Math.max(280, Math.min(420, Math.floor((piesRow.clientWidth - 60) / 2)));
  const pieH = 300;
  const pCtx = setupCanvas(pPie, pieW, pieH, dpr);
  const sCtx = setupCanvas(sPie, pieW, pieH, dpr);

  drawPieChart(pCtx, [p.coches_electricos || 0, p.coches_hibridos || 0], ['#03A9F4', '#8BC34A'], ['EV', 'PHEV']);
  drawPieChart(sCtx, [s.coches_electricos || 0, s.coches_hibridos || 0], ['#03A9F4', '#8BC34A'], ['EV', 'PHEV']);
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

function drawGroupedBarChart(ctx, labels, series, colors) {
  // Usar medidas en CSS px (coherentes con el setTransform de setupCanvas)
  const W = ctx.canvas.clientWidth || parseInt(ctx.canvas.style.width) || 900;
  const H = ctx.canvas.clientHeight || parseInt(ctx.canvas.style.height) || 360;
  ctx.clearRect(0, 0, W, H);

  // Paddings: añadir margen derecho para la leyenda
  const left = 50, right = 140, top = 30, bottom = 48;
  const chartW = W - left - right;
  const chartH = H - top - bottom;
  const groups = labels.length;
  const innerBars = series.length; // stations

  // Max por grupo para evitar que Energía aplaste otros valores
  const maxByGroup = labels.map((_, g) => Math.max(1, ...series.map(s => s[g])));

  const groupWidth = chartW / groups;
  const avail = groupWidth * 0.7; // 70% del ancho del grupo para barras
  const barGap = 10;
  const barWidth = Math.min(42, (avail - (innerBars - 1) * barGap) / innerBars);

  // Ejes
  ctx.strokeStyle = '#666';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(left, H - bottom);
  ctx.lineTo(W - right, H - bottom);
  ctx.moveTo(left, top);
  ctx.lineTo(left, H - bottom);
  ctx.stroke();

  // Etiquetas X
  ctx.fillStyle = '#ccc';
  ctx.font = '12px sans-serif';
  ctx.textAlign = 'center';
  labels.forEach((lab, i) => {
    const x = left + i * groupWidth + groupWidth / 2;
    ctx.fillText(lab, x, H - bottom + 18);
  });

  // Barras
  for (let g = 0; g < groups; g++) {
    const baseX = left + g * groupWidth + (groupWidth - (innerBars * barWidth + (innerBars - 1) * barGap)) / 2;
    for (let b = 0; b < innerBars; b++) {
      const val = series[b][g];
      const h = (val / maxByGroup[g]) * chartH;
      const x = baseX + b * (barWidth + barGap);
      const y = H - bottom - h;
      ctx.fillStyle = colors[b % colors.length];
      ctx.fillRect(x, y, barWidth, h);
      // valor
      ctx.fillStyle = '#ddd';
      ctx.textAlign = 'center';
      ctx.fillText(formatAbbr(val), x + barWidth / 2, Math.max(top + 12, y - 6));
    }
  }

  // Leyenda
  const legend = [
    { name: 'Portobelo', color: colors[0] },
    { name: 'Salvio', color: colors[1] },
  ];
  let lx = W - right + 10, ly = top + 10;
  legend.forEach(({ name, color }) => {
    ctx.fillStyle = color;
    ctx.fillRect(lx, ly - 10, 14, 14);
    ctx.fillStyle = '#ccc';
    ctx.font = '12px sans-serif';
    ctx.textAlign = 'left';
    ctx.fillText(name, lx + 20, ly + 2);
    ly += 18;
  });
}

function formatAbbr(n) {
  const abs = Math.abs(n);
  if (abs >= 1_000_000) return (n / 1_000_000).toFixed(1).replace(/\.0$/, '') + 'M';
  if (abs >= 1_000) return (n / 1_000).toFixed(1).replace(/\.0$/, '') + 'K';
  return String(n);
}

function drawPieChart(ctx, data, colors, labels) {
  const W = ctx.canvas.clientWidth || parseInt(ctx.canvas.style.width) || 400; // CSS px
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

  // Legend centrada abajo para evitar textos sobre el gráfico
  const items = labels.map((lab, i) => ({
    name: `${lab}: ${data[i]} (${Math.round((data[i] / total) * 100)}%)`,
    color: colors[i],
  }));
  ctx.font = '12px sans-serif';
  ctx.textAlign = 'left';
  let totalWidth = 0;
  const box = 12, gap = 10, itemGap = 18;
  items.forEach(it => { totalWidth += box + gap + ctx.measureText(it.name).width + itemGap; });
  let x = Math.max(10, (W - totalWidth) / 2);
  const y = H - 18;
  items.forEach(it => {
    ctx.fillStyle = it.color;
    ctx.fillRect(x, y - 10, box, box);
    ctx.fillStyle = '#ccc';
    ctx.fillText(it.name, x + box + gap, y);
    x += box + gap + ctx.measureText(it.name).width + itemGap;
  });
}
