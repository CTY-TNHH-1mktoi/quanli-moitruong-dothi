'use strict';

(() => {
  const base = location.protocol === 'file:' ? 'http://127.0.0.1:5000' : '';
  const select = document.getElementById('locationSelect');
  const search = document.getElementById('locationSearch');
  const busyReasons = new Set();
  let places = [];
  let selected = {MaDiaDiem: 'hanoi', Ten: 'Hà Nội', ViDo: 21.0285, KinhDo: 105.8542, TenKhuVucTiengOn: 'Cầu Giấy, Hà Nội'};
  const normalize = (value) => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/đ/gi, 'd').toLowerCase();

  function renderHeader() {
    document.getElementById('locationTitle').textContent = selected.Ten;
    document.getElementById('locationSource').textContent = `Thời tiết và không khí: vị trí tham chiếu ${selected.Ten} (Open-Meteo). Tiếng ồn: quanh ${selected.TenKhuVucTiengOn} (NoiseCapture).`;
    document.getElementById('locationDetails').textContent = `Tọa độ tham chiếu: ${selected.ViDo.toFixed(4)}, ${selected.KinhDo.toFixed(4)} · ${selected.NguonToaDo || 'Dữ liệu dự án'}`;
  }

  function renderOptions() {
    const term = normalize(search.value.trim());
    const matches = places.filter((place) => normalize(`${place.Ten} ${place.Nhom}`).includes(term));
    select.replaceChildren();
    const groups = new Map();
    function option(place, group) {
      const element = document.createElement('option');
      element.value = place.MaDiaDiem;
      element.textContent = place.Ten;
      group.append(element);
    }
    if (!matches.some((place) => place.MaDiaDiem === selected.MaDiaDiem)) {
      option(selected, select);
    }
    matches.forEach((place) => {
      if (!groups.has(place.Nhom)) {
        const group = document.createElement('optgroup');
        group.label = place.Nhom;
        groups.set(place.Nhom, group);
        select.append(group);
      }
      option(place, groups.get(place.Nhom));
    });
    select.value = selected.MaDiaDiem;
    if (term && !matches.length) {
      document.getElementById('locationDetails').textContent = 'Không tìm thấy địa điểm phù hợp. Hãy thử tên khác.';
    } else renderHeader();
  }

  async function loadCatalogue(notify = false) {
    try {
      const response = await fetch(`${base}/api/diadiem`);
      const result = await response.json();
      if (!response.ok) throw new Error(result.loi || 'Không tải được danh sách địa điểm.');
      places = result.DiaDiem;
      let saved = null;
      try { saved = localStorage.getItem('environment.location.v1'); } catch (error) { /* Storage can be disabled. */ }
      selected = places.find((place) => place.MaDiaDiem === saved)
        || places.find((place) => place.MaDiaDiem === result.MacDinh);
      document.getElementById('locationError').hidden = true;
      renderOptions();
      if (notify) document.dispatchEvent(new CustomEvent('locationchange', {detail: selected}));
    } catch (error) {
      document.getElementById('locationErrorText').textContent = 'Chưa tải được danh sách địa điểm. Hãy thử lại.';
      document.getElementById('locationError').hidden = false;
    }
    return selected;
  }

  let ready = loadCatalogue();
  window.EnvironmentLocation = {
    get ready() { return ready; },
    get current() { return selected; },
    get places() { return places.slice(); },
    setBusy(reason, value) {
      if (value) busyReasons.add(reason); else busyReasons.delete(reason);
      select.disabled = busyReasons.size > 0;
      search.disabled = busyReasons.size > 0;
      document.getElementById('locationRetry').disabled = busyReasons.size > 0;
    },
    query(path, identifier = selected.MaDiaDiem) {
      return `${path}${path.includes('?') ? '&' : '?'}location=${encodeURIComponent(identifier)}`;
    },
  };
  select.addEventListener('change', () => {
    if (busyReasons.size) return;
    selected = places.find((place) => place.MaDiaDiem === select.value) || selected;
    try { localStorage.setItem('environment.location.v1', selected.MaDiaDiem); } catch (error) { /* Keep the selection for this page. */ }
    renderHeader();
    document.dispatchEvent(new CustomEvent('locationchange', {detail: selected}));
  });
  search.addEventListener('input', renderOptions);
  document.getElementById('locationRetry').addEventListener('click', () => {
    ready = loadCatalogue(true);
  });
})();
