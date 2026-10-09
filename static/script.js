// JavaScript của Frontend: gọi API backend (app.py), đổ dữ liệu lên giao diện, vẽ biểu đồ Canvas.
'use strict';

// Mở bằng http://localhost:5000 thì gọi cùng địa chỉ; mở thẳng file index.html thì trỏ về backend.
const API_BASE = location.protocol === 'file:' ? 'http://127.0.0.1:5000' : '';
const REFRESH_MS = 10 * 60 * 1000 + 5000;  // backend chỉ gọi API mới sau 10 phút -> thêm 5 giây cho chắc
const SLOW_HINT_MS = 8000;                 // lần đầu backend phải tải dữ liệu tiếng ồn nên có thể chậm

// Cấu hình từng thẻ chỉ số: field = tên trường trong DuLieu, alert = LoaiCanhBao backend dùng,
// max = giá trị ứng với thanh tiến trình đầy (chỉ để hiển thị, không phải ngưỡng cảnh báo).
const METRICS = {
  pm25:     { field: 'PM25',    alert: 'PM2.5',    digits: 1, max: 75 },
  pm10:     { field: 'PM10',    alert: 'PM10',     digits: 1, max: 200 },
  temp:     { field: 'NhietDo', alert: 'Nhiệt độ', digits: 1, max: 45 },
  humidity: { field: 'DoAm',    alert: 'Độ ẩm',    digits: 0, max: 100 },
  noise:    { field: 'TiengOn', alert: 'Tiếng ồn', digits: 1, max: 100 },
};

// KetQua (backend) -> mã màu của thẻ AQI
const AQI_LEVELS = {
  'Tốt': 'good', 'Trung bình': 'moderate', 'Kém': 'poor',
  'Xấu': 'bad', 'Rất xấu': 'very-bad', 'Nguy hại': 'hazard',
};

const $ = (selector, root = document) => root.querySelector(selector);

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

// ---------------------------------------------------------------------------
// Gọi API
// ---------------------------------------------------------------------------
async function getJSON(path, signal) {
  let res;
  try {
    res = await fetch(API_BASE + path, {signal});
  } catch (err) {
    throw new Error('Không kết nối được máy chủ. Hãy kiểm tra app.py đang chạy tại http://localhost:5000.');
  }
  let body = null;
  try { body = await res.json(); } catch (err) { /* phản hồi không phải JSON */ }
  if (!res.ok) throw new Error((body && body.loi) || `Máy chủ trả về lỗi ${res.status}.`);
  return body;
}

// ---------------------------------------------------------------------------
// Định dạng
// ---------------------------------------------------------------------------
const pad2 = (n) => String(n).padStart(2, '0');

function formatNumber(value, digits) {
  return value === null || value === undefined ? '—' : Number(value).toFixed(digits);
}

function parseDate(iso) {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? null : d;
}

function formatFull(iso) {          // 17:30, 27/09/2026
  const d = parseDate(iso);
  return d ? `${pad2(d.getHours())}:${pad2(d.getMinutes())}, ${pad2(d.getDate())}/${pad2(d.getMonth() + 1)}/${d.getFullYear()}` : '—';
}

function formatShort(iso) {         // 27/09 17:30
  const d = parseDate(iso);
  return d ? `${pad2(d.getDate())}/${pad2(d.getMonth() + 1)} ${pad2(d.getHours())}:${pad2(d.getMinutes())}` : '';
}

function formatClock(iso) {         // 17:30
  const d = parseDate(iso);
  return d ? `${pad2(d.getHours())}:${pad2(d.getMinutes())}` : '';
}

// ---------------------------------------------------------------------------
// Trạng thái chung
// ---------------------------------------------------------------------------
function setStatus(state, text) {   // state: loading | ok | error
  const pill = $('#statusPill');
  pill.classList.remove('loading', 'ok', 'error');
  pill.classList.add(state);
  $('#statusText').textContent = text;
}

function showError(message) {
  $('#errorText').textContent = message;
  $('#errorBox').hidden = false;
}

function hideError() {
  $('#errorBox').hidden = true;
}

// ---------------------------------------------------------------------------
// Dữ liệu hiện tại (/api/capnhat)
// ---------------------------------------------------------------------------
function renderCurrent(result) {
  const data = result.DuLieu || {};

  $('#lastUpdate').textContent = formatFull(result.ThoiGian);

  // Mức cảnh báo theo từng chỉ số, lấy từ danh sách CanhBao của backend
  const levels = {};
  (result.CanhBao || []).forEach((a) => {
    if (a.MucDo === 'Cao') levels[a.LoaiCanhBao] = 'danger';
    else if (levels[a.LoaiCanhBao] !== 'danger') levels[a.LoaiCanhBao] = 'warning';
  });

  Object.entries(METRICS).forEach(([key, cfg]) => {
    const card = $(`[data-metric="${key}"]`);
    if (!card) return;
    const value = data[cfg.field];
    const badge = $('[data-role="badge"]', card);
    const bar = $('[data-role="bar"]', card);

    $('[data-role="value"]', card).textContent = formatNumber(value, cfg.digits);
    bar.style.width = value === null || value === undefined
      ? '0%'
      : `${Math.min(Math.max((value / cfg.max) * 100, 0), 100)}%`;

    if (value === null || value === undefined) {
      badge.className = 'muted';
      badge.textContent = 'Chưa có dữ liệu';
    } else if (levels[cfg.alert] === 'danger') {
      badge.className = 'danger';
      badge.textContent = 'Nguy hiểm';
    } else if (levels[cfg.alert] === 'warning') {
      badge.className = 'warning';
      badge.textContent = 'Theo dõi';
    } else {
      badge.className = 'normal';
      badge.textContent = 'Bình thường';
    }
  });

  renderAnalysis(result.PhanTich, data.US_AQI);
  renderPrediction(result.DuDoanRF);
  const noise = data.TiengOn_ChiTiet;
  $('#noiseSourceNote').textContent = noise
    ? `Tổng hợp quanh ${noise.KhuVuc || result.DiaDiem?.Ten || 'khu vực'}; không đo trực tiếp.${noise.DoGanNhat ? ` Lượt đo gần nhất trong nguồn: ${formatFull(noise.DoGanNhat)}.` : ''}`
    : 'Chưa có dữ liệu NoiseCapture phù hợp tại địa điểm này.';
}

function renderAnalysis(analysis, aqi) {
  const card = $('#aqiCard');
  const hasAqi = aqi !== null && aqi !== undefined;
  const level = analysis ? AQI_LEVELS[analysis.KetQua] : null;

  if (level) card.dataset.level = level; else delete card.dataset.level;
  $('#aqiValue').textContent = hasAqi ? Math.round(aqi) : '—';
  $('#aqiBar').style.width = hasAqi ? `${Math.min((aqi / 300) * 100, 100)}%` : '0%';

  if (!analysis) return;

  $('#aqiStatus').textContent = analysis.KetQua;
  $('#aqiNote').textContent = analysis.NhanXet;
  $('#aiTitle').textContent = `Chất lượng không khí: ${analysis.KetQua}`;
  $('#aiSummary').textContent = analysis.NhanXet;
  $('#aiAdvice').textContent = analysis.KhuyenNghi;
  $('#aiBox').classList.add('filled');
}

function renderPrediction(prediction) {
  const air = $('#rfAir');
  const noise = $('#rfNoise');
  const status = $('#rfStatus');
  if (prediction && prediction.TrangThai === 'ok') {
    air.textContent = prediction.ChatLuongKhongKhi;
    noise.textContent = prediction.MucTiengOn;
    status.textContent = 'Phân loại từ 5 chỉ số môi trường hiện tại.';
    return;
  }
  air.textContent = '—';
  noise.textContent = '—';
  status.textContent = prediction && prediction.TrangThai === 'thieu_du_lieu'
    ? 'Chưa đủ 5 chỉ số (gồm tiếng ồn) để chạy mô hình.'
    : 'Chưa tải được mô hình dự đoán.';
}

function renderCurrentFailed() {
  $('#aqiStatus').textContent = 'Chưa có dữ liệu';
  $('#aqiNote').textContent = 'Chưa lấy được dữ liệu chất lượng không khí.';
  $('#aiTitle').textContent = 'Chưa có tư vấn';
  $('#aiSummary').textContent = 'Chưa lấy được dữ liệu để đưa ra gợi ý.';
  $('#aiAdvice').textContent = '';
  $('#aiBox').classList.remove('filled');
  renderPrediction(null);
}

// ---------------------------------------------------------------------------
// Biểu đồ xu hướng PM2.5 (/api/dulieu/lichsu)
// ---------------------------------------------------------------------------
const canvas = $('#trendCanvas');
let trendPoints = [];               // [{ v: giá trị PM2.5, t: thời gian }]

function renderTrend(rows) {
  trendPoints = rows
    .filter((r) => r.PM25 !== null && r.PM25 !== undefined)
    .map((r) => ({ v: Number(r.PM25), t: r.ThoiGian }));

  const n = trendPoints.length;
  const last = n ? trendPoints[n - 1].v : null;

  $('#trendValue').textContent = formatNumber(last, 1);
  $('#trendLabel').textContent = describeTrend(trendPoints);
  canvas.setAttribute('aria-label', n
    ? `Biểu đồ xu hướng PM2.5 gồm ${n} lần đo, gần nhất là ${formatNumber(last, 1)} µg/m³`
    : 'Biểu đồ xu hướng PM2.5, chưa có dữ liệu');

  // Nhãn thời gian: tối đa 5 mốc, lấy từ dữ liệu thật
  const labels = $('#chartLabels');
  labels.replaceChildren();
  if (n) {
    const count = Math.min(5, n);
    const indexes = new Set(Array.from({ length: count }, (_, i) => Math.round((i * (n - 1)) / Math.max(count - 1, 1))));
    [...indexes].forEach((idx) => {
      labels.append(el('span', '', idx === n - 1 ? 'Hiện tại' : formatClock(trendPoints[idx].t)));
    });
  }

  drawTrend();
}

function describeTrend(points) {
  if (points.length < 2) return 'Chưa đủ dữ liệu';
  const first = points[0].v;
  const last = points[points.length - 1].v;
  const threshold = Math.max(3, first * 0.15);
  if (last - first > threshold) return 'Đang tăng';
  if (first - last > threshold) return 'Đang giảm';
  return 'Dao động nhẹ';
}

function drawTrend() {
  if (!canvas) return;
  const rect = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  const width = Math.max(rect.width, 320);
  const height = 220;

  canvas.width = width * dpr;
  canvas.height = height * dpr;
  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, width, height);

  const pad = { top: 18, right: 12, bottom: 18, left: 12 };
  const chartW = width - pad.left - pad.right;
  const chartH = height - pad.top - pad.bottom;

  // Lưới ngang
  ctx.strokeStyle = '#edf1ef';
  ctx.lineWidth = 1;
  [0, .25, .5, .75, 1].forEach((r) => {
    const y = pad.top + chartH * r;
    ctx.beginPath();
    ctx.moveTo(pad.left, y);
    ctx.lineTo(width - pad.right, y);
    ctx.stroke();
  });

  if (!trendPoints.length) {
    ctx.fillStyle = '#8a96a3';
    ctx.font = '13px Inter, Arial, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('Chưa có dữ liệu lịch sử', width / 2, height / 2);
    return;
  }

  // Trục dọc tự co giãn theo dữ liệu
  const values = trendPoints.map((p) => p.v);
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  const margin = Math.max((hi - lo) * 0.2, 5);
  const min = Math.max(0, lo - margin);
  const max = hi + margin;

  const points = values.map((value, i) => ({
    x: values.length === 1 ? pad.left + chartW / 2 : pad.left + (chartW * i) / (values.length - 1),
    y: pad.top + chartH - ((value - min) / (max - min)) * chartH,
  }));

  // Gradient vùng dưới biểu đồ
  const gradient = ctx.createLinearGradient(0, pad.top, 0, height);
  gradient.addColorStop(0, 'rgba(23,107,72,.22)');
  gradient.addColorStop(1, 'rgba(23,107,72,0)');

  ctx.beginPath();
  ctx.moveTo(points[0].x, height - pad.bottom);
  points.forEach((p) => ctx.lineTo(p.x, p.y));
  ctx.lineTo(points[points.length - 1].x, height - pad.bottom);
  ctx.closePath();
  ctx.fillStyle = gradient;
  ctx.fill();

  // Đường biểu diễn
  ctx.beginPath();
  points.forEach((p, i) => (i ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y)));
  ctx.strokeStyle = '#176b48';
  ctx.lineWidth = 3;
  ctx.lineJoin = 'round';
  ctx.lineCap = 'round';
  ctx.stroke();

  // Nút tròn trên biểu đồ
  points.forEach((p, i) => {
    ctx.beginPath();
    ctx.arc(p.x, p.y, i === points.length - 1 ? 5 : 3.5, 0, Math.PI * 2);
    ctx.fillStyle = '#fff';
    ctx.fill();
    ctx.strokeStyle = '#176b48';
    ctx.lineWidth = 2;
    ctx.stroke();
  });
}

function renderTrendFailed() {
  trendPoints = [];
  $('#trendValue').textContent = '—';
  $('#trendLabel').textContent = 'Không tải được lịch sử';
  $('#chartLabels').replaceChildren();
  drawTrend();
}

// ---------------------------------------------------------------------------
// Lịch sử cảnh báo (/api/canhbao)
// ---------------------------------------------------------------------------
function historyItem(kind, icon, title, text, time) {
  const item = el('div', 'history-item');
  const body = el('div');
  body.append(el('strong', '', title), el('p', '', text));
  item.append(el('div', `history-icon ${kind}`, icon), body);
  if (time) {
    const t = el('time', '', time);
    item.append(t);
  }
  return item;
}

function renderAlerts(list) {
  const box = $('#warningHistory');
  box.replaceChildren();

  if (!list.length) {
    box.append(historyItem('normal', '✓', 'Chưa có cảnh báo đã lưu', 'Chưa ghi nhận cảnh báo cho địa điểm đang chọn.'));
    return;
  }
  list.forEach((a) => {
    const high = a.MucDo === 'Cao';
    box.append(historyItem(
      high ? 'danger' : 'warning',
      '!',
      `${a.LoaiCanhBao} ${high ? 'ở mức nguy hiểm' : 'cần theo dõi'}`,
      a.NoiDung,
      formatShort(a.ThoiGian),
    ));
  });
}

function renderAlertsFailed(message) {
  const box = $('#warningHistory');
  box.replaceChildren(historyItem('warning', '!', 'Không tải được lịch sử cảnh báo', message));
}

// ---------------------------------------------------------------------------
// Luồng chính
// ---------------------------------------------------------------------------
let loading = false;
let hasCurrentData = false;         // đã từng lấy được dữ liệu hiện tại chưa (để giữ số cũ nếu lần sau lỗi)
let refreshVersion = 0;
let activeRefresh = null;

async function loadAll(changed = false) {
  await window.EnvironmentLocation.ready;
  if (loading && !changed) return;
  if (changed) {
    activeRefresh?.abort();
    hasCurrentData = false;
    renderCurrent({DuLieu: {}});
    renderCurrentFailed();
    renderTrendFailed();
    $('#warningHistory').replaceChildren();
    hideError();
  }
  const version = ++refreshVersion;
  const identifier = window.EnvironmentLocation.current.MaDiaDiem;
  const controller = new AbortController();
  activeRefresh = controller;
  loading = true;
  $('#mainContent').setAttribute('aria-busy', 'true');
  setStatus('loading', 'Đang tải dữ liệu…');
  const slowTimer = setTimeout(
    () => { if (version === refreshVersion) setStatus('loading', 'Đang lấy dữ liệu cho địa điểm đã chọn…'); },
    SLOW_HINT_MS,
  );

  // 1) Gọi /api/capnhat trước để backend lưu bản ghi + cảnh báo mới vào DB
  let currentOk = true;
  try {
    const result = await getJSON(window.EnvironmentLocation.query('/api/capnhat', identifier), controller.signal);
    if (version !== refreshVersion) { clearTimeout(slowTimer); return; }
    renderCurrent(result);
    hasCurrentData = true;
    hideError();
  } catch (err) {
    if (version !== refreshVersion) { clearTimeout(slowTimer); return; }
    currentOk = false;
    if (!hasCurrentData) renderCurrentFailed();
    showError(err.message);
  }

  // 2) Sau đó đọc lịch sử và cảnh báo từ DB (hai phần độc lập, lỗi phần nào hiện phần đó)
  const [history, alerts] = await Promise.allSettled([
    getJSON(window.EnvironmentLocation.query('/api/dulieu/lichsu?limit=12', identifier), controller.signal),
    getJSON(window.EnvironmentLocation.query('/api/canhbao?limit=8', identifier), controller.signal),
  ]);
  if (version !== refreshVersion) { clearTimeout(slowTimer); return; }
  if (history.status === 'fulfilled') renderTrend(history.value); else renderTrendFailed();
  if (alerts.status === 'fulfilled') renderAlerts(alerts.value); else renderAlertsFailed(alerts.reason.message);

  clearTimeout(slowTimer);
  if (currentOk) setStatus('ok', 'Hệ thống hoạt động');
  else setStatus('error', 'Chưa lấy được dữ liệu mới');
  $('#mainContent').setAttribute('aria-busy', 'false');
  loading = false;
}

$('#retryBtn').addEventListener('click', () => loadAll());
document.addEventListener('locationchange', () => loadAll(true));

// Xử lý resize màn hình
let resizeTimer;
window.addEventListener('resize', () => {
  cancelAnimationFrame(resizeTimer);
  resizeTimer = requestAnimationFrame(drawTrend);
});

loadAll();
setInterval(loadAll, REFRESH_MS);
