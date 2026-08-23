const $ = (s) => document.querySelector(s);
const $$ = (s) => document.querySelectorAll(s);

let currentSummary = null;
let currentProduct = null;

function formatMoney(n) {
  return '€' + Number(n || 0).toLocaleString('en', {minimumFractionDigits: 2, maximumFractionDigits: 2});
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
  Plotly.newPlot('chart-trend', JSON.parse(charts.trend), {}, {responsive: true});
  Plotly.newPlot('chart-top', JSON.parse(charts.top), {}, {responsive: true});
  Plotly.newPlot('chart-country', JSON.parse(charts.country), {}, {responsive: true});
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
  showSections();
}

async function loadDemo() {
  setLoading('#upload-loading', true);
  try {
    const res = await fetch('/api/demo');
    const data = await res.json();
    updateView(data);
  } catch (e) {
    alert('Demo load failed: ' + e.message);
  } finally {
    setLoading('#upload-loading', false);
  }
}

async function uploadFile(file) {
  const form = new FormData();
  form.append('file', file);
  form.append('platform', $('#platform').value);
  form.append('currency', $('#currency').value || 'EUR');
  form.append('base_currency', $('#base_currency').value || 'EUR');
  setLoading('#upload-loading', true);
  try {
    const res = await fetch('/api/upload', {method: 'POST', body: form});
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    updateView(data);
  } catch (e) {
    alert('Upload failed: ' + e.message);
  } finally {
    setLoading('#upload-loading', false);
  }
}

async function applyFilters() {
  const params = new URLSearchParams();
  const start = $('#filter-start').value;
  const end = $('#filter-end').value;
  const platforms = Array.from($('#filter-platform').selectedOptions).map(o => o.value);
  if (start) params.append('start', start);
  if (end) params.append('end', end);
  platforms.forEach(p => params.append('platform', p));
  setLoading('#upload-loading', true);
  try {
    const res = await fetch('/api/filters?' + params.toString());
    const data = await res.json();
    updateView(data);
  } catch (e) {
    alert('Filter failed: ' + e.message);
  } finally {
    setLoading('#upload-loading', false);
  }
}

async function loadDrilldown(productName) {
  currentProduct = productName;
  $('#drilldown-section').style.display = 'block';
  $('#drilldown-title').textContent = 'Trend — ' + productName;
  try {
    const res = await fetch('/api/product/' + encodeURIComponent(productName) + '/trend');
    const data = await res.json();
    Plotly.newPlot('chart-drilldown', data.chart, {}, {responsive: true});
    window.scrollTo({top: $('#drilldown-section').offsetTop - 24, behavior: 'smooth'});
  } catch (e) {
    alert('Drill-down failed: ' + e.message);
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
  dropzone.addEventListener('click', () => input.click());
  input.addEventListener('change', () => {
    if (input.files[0]) uploadFile(input.files[0]);
  });
  dropzone.addEventListener('dragover', (e) => { e.preventDefault(); dropzone.classList.add('dragover'); });
  dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));
  dropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropzone.classList.remove('dragover');
    if (e.dataTransfer.files[0]) uploadFile(e.dataTransfer.files[0]);
  });
}

function initTour() {
  if (localStorage.getItem('salesInsightTourDone')) return;
  const steps = [
    {target: '#btn-demo', text: 'Start here to explore the dashboard with synthetic data.'},
    {target: '#dropzone', text: 'Upload your Etsy, Shopify or Amazon CSV here.'},
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
    target.classList.add('tour-highlight');
    const rect = target.getBoundingClientRect();
    overlay.innerHTML = `<div>${step.text}</div><button id="tour-next">${stepIndex === steps.length - 1 ? 'Finish' : 'Next'}</button>`;
    overlay.style.top = (rect.bottom + 12) + 'px';
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
  $('#btn-demo').addEventListener('click', loadDemo);
  $('#btn-theme').addEventListener('click', toggleTheme);
  $('#btn-apply-filters').addEventListener('click', applyFilters);
  $('#btn-export').addEventListener('click', (e) => {
    e.preventDefault();
    const fmt = confirm('Export PDF? Cancel for Excel.') ? 'pdf' : 'xlsx';
    window.location.href = '/api/export/' + fmt;
  });
  setTimeout(initTour, 500);
});
