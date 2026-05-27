const TZ = "America/Mazatlan";
let activeRange = "hour";
let meta = null;
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

function fmtDate(value, mode = "table") {
  if (!value) return "-";
  const d = new Date(value);
  if (mode === "chart") {
    return d.toLocaleString("es-MX", {
      timeZone: TZ,
      day: "2-digit",
      month: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    });
  }
  return d.toLocaleString("es-MX", {
    timeZone: TZ,
    day: "2-digit",
    month: "2-digit",
    year: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function addOneHour(timeStr) {
  const [h, m] = timeStr.split(":").map(Number);
  const total = (h * 60 + m + 60) % (24 * 60);
  const nh = Math.floor(total / 60);
  const nm = total % 60;
  return `${String(nh).padStart(2, "0")}:${String(nm).padStart(2, "0")}`;
}

function crossesMidnight(start, end) {
  if (!start || !end) return false;
  return end <= start;
}

function showFilterPanel() {
  document.querySelectorAll(".filter-group").forEach((el) => {
    el.classList.toggle("hidden", el.dataset.filter !== activeRange);
  });
}

function setupYearSelect(years) {
  const select = document.getElementById("year-picker");
  select.innerHTML = years
    .map((y) => `<option value="${y}">${y}</option>`)
    .join("");
  if (meta?.current_year) {
    select.value = String(meta.current_year);
  }
}

function initFiltersFromMeta() {
  if (!meta) return;
  document.getElementById("hour-date").value = meta.today;
  document.getElementById("day-date").value = meta.today;
  document.getElementById("month-picker").value = meta.current_month;
  setupYearSelect(meta.years);

  const now = new Date();
  const hour = parseInt(
    now.toLocaleString("en-US", { timeZone: TZ, hour: "numeric", hour12: false }),
    10
  );
  const startHour = `${String(hour).padStart(2, "0")}:00`;

  const startEl = document.getElementById("hour-start");
  const endEl = document.getElementById("hour-end");
  startEl.value = startHour;
  endEl.value = addOneHour(startHour);
  endEl.disabled = false;
  updateHourHint();
}

function updateHourHint() {
  const start = document.getElementById("hour-start").value;
  const end = document.getElementById("hour-end").value;
  const hint = document.getElementById("hour-hint");
  if (!start) {
    hint.textContent = "Selecciona hora inicial";
    return;
  }
  if (!end) {
    hint.textContent = "";
    return;
  }
  hint.textContent = crossesMidnight(start, end)
    ? "El intervalo termina al dia siguiente"
    : "";
}

function onHourStartChange() {
  const startEl = document.getElementById("hour-start");
  const endEl = document.getElementById("hour-end");
  const start = startEl.value;

  if (!start) {
    endEl.value = "";
    endEl.disabled = true;
    updateHourHint();
    return;
  }

  endEl.disabled = false;
  endEl.value = addOneHour(start);
  updateHourHint();
}

function buildQueryParams() {
  const params = new URLSearchParams({ range: activeRange });

  if (activeRange === "hour") {
    params.set("date", document.getElementById("hour-date").value);
    const start = document.getElementById("hour-start").value;
    const end = document.getElementById("hour-end").value;
    if (start) params.set("start_time", start);
    if (end) params.set("end_time", end);
  } else if (activeRange === "day") {
    params.set("date", document.getElementById("day-date").value);
  } else if (activeRange === "month") {
    params.set("month", document.getElementById("month-picker").value);
  } else if (activeRange === "year") {
    params.set("year", document.getElementById("year-picker").value);
  }

  return params;
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
  document.getElementById("updated-at").textContent =
    `Ultima actualizacion: ${updated} (${payload.source}) · ${meta?.timezone_label || TZ}`;
}

function renderAverages(avg, count, windowInfo) {
  const hasData = count > 0;
  const label = windowInfo?.label || "periodo seleccionado";
  document.getElementById("range-label").textContent = `Promedios · ${label}`;
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
  const labels = series.map((row) => fmtDate(row.recorded_at, "chart"));
  const data = series.map((row) => (row[field] == null ? null : Number(row[field])));

  if (chartInstances[canvasId]) chartInstances[canvasId].destroy();

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
          callbacks: { label: (ctx) => `${label}: ${fmt(ctx.parsed.y)}` },
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
    body.innerHTML = '<tr><td colspan="7">Sin registros para este periodo.</td></tr>';
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

async function loadMeta() {
  const res = await fetch("/api/meta");
  meta = await res.json();
  initFiltersFromMeta();
}

async function loadCurrent() {
  const res = await fetch("/api/current");
  const data = await res.json();
  renderCurrent(data);
}

async function loadStats() {
  const params = buildQueryParams();
  const res = await fetch(`/api/stats?${params}`);
  const data = await res.json();
  if (data.error) {
    document.getElementById("range-label").textContent = data.error;
    return;
  }
  const count = data.averages?.sample_count ?? data.count ?? 0;
  renderAverages(data.averages || {}, count, data.window);
  renderCharts(data.series || []);
  renderHistory(data.rows || []);
}

function setupTabs() {
  document.querySelectorAll("#range-tabs .tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("#range-tabs .tab").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      activeRange = btn.dataset.range;
      showFilterPanel();
      loadStats();
    });
  });
}

function setupFilters() {
  document.getElementById("hour-start").addEventListener("change", onHourStartChange);
  document.getElementById("hour-start").addEventListener("input", onHourStartChange);
  document.getElementById("hour-end").addEventListener("change", updateHourHint);
  document.getElementById("btn-apply").addEventListener("click", loadStats);

  ["hour-date", "day-date", "month-picker", "year-picker"].forEach((id) => {
    document.getElementById(id).addEventListener("change", loadStats);
  });
}

async function refreshAll() {
  await Promise.all([loadCurrent(), loadStats()]);
}

async function init() {
  showFilterPanel();
  setupTabs();
  setupFilters();
  await loadMeta();
  await refreshAll();
  setInterval(refreshAll, 30000);
}

init();
