/**
 * ReliefRadar - Humanitarian Intelligence Coordinator Dashboard
 * Frontend Application Controller
 */

let currentScanMode = "DEMO";
let currentFindingId = null;
let classificationChart = null;
let districtChart = null;
let allFindings = [];

document.addEventListener("DOMContentLoaded", () => {
  initIcons();
  checkHealth();
  refreshDashboard();

  // Attach auto-refresh listener
  document.getElementById("btn-refresh").addEventListener("click", () => {
    refreshDashboard();
    showToast("Dashboard data refreshed.");
  });
});

function initIcons() {
  if (window.lucide) {
    window.lucide.createIcons();
  }
}

// ----------------- Health & API Status -----------------
async function checkHealth() {
  try {
    const res = await fetch("/api/health");
    const data = await res.json();

    const pill = document.getElementById("api-status-pill");
    const text = document.getElementById("api-status-text");
    const badge = document.getElementById("mode-badge");
    const modeText = document.getElementById("mode-text");

    if (data.keys_status.live_ready) {
      text.innerText = "Live APIs Connected";
      pill.style.borderColor = "var(--color-covered)";
      text.style.color = "var(--color-covered)";
    } else {
      text.innerText = "Demo Mode (API Keys Unconfigured)";
      pill.style.borderColor = "var(--border-color)";
      text.style.color = "var(--text-muted)";
    }

    if (data.mode.includes("DEMO") || data.database.is_demo_loaded) {
      badge.className = "mode-badge demo";
      modeText.innerText = "SYNTHETIC DEMO DATA";
    } else if (data.mode === "LIVE") {
      badge.className = "mode-badge live";
      modeText.innerText = "LIVE MONITOR";
    } else {
      badge.className = "mode-badge demo";
      modeText.innerText = "IDLE / DEMO READY";
    }
  } catch (err) {
    console.error("Health check error:", err);
  }
}

// ----------------- Mode Switching -----------------
function setScanMode(mode) {
  currentScanMode = mode;
  document.getElementById("btn-mode-demo").classList.toggle("active", mode === "DEMO");
  document.getElementById("btn-mode-live").classList.toggle("active", mode === "LIVE");

  if (mode === "LIVE") {
    showToast("Switched to LIVE MODE (Uses TinyFish Search & Fetch).");
  } else {
    showToast("Switched to DEMO MODE (Uses South Odisha synthetic testbed).");
  }
}

// ----------------- Main Dashboard Data -----------------
async function refreshDashboard() {
  await Promise.all([
    fetchDashboardMetrics(),
    fetchFindings(),
    fetchSources()
  ]);
  initIcons();
}

async function fetchDashboardMetrics() {
  try {
    const res = await fetch("/api/dashboard");
    const data = await res.json();

    // Summary cards
    document.getElementById("val-sources-discovered").innerText = data.summary.sources_discovered;
    document.getElementById("val-sources-fetched").innerText = `${data.summary.sources_fetched} Fetched Cleanly`;
    document.getElementById("val-facts-verified").innerText = data.summary.verified_facts;
    document.getElementById("val-facts-rejected").innerText = `${data.summary.rejected_facts} Hallucinations Blocked`;
    document.getElementById("val-gap-count").innerText = data.summary.gap_count;
    document.getElementById("val-conflict-count").innerText = data.summary.conflict_count;
    document.getElementById("val-unknown-count").innerText = data.summary.unknown_count;
    document.getElementById("val-covered-count").innerText = data.summary.covered_count;

    // District cards
    if (data.districts.Ganjam) {
      const g = data.districts.Ganjam;
      document.getElementById("badge-ganjam-count").innerText = `${g.total_findings} Findings`;
      document.getElementById("ganjam-gap").innerText = g.gaps;
      document.getElementById("ganjam-conflict").innerText = g.conflicts;
      document.getElementById("ganjam-unknown").innerText = g.unknowns;
      document.getElementById("ganjam-covered").innerText = g.covered;
    }

    if (data.districts.Gajapati) {
      const gj = data.districts.Gajapati;
      document.getElementById("badge-gajapati-count").innerText = `${gj.total_findings} Findings`;
      document.getElementById("gajapati-gap").innerText = gj.gaps;
      document.getElementById("gajapati-conflict").innerText = gj.conflicts;
      document.getElementById("gajapati-unknown").innerText = gj.unknowns;
      document.getElementById("gajapati-covered").innerText = gj.covered;
    }

    updateCharts(data);
  } catch (err) {
    console.error("Dashboard metrics error:", err);
  }
}

// ----------------- Chart.js Visualizers -----------------
function updateCharts(data) {
  const sum = data.summary;

  // 1. Classification Donut Chart
  const ctxClass = document.getElementById("chart-classification").getContext("2d");
  if (classificationChart) {
    classificationChart.destroy();
  }

  const hasData = (sum.gap_count + sum.conflict_count + sum.unknown_count + sum.covered_count) > 0;
  const chartData = hasData 
    ? [sum.gap_count, sum.conflict_count, sum.unknown_count, sum.covered_count]
    : [1, 1, 1, 1];

  classificationChart = new Chart(ctxClass, {
    type: "doughnut",
    data: {
      labels: ["GAP", "CONFLICT", "UNKNOWN", "COVERED"],
      datasets: [{
        data: chartData,
        backgroundColor: hasData 
          ? ["#EF4444", "#3B82F6", "#F59E0B", "#22C55E"]
          : ["#233852", "#233852", "#233852", "#233852"],
        borderWidth: 2,
        borderColor: "#162338"
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: "bottom",
          labels: { color: "#94A3B8", boxWidth: 10, font: { size: 11 } }
        }
      },
      cutout: "65%"
    }
  });

  // 2. District Comparison Bar Chart
  const ctxDist = document.getElementById("chart-district").getContext("2d");
  if (districtChart) {
    districtChart.destroy();
  }

  const ganjam = data.districts.Ganjam || { gaps: 0, conflicts: 0, unknowns: 0, covered: 0 };
  const gajapati = data.districts.Gajapati || { gaps: 0, conflicts: 0, unknowns: 0, covered: 0 };

  districtChart = new Chart(ctxDist, {
    type: "bar",
    data: {
      labels: ["Ganjam", "Gajapati"],
      datasets: [
        { label: "GAP", data: [ganjam.gaps, gajapati.gaps], backgroundColor: "#EF4444" },
        { label: "CONFLICT", data: [ganjam.conflicts, gajapati.conflicts], backgroundColor: "#3B82F6" },
        { label: "UNKNOWN", data: [ganjam.unknowns, gajapati.unknowns], backgroundColor: "#F59E0B" },
        { label: "COVERED", data: [ganjam.covered, gajapati.covered], backgroundColor: "#22C55E" }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: { stacked: true, grid: { color: "#1F2E45" }, ticks: { color: "#94A3B8" } },
        y: { stacked: true, grid: { color: "#1F2E45" }, ticks: { color: "#94A3B8", stepSize: 1 } }
      },
      plugins: {
        legend: {
          position: "bottom",
          labels: { color: "#94A3B8", boxWidth: 10, font: { size: 10 } }
        }
      }
    }
  });
}

// ----------------- Findings Table -----------------
async function fetchFindings() {
  const district = document.getElementById("filter-district").value;
  const classification = document.getElementById("filter-status").value;
  const priority = document.getElementById("filter-priority").value;
  const search = document.getElementById("filter-search").value;

  const params = new URLSearchParams();
  if (district !== "all") params.append("district", district);
  if (classification !== "all") params.append("classification", classification);
  if (priority !== "all") params.append("priority", priority);
  if (search.trim()) params.append("search", search.trim());

  try {
    const res = await fetch(`/api/findings?${params.toString()}`);
    const data = await res.json();
    allFindings = data.findings;
    renderFindingsTable(data.findings);
    document.getElementById("findings-total-badge").innerText = `${data.count} Findings`;
  } catch (err) {
    console.error("Fetch findings error:", err);
  }
}

function renderFindingsTable(findings) {
  const tbody = document.getElementById("findings-table-body");
  if (!findings || findings.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="9" class="table-empty-state">
          <i data-lucide="inbox"></i>
          <p>No matching findings located with current filters.</p>
        </td>
      </tr>
    `;
    initIcons();
    return;
  }

  tbody.innerHTML = findings.map(f => {
    const statusClass = f.classification.toLowerCase();
    const priorityClass = f.priority.toLowerCase();
    const reviewClass = f.review_status.toLowerCase();

    return `
      <tr>
        <td><strong>${escapeHtml(f.district)}</strong></td>
        <td>${escapeHtml(f.location)}</td>
        <td>${escapeHtml(f.item)}</td>
        <td><span class="status-badge ${statusClass}">${f.classification}</span></td>
        <td><span class="priority-pill ${priorityClass}">${f.priority}</span></td>
        <td style="color: var(--text-muted); font-size: 0.78rem;">${f.report_date || 'Recent'}</td>
        <td style="text-align: center;"><span style="font-family: var(--font-mono); font-weight: 600;">${f.evidence_count}</span></td>
        <td><span class="review-badge ${reviewClass}">${f.review_status}</span></td>
        <td>
          <button class="btn-secondary btn-sm" onclick="openInspectorModal(${f.id})">
            <i data-lucide="eye"></i> Inspect
          </button>
        </td>
      </tr>
    `;
  }).join("");

  initIcons();
}

function applyFilters() {
  fetchFindings();
}

// ----------------- Evidence Inspector & Review Modal -----------------
async function openInspectorModal(findingId) {
  currentFindingId = findingId;
  const modal = document.getElementById("inspector-modal");
  modal.style.display = "flex";

  try {
    const res = await fetch(`/api/findings/${findingId}`);
    const f = await res.json();

    document.getElementById("modal-title").innerText = `${f.location}: ${f.item}`;
    document.getElementById("modal-district-tag").innerText = f.district;
    
    const badge = document.getElementById("modal-status-badge");
    badge.className = `status-badge ${f.classification.toLowerCase()}`;
    badge.innerText = f.classification;

    document.getElementById("modal-reasoning").innerText = f.reasoning;
    document.getElementById("modal-review-status").innerText = f.review_status;
    document.getElementById("modal-reviewed-at").innerText = f.reviewed_at ? `(Updated: ${new Date(f.reviewed_at).toLocaleTimeString()})` : "";
    document.getElementById("review-notes-input").value = f.reviewer_notes || "";

    // CONFLICT side-by-side view vs STANDARD view
    const conflictView = document.getElementById("conflict-comparison-view");
    const standardView = document.getElementById("standard-evidence-view");

    if (f.classification === "CONFLICT" && f.supply_fact && f.need_fact) {
      conflictView.style.display = "grid";
      standardView.style.display = "none";

      document.getElementById("conflict-claim-quote").innerText = f.supply_fact.evidence_quote;
      document.getElementById("conflict-claim-source").innerText = f.supply_fact.source?.title || "Official Portal Claim";
      document.getElementById("conflict-claim-link").href = f.supply_fact.source?.url || "#";

      document.getElementById("conflict-ground-quote").innerText = f.need_fact.evidence_quote;
      document.getElementById("conflict-ground-source").innerText = f.need_fact.source?.title || "Field NGO Ground Dispatch";
      document.getElementById("conflict-ground-link").href = f.need_fact.source?.url || "#";
    } else {
      conflictView.style.display = "none";
      standardView.style.display = "block";

      const primaryFact = f.need_fact || f.supply_fact;
      if (primaryFact) {
        document.getElementById("modal-quote-text").innerText = primaryFact.evidence_quote;
        document.getElementById("modal-source-title").innerText = primaryFact.source?.title || "Field Source";
        document.getElementById("modal-source-url-text").innerText = primaryFact.source?.url || "";
        document.getElementById("modal-source-link").href = primaryFact.source?.url || "#";

        const verBadge = document.getElementById("modal-quote-verification");
        if (primaryFact.is_verified) {
          verBadge.className = "verification-badge verified";
          verBadge.innerHTML = `<i data-lucide="shield-check"></i> Substring Verified in Source`;
        } else {
          verBadge.className = "verification-badge rejected";
          verBadge.innerHTML = `<i data-lucide="alert-triangle"></i> Verification Failed`;
        }
      }
    }

    // Review history
    const historyBox = document.getElementById("modal-review-history");
    const historyEntries = document.getElementById("modal-history-entries");
    if (f.reviews && f.reviews.length > 0) {
      historyBox.style.display = "block";
      historyEntries.innerHTML = f.reviews.map(r => `
        <div class="history-entry">
          <strong>${r.action}</strong>: ${escapeHtml(r.notes || 'No notes')} 
          <span style="color: var(--text-dim);">(${new Date(r.created_at).toLocaleString()})</span>
        </div>
      `).join("");
    } else {
      historyBox.style.display = "none";
    }

    initIcons();
  } catch (err) {
    console.error("Inspector error:", err);
  }
}

function closeInspectorModal() {
  document.getElementById("inspector-modal").style.display = "none";
  currentFindingId = null;
}

function closeModalOnBackdrop(e) {
  if (e.target.id === "inspector-modal") {
    closeInspectorModal();
  }
}

// ----------------- Coordinator Review Actions -----------------
async function submitReviewAction(action) {
  if (!currentFindingId) return;

  const notes = document.getElementById("review-notes-input").value;

  try {
    const res = await fetch(`/api/findings/${currentFindingId}/review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, notes })
    });

    if (!res.ok) {
      const err = await res.json();
      showToast(`Error: ${err.detail || 'Review failed'}`);
      return;
    }

    const data = await res.json();
    showToast(`Decision saved: ${data.review_status}`);
    closeInspectorModal();
    refreshDashboard();
  } catch (err) {
    console.error("Review action error:", err);
    showToast("Network error submitting review.");
  }
}

// ----------------- Pipeline Execution -----------------
async function triggerScan() {
  const district = document.getElementById("scan-district").value;
  const query = document.getElementById("scan-query").value;
  const progressBox = document.getElementById("scan-progress-box");
  const msgEl = document.getElementById("scan-status-message");

  progressBox.style.display = "block";
  msgEl.innerText = `Connecting to TinyFish pipeline for ${district}...`;

  // Step animations
  setStepActive("step-search");
  await delay(400);

  setStepActive("step-fetch");
  await delay(400);

  setStepActive("step-extract");
  await delay(400);

  try {
    const res = await fetch("/api/scan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        district,
        query,
        mode: currentScanMode
      })
    });

    if (!res.ok) {
      const errData = await res.json();
      throw new Error(errData.detail || "Scan request failed.");
    }

    setStepActive("step-verify");
    await delay(300);

    setStepActive("step-classify");
    const result = await res.json();

    msgEl.innerText = `Scan Complete (${result.mode}): Discovered ${result.sources_discovered || 0} sources, verified ${result.verified_quotes || 0} facts, generated ${result.findings_generated || 0} actionable findings.`;
    
    showToast(`Scan Complete: ${result.findings_generated || 0} findings evaluated.`);
    await checkHealth();
    await refreshDashboard();
  } catch (err) {
    console.error("Scan error:", err);
    msgEl.innerText = `Scan Stopped: ${err.message}`;
    showToast(`Error: ${err.message}`);
  }
}

function setStepActive(stepId) {
  const steps = ["step-search", "step-fetch", "step-extract", "step-verify", "step-classify"];
  let reached = false;

  steps.forEach(id => {
    const el = document.getElementById(id);
    if (id === stepId) {
      el.className = "step active";
      reached = true;
    } else if (!reached) {
      el.className = "step completed";
    } else {
      el.className = "step";
    }
  });
}

// ----------------- Load & Clear Demo Data -----------------
async function loadDemoData() {
  try {
    const res = await fetch("/api/demo/load", { method: "POST" });
    const data = await res.json();
    showToast(`South Odisha Dataset Loaded: ${data.findings_generated} findings.`);
    await checkHealth();
    await refreshDashboard();
  } catch (err) {
    console.error("Load demo error:", err);
    showToast("Failed to load demo data.");
  }
}

async function clearData() {
  if (!confirm("Are you sure you want to clear all loaded crisis records?")) return;

  try {
    await fetch("/api/demo/clear", { method: "POST" });
    showToast("All local records cleared.");
    await checkHealth();
    await refreshDashboard();
  } catch (err) {
    console.error("Clear error:", err);
  }
}

// ----------------- Discovered Sources List -----------------
async function fetchSources() {
  try {
    const res = await fetch("/api/sources");
    const data = await res.json();

    document.getElementById("sources-count-badge").innerText = data.count;
    const container = document.getElementById("sources-list-container");

    if (!data.sources || data.sources.length === 0) {
      container.innerHTML = `<p style="color: var(--text-muted); font-size: 0.8rem;">No sources crawled yet.</p>`;
      return;
    }

    container.innerHTML = data.sources.map(s => `
      <div class="source-card">
        <div class="source-card-header">
          <div class="source-card-title">${escapeHtml(s.title || 'Untitled Source')}</div>
          <span class="status-badge ${s.fetch_status === 'SUCCESS' ? 'covered' : 'gap'}">${s.fetch_status}</span>
        </div>
        <div class="source-snippet">${escapeHtml(s.snippet || s.text_snippet || '')}</div>
        <div class="source-card-footer">
          <span style="font-family: var(--font-mono);">${s.facts_count} Facts Extracted</span>
          <a href="${s.url}" target="_blank" rel="noopener" class="link-open-source">
            View Page <i data-lucide="external-link" style="width: 12px; height: 12px;"></i>
          </a>
        </div>
      </div>
    `).join("");

    initIcons();
  } catch (err) {
    console.error("Fetch sources error:", err);
  }
}

// ----------------- Utilities -----------------
function showToast(message) {
  const toast = document.getElementById("toast");
  const msg = document.getElementById("toast-message");
  msg.innerText = message;
  toast.style.display = "block";

  setTimeout(() => {
    toast.style.display = "none";
  }, 3500);
}

function escapeHtml(text) {
  if (!text) return "";
  const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
  return String(text).replace(/[&<>"']/g, m => map[m]);
}

function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}
