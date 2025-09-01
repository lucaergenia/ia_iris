document.addEventListener("DOMContentLoaded", () => {
  const stationSelect = document.getElementById("stationSelect");
  const filterSelect = document.getElementById("filterSelect");

  loadStationData(stationSelect.value, filterSelect.value);

  stationSelect.addEventListener("change", () => {
    loadStationData(stationSelect.value, filterSelect.value);
  });

  filterSelect.addEventListener("change", () => {
    loadStationData(stationSelect.value, filterSelect.value);
  });
});

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
