'use strict';

(() => {
  const base = location.protocol === 'file:' ? 'http://127.0.0.1:5000' : '';
  const select = document.getElementById('locationSelect');
  const search = document.getElementById('locationSearch');
  const locate = document.getElementById('locateMe');
  const locateLabel = document.getElementById('locateMeLabel');
  const geolocationStatus = document.getElementById('geolocationStatus');
  const busyReasons = new Set();
  let places = [];
  let catalogueLoading = false;
  let locating = false;
  let geolocationVersion = 0;
  let selected = {MaDiaDiem: 'hanoi', Ten: 'Hà Nội', ViDo: 21.0285, KinhDo: 105.8542, TenKhuVucTiengOn: 'Cầu Giấy, Hà Nội'};

  function syncControls() {
    const busy = catalogueLoading || busyReasons.size > 0;
    select.disabled = busy;
    search.disabled = busy;
    document.getElementById('locationRetry').disabled = busy;
    locate.disabled = busy || locating || !places.length;
    locate.setAttribute('aria-busy', String(locating));
    locateLabel.textContent = locating ? 'Đang định vị…' : 'Lấy vị trí hiện tại';
  }

  function showGeolocationStatus(message, state) {
    geolocationStatus.textContent = message;
    geolocationStatus.dataset.state = state;
    geolocationStatus.hidden = false;
  }

  function resetGeolocation() {
    // A manual choice supersedes a position request still waiting for permission.
    geolocationVersion += 1;
    locating = false;
    geolocationStatus.hidden = true;
    geolocationStatus.textContent = '';
    syncControls();
  }

  function validCoordinates(latitude, longitude) {
    return Number.isFinite(latitude) && Math.abs(latitude) <= 90
      && Number.isFinite(longitude) && Math.abs(longitude) <= 180;
  }

  function distanceKm(latitude, longitude, place) {
    const radians = (degrees) => degrees * Math.PI / 180;
    const latDifference = radians(place.ViDo - latitude);
    const lonDifference = radians(place.KinhDo - longitude);
    const haversine = Math.sin(latDifference / 2) ** 2
      + Math.cos(radians(latitude)) * Math.cos(radians(place.ViDo)) * Math.sin(lonDifference / 2) ** 2;
    return 6371 * 2 * Math.asin(Math.sqrt(Math.min(1, Math.max(0, haversine))));
  }

  function locateNearest() {
    if (locate.disabled) return;
    resetGeolocation();
    if (!window.isSecureContext) {
      showGeolocationStatus('Hãy mở trang bằng HTTPS hoặc localhost để lấy vị trí.', 'error');
      return;
    }
    if (!navigator.geolocation) {
      showGeolocationStatus('Trình duyệt chưa hỗ trợ lấy vị trí. Bạn hãy chọn địa điểm trong danh sách.', 'error');
      return;
    }
    const request = geolocationVersion;
    locating = true;
    syncControls();
    showGeolocationStatus('Đang lấy vị trí để tìm địa điểm gần nhất…', 'loading');

    function fail(error) {
      if (request !== geolocationVersion) return;
      locating = false;
      syncControls();
      const messages = {
        1: 'Bạn chưa cho phép truy cập vị trí. Hãy bật quyền vị trí cho trang rồi thử lại.',
        2: 'Chưa xác định được vị trí. Kiểm tra dịch vụ vị trí trên thiết bị rồi thử lại.',
        3: 'Lấy vị trí quá lâu. Hãy thử lại hoặc chọn địa điểm trong danh sách.',
      };
      showGeolocationStatus(messages[error?.code] || 'Không lấy được vị trí hiện tại. Bạn có thể thử lại hoặc chọn địa điểm trong danh sách.', 'error');
    }

    try {
      navigator.geolocation.getCurrentPosition((position) => {
        if (request !== geolocationVersion) return;
        locating = false;
        syncControls();
        const {latitude, longitude} = position.coords;
        if (!validCoordinates(latitude, longitude)) { fail(); return; }
        let nearest = null;
        let distance = Infinity;
        for (const place of places) {
          if (!validCoordinates(place.ViDo, place.KinhDo)) continue;
          const candidateDistance = distanceKm(latitude, longitude, place);
          if (candidateDistance < distance) { nearest = place; distance = candidateDistance; }
        }
        if (!nearest) {
          showGeolocationStatus('Chưa có địa điểm với tọa độ hợp lệ để đối chiếu. Bạn hãy chọn trong danh sách.', 'error');
          return;
        }
        if (!selectPlace(nearest.MaDiaDiem)) {
          showGeolocationStatus('Hệ thống đang xử lý yêu cầu khác. Bạn hãy lấy lại vị trí sau khi hoàn tất.', 'error');
          return;
        }
        const distanceLabel = distance < .1 ? 'dưới 100 m'
          : distance < 1 ? `khoảng ${Math.round(distance * 1000).toLocaleString('vi-VN')} m`
          : `khoảng ${distance.toLocaleString('vi-VN', {maximumFractionDigits: 1})} km`;
        showGeolocationStatus(`Đã chọn ${nearest.Ten}, gần bạn nhất trong danh sách (${distanceLabel}).`, 'success');
      }, fail, {enableHighAccuracy: true, timeout: 12000, maximumAge: 0});
    } catch (error) { fail(error); }
  }

  function renderHeader() {
    document.getElementById('locationTitle').textContent = selected.Ten;
    document.getElementById('locationSource').textContent = `Thời tiết và không khí: vị trí tham chiếu ${selected.Ten} (Open-Meteo). Tiếng ồn: quanh ${selected.TenKhuVucTiengOn} (NoiseCapture).`;
    document.getElementById('locationDetails').textContent = `Tọa độ tham chiếu: ${selected.ViDo.toFixed(4)}, ${selected.KinhDo.toFixed(4)} · ${selected.NguonToaDo || 'Dữ liệu dự án'}`;
  }

  function renderOptions() {
    select.replaceChildren();
    const groups = new Map();
    function option(place, group) {
      const element = document.createElement('option');
      element.value = place.MaDiaDiem;
      element.textContent = place.Ten;
      group.append(element);
    }
    if (!places.some((place) => place.MaDiaDiem === selected.MaDiaDiem)) {
      option(selected, select);
    }
    places.forEach((place) => {
      if (!groups.has(place.Nhom)) {
        const group = document.createElement('optgroup');
        group.label = place.Nhom;
        groups.set(place.Nhom, group);
        select.append(group);
      }
      option(place, groups.get(place.Nhom));
    });
    select.value = selected.MaDiaDiem;
    renderHeader();
  }

  function selectPlace(identifier) {
    if (catalogueLoading || busyReasons.size) return false;
    const place = places.find((item) => item.MaDiaDiem === identifier);
    if (!place) return false;
    resetGeolocation();
    const changed = selected.MaDiaDiem !== identifier;
    selected = place;
    select.value = identifier;
    try { localStorage.setItem('environment.location.v1', identifier); } catch (error) { /* Keep the selection for this page. */ }
    renderHeader();
    if (changed) document.dispatchEvent(new CustomEvent('locationchange', {detail: selected}));
    return true;
  }

  async function loadCatalogue(notify = false) {
    catalogueLoading = true;
    resetGeolocation();
    try {
      const response = await fetch(`${base}/api/diadiem`);
      const result = await response.json();
      if (!response.ok) throw new Error(result.loi || 'Không tải được danh sách địa điểm.');
      if (!Array.isArray(result.DiaDiem) || !result.DiaDiem.length) throw new Error('Danh sách địa điểm trống.');
      places = result.DiaDiem;
      let saved = null;
      try { saved = localStorage.getItem('environment.location.v1'); } catch (error) { /* Storage can be disabled. */ }
      selected = places.find((place) => place.MaDiaDiem === saved)
        || places.find((place) => place.MaDiaDiem === result.MacDinh) || places[0];
      document.getElementById('locationError').hidden = true;
      renderOptions();
      if (notify) document.dispatchEvent(new CustomEvent('locationchange', {detail: selected}));
    } catch (error) {
      document.getElementById('locationErrorText').textContent = 'Chưa tải được danh sách địa điểm. Hãy thử lại.';
      document.getElementById('locationError').hidden = false;
    } finally {
      catalogueLoading = false;
      syncControls();
    }
    return selected;
  }

  let ready = loadCatalogue();
  window.EnvironmentLocation = {
    get ready() { return ready; },
    get current() { return selected; },
    get places() { return places.slice(); },
    select: selectPlace,
    setBusy(reason, value) {
      if (value) busyReasons.add(reason); else busyReasons.delete(reason);
      syncControls();
    },
    query(path, identifier = selected.MaDiaDiem) {
      return `${path}${path.includes('?') ? '&' : '?'}location=${encodeURIComponent(identifier)}`;
    },
  };
  select.addEventListener('change', () => selectPlace(select.value));
  locate.addEventListener('click', locateNearest);
  document.getElementById('locationRetry').addEventListener('click', () => {
    ready = loadCatalogue(true);
  });
})();
