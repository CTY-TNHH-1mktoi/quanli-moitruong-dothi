'use strict';

(() => {
  const base = location.protocol === 'file:' ? 'http://127.0.0.1:5000' : '';
  const byId = (id) => document.getElementById(id);
  const form = byId('reportForm');
  const period = byId('reportPeriod');
  const create = byId('reportCreate');
  const csv = byId('reportCsv');
  const print = byId('reportPrint');
  const status = byId('reportStatus');
  const history = byId('reportHistory');
  const more = byId('reportHistoryMore');
  let historyOffset = 0;
  let current = null;
  let busy = false;
  const selectedLocation = () => window.EnvironmentLocation.current;
  const scoped = (path) => window.EnvironmentLocation.query(path);

  function node(tag, text, className) {
    const element = document.createElement(tag);
    if (text !== undefined) element.textContent = text;
    if (className) element.className = className;
    return element;
  }

  const number = (value, digits = 1) => value == null ? '—' : Number(value).toLocaleString('vi-VN', {maximumFractionDigits: digits});
  const date = (value) => value ? new Date(value).toLocaleString('vi-VN', {hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit', year: 'numeric'}) : '—';
  const periodLabel = (days) => days === 1 ? '24 giờ' : `${days} ngày`;

  function setBusy(value) {
    busy = value;
    window.EnvironmentLocation.setBusy('reports', value);
    form.setAttribute('aria-busy', String(value));
    create.disabled = value;
    period.disabled = value;
    csv.disabled = value || !current || !current.TongQuan.SoBanGhi;
    print.disabled = value || !current;
    history.querySelectorAll('button').forEach((button) => { button.disabled = value; });
    byId('reportRetry').disabled = value;
    more.disabled = value;
    create.textContent = value ? 'Đang xử lý…' : 'Tạo & lưu báo cáo';
  }

  function showError(message) {
    byId('reportErrorText').textContent = message;
    byId('reportError').hidden = false;
  }

  async function request(path, options = {}) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 30000);
    try {
      const response = await fetch(base + path, {...options, signal: controller.signal});
      const result = await response.json();
      if (!response.ok) throw new Error(result.loi || 'Không đọc được báo cáo.');
      return result;
    } catch (error) {
      if (error.name === 'AbortError') throw new Error('Máy chủ chưa phản hồi. Tải lại lịch sử để kiểm tra báo cáo đã được lưu hay chưa.');
      if (error instanceof TypeError) throw new Error('Không kết nối được máy chủ để đọc hoặc lưu báo cáo.');
      throw error;
    } finally {
      clearTimeout(timer);
    }
  }

  function renderAdvice(id, items) {
    const box = byId(id);
    box.replaceChildren();
    items.forEach((item) => {
      const entry = node('div', undefined, 'report-advice');
      entry.append(node('strong', item.TieuDe), node('p', item.NoiDung), node('small', item.CanCu));
      if (item.MucDo === 'Cao') entry.classList.add('high');
      box.append(entry);
    });
  }

  function render(report) {
    if (report.DiaDiem?.MaDiaDiem !== selectedLocation().MaDiaDiem) {
      throw new Error('Báo cáo không thuộc địa điểm đang chọn. Hãy tải lại lịch sử.');
    }
    current = report;
    period.value = String(report.SoNgay);
    byId('reportOutput').hidden = false;
    byId('reportTitle').textContent = `${report.DiaDiem.Ten} · Báo cáo #${report.MaBaoCao} · ${periodLabel(report.SoNgay)}`;
    byId('reportMeta').textContent = `${date(report.TuNgay)} → ${date(report.DenNgay)} · Tạo lúc ${date(report.ThoiGianTao)}`;
    const overview = report.TongQuan;
    byId('reportPriority').textContent = `Ưu tiên trong kỳ: ${overview.MucUuTien}`;
    byId('reportPriority').classList.toggle('high', overview.SoCanhBaoCao > 0);
    byId('reportSummary').textContent = overview.TomTat;
    byId('reportCoverage').textContent = overview.SoBanGhi
      ? `Bản ghi thực tế từ ${date(overview.ThoiGianDau)} đến ${date(overview.ThoiGianCuoi)} · ${overview.SoNguon} nguồn. Khoảng này có thể ngắn hơn kỳ đã chọn.`
      : 'Không có bản ghi môi trường trong kỳ đã chọn.';
    const stats = byId('reportStats');
    stats.replaceChildren();
    [
      ['Bản ghi môi trường', overview.SoBanGhi],
      ['Cảnh báo đã lưu', overview.SoCanhBao],
      ['Cảnh báo mức cao', overview.SoCanhBaoCao],
      ['Bản ghi có cảnh báo', overview.TyLeBanGhiCoCanhBao == null ? '—' : `${number(overview.TyLeBanGhiCoCanhBao)}%`],
    ].forEach(([label, value]) => {
      const card = node('div', undefined, 'report-stat');
      card.append(node('span', label), node('strong', String(value)));
      stats.append(card);
    });

    const metrics = byId('reportMetrics');
    metrics.replaceChildren();
    report.ChiSo.forEach((metric) => {
      const row = node('tr');
      const label = node('th', metric.Ten);
      label.scope = 'row';
      label.append(node('small', metric.DonVi));
      row.append(label);
      let change = 'Chưa đủ dữ liệu';
      if (metric.LoaiDuLieu === 'tong_hop_khu_vuc') change = 'Tổng hợp khu vực';
      else if (metric.ThayDoi != null) change = `${metric.ThayDoi > 0 ? '+' : ''}${number(metric.ThayDoi)}`;
      [
        `${metric.SoBanGhi}/${overview.SoBanGhi}`,
        metric.LoaiDuLieu === 'tong_hop_khu_vuc' ? 'Không tính TB' : number(metric.TrungBinh),
        number(metric.ThapNhat), number(metric.CaoNhat), number(metric.GanNhat), change,
        metric.TyLeNguongLuuY == null ? '—' : `${metric.VuotNguongLuuY}/${metric.SoBanGhi} (${number(metric.TyLeNguongLuuY)}%)`,
      ].forEach((value) => row.append(node('td', value)));
      metrics.append(row);
    });
    renderAdvice('reportPlanning', report.QuyHoach);
    renderAdvice('reportResponse', report.XuLySuCo);

    byId('reportTrendDescription').textContent = report.SoNgay === 1
      ? 'Nhóm theo giờ có bản ghi; không nội suy các khoảng thiếu dữ liệu.'
      : 'Nhóm theo ngày có bản ghi; không nội suy các ngày thiếu dữ liệu.';
    const trend = byId('reportTrend');
    trend.replaceChildren();
    report.XuHuong.forEach((bucket) => {
      const row = node('tr');
      const label = report.SoNgay === 1 ? date(bucket.ThoiGian) : new Date(bucket.ThoiGian).toLocaleDateString('vi-VN');
      [label, `${bucket.SoBanGhiPM25}/${bucket.SoBanGhi}`, number(bucket.TrungBinhPM25), number(bucket.CaoNhatPM25)]
        .forEach((value) => row.append(node('td', value)));
      trend.append(row);
    });
    if (!report.XuHuong.length) {
      const row = node('tr');
      const cell = node('td', 'Chưa có bản ghi trong kỳ.');
      cell.colSpan = 4;
      row.append(cell);
      trend.append(row);
    }

    const summary = byId('reportAlertSummary');
    summary.replaceChildren();
    report.CanhBaoTheoLoai.forEach((item) => summary.append(node('span', `${item.LoaiCanhBao}: ${item.SoCanhBao} cảnh báo · ${item.SoCanhBaoCao} mức cao`)));
    if (!report.CanhBaoTheoLoai.length) summary.append(node('p', overview.SoBanGhi ? 'Không có cảnh báo đã lưu gắn với các bản ghi trong kỳ.' : 'Chưa có dữ liệu để đánh giá cảnh báo.'));
    const alerts = byId('reportAlerts');
    alerts.replaceChildren();
    report.CanhBao.slice(0, 10).forEach((alert) => {
      const entry = node('li');
      entry.append(node('strong', `${alert.LoaiCanhBao} · ${alert.MucDo}`), node('p', alert.NoiDung), node('small', date(alert.ThoiGian)));
      alerts.append(entry);
    });
    if (report.CanhBao.length > 10) alerts.append(node('li', `Hiển thị 10/${report.CanhBao.length} cảnh báo gần nhất; số liệu tổng hợp tính toàn bộ kỳ.`));
    const notes = byId('reportNotes');
    notes.replaceChildren(...report.GhiChu.map((text) => node('li', text)));
    notes.append(node('li', `Nguồn có trong kỳ: ${report.Nguon.map((source) => `${source.TenNguon} (${source.SoBanGhi} bản ghi)`).join('; ') || 'chưa có'}.`));
    status.textContent = `Đã lưu báo cáo #${report.MaBaoCao}. Dữ liệu được giữ nguyên theo thời điểm tạo.`;
  }

  async function loadHistory(append = false) {
    const offset = append ? historyOffset : 0;
    const reports = await request(scoped(`/api/baocao?limit=10&offset=${offset}`));
    if (!append) history.replaceChildren();
    reports.forEach((report) => {
      const entry = node('div', undefined, 'report-history-item');
      const copy = node('div');
      copy.append(node('strong', `Báo cáo #${report.MaBaoCao} · ${periodLabel(report.SoNgay)}`),
        node('p', `${date(report.ThoiGianTao)} · ${report.SoBanGhi} bản ghi · ${report.SoCanhBao} cảnh báo`));
      const open = node('button', 'Mở');
      open.type = 'button';
      open.dataset.reportId = String(report.MaBaoCao);
      open.setAttribute('aria-label', `Mở báo cáo số ${report.MaBaoCao}`);
      open.addEventListener('click', () => openReport(report.MaBaoCao));
      entry.append(copy, open);
      history.append(entry);
    });
    if (!reports.length && !append) history.append(node('p', `Chưa có báo cáo đã lưu cho ${selectedLocation().Ten}. Chọn kỳ và bấm Tạo & lưu báo cáo.`, 'report-description'));
    historyOffset = offset + reports.length;
    more.hidden = reports.length < 10;
    return reports;
  }

  async function openReport(id) {
    if (busy) return;
    setBusy(true);
    byId('reportError').hidden = true;
    status.textContent = 'Đang mở báo cáo đã lưu…';
    try { render(await request(scoped(`/api/baocao/${id}`))); }
    catch (error) { showError(error.message); status.textContent = 'Chưa mở được báo cáo.'; }
    finally { setBusy(false); }
  }

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    await window.EnvironmentLocation.ready;
    if (busy) return;
    const days = Number(period.value);
    setBusy(true);
    byId('reportError').hidden = true;
    status.textContent = 'Đang tổng hợp dữ liệu và lưu báo cáo…';
    try {
      render(await request('/api/baocao', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({days, location: selectedLocation().MaDiaDiem})}));
      try { await loadHistory(); }
      catch (error) { showError(`Báo cáo đã lưu, nhưng chưa tải lại được lịch sử: ${error.message}`); }
    } catch (error) {
      showError(error.message);
      status.textContent = current ? `Đang hiển thị báo cáo #${current.MaBaoCao}; chưa xác nhận lưu báo cáo mới.` : 'Chưa tạo được báo cáo.';
    } finally { setBusy(false); }
  });

  function csvCell(value) {
    let text = value == null ? '' : String(value);
    // Text source names may come from outside the app; do not execute as formulas.
    if (typeof value === 'string' && /^[=+@\-\t\r]/.test(text)) text = `'${text}`;
    return `"${text.replace(/"/g, '""')}"`;
  }

  csv.addEventListener('click', () => {
    if (!current || busy || !current.TongQuan.SoBanGhi) return;
    const counts = new Map();
    current.CanhBao.forEach((alert) => {
      const count = counts.get(alert.Manguon) || {all: 0, high: 0};
      count.all += 1;
      if (alert.MucDo === 'Cao') count.high += 1;
      counts.set(alert.Manguon, count);
    });
    const rows = [[
      'Mã báo cáo', 'Mã địa điểm', 'Địa điểm', 'Vĩ độ tham chiếu', 'Kinh độ tham chiếu',
      'Kỳ bắt đầu', 'Kỳ kết thúc', 'Mã bản ghi', 'Nguồn', 'Thời gian',
      'PM2.5 (µg/m³)', 'PM10 (µg/m³)', 'Nhiệt độ (°C)', 'Độ ẩm (%)', 'Tiếng ồn tổng hợp (dBA)', 'Số cảnh báo', 'Cảnh báo mức cao',
    ]];
    current.DuLieu.forEach((row) => rows.push([
      current.MaBaoCao, current.DiaDiem.MaDiaDiem, current.DiaDiem.Ten, current.DiaDiem.ViDo, current.DiaDiem.KinhDo,
      current.TuNgay, current.DenNgay, row.Manguon, row.TenNguon, row.ThoiGian,
      row.PM25, row.PM10, row.NhietDo, row.DoAm, row.TiengOn, counts.get(row.Manguon)?.all || 0, counts.get(row.Manguon)?.high || 0,
    ]));
    const blob = new Blob(['\uFEFF' + rows.map((row) => row.map(csvCell).join(',')).join('\r\n')], {type: 'text/csv;charset=utf-8;'});
    const url = URL.createObjectURL(blob);
    const link = node('a');
    link.href = url;
    link.download = `bao-cao-${current.DiaDiem.MaDiaDiem}-${current.MaBaoCao}.csv`;
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });

  print.addEventListener('click', () => {
    if (current && !busy) window.print();
  });

  async function initialize(changed = false) {
    await window.EnvironmentLocation.ready;
    if (busy) return;
    if (changed) {
      current = null;
      historyOffset = 0;
      history.replaceChildren();
      more.hidden = true;
      byId('reportOutput').hidden = true;
    }
    setBusy(true);
    byId('reportError').hidden = true;
    try {
      const reports = await loadHistory();
      if (!current && reports.length) render(await request(scoped(`/api/baocao/${reports[0].MaBaoCao}`)));
      else if (!current) status.textContent = `${selectedLocation().Ten}: chọn kỳ để tạo và lưu báo cáo đầu tiên.`;
    } catch (error) { showError(error.message); status.textContent = 'Chưa tải được lịch sử báo cáo.'; }
    finally { setBusy(false); }
  }
  byId('reportRetry').addEventListener('click', () => initialize());
  document.addEventListener('locationchange', () => initialize(true));
  more.addEventListener('click', async () => {
    if (busy) return;
    setBusy(true);
    byId('reportError').hidden = true;
    try { await loadHistory(true); }
    catch (error) { showError(error.message); }
    finally { setBusy(false); }
  });
  initialize();
})();
