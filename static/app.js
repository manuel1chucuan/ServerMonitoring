let activeRange = "hour";

function fmt(value, suffix = "") {
  if (value === null || value === undefined) return "N/D";
  return `${Number(value).toFixed(2)}${suffix}`;
}

function fmtDate(value) {
  if (!value) return "-";
  return new Date(value).toLocaleString("es-MX", { timeZone: "UTC" }) + " UTC";
}

function levelClass(percent) {
  if (percent >= 90) return "danger";
  if (percent >= 75) return "warn";
  return "ok";
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

function renderHistory(rows) {
  const body = document.getElementById("history-body");
  if (!rows.length) {
    body.innerHTML = '<tr><td colspan="7">Sin registros para este rango.</td></tr>';
    return;
  }

  body.innerHTML = rows.map((row) => `
    <tr>
      <td>${fmtDate(row.recorded_at)}</td>
      <td>${fmt(row.cpu_percent)}</td>
      <td>${fmt(row.ram_percent)}</td>
      <td>${row.ram_used_mb} / ${row.ram_total_mb} MB</td>
      <td>${fmt(row.disk_percent)}</td>
      <td>${fmt(row.disk_used_gb)} / ${fmt(row.disk_total_gb)} GB</td>
      <td>${row.temp_celsius == null ? "N/D" : fmt(row.temp_celsius)}</td>
    </tr>
  `).join("");
}

async function loadCurrent() {
  const res = await fetch("/api/current");
  const data = await res.json();
  renderCurrent(data);
}

async function loadHistory() {
  const res = await fetch(`/api/history?range=${activeRange}`);
  const data = await res.json();
  renderHistory(data.rows || []);
}

function setupTabs() {
  document.querySelectorAll(".tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      activeRange = btn.dataset.range;
      loadHistory();
    });
  });
}

async function refreshAll() {
  await Promise.all([loadCurrent(), loadHistory()]);
}

setupTabs();
refreshAll();
setInterval(refreshAll, 30000);
