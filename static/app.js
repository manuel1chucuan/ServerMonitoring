let activeRange = "hour";

const RANGE_LABELS = {
  hour: "ultima hora",
  day: "ultimo dia",
  week: "ultima semana",
  month: "ultimo mes",
};

const chartInstances = {};

const chartDefaults = {
  responsive: true,
  maintainAspectRatio: false,
  interaction: { mode: "index", intersect: false },
  plugins: {
    legend: { display: false },
    tooltip: {
      backgroundColor: "#1a2332",
      borderColor: "#3a4f6d",
      borderWidth: 1,
    },
  },
  scales: {
    x: {
      ticks: { color: "#9aa7b8", maxTicksLimit: 8 },
      grid: { color: "rgba(154, 167, 184, 0.12)" },
    },
    y: {
      beginAtZero: true,
      ticks: { color: "#9aa7b8" },
      grid: { color: "rgba(154, 167, 184, 0.12)" },
    },
  },
};

function fmt(value, suffix = "") {
  if (value === null || value === undefined) return "N/D";
  return `${Number(value).toFixed(2)}${suffix}`;
}

function fmtDate(value, short = false) {
  if (!value) return "-";
  const opts = short
    ? { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "UTC" }
    : { timeZone: "UTC" };
  const text = new Date(value).toLocaleString("es-MX", opts);
  return short ? `${text} UTC` : `${text} UTC`;
}

function renderCurrent(payload) {
  const m = payload.metrics;
  document.getElementById("cpu-value").textContent = fmt(m.cpu_percent);
  document.getElementById("ram-value").textContent = fmt(m.ram_percent);
  document.getElementById("ram-detail").textContent = `${m.ram_used_mb} / ${m.ram_total_mb} MB`;
  document.getElementById("disk-value").textContent = fmt(m.disk_percent);
  document.getElementById("disk-detail").textContent = `${fmt(m.disk_used_gb)} / ${fmt(m.disk_total_gb)} GB`;
  document.getElementById("temp-value").textContent = m.temp_celsius == null ? "N/D" : fmt(m.temp_celsius);

  const updated = m.recorded_at ? fmtDate(m.recorded_at) : "en vivo";
  document.getElementById("updated-at").textContent = `Ultima actualizacion: ${updated} (${payload.source})`;
}

function renderAverages(avg, count) {
  const hasData = count > 0;
  document.getElementById("range-label").textContent = `Promedios de la ${RANGE_LABELS[activeRange]}`;
  document.getElementById("sample-count").textContent = hasData
    ? `Basado en ${count} muestra${count === 1 ? "" : "s"}`
    : "Sin muestras en este periodo";

  document.getElementById("avg-cpu").textContent = hasData ? fmt(avg.cpu_percent) : "N/D";
  document.getElementById("avg-ram").textContent = hasData ? fmt(avg.ram_percent) : "N/D";
  document.getElementById("avg-ram-detail").textContent = hasData
    ? `~${avg.ram_used_mb} MB usados`
    : "--";
  document.getElementById("avg-disk").textContent = hasData ? fmt(avg.disk_percent) : "N/D";
  document.getElementById("avg-disk-detail").textContent = hasData
    ? `~${fmt(avg.disk_used_gb)} GB usados`
    : "--";
  document.getElementById("avg-temp").textContent =
    hasData && avg.temp_celsius != null ? fmt(avg.temp_celsius) : "N/D";
}

function buildChart(canvasId, label, series, field, color) {
  const ctx = document.getElementById(canvasId);
  const labels = series.map((row) => fmtDate(row.recorded_at, true));
  const data = series.map((row) =>
    row[field] == null ? null : Number(row[field])
  );

  if (chartInstances[canvasId]) {
    chartInstances[canvasId].destroy();
  }

  chartInstances[canvasId] = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label,
          data,
          borderColor: color,
          backgroundColor: `${color}33`,
          fill: true,
          tension: 0.3,
          pointRadius: series.length > 40 ? 0 : 3,
          pointHoverRadius: 4,
          spanGaps: true,
        },
      ],
    },
    options: {
      ...chartDefaults,
      plugins: {
        ...chartDefaults.plugins,
        tooltip: {
          ...chartDefaults.plugins.tooltip,
          callbacks: {
            label: (ctx) => `${label}: ${fmt(ctx.parsed.y)}`,
          },
        },
      },
    },
  });
}

function renderCharts(series) {
  buildChart("chart-cpu", "CPU", series, "cpu_percent", "#3d8bfd");
  buildChart("chart-ram", "RAM", series, "ram_percent", "#3dd68c");
  buildChart("chart-disk", "Disco", series, "disk_percent", "#f5a524");
  buildChart("chart-temp", "Temperatura", series, "temp_celsius", "#f31260");
}

function renderHistory(rows) {
  const body = document.getElementById("history-body");
  if (!rows.length) {
    body.innerHTML = '<tr><td colspan="7">Sin registros para este rango.</td></tr>';
    return;
  }

  body.innerHTML = rows
    .map(
      (row) => `
    <tr>
      <td>${fmtDate(row.recorded_at)}</td>
      <td>${fmt(row.cpu_percent)}</td>
      <td>${fmt(row.ram_percent)}</td>
      <td>${row.ram_used_mb} / ${row.ram_total_mb} MB</td>
      <td>${fmt(row.disk_percent)}</td>
      <td>${fmt(row.disk_used_gb)} / ${fmt(row.disk_total_gb)} GB</td>
      <td>${row.temp_celsius == null ? "N/D" : fmt(row.temp_celsius)}</td>
    </tr>
  `
    )
    .join("");
}

async function loadCurrent() {
  const res = await fetch("/api/current");
  const data = await res.json();
  renderCurrent(data);
}

async function loadStats() {
  const res = await fetch(`/api/stats?range=${activeRange}`);
  const data = await res.json();
  const count = data.averages?.sample_count ?? data.count ?? 0;
  renderAverages(data.averages || {}, count);
  renderCharts(data.series || []);
  renderHistory(data.rows || []);
}

function setupTabs() {
  document.querySelectorAll("#range-tabs .tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("#range-tabs .tab").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      activeRange = btn.dataset.range;
      loadStats();
    });
  });
}

async function refreshAll() {
  await Promise.all([loadCurrent(), loadStats()]);
}

setupTabs();
refreshAll();
setInterval(refreshAll, 30000);
