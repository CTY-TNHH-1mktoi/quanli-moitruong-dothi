'use strict';

(() => {
  const container = document.getElementById('locationMap');
  const status = document.getElementById('mapStatus');
  const retry = document.getElementById('mapRetry');
  const recenter = document.getElementById('mapRecenter');
  const airToggle = document.getElementById('mapAirToggle');
  const airStatus = document.getElementById('mapAirStatus');
  const airRetry = document.getElementById('mapAirRetry');
  const opacity = document.getElementById('mapAirOpacity');
  let selected;
  let map;
  let tiles;
  let marker;
  let noiseMarker;
  let noisePoint;
  let failedTiles = 0;
  let airLayer;
  let airData = null;
  let airTimer;
  let airRequest;
  let airVersion = 0;
  let cityLabels;

  function sourceTime(value) {
    if (!value) return 'chưa rõ thời gian';
    const iso = /(?:Z|[+-]\d{2}:\d{2})$/.test(value) ? value : `${value}+07:00`;
    return new Date(iso).toLocaleString('vi-VN', {timeZone: 'Asia/Ho_Chi_Minh',
      day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit'});
  }

  function updateAirControls() {
    document.getElementById('mapAirLegend').hidden = !airToggle.checked;
    document.getElementById('mapAirStatusRow').hidden = !airToggle.checked;
    opacity.disabled = !airToggle.checked;
    if (selected) document.getElementById('mapHeading').textContent = airToggle.checked
      ? `Chất lượng không khí tại ${selected.Ten}` : 'Bản đồ địa điểm đang chọn';
  }

  function queueAirLoad(delay = 650) {
    clearTimeout(airTimer);
    airRequest?.abort();
    const version = ++airVersion;
    if (!airToggle.checked || !map || !selected) return;
    airTimer = setTimeout(() => loadAirData(version), delay);
  }

  async function loadAirData(version) {
    if (version !== airVersion || !airToggle.checked) return;
    const controller = new AbortController();
    airRequest = controller;
    const timer = setTimeout(() => controller.abort(), 35000);
    const identifier = selected.MaDiaDiem;
    const bounds = map.getBounds();
    const query = new URLSearchParams({location: identifier,
      south: bounds.getSouth(), west: bounds.getWest(), north: bounds.getNorth(), east: bounds.getEast()});
    const base = location.protocol === 'file:' ? 'http://127.0.0.1:5000' : '';
    airStatus.textContent = 'Đang lấy AQI cho vùng bản đồ đang xem…';
    airRetry.hidden = true;
    try {
      const response = await fetch(`${base}/api/bando/khongkhi?${query}`, {signal: controller.signal});
      const result = await response.json();
      if (version !== airVersion || identifier !== selected.MaDiaDiem) return;
      if (!response.ok) throw new Error(result.loi || 'Chưa tải được lớp màu AQI.');
      if (result.DiaDiem?.MaDiaDiem !== identifier) throw new Error('Dữ liệu bản đồ không đúng địa điểm đang chọn.');
      airData = result;
      airLayer.setData(result);
      if (!result.SoDiem) {
        airStatus.textContent = 'Chưa có dữ liệu AQI phủ vùng đang xem. Lớp màu hiện hỗ trợ Việt Nam và khu vực lân cận.';
        return;
      }
      const first = sourceTime(result.ThoiGianNguonDau);
      const last = result.ThoiGianNguonDau === result.ThoiGianNguonCuoi ? '' : ` → ${sourceTime(result.ThoiGianNguonCuoi)}`;
      airStatus.textContent = `${result.Nguon} · US AQI · Nguồn lúc ${first}${last} (giờ Việt Nam) · Mô hình khoảng ${result.DoPhanGiaiMoHinhKm} km · Lấy mẫu khoảng ${Math.round(result.BuocLuoiDo * 111)} km. ${result.CanhBao || 'Bấm bản đồ để xem AQI ước tính.'}`;
      airRetry.hidden = !result.CanhBao;
    } catch (error) {
      if (version !== airVersion) return;
      airStatus.textContent = error.name === 'AbortError'
        ? 'Nguồn AQI chưa phản hồi. Bạn có thể thử tải lại.'
        : (error instanceof TypeError ? 'Chưa kết nối được máy chủ để tải lớp màu AQI.' : error.message);
      airRetry.hidden = false;
    } finally {
      clearTimeout(timer);
      if (airRequest === controller) airRequest = null;
    }
  }

  function coordinates(place) {
    const point = [Number(place.ViDo), Number(place.KinhDo)];
    if (!point.every(Number.isFinite) || Math.abs(point[0]) > 90 || Math.abs(point[1]) > 180) {
      throw new Error('Địa điểm chưa có tọa độ hợp lệ để hiển thị bản đồ.');
    }
    return point;
  }

  function popup(title, point, description) {
    const box = document.createElement('div');
    const heading = document.createElement('strong');
    heading.textContent = title;
    const coords = document.createElement('p');
    coords.textContent = `${point[0].toFixed(5)}, ${point[1].toFixed(5)}`;
    const note = document.createElement('p');
    note.textContent = description;
    box.append(heading, coords, note);
    return box;
  }

  function icon(kind) {
    return L.divIcon({
      className: `map-pin ${kind}`,
      html: '<span aria-hidden="true"></span>',
      iconSize: [30, 36], iconAnchor: [15, 36], popupAnchor: [0, -34],
    });
  }

  function frameSelected() {
    if (!map || !selected) return;
    map.stop();
    map.invalidateSize({pan: false});
    const point = coordinates(selected);
    if (airToggle.checked) {
      map.setView(point, 8, {animate: false});
    } else if (noisePoint) {
      map.fitBounds(L.latLngBounds([point, noisePoint]), {padding: [48, 48], maxZoom: 12, animate: false});
    } else {
      map.setView(point, selected.TepTiengOn ? 14 : 12, {animate: false});
    }
  }

  function showLocation(place) {
    selected = place;
    try {
      const point = coordinates(place);
      document.getElementById('mapLocationLabel').textContent = `${place.Ten} · ${point[0].toFixed(5)}, ${point[1].toFixed(5)}`;
      document.getElementById('mapOpen').href = `https://www.openstreetmap.org/?mlat=${point[0]}&mlon=${point[1]}#map=${place.TepTiengOn ? 14 : 12}/${point[0]}/${point[1]}`;
      container.setAttribute('aria-label', `Bản đồ vị trí tham chiếu ${place.Ten}`);
      updateAirControls();
      if (!map) return;
      airData = null;
      airLayer?.setData(null);
      map.closePopup();
      marker?.remove();
      marker = L.marker(point, {icon: icon('environment'), title: place.Ten, keyboard: true}).addTo(map)
        .bindPopup(popup(place.Ten, point, 'Vị trí tham chiếu thời tiết và không khí của địa điểm đang chọn.'));
      noiseMarker?.remove();
      noiseMarker = null;
      noisePoint = null;
      if (!airToggle.checked && Number.isFinite(place.ViDoTiengOn) && Number.isFinite(place.KinhDoTiengOn)) {
        const reference = [place.ViDoTiengOn, place.KinhDoTiengOn];
        if (map.distance(point, reference) > 10) {
          noisePoint = reference;
          noiseMarker = L.marker(reference, {icon: icon('noise'), title: `Tiếng ồn: ${place.TenKhuVucTiengOn}`, keyboard: true}).addTo(map)
            .bindPopup(popup(place.TenKhuVucTiengOn, reference, 'Vị trí tham chiếu để tổng hợp tiếng ồn NoiseCapture; không phải đo trực tiếp theo thời gian thực.'));
        }
      }
      document.getElementById('mapNoiseLegend').hidden = !noisePoint;
      recenter.disabled = false;
      frameSelected();
      queueAirLoad(0);
    } catch (error) {
      status.textContent = error.message;
      recenter.disabled = true;
    }
  }

  async function initialize() {
    await window.EnvironmentLocation.ready;
    if (!window.L) {
      showLocation(window.EnvironmentLocation.current);
      status.textContent = 'Chưa tải được bản đồ. Tên địa điểm và tọa độ vẫn hiển thị ở trên.';
      retry.textContent = 'Tải lại trang';
      retry.hidden = false;
      return;
    }
    map = L.map(container, {scrollWheelZoom: false, zoomControl: false, minZoom: 5,
      maxBounds: [[3, 96], [29, 119]], maxBoundsViscosity: .75});
    L.control.zoom({zoomInTitle: 'Phóng to', zoomOutTitle: 'Thu nhỏ'}).addTo(map);
    tiles = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      minZoom: 3, maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors',
    });
    tiles.on('loading', () => {
      failedTiles = 0;
      retry.hidden = true;
      status.textContent = 'Đang tải nền bản đồ…';
    });
    tiles.on('tileerror', () => {
      failedTiles += 1;
      retry.hidden = false;
      status.textContent = 'Chưa tải đủ nền bản đồ. Kiểm tra kết nối Internet hoặc bấm thử tải lại; dấu vị trí và tọa độ vẫn dùng được.';
    });
    tiles.on('load', () => {
      if (!failedTiles) {
        retry.hidden = true;
        status.textContent = 'Kéo để xem xung quanh; dùng + / − hoặc hai ngón tay để phóng to, thu nhỏ.';
      }
    });
    tiles.addTo(map);
    showLocation(window.EnvironmentLocation.current);
    airLayer = window.EnvironmentAirQuality.createLayer();
    if (airToggle.checked) airLayer.addTo(map);
    cityLabels = L.layerGroup();
    window.EnvironmentLocation.places.filter((place) => place.Nhom === 'Thành phố').forEach((place) => {
      const label = document.createElement('span');
      label.textContent = place.Ten;
      L.circleMarker(coordinates(place), {radius: 3, color: '#fff', weight: 1.5,
        fillColor: '#314252', fillOpacity: 1, interactive: false}).addTo(cityLabels)
        .bindTooltip(label, {permanent: true, direction: 'right', offset: [8, 0], className: 'map-city-label'});
    });
    if (airToggle.checked) cityLabels.addTo(map);
    map.attributionControl.addAttribution('<a href="https://open-meteo.com/en/docs/air-quality-api" target="_blank" rel="noopener">Open-Meteo / CAMS</a>');
    map.on('moveend', () => queueAirLoad());
    map.on('click', (event) => {
      if (!airToggle.checked || !airData) return;
      const value = window.EnvironmentAirQuality.sampleGrid(airData, event.latlng.lat, event.latlng.lng);
      const rounded = Math.round(value);
      const level = rounded <= 50 ? 'Tốt' : rounded <= 100 ? 'Trung bình' : rounded <= 150 ? 'Kém'
        : rounded <= 200 ? 'Xấu' : rounded <= 300 ? 'Rất xấu' : 'Nguy hại';
      const title = value == null ? 'Chưa có dữ liệu AQI tại đây' : `US AQI ước tính: ${rounded} · ${level}`;
      L.popup().setLatLng(event.latlng).setContent(popup(title, [event.latlng.lat, event.latlng.lng],
        value == null ? 'Vùng này chưa có đủ điểm mô hình để nội suy.'
          : `Nội suy từ các điểm mô hình, không phải số đo tại chỗ. Dữ liệu từ ${sourceTime(airData.ThoiGianNguonDau)} đến ${sourceTime(airData.ThoiGianNguonCuoi)} (giờ Việt Nam).`)).openOn(map);
    });
    if (window.ResizeObserver) {
      new ResizeObserver(() => map.invalidateSize({pan: false})).observe(container);
    }
  }

  document.addEventListener('locationchange', (event) => showLocation(event.detail));
  recenter.addEventListener('click', frameSelected);
  airToggle.addEventListener('change', () => {
    updateAirControls();
    if (!map || !airLayer) return;
    if (airToggle.checked) {
      airLayer.addTo(map);
      cityLabels?.addTo(map);
    } else {
      airLayer.remove();
      cityLabels?.remove();
    }
    showLocation(selected);
  });
  opacity.addEventListener('input', () => {
    document.getElementById('mapAirOpacityValue').textContent = `${opacity.value}%`;
    airLayer?.setOpacity(Number(opacity.value) / 100);
  });
  airRetry.addEventListener('click', () => queueAirLoad(0));
  const fullscreen = document.getElementById('mapFullscreen');
  const card = document.querySelector('.location-map-card');
  if (!document.fullscreenEnabled) fullscreen.hidden = true;
  fullscreen.addEventListener('click', async () => {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else await card.requestFullscreen();
    } catch (error) { status.textContent = 'Trình duyệt chưa cho phép toàn màn hình. Bạn vẫn có thể kéo và phóng to bản đồ.'; }
  });
  document.addEventListener('fullscreenchange', () => {
    fullscreen.textContent = document.fullscreenElement ? 'Thoát toàn màn hình ⛶' : 'Toàn màn hình ⛶';
    map?.invalidateSize({pan: false});
  });
  setInterval(() => { if (!document.hidden) queueAirLoad(0); }, 10 * 60 * 1000);
  retry.addEventListener('click', () => {
    if (!tiles) { window.location.reload(); return; }
    tiles.redraw();
  });
  initialize();
})();
