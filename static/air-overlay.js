'use strict';

(() => {
  const stops = [
    [0, [0, 228, 0]], [50, [0, 228, 0]], [100, [255, 255, 0]],
    [150, [255, 126, 0]], [200, [255, 0, 0]], [300, [143, 63, 151]], [500, [126, 0, 35]],
  ];
  const valid = (value) => typeof value === 'number' && Number.isFinite(value) && value >= 0;

  function colorFor(value) {
    if (!valid(value)) return null;
    value = Math.min(value, 500);
    for (let i = 1; i < stops.length; i += 1) {
      if (value <= stops[i][0]) {
        const left = stops[i - 1], right = stops[i];
        const fraction = (value - left[0]) / (right[0] - left[0]);
        return left[1].map((channel, index) => Math.round(channel + fraction * (right[1][index] - channel)));
      }
    }
    return stops[stops.length - 1][1].slice();
  }

  function sampleGrid(data, lat, lon) {
    const lats = data?.ViDo || [], lons = data?.KinhDo || [];
    if (lats.length < 2 || lons.length < 2 || lat < lats[0] || lat > lats.at(-1) || lon < lons[0] || lon > lons.at(-1)) return null;
    const row = Math.min((lat - lats[0]) / data.BuocLuoiDo, lats.length - 1);
    const col = Math.min((lon - lons[0]) / data.BuocLuoiDo, lons.length - 1);
    const y = Math.min(Math.floor(row), lats.length - 2), x = Math.min(Math.floor(col), lons.length - 2);
    const dy = row - y, dx = col - x;
    const weighted = [[y, x, (1 - dy) * (1 - dx)], [y, x + 1, (1 - dy) * dx],
      [y + 1, x, dy * (1 - dx)], [y + 1, x + 1, dy * dx]];
    let result = 0;
    for (const [r, c, weight] of weighted) {
      if (weight <= 1e-9) continue;
      const value = data.AQI?.[r]?.[c];
      if (!valid(value)) return null; // Missing model values remain transparent.
      result += weight * value;
    }
    return result;
  }

  function createLayer() {
    const L = window.L;
    return new (L.Layer.extend({
      onAdd(map) {
        this._owner = map;
        if (!map.getPane('airQualityPane')) {
          const pane = map.createPane('airQualityPane');
          pane.style.zIndex = '350';
          pane.style.pointerEvents = 'none';
        }
        this._canvas = L.DomUtil.create('canvas', 'air-quality-canvas', map.getPane('airQualityPane'));
        this._canvas.setAttribute('aria-hidden', 'true');
        this._canvas.style.opacity = String(this._opacity ?? .68);
        map.on('moveend zoomend resize', this.render, this);
        this.render();
      },
      onRemove(map) {
        map.off('moveend zoomend resize', this.render, this);
        this._canvas.remove();
        this._owner = null;
      },
      setData(data) {
        this._data = data;
        if (this._owner) this.render();
        return this;
      },
      setOpacity(value) {
        this._opacity = value;
        if (this._canvas) this._canvas.style.opacity = String(value);
      },
      render() {
        const map = this._owner;
        if (!map) return;
        const size = map.getSize(), canvas = this._canvas;
        const scale = 4;
        canvas.width = Math.max(1, Math.ceil(size.x / scale));
        canvas.height = Math.max(1, Math.ceil(size.y / scale));
        canvas.style.width = `${size.x}px`;
        canvas.style.height = `${size.y}px`;
        L.DomUtil.setPosition(canvas, map.containerPointToLayerPoint([0, 0]));
        if (!this._data?.SoDiem) return;
        const ctx = canvas.getContext('2d');
        const pixels = ctx.createImageData(canvas.width, canvas.height);
        const west = map.containerPointToLatLng([0, 0]).lng;
        const east = map.containerPointToLatLng([size.x, 0]).lng;
        for (let y = 0; y < canvas.height; y += 1) {
          const lat = map.containerPointToLatLng([0, y * scale]).lat;
          for (let x = 0; x < canvas.width; x += 1) {
            const lon = west + (east - west) * x * scale / size.x;
            const color = colorFor(sampleGrid(this._data, lat, lon));
            if (!color) continue;
            const index = (y * canvas.width + x) * 4;
            pixels.data[index] = color[0];
            pixels.data[index + 1] = color[1];
            pixels.data[index + 2] = color[2];
            pixels.data[index + 3] = 255;
          }
        }
        ctx.putImageData(pixels, 0, 0);
      },
    }))();
  }

  const api = {colorFor, sampleGrid, createLayer};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else window.EnvironmentAirQuality = api;
})();
