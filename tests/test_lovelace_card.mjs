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

console.log("Lovelace card & editor tests passed.");
