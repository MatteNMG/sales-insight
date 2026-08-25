const $ = (s) => document.querySelector(s);
const $$ = (s) => document.querySelectorAll(s);

let currentSummary = null;
let currentProduct = null;
let selectedFile = null;

function formatMoney(n) {
  return '€' + Number(n || 0).toLocaleString('en', {minimumFractionDigits: 2, maximumFractionDigits: 2});
}

function showError(msg) {
  const box = $('#error-box');
  box.textContent = msg;
  box.style.display = 'block';
  box.scrollIntoView({behavior:'smooth', block:'nearest'});
}
function clearError() {
  $('#error-box').style.display = 'none';
}
function showInfo(msg) {
  const box = $('#info-box');
  box.textContent = msg;
  box.style.display = 'block';
  setTimeout(() => box.style.display = 'none', 4000);
}

function setLoading(id, active) {
  const el = $(id);
  if (!el) return;
  if (active) el.classList.add('active');
  else el.classList.remove('active');
}

function renderSummary(summary) {
  $('#m-revenue').textContent = formatMoney(summary.revenue);
  $('#m-orders').textContent = summary.orders;
  $('#m-units').textContent = summary.units;
  $('#m-aov').textContent = formatMoney(summary.aov);

  const revDelta = summary.revenue_delta || 0;
  const deltaEl = $('#d-revenue');
  deltaEl.textContent = (revDelta >= 0 ? '↑ ' : '↓ ') + Math.abs(revDelta) + '%';
  deltaEl.className = 'delta ' + (revDelta >= 0 ? 'up' : 'down');

  $('#period').textContent = 'Live data · ' + (summary.product_count || 0) + ' products';
}

function renderCharts(charts) {
  Plotly.newPlot('chart-trend', JSON.parse(charts.trend), {}, {responsive: true, displayModeBar: false});
  Plotly.newPlot('chart-top', JSON.parse(charts.top), {}, {responsive: true, displayModeBar: false});
  Plotly.newPlot('chart-country', JSON.parse(charts.country), {}, {responsive: true, displayModeBar: false});
}

function renderProducts(products) {
  const tbody = $('#products-body');
  tbody.innerHTML = '';
  products.slice(0, 10).forEach(p => {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${p.name}</td><td>${formatMoney(p.revenue)}</td>`;
    tr.addEventListener('click', () => loadDrilldown(p.name));
    tbody.appendChild(tr);
  });
}

function renderScenarioProducts(products) {
  const select = $('#scenario-product');
  select.innerHTML = '';
  products.forEach(product => {
    const option = document.createElement('option');
    option.value = product.name;
    option.textContent = product.name;
    select.appendChild(option);
  });
  $('#scenario-section').style.display = products.length ? 'block' : 'none';
}

async function runPriceScenario(event) {
  event.preventDefault();
  const result = $('#scenario-result');
  try {
    const data = await fetchJson('/api/price-scenario', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        product: $('#scenario-product').value,
        price_change_percent: Number($('#scenario-change').value),
      }),
    });
    result.textContent = `Projected historical-period revenue: ${formatMoney(data.projected_revenue)} versus ${formatMoney(data.current_revenue)} · ${data.confidence} confidence. ${data.caveat}`;
    result.style.color = 'var(--pine)';
  } catch (error) {
    result.textContent = error.message;
    result.style.color = 'var(--brick)';
  }
}

function renderInsights(insights) {
  const section = $('#insights-section');
  const body = $('#insights-body');
  body.innerHTML = '';
  if (!insights || !insights.length) {
    section.style.display = 'none';
    return;
  }
  insights.forEach(insight => {
    const card = document.createElement('div');
    card.className = `insight-card ${insight.severity}`;
    card.textContent = insight.message;
    body.appendChild(card);
  });
  section.style.display = 'block';
}

function showSections() {
  $('#empty-state').style.display = 'none';
  $('#charts-section').style.display = 'block';
  $('#products-section').style.display = 'block';
  $('#btn-export').style.display = 'inline-flex';
}

function updateView(payload) {
  currentSummary = payload.summary;
  renderSummary(payload.summary);
  renderCharts(payload.charts);
  renderProducts(payload.summary.top_products);
  renderScenarioProducts(payload.summary.top_products);
  renderInsights(payload.insights);
  showSections();
}

async function fetchJson(url, options) {
  const res = await fetch(url, options);
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

async function loadDemo() {
  clearError();
  setLoading('#upload-loading', true);
  try {
    const data = await fetchJson('/api/demo');
    updateView(data);
    await loadHistory();
    showInfo('Demo data loaded from local synthetic orders.');
  } catch (e) {
    showError('Demo load failed: ' + e.message);
  } finally {
    setLoading('#upload-loading', false);
  }
}

async function checkFile(file) {
  const form = new FormData();
  form.append('file', file);
  form.append('platform', $('#platform').value);
  const box = $('#file-check');
  const button = $('#btn-upload');
  button.disabled = true;
  try {
    const data = await fetchJson('/api/check', {method: 'POST', body: form});
    if (data.ok) {
      box.textContent = `${file.name}: ${data.platform} format detected · ${data.row_count_preview} preview rows ready.`;
      box.style.color = 'var(--pine)';
      button.disabled = false;
    } else {
      box.textContent = data.error;
      box.style.color = 'var(--brick)';
    }
    box.style.display = 'block';
    return data.ok;
  } catch (e) {
    box.textContent = e.message;
    box.style.color = 'var(--brick)';
    box.style.display = 'block';
    return false;
  }
}

async function uploadFile(file) {
  clearError();
  if (!file || !await checkFile(file)) return;
  const form = new FormData();
  form.append('file', file);
  form.append('platform', $('#platform').value);
  form.append('currency', $('#currency').value || 'EUR');
  form.append('base_currency', $('#base_currency').value || 'EUR');
  setLoading('#upload-loading', true);
  try {
    const data = await fetchJson('/api/upload', {method: 'POST', body: form});
    if (data.error) throw new Error(data.error);
    updateView(data);
    await loadHistory();
    showInfo('CSV processed locally. Data saved to history.');
  } catch (e) {
    showError('Upload failed: ' + e.message);
  } finally {
    setLoading('#upload-loading', false);
  }
}

async function applyFilters() {
  clearError();
  const params = new URLSearchParams();
  const start = $('#filter-start').value;
  const end = $('#filter-end').value;
  const platforms = Array.from($('#filter-platform').selectedOptions).map(o => o.value);
  if (start) params.append('start', start);
  if (end) params.append('end', end);
  platforms.forEach(p => params.append('platform', p));
  setLoading('#upload-loading', true);
  try {
    const data = await fetchJson('/api/filters?' + params.toString());
    updateView(data);
  } catch (e) {
    showError('Filter failed: ' + e.message);
  } finally {
    setLoading('#upload-loading', false);
  }
}

async function loadLatest() {
  try {
    const data = await fetchJson('/api/latest');
    if (data.summary && data.summary.orders > 0) {
      updateView(data);
      await loadHistory();
    }
  } catch (e) {
    // silent: no history yet
  }
}

async function loadHistory() {
  try {
    const data = await fetchJson('/api/history');
    const section = $('#history-section');
    const body = $('#history-body');
    if (data.batches && data.batches.length) {
      section.style.display = 'block';
      body.innerHTML = data.batches.map(b =>
        `<div class="history-card">
          <span>${b.min_date} → ${b.max_date}</span>
          <span>${b.rows} rows · ${b.platforms} platform(s)</span>
        </div>`
      ).join('');
    } else {
      section.style.display = 'none';
    }
  } catch (e) {
    console.warn('History load failed', e);
  }
}

async function loadDrilldown(productName) {
  clearError();
  currentProduct = productName;
  $('#drilldown-section').style.display = 'block';
  $('#drilldown-title').textContent = 'Trend — ' + productName;
  try {
    const data = await fetchJson('/api/product/' + encodeURIComponent(productName) + '/trend');
    Plotly.newPlot('chart-drilldown', data.chart, {}, {responsive: true, displayModeBar: false});
    window.scrollTo({top: $('#drilldown-section').offsetTop - 24, behavior: 'smooth'});
  } catch (e) {
    showError('Drill-down failed: ' + e.message);
  }
}

function toggleTheme() {
  const html = document.documentElement;
  const isDark = html.getAttribute('data-theme') === 'dark';
  html.setAttribute('data-theme', isDark ? 'light' : 'dark');
  $('#btn-theme').textContent = isDark ? 'Dark mode' : 'Light mode';
}

function initUpload() {
  const dropzone = $('#dropzone');
  const input = $('#file-input');
  const form = $('#upload-form');
  dropzone.addEventListener('click', () => input.click());
  input.addEventListener('change', async () => {
    selectedFile = input.files[0] || null;
    if (selectedFile) await checkFile(selectedFile);
  });
  $('#platform').addEventListener('change', async () => {
    if (selectedFile) await checkFile(selectedFile);
  });
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    await uploadFile(selectedFile);
  });
  dropzone.addEventListener('dragover', (e) => { e.preventDefault(); dropzone.classList.add('dragover'); });
  dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));
  dropzone.addEventListener('drop', async (e) => {
    e.preventDefault();
    dropzone.classList.remove('dragover');
    selectedFile = e.dataTransfer.files[0] || null;
    if (selectedFile) await checkFile(selectedFile);
  });
}

function initPrivacyBanner() {
  const banner = $('#privacy-banner');
  if (localStorage.getItem('salesInsightPrivacyDismissed')) {
    banner.style.display = 'none';
  }
  $('#btn-dismiss-privacy').addEventListener('click', () => {
    banner.style.display = 'none';
    localStorage.setItem('salesInsightPrivacyDismissed', '1');
  });
}

function initFeedback() {
  $('#feedback-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const rating = parseInt($('#feedback-rating').value, 10);
    const comment = $('#feedback-comment').value.trim();
    const email = $('#feedback-email').value.trim();
    if (!comment || !rating) return;
    try {
      await fetchJson('/api/feedback', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({rating, comment, email}),
      });
      $('#feedback-form').reset();
      $('#feedback-status').textContent = 'Thanks for the feedback!';
      $('#feedback-status').style.color = 'var(--pine)';
    } catch (err) {
      $('#feedback-status').textContent = 'Error: ' + err.message;
      $('#feedback-status').style.color = 'var(--brick)';
    }
  });
}

function initTour() {
  if (localStorage.getItem('salesInsightTourDone')) return;
  const steps = [
    {target: '#privacy-banner', text: 'Your CSVs are processed locally — nothing is uploaded to the cloud.'},
    {target: '#btn-demo', text: 'Start here to explore the dashboard with synthetic data.'},
    {target: '#dropzone', text: 'Upload your Etsy, Shopify or Amazon CSV here. We\'ll check the format first.'},
    {target: '#metrics', text: 'Key metrics update automatically after upload.'},
  ];
  let stepIndex = 0;
  const overlay = document.createElement('div');
  overlay.className = 'tour-step';
  overlay.id = 'tour-overlay';
  document.body.appendChild(overlay);

  function showStep() {
    if (stepIndex >= steps.length) {
      overlay.remove();
      localStorage.setItem('salesInsightTourDone', '1');
      return;
    }
    const step = steps[stepIndex];
    const target = $(step.target);
    if (!target) { stepIndex += 1; showStep(); return; }
    target.classList.add('tour-highlight');
    const rect = target.getBoundingClientRect();
    overlay.innerHTML = `<div>${step.text}</div><button id="tour-next">${stepIndex === steps.length - 1 ? 'Finish' : 'Next'}</button>`;
    overlay.style.top = (rect.bottom + 12 + window.scrollY) + 'px';
    overlay.style.left = Math.min(rect.left, window.innerWidth - 280) + 'px';
    $('#tour-next').addEventListener('click', () => {
      target.classList.remove('tour-highlight');
      stepIndex += 1;
      showStep();
    });
  }
  showStep();
}

document.addEventListener('DOMContentLoaded', () => {
  initUpload();
  initPrivacyBanner();
  initFeedback();
  $('#scenario-form').addEventListener('submit', runPriceScenario);
  $('#btn-demo').addEventListener('click', loadDemo);
  $('#btn-theme').addEventListener('click', toggleTheme);
  $('#btn-apply-filters').addEventListener('click', applyFilters);
  $('#btn-export').addEventListener('click', (e) => {
    e.preventDefault();
    const fmt = confirm('Export PDF? Cancel for Excel.') ? 'pdf' : 'xlsx';
    window.location.href = '/api/export/' + fmt;
  });
  loadLatest();
  setTimeout(initTour, 800);
});
