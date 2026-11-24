/**
 * Headless Node.js behavioral tests for the ARPA Veneto Meteo Lovelace card
 * and its ha-form visual editor.
 */

const defined = new Map();

class FakeElement {
  constructor(tag = "div") {
    this.tagName = String(tag).toUpperCase();
    this.children = [];
    this.attributes = new Map();
    this.dataset = {};
    this.style = {
      _map: new Map(),
      setProperty(k, v) {
        this._map.set(k, v);
      },
      removeProperty(k) {
        this._map.delete(k);
      },
      getPropertyValue(k) {
        return this._map.get(k) || "";
      },
    };
    this.className = "";
    this._innerHTML = "";
    this.textContent = "";
    this.open = false;
    this.returnValue = "";
    this._events = new Map();
  }

  attachShadow() {
    this.shadowRoot = new FakeElement("shadow-root");
    return this.shadowRoot;
  }

  setAttribute(k, v) {
    this.attributes.set(k, String(v));
  }

  getAttribute(k) {
    return this.attributes.get(k) ?? null;
  }

  appendChild(ch) {
    this.children.push(ch);
    return ch;
  }

  append(...chs) {
    for (const c of chs) this.children.push(c);
  }

  replaceChildren(...chs) {
    this.children = [...chs];
  }

  addEventListener(type, fn) {
    if (!this._events.has(type)) this._events.set(type, []);
    this._events.get(type).push(fn);
  }

  dispatchEvent(ev) {
    for (const fn of this._events.get(ev.type) || []) fn(ev);
    return true;
  }

  set innerHTML(v) {
    this._innerHTML = String(v);
  }

  get innerHTML() {
    return this._innerHTML;
  }

  showModal() {
    this.open = true;
  }

  close() {
    this.open = false;
    this.dispatchEvent({ type: "close" });
  }

  querySelector(sel) {
    if (sel === ".dialog-title") return this._title || (this._title = new FakeElement("h1"));
    if (sel === ".dialog-close") return this._close || (this._close = new FakeElement("button"));
    if (sel === ".dialog-content") return this._content || (this._content = new FakeElement("div"));
    if (sel === ".dialog-footer") return this._footer || (this._footer = new FakeElement("div"));
    return null;
  }
}

globalThis.HTMLElement = FakeElement;
globalThis.HTMLDialogElement = class extends FakeElement {};
globalThis.CustomEvent = class {
  constructor(type, init = {}) {
    this.type = type;
    this.detail = init.detail;
  }
};
globalThis.window = globalThis;
globalThis.document = {
  createElement(tag) {
    const Cls = defined.get(tag.toLowerCase());
    return Cls ? new Cls() : new FakeElement(tag);
  },
};
globalThis.customElements = {
  define(name, cls) {
    defined.set(name, cls);
  },
  get(name) {
    return defined.get(name);
  },
  whenDefined(name) {
    return Promise.resolve(defined.get(name));
  },
};

// Stub Home Assistant shell element so card registration fires cleanly
customElements.define("home-assistant", class extends HTMLElement {});
customElements.define("ha-form", class extends HTMLElement {});

function assert(cond, msg) {
  if (!cond) throw new Error(`Assertion failed: ${msg}`);
}

await import("../custom_components/arpa_veneto_meteo/frontend/arpa-veneto-meteo-card.js");
await new Promise((r) => setTimeout(r, 20));

const CardCls = customElements.get("arpa-veneto-meteo-card");
const EditorCls = customElements.get("arpa-veneto-meteo-card-editor");
assert(CardCls, "Card custom element was not defined");
assert(EditorCls, "Editor custom element was not defined");
assert(
  window.customCards.some((c) => c.type === "arpa-veneto-meteo-card" && c.preview === true),
  "window.customCards registration missing or preview not enabled"
);

let unsubCount = 0;
const mockHass = {
  language: "it",
  locale: { language: "it", number_format: "decimal_comma", time_format: "24" },
  themes: { darkMode: false },
  devices: { dev1: { id: "dev1", name: "ARPA Veneto - Padova (PD)", model: "Padova" } },
  entities: {
    "weather.padova": { entity_id: "weather.padova", device_id: "dev1", platform: "arpa_veneto_meteo", translation_key: "arpav_weather" },
    "sensor.temp": { entity_id: "sensor.temp", device_id: "dev1", platform: "arpa_veneto_meteo", translation_key: "temperature" },
    "sensor.min24": { entity_id: "sensor.min24", device_id: "dev1", platform: "arpa_veneto_meteo", translation_key: "temperature_min_24h" },
    "sensor.max24": { entity_id: "sensor.max24", device_id: "dev1", platform: "arpa_veneto_meteo", translation_key: "temperature_max_24h" },
    "sensor.hum": { entity_id: "sensor.hum", device_id: "dev1", platform: "arpa_veneto_meteo", translation_key: "humidity" },
    "sensor.wind": { entity_id: "sensor.wind", device_id: "dev1", platform: "arpa_veneto_meteo", translation_key: "wind_speed" },
    "sensor.bearing": { entity_id: "sensor.bearing", device_id: "dev1", platform: "arpa_veneto_meteo", translation_key: "wind_bearing" },
    "sensor.gust": { entity_id: "sensor.gust", device_id: "dev1", platform: "arpa_veneto_meteo", translation_key: "wind_gust_24h" },
    "sensor.pm10": { entity_id: "sensor.pm10", device_id: "dev1", platform: "arpa_veneto_meteo", translation_key: "pm10_daily" },
    "sensor.pm25": { entity_id: "sensor.pm25", device_id: "dev1", platform: "arpa_veneto_meteo", translation_key: "pm25_daily" },
    "sensor.o3": { entity_id: "sensor.o3", device_id: "dev1", platform: "arpa_veneto_meteo", translation_key: "ozone" },
    "sensor.pollen": { entity_id: "sensor.pollen", device_id: "dev1", platform: "arpa_veneto_meteo", translation_key: "pollen_risk" },
    "sensor.pollen_cup": { entity_id: "sensor.pollen_cup", device_id: "dev1", platform: "arpa_veneto_meteo" },
    "sensor.bul": { entity_id: "sensor.bul", device_id: "dev1", platform: "arpa_veneto_meteo", translation_key: "bulletin_summary" },
    "sensor.river": { entity_id: "sensor.river", device_id: "dev1", platform: "arpa_veneto_meteo", translation_key: "river_level" },
    "sensor.av_dol": { entity_id: "sensor.av_dol", device_id: "dev1", platform: "arpa_veneto_meteo", translation_key: "avalanche_dolomiti" },
    "binary_sensor.alert": { entity_id: "binary_sensor.alert", device_id: "dev1", platform: "arpa_veneto_meteo", translation_key: "weather_alert" },
    "image.radar": { entity_id: "image.radar", device_id: "dev1", platform: "arpa_veneto_meteo", translation_key: "radar" },
  },
  states: {
    "weather.padova": { entity_id: "weather.padova", state: "partlycloudy", last_updated: "t1", attributes: { temperature: 11.4, temperature_unit: "°C", station_name: "Padova (PD)", zone_name: "Padova e pianura centrale" } },
    "sensor.temp": { entity_id: "sensor.temp", state: "11.4", last_updated: "t1", attributes: { unit_of_measurement: "°C" } },
    "sensor.min24": { entity_id: "sensor.min24", state: "4.2", last_updated: "t1", attributes: { unit_of_measurement: "°C" } },
    "sensor.max24": { entity_id: "sensor.max24", state: "14.8", last_updated: "t1", attributes: { unit_of_measurement: "°C" } },
    "sensor.hum": { entity_id: "sensor.hum", state: "72", last_updated: "t1", attributes: { unit_of_measurement: "%" } },
    "sensor.wind": { entity_id: "sensor.wind", state: "12.5", last_updated: "t1", attributes: { unit_of_measurement: "km/h" } },
    "sensor.bearing": { entity_id: "sensor.bearing", state: "45", last_updated: "t1", attributes: { unit_of_measurement: "°", cardinal: "NE" } },
    "sensor.gust": { entity_id: "sensor.gust", state: "24.1", last_updated: "t1", attributes: { unit_of_measurement: "km/h" } },
    "sensor.pm10": { entity_id: "sensor.pm10", state: "38.2", last_updated: "t1", attributes: { unit_of_measurement: "µg/m³", source_name: "PD Mandria" } },
    "sensor.pm25": { entity_id: "sensor.pm25", state: "18.5", last_updated: "t1", attributes: { unit_of_measurement: "µg/m³", source_name: "PD Mandria" } },
    "sensor.o3": { entity_id: "sensor.o3", state: "64.0", last_updated: "t1", attributes: { unit_of_measurement: "µg/m³", daily_max: 88.0 } },
    "sensor.pollen": { entity_id: "sensor.pollen", state: "moderate", last_updated: "t1", attributes: { species: { cup: { name: "Cupressaceae", risk: "moderate", value: 42 } } } },
    "sensor.pollen_cup": { entity_id: "sensor.pollen_cup", state: "42", last_updated: "t1", attributes: { source: "pollen_station", species_code: "509", species_name: "Cupressaceae", unit_of_measurement: "granuli/m³" } },
    "sensor.bul": { entity_id: "sensor.bul", state: "Evoluzione...", last_updated: "t1", attributes: { bulletin_code: "MV", general_evolution: "Testo completo evoluzione", daily_forecasts: [{ date: "2026-11-24", text: "Soleggiato" }] } },
    "sensor.river": { entity_id: "sensor.river", state: "1.42", last_updated: "t1", attributes: { unit_of_measurement: "m", trend: "+", hydro_station_name: "Bacchiglione" } },
    "sensor.av_dol": { entity_id: "sensor.av_dol", state: "3_considerable", last_updated: "t1", attributes: { situation: "Neve ventata" } },
    "binary_sensor.alert": { entity_id: "binary_sensor.alert", state: "on", last_updated: "t1", attributes: { alert: "Vento forte" } },
    "image.radar": { entity_id: "image.radar", state: "2026-11-24T08:40:00Z", last_updated: "t1", attributes: { entity_picture: "/api/image_proxy/image.radar?token=abc", radar_source: "mosaic" } },
  },
  connection: {
    subscribeMessage(cb) {
      cb({ forecast: [{ datetime: "2026-11-24", condition: "sunny", temperature: 15, templow: 5, precipitation_probability: 20 }] });
      return Promise.resolve(() => {
        unsubCount += 1;
      });
    },
  },
};

// 1. Minimal stub config auto-selects first ARPA Veneto Meteo device
const stub = CardCls.getStubConfig(mockHass);
assert(
  stub.device_id === "dev1" && Object.keys(stub).length === 1,
  `Expected minimal stub { device_id: "dev1" }, got ${JSON.stringify(stub)}`
);

// 2. Full card renders every enabled section using native HA patterns
const card = new CardCls();
card.setConfig({ device_id: "dev1", forecast_type: "both" });
card.hass = mockHass;
assert(card.hass === mockHass, "hass getter should return current hass");
const htmlFull = card._bodyEl.innerHTML;
for (const expected of [
  "class=\"tile\"",
  "class=\"tile-icon\"",
  "class=\"value\"",
  "Padova (PD)",
  "11,4",
  "°C",
  "class=\"alert warning\"",
  "Vento forte",
  "class=\"metrics-grid",
  "class=\"metric-card\"",
  "class=\"badges\"",
  "class=\"segmented\"",
  "Mosaico Veneto",
  "PM10",
  "PM2.5",
  "O3",
  "Cupressaceae",
  "sensor.pollen_cup",
  "Bacchiglione",
  "Dolomiti",
  "Bollettino meteo",
  "&amp;v=2026-11-24T08%3A40%3A00Z",
]) {
  assert(htmlFull.includes(expected), `Missing expected content in full render: ${expected}`);
}

// 3. Unrelated entity state update does not trigger unnecessary re-render
const unrelatedHass = {
  ...mockHass,
  states: { ...mockHass.states, "light.kitchen": { entity_id: "light.kitchen", state: "on" } },
};
assert(!card._changed(mockHass, unrelatedHass), "Unrelated entity should not trigger _changed");

// 4. Section toggles hide disabled sections cleanly
card.setConfig({
  device_id: "dev1",
  show_alerts: false,
  show_metrics: false,
  show_forecast: false,
  show_radar: false,
  show_bulletin: false,
  show_air_quality: false,
  show_pollen: false,
  show_hydrology: false,
  show_avalanche: false,
});
const htmlHeaderOnly = card._bodyEl.innerHTML;
assert(htmlHeaderOnly.includes("Padova (PD)"), "Header should still be rendered");
for (const hidden of ["Mosaico Veneto", "PM10", "Cupressaceae", "Bacchiglione", "Dolomiti", "Vento forte", "Bollettino meteo"]) {
  assert(!htmlHeaderOnly.includes(hidden), `Hidden section leaked into output: ${hidden}`);
}

// 5. Individual weather metric toggles work independently
card.setConfig({ device_id: "dev1", show_metric_humidity: false, show_metric_wind: true });
assert(!card._bodyEl.innerHTML.includes("Umidità"), "Humidity badge should be hidden");
assert(card._bodyEl.innerHTML.includes("NE"), "Wind badge should remain visible");

// 6. Native modal dialogs render full details and close cleanly
card.setConfig({ device_id: "dev1" });
card._openBulletinDialog();
assert(card._dialogEl.open && card._dialogEl._content.innerHTML.includes("Testo completo evoluzione"), "Bulletin dialog failed");
card._dialogEl.close();
assert(!card._dialogEl.open, "Bulletin dialog did not close");

card._openPollenDialog();
assert(card._dialogEl.open && card._dialogEl._content.innerHTML.includes("Cupressaceae"), "Pollen dialog failed");
card._dialogEl.close();

card._openRadarDialog();
assert(card._dialogEl.open && card._dialogEl._content.innerHTML.includes("image_proxy"), "Radar dialog failed");
card._dialogEl.close();

card._openAvalancheDialog();
assert(card._dialogEl.open && card._dialogEl._content.innerHTML.includes("Neve ventata"), "Avalanche dialog failed");
card._dialogEl.close();

// 7. Language switch updates UI strings to English
const enHass = { ...mockHass, language: "en", locale: { language: "en", number_format: "comma_decimal", time_format: "24" } };
card.hass = enHass;
assert(card._bodyEl.innerHTML.includes("Weather bulletin"), "English strings did not render");

// 7b. Dark theme keeps the radar mosaic's colors: no inverting filter, original image until the
// recolored copy is ready (no canvas here, so it stays the original without errors)
const darkHass = { ...mockHass, themes: { darkMode: true } };
card.hass = darkHass;
const htmlDark = card._bodyEl.innerHTML;
assert(!htmlDark.includes("dark-mosaic") && !htmlDark.includes("invert("), "Dark radar must not be inverted");
assert(htmlDark.includes("/api/image_proxy/image.radar?token=abc"), "Dark radar should fall back to the original image");
card._openRadarDialog();
assert(card._dialogEl._content.innerHTML.includes("image_proxy"), "Dark radar dialog should show the original image");
card._dialogEl.close();
await new Promise((r) => setTimeout(r, 10));
card.hass = enHass;

// 7c. Radar recoloring for dark cards: borders take the line color, colors too dark for the
// background are lifted to 3:1 contrast, the rest of the ARPAV scale is untouched
const recolor = CardCls.recolorRadarForDark;
assert(typeof recolor === "function", "recolorRadarForDark should be exposed for tests");
const lin = (c) => ((c / 255) <= 0.04045 ? c / 255 / 12.92 : (((c / 255) + 0.055) / 1.055) ** 2.4);
const lum = (r, g, b) => 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
const contrast = (a, b) => (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
const px = new Uint8ClampedArray([
  0, 0, 0, 120, // border line, anti-aliased
  0, 0, 172, 255, // weakest precipitation class (dark blue)
  60, 240, 80, 255, // light green
  255, 255, 0, 255, // yellow
  0, 0, 0, 0, // transparent
]);
recolor(px, [155, 155, 155], [28, 28, 28]);
assert(px[0] === 155 && px[1] === 155 && px[2] === 155 && px[3] === 240, `Border not recolored: ${px.slice(0, 4)}`);
assert(contrast(lum(px[4], px[5], px[6]), lum(28, 28, 28)) >= 3, `Dark blue not lifted: ${px.slice(4, 8)}`);
assert(px[6] > px[4] && px[6] > px[5], `Dark blue should stay blue: ${px.slice(4, 8)}`);
assert(px[8] === 60 && px[9] === 240 && px[10] === 80, `Green should be untouched: ${px.slice(8, 12)}`);
assert(px[12] === 255 && px[13] === 255 && px[14] === 0, `Yellow should be untouched: ${px.slice(12, 16)}`);
assert(px[19] === 0, "Transparent pixels should stay transparent");
const pxLight = new Uint8ClampedArray([0, 0, 172, 255]);
recolor(pxLight, [114, 114, 114], [255, 255, 255]);
assert(pxLight[2] === 172 && pxLight[0] === 0, "Colors must not be lifted on a light background");

// 8. Disconnect cleanly unsubscribes forecast WebSocket subscriptions
card.disconnectedCallback();
await new Promise((r) => setTimeout(r, 10));
assert(unsubCount >= 1, "Forecast subscriptions were not unsubscribed on disconnect");

// 9. Visual editor uses ha-form with device filter, flatten expandable sections, and minimal YAML
const editor = new EditorCls();
let emitted = null;
editor.addEventListener("config-changed", (ev) => {
  emitted = ev.detail.config;
});
editor.setConfig({ type: "custom:arpa-veneto-meteo-card", device_id: "dev1" });
editor.hass = enHass;
assert(editor._form && Array.isArray(editor._form.schema) && editor._form.schema.length === 5, "Editor schema structure unexpected");
assert(
  editor._form.schema[0]?.selector?.device?.filter?.integration === "arpa_veneto_meteo",
  "Device selector must filter by integration"
);
assert(
  editor._form.schema[3]?.flatten === true && editor._form.schema[4]?.flatten === true,
  "Expandable sections must set flatten: true"
);
assert(typeof editor._form.computeHelper === "function", "Editor must define computeHelper");
editor._form.dispatchEvent({
  type: "value-changed",
  detail: { value: { device_id: "dev1", show_header: true, show_radar: false, show_pollen: false, name: "" } },
});
assert(
  emitted &&
    emitted.type === "custom:arpa-veneto-meteo-card" &&
    emitted.device_id === "dev1" &&
    emitted.show_radar === false &&
    emitted.show_pollen === false &&
    !("show_header" in emitted) &&
    !("name" in emitted),
  `Editor config-changed payload should omit defaults and empty strings: ${JSON.stringify(emitted)}`
);

// 10. Editor hides the options of hidden sections
editor.setConfig({ type: "custom:arpa-veneto-meteo-card", device_id: "dev1", show_radar: false, show_forecast: false });
const sectionNames = JSON.stringify(editor._form.schema[3].schema);
assert(!sectionNames.includes("radar_collapsed"), "radar_collapsed should be hidden when the radar is off");
assert(!sectionNames.includes("forecast_type"), "Forecast options should be hidden when the forecast is off");
editor.setConfig({ type: "custom:arpa-veneto-meteo-card", device_id: "dev1" });
const sectionNamesOn = JSON.stringify(editor._form.schema[3].schema);
assert(sectionNamesOn.includes("radar_collapsed") && sectionNamesOn.includes("forecast_type"), "Section options should show by default");

// 11. Sections dashboards keep full cards at min 9 columns and compact cards at min 6 columns
const grid = new CardCls().getGridOptions();
assert(grid.columns === 12 && grid.min_columns === 9, `Unexpected grid options: ${JSON.stringify(grid)}`);
const compactCard = new CardCls();
compactCard.setConfig({ device_id: "dev1", compact: true });
const compactGrid = compactCard.getGridOptions();
assert(compactGrid.columns === 12 && compactGrid.min_columns === 6, `Unexpected compact grid options: ${JSON.stringify(compactGrid)}`);

// 11b. Disconnecting revokes any cached dark radar object URL
const revoked = [];
const prevRevoke = URL.revokeObjectURL;
URL.revokeObjectURL = (u) => revoked.push(u);
try {
  const leakCard = new CardCls();
  leakCard._radarDark = { key: "k1", url: "blob:test-radar" };
  leakCard.disconnectedCallback();
  assert(revoked.includes("blob:test-radar") && leakCard._radarDark === null, "Dark radar object URL was not revoked on disconnect");
} finally {
  URL.revokeObjectURL = prevRevoke;
}

// 12. Only entities the card shows trigger a redraw; every key the card reads is watched
const { readFileSync } = await import("node:fs");
const cardSource = readFileSync(new URL("../custom_components/arpa_veneto_meteo/frontend/arpa-veneto-meteo-card.js", import.meta.url), "utf8");
const readKeys = [...new Set([...cardSource.matchAll(/map\["([a-z_]+\.[a-z0-9_]+)"\]/g)].map((m) => m[1]))];
assert(readKeys.length > 30, `Expected to find the card's entity keys, got ${readKeys.length}`);
const watchEntities = { ...mockHass.entities };
const watchStates = { ...mockHass.states };
for (const key of [...readKeys, "sensor.precipitation_1h"]) {
  const id = `${key.split(".")[0]}.w_${key.split(".")[1]}`;
  watchEntities[id] = { entity_id: id, device_id: "dev1", platform: "arpa_veneto_meteo", translation_key: key.split(".")[1] };
  watchStates[id] = { entity_id: id, state: "1", attributes: {} };
}
const watchHass = { ...mockHass, entities: watchEntities, states: watchStates };
const watchCard = new CardCls();
watchCard.setConfig({ device_id: "dev1", show_forecast: false });
watchCard.hass = watchHass;
for (const key of readKeys) {
  const id = `${key.split(".")[0]}.w_${key.split(".")[1]}`;
  const next = { ...watchHass, states: { ...watchStates, [id]: { entity_id: id, state: "2", attributes: {} } } };
  assert(watchCard._changed(watchHass, next), `A state change of ${key} should redraw the card`);
}
const rolling = { ...watchHass, states: { ...watchStates, "sensor.w_precipitation_1h": { entity_id: "sensor.w_precipitation_1h", state: "2", attributes: {} } } };
assert(!watchCard._changed(watchHass, rolling), "A sensor the card doesn't show should not redraw it");

// 13. Per-species pollen sensors are found by translation key (1.1.1) and by attributes (1.1.0)
const pollenHass = {
  ...mockHass,
  entities: {
    ...mockHass.entities,
    "sensor.pollen_alt": { entity_id: "sensor.pollen_alt", device_id: "dev1", platform: "arpa_veneto_meteo", translation_key: "pollen_species" },
  },
  states: {
    ...mockHass.states,
    "sensor.pollen": { ...mockHass.states["sensor.pollen"], attributes: { species: { cup: { name: "Cupressaceae", risk: "moderate", risk_label: "Media", value: 42 }, alt: { name: "Alternaria", risk: "low", value: 12 } } } },
    "sensor.pollen_alt": { entity_id: "sensor.pollen_alt", state: "12", attributes: { source: "pollen_station", species_code: "601", species_name: "Alternaria" } },
  },
};
const pollenCard = new CardCls();
pollenCard.setConfig({ device_id: "dev1", show_forecast: false });
pollenCard.hass = pollenHass;
const pollenHtml = pollenCard._bodyEl.innerHTML;
assert(pollenHtml.includes("sensor.pollen_alt") && pollenHtml.includes("sensor.pollen_cup"), "Both pollen sensor variants should be linked");

// 14. Pollen dialog in English: translated level and unit, not ARPAV's Italian label
pollenCard.hass = { ...pollenHass, language: "en", locale: { language: "en", number_format: "comma_decimal", time_format: "24" } };
pollenCard._openPollenDialog();
const pollenDialog = pollenCard._dialogEl._content.innerHTML;
assert(pollenDialog.includes("grains/m³") && !pollenDialog.includes("granuli"), "Pollen unit should be translated");
assert(pollenDialog.includes("Moderate") && !pollenDialog.includes("Media"), "Pollen level should use the card's translation");
pollenCard._dialogEl.close();

// 15. Altitude temperatures arrive as text from ARPAV, "0" included
const altHass = {
  ...mockHass,
  states: {
    ...mockHass.states,
    "weather.padova": { ...mockHass.states["weather.padova"], attributes: { ...mockHass.states["weather.padova"].attributes, temperature_1500m: "0", temperature_2000m: "-3" } },
  },
};
const altCard = new CardCls();
altCard.setConfig({ device_id: "dev1", show_forecast: false });
altCard.hass = altHass;
assert(altCard._bodyEl.innerHTML.includes("1500m 0°") && altCard._bodyEl.innerHTML.includes("2000m -3°"), "Altitude temperatures missing");

// 16. Forecast days follow the time zone chosen in the profile
const tzForecast = [{ datetime: "2026-11-24T00:00:00+01:00", condition: "sunny", temperature: 10 }];
const tzLabel = (timeZone) => {
  const tzCard = new CardCls();
  tzCard.setConfig({ device_id: "dev1" });
  tzCard.hass = {
    ...mockHass,
    locale: { language: "en", number_format: "comma_decimal", time_format: "24", time_zone: "server" },
    language: "en",
    config: { time_zone: timeZone },
    connection: { subscribeMessage: (cb) => { cb({ forecast: tzForecast }); return Promise.resolve(() => {}); } },
  };
  return tzCard._bodyEl.innerHTML;
};
assert(tzLabel("America/Los_Angeles").includes("23 Mon"), "Forecast day should use the server time zone (Los Angeles)");
assert(tzLabel("Asia/Tokyo").includes("24 Tue"), "Forecast day should use the server time zone (Tokyo)");

// 17. A refused forecast subscription shows "no forecast" instead of loading forever
const failCard = new CardCls();
failCard.setConfig({ device_id: "dev1" });
failCard.hass = { ...mockHass, connection: { subscribeMessage: () => Promise.reject(new Error("not supported")) } };
await new Promise((r) => setTimeout(r, 10));
assert(failCard._bodyEl.innerHTML.includes("Nessuna previsione disponibile"), "Failed subscription should show the empty forecast text");

// 18. Switching to another station drops the previous station's forecasts
const switchCard = new CardCls();
switchCard.setConfig({ device_id: "dev1" });
switchCard.hass = mockHass;
assert(switchCard._forecasts.daily?.length === 1, "Forecast should be loaded for the first station");
const otherHass = {
  ...mockHass,
  devices: { ...mockHass.devices, dev2: { id: "dev2", name: "ARPA Veneto - Belluno", model: "Belluno" } },
  entities: { ...mockHass.entities, "weather.belluno": { entity_id: "weather.belluno", device_id: "dev2", platform: "arpa_veneto_meteo", translation_key: "arpav_weather" } },
  states: { ...mockHass.states, "weather.belluno": { entity_id: "weather.belluno", state: "snowy", attributes: { temperature: -1 } } },
  connection: { subscribeMessage: () => new Promise(() => {}) },
};
switchCard.setConfig({ device_id: "dev2" });
switchCard.hass = otherHass;
assert(switchCard._forecasts.daily === null, "Forecasts of the previous station should be dropped");
assert(switchCard._bodyEl.innerHTML.includes("Caricamento previsioni"), "New station should show loading until its forecast arrives");

console.log("Lovelace card & editor tests passed.");
