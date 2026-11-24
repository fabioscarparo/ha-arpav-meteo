/**
 * ARPA Veneto Meteo Lovelace Card and Visual Editor.
 *
 * Zero-dependency ES module web component built strictly on Home Assistant's
 * native design system tokens and component patterns (tile header, big value,
 * ha-badge, ha-alert, card features, ha-control-select, ha-form, ha-dialog).
 */

const VERSION = "1.1.0";
const DOMAIN = "arpa_veneto_meteo";
const CARD_TYPE = "arpa-veneto-meteo-card";
const EDITOR_TYPE = "arpa-veneto-meteo-card-editor";

console.info(
  `%c ARPA-VENETO-METEO-CARD %c ${VERSION} `,
  "color: #fff; background: #03a9f4; font-weight: 500",
  ""
);

const DEFAULTS = {
  device_id: "",
  entity: "",
  name: "",
  color: "",
  compact: false,
  show_header: true,
  show_alerts: true,
  show_metrics: true,
  show_forecast: true,
  forecast_type: "daily",
  forecast_days: 5,
  show_radar: true,
  radar_collapsed: false,
  show_bulletin: true,
  show_air_quality: true,
  show_pollen: true,
  show_hydrology: true,
  show_avalanche: true,
  show_metric_humidity: true,
  show_metric_wind: true,
  show_metric_precipitation: true,
  show_metric_pressure: true,
  show_metric_dew_point: true,
  show_metric_solar_uv: true,
  show_metric_visibility: true,
  show_metric_snow: true,
  show_metric_leaf_wetness: true,
};

// Home Assistant named ui_color palette mapped to native CSS custom properties.
const HA_COLORS = new Set([
  "primary",
  "accent",
  "red",
  "pink",
  "purple",
  "deep-purple",
  "indigo",
  "blue",
  "light-blue",
  "cyan",
  "teal",
  "green",
  "light-green",
  "lime",
  "yellow",
  "amber",
  "orange",
  "deep-orange",
  "brown",
  "light-grey",
  "grey",
  "dark-grey",
  "blue-grey",
  "black",
  "white",
  "disabled",
]);

const colorVar = (color) => {
  if (!color || typeof color !== "string") return null;
  const trimmed = color.trim();
  if (!trimmed) return null;
  return HA_COLORS.has(trimmed) ? `var(--${trimmed}-color)` : trimmed;
};

// Map Home Assistant weather conditions to MDI icons and a single tile accent token.
const CONDITION_META = {
  sunny: { icon: "mdi:weather-sunny", color: "var(--amber-color, #ffc107)" },
  "clear-night": { icon: "mdi:weather-night", color: "var(--indigo-color, #3f51b5)" },
  partlycloudy: { icon: "mdi:weather-partly-cloudy", color: "var(--primary-color, #03a9f4)" },
  cloudy: { icon: "mdi:weather-cloudy", color: "var(--blue-grey-color, #607d8b)" },
  fog: { icon: "mdi:weather-fog", color: "var(--grey-color, #9e9e9e)" },
  rainy: { icon: "mdi:weather-rainy", color: "var(--blue-color, #2196f3)" },
  pouring: { icon: "mdi:weather-pouring", color: "var(--indigo-color, #3f51b5)" },
  lightning: { icon: "mdi:weather-lightning", color: "var(--deep-purple-color, #673ab7)" },
  "lightning-rainy": {
    icon: "mdi:weather-lightning-rainy",
    color: "var(--deep-purple-color, #673ab7)",
  },
  snowy: { icon: "mdi:weather-snowy", color: "var(--cyan-color, #00bcd4)" },
  "snowy-rainy": { icon: "mdi:weather-snowy-rainy", color: "var(--cyan-color, #00bcd4)" },
  hail: { icon: "mdi:weather-hail", color: "var(--cyan-color, #00bcd4)" },
  windy: { icon: "mdi:weather-windy", color: "var(--teal-color, #009688)" },
  "windy-variant": { icon: "mdi:weather-windy-variant", color: "var(--teal-color, #009688)" },
  exceptional: { icon: "mdi:alert-circle-outline", color: "var(--error-color, #db4437)" },
};

// Semantic colors reserved strictly for meaningful severity levels.
const POLLEN_LEVEL_COLORS = {
  absent: "var(--secondary-text-color, #727272)",
  low: "var(--secondary-text-color, #727272)",
  moderate: "var(--warning-color, #ffa600)",
  high: "var(--error-color, #db4437)",
};

const AVALANCHE_LEVEL_META = {
  not_issued: { level: 0, color: "var(--disabled-text-color, #bdbdbd)" },
  "1_low": { level: 1, color: "var(--success-color, #43a047)" },
  "2_moderate": { level: 2, color: "var(--amber-color, #ffc107)" },
  "3_considerable": { level: 3, color: "var(--orange-color, #ff9800)" },
  "4_high": { level: 4, color: "var(--error-color, #db4437)" },
  "5_very_high": { level: 5, color: "var(--purple-color, #9c27b0)" },
};

const POLLEN_RANK = { absent: 0, low: 1, moderate: 2, high: 3 };

// Card and editor strings (English default, Italian native).
const STRINGS = {
  en: {
    select_device_title: "ARPA Veneto Meteo",
    select_device_hint: "Edit this card and choose an ARPA Veneto Meteo device.",
    device_unavailable: "Unavailable",
    feels_like: "Feels like",
    min_short: "Min",
    max_short: "Max",
    alert_weather: "Weather alert",
    alert_pm10: "PM10 limit exceeded",
    alert_ozone: "Ozone threshold exceeded",
    section_forecast: "Forecast",
    section_radar: "Weather radar",
    section_bulletin: "Weather bulletin",
    section_air_quality: "Air quality",
    section_pollen: "Allergenic pollen",
    section_hydrology: "Hydrology",
    section_avalanche: "Snow & avalanches",
    forecast_daily: "Daily",
    forecast_twice_daily: "Half-day",
    forecast_morning: "AM",
    forecast_afternoon: "PM",
    forecast_loading: "Loading forecast...",
    forecast_empty: "No forecast available",
    radar_mosaic: "Veneto Mosaic",
    radar_teolo: "Monte Grande - Teolo",
    radar_concordia: "Concordia Sagittaria",
    radar_expand: "Expand radar image",
    radar_show: "Show radar",
    radar_hide: "Hide",
    radar_alt: "ARPA Veneto weather radar map",
    bulletin_read_full: "Read full bulletin",
    bulletin_general: "General evolution",
    bulletin_daily: "Daily forecast",
    bulletin_alert: "Alert & special phenomena",
    bulletin_reliability: "Reliability",
    bulletin_issued: "Issued",
    aq_hourly: "Hourly",
    aq_daily_max: "Daily max",
    aq_limit: "Limit",
    aq_threshold: "Threshold",
    pollen_details: "All species",
    pollen_absent: "Absent",
    pollen_low: "Low",
    pollen_moderate: "Moderate",
    pollen_high: "High",
    pollen_comment: "ARPAV comment",
    hydro_level: "River level",
    hydro_discharge: "Discharge",
    hydro_rising: "Rising",
    hydro_falling: "Falling",
    hydro_stable: "Stable",
    avalanche_dolomiti: "Dolomiti",
    avalanche_prealpi: "Prealpi",
    avalanche_situation: "Situation",
    avalanche_forecast: "Forecast",
    avalanche_guidance: "Guidance",
    avalanche_fresh_snow: "Fresh snow",
    avalanche_locations: "Dangerous locations",
    metric_humidity: "Humidity",
    metric_wind: "Wind",
    metric_gust: "Gust",
    metric_rain: "Rain",
    metric_rain_prob: "Rain prob.",
    metric_pressure: "Pressure",
    metric_dew_point: "Dew point",
    metric_solar: "Solar",
    metric_uv: "UV",
    metric_visibility: "Visibility",
    metric_snow: "Snow",
    metric_snow_line: "Snow line",
    metric_leaf: "Leaf wetness",
    altitude_temps: "Altitude",
    open_more_info: "Entity details",
    close: "Close",
    // Editor labels & helpers
    editor_device_id: "Device",
    helper_device_id: "Select an ARPA Veneto Meteo station device",
    editor_name: "Name",
    helper_name: "Optional custom title shown in the card header",
    editor_color: "Color",
    helper_color: "Optional accent color; defaults to current weather condition",
    editor_compact: "Compact layout",
    editor_sections: "Visible sections",
    editor_show_header: "Header and current temperature",
    editor_show_alerts: "Active weather and air quality alerts",
    editor_show_metrics: "Current conditions cards",
    editor_show_forecast: "Forecast",
    editor_forecast_type: "Forecast view",
    editor_forecast_type_daily: "Daily",
    editor_forecast_type_twice: "Half-day (AM / PM)",
    editor_forecast_type_both: "Both (with switcher)",
    editor_forecast_days: "Forecast days",
    editor_show_radar: "Weather radar",
    editor_radar_collapsed: "Start with radar collapsed",
    editor_show_bulletin: "Regional weather bulletin",
    editor_show_air_quality: "Air quality (PM10, PM2.5, Ozone)",
    editor_show_pollen: "Allergenic pollen",
    editor_show_hydrology: "Hydrology (river level & discharge)",
    editor_show_avalanche: "Snow & avalanches",
    editor_metrics: "Current conditions visibility",
    editor_show_metric_humidity: "Humidity",
    editor_show_metric_wind: "Wind speed, direction & gust",
    editor_show_metric_precipitation: "Precipitation & rain probability",
    editor_show_metric_pressure: "Atmospheric pressure",
    editor_show_metric_dew_point: "Dew point",
    editor_show_metric_solar_uv: "Solar radiation & UV index",
    editor_show_metric_visibility: "Visibility",
    editor_show_metric_snow: "Snow depth, snow line & altitude temps",
    editor_show_metric_leaf_wetness: "Leaf wetness",
  },
  it: {
    select_device_title: "ARPA Veneto Meteo",
    select_device_hint: "Modifica questa scheda e seleziona un dispositivo ARPA Veneto Meteo.",
    device_unavailable: "Non disponibile",
    feels_like: "Percepita",
    min_short: "Min",
    max_short: "Max",
    alert_weather: "Avviso meteo",
    alert_pm10: "Limite PM10 superato",
    alert_ozone: "Soglia Ozono superata",
    section_forecast: "Previsioni",
    section_radar: "Radar meteo",
    section_bulletin: "Bollettino meteo",
    section_air_quality: "Qualità dell'aria",
    section_pollen: "Pollini allergenici",
    section_hydrology: "Idrologia",
    section_avalanche: "Neve e valanghe",
    forecast_daily: "Giornaliero",
    forecast_twice_daily: "Biorario",
    forecast_morning: "Mat",
    forecast_afternoon: "Pom",
    forecast_loading: "Caricamento previsioni...",
    forecast_empty: "Nessuna previsione disponibile",
    radar_mosaic: "Mosaico Veneto",
    radar_teolo: "Monte Grande - Teolo",
    radar_concordia: "Concordia Sagittaria",
    radar_expand: "Ingrandisci radar",
    radar_show: "Mostra radar",
    radar_hide: "Nascondi",
    radar_alt: "Mappa radar meteo ARPA Veneto",
    bulletin_read_full: "Leggi bollettino completo",
    bulletin_general: "Evoluzione generale",
    bulletin_daily: "Previsione giornaliera",
    bulletin_alert: "Avviso e fenomeni particolari",
    bulletin_reliability: "Attendibilità",
    bulletin_issued: "Emesso",
    aq_hourly: "Orario",
    aq_daily_max: "Max giorn.",
    aq_limit: "Limite",
    aq_threshold: "Soglia",
    pollen_details: "Tutte le specie",
    pollen_absent: "Assente",
    pollen_low: "Basso",
    pollen_moderate: "Moderato",
    pollen_high: "Elevato",
    pollen_comment: "Commento ARPAV",
    hydro_level: "Livello idrometrico",
    hydro_discharge: "Portata",
    hydro_rising: "In crescita",
    hydro_falling: "In calo",
    hydro_stable: "Stabile",
    avalanche_dolomiti: "Dolomiti",
    avalanche_prealpi: "Prealpi",
    avalanche_situation: "Situazione",
    avalanche_forecast: "Previsione",
    avalanche_guidance: "Indicazioni",
    avalanche_fresh_snow: "Neve fresca",
    avalanche_locations: "Luoghi pericolosi",
    metric_humidity: "Umidità",
    metric_wind: "Vento",
    metric_gust: "Raffica",
    metric_rain: "Pioggia",
    metric_rain_prob: "Prob. pioggia",
    metric_pressure: "Pressione",
    metric_dew_point: "Rugiada",
    metric_solar: "Sole",
    metric_uv: "UV",
    metric_visibility: "Visibilità",
    metric_snow: "Neve",
    metric_snow_line: "Quota neve",
    metric_leaf: "Bagnatura",
    altitude_temps: "Quota",
    open_more_info: "Dettagli entità",
    close: "Chiudi",
    // Editor labels & helpers
    editor_device_id: "Dispositivo",
    helper_device_id: "Seleziona una stazione ARPA Veneto Meteo configurata",
    editor_name: "Nome",
    helper_name: "Titolo personalizzato opzionale nell'intestazione",
    editor_color: "Colore",
    helper_color: "Colore accento opzionale; predefinito in base alle condizioni meteo",
    editor_compact: "Layout compatto",
    editor_sections: "Sezioni visibili",
    editor_show_header: "Intestazione e temperatura attuale",
    editor_show_alerts: "Banner avvisi meteo e qualità aria",
    editor_show_metrics: "Schede condizioni attuali",
    editor_show_forecast: "Previsioni",
    editor_forecast_type: "Vista previsioni",
    editor_forecast_type_daily: "Giornaliero",
    editor_forecast_type_twice: "Biorario (Mattina / Pomeriggio)",
    editor_forecast_type_both: "Entrambi (con selettore)",
    editor_forecast_days: "Giorni di previsione",
    editor_show_radar: "Radar meteo",
    editor_radar_collapsed: "Avvia con radar compresso",
    editor_show_bulletin: "Bollettino meteo regionale",
    editor_show_air_quality: "Qualità dell'aria (PM10, PM2.5, Ozono)",
    editor_show_pollen: "Pollini allergenici",
    editor_show_hydrology: "Idrologia (livello fiume e portata)",
    editor_show_avalanche: "Neve e valanghe",
    editor_metrics: "Visibilità condizioni attuali",
    editor_show_metric_humidity: "Umidità",
    editor_show_metric_wind: "Velocità, direzione e raffiche vento",
    editor_show_metric_precipitation: "Precipitazioni e probabilità pioggia",
    editor_show_metric_pressure: "Pressione atmosferica",
    editor_show_metric_dew_point: "Punto di rugiada",
    editor_show_metric_solar_uv: "Radiazione solare e indice UV",
    editor_show_metric_visibility: "Visibilità",
    editor_show_metric_snow: "Neve, quota neve e temperature in quota",
    editor_show_metric_leaf_wetness: "Bagnatura fogliare",
  },
};

const t = (hass, key, fallback = key) => {
  const lang = hass?.locale?.language || hass?.language || "en";
  const table = STRINGS[lang] || STRINGS[String(lang).split("-")[0]] || {};
  return table[key] ?? STRINGS.en[key] ?? fallback;
};

const escapeHtml = (s) =>
  String(s ?? "").replace(
    /[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]
  );

const isLiveState = (stateObj) => {
  if (!stateObj || stateObj.attributes?.restored === true) return false;
  return stateObj.state !== "unavailable" && stateObj.state !== "unknown" && stateObj.state !== "";
};

const numericState = (stateObj) => {
  if (!isLiveState(stateObj)) return undefined;
  const value = Number(stateObj.state);
  return Number.isFinite(value) ? value : undefined;
};

function numberLocale(hass) {
  switch (hass?.locale?.number_format) {
    case "comma_decimal":
      return "en-US";
    case "decimal_comma":
      return "de";
    case "space_comma":
      return "fr";
    case "quote_decimal":
      return "de-CH";
    case "system":
      return undefined;
    default:
      return hass?.locale?.language || hass?.language || "en";
  }
}

function formatNumber(hass, value, maxDigits = 1) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) {
    return "-";
  }
  try {
    return new Intl.NumberFormat(numberLocale(hass), {
      minimumFractionDigits: 0,
      maximumFractionDigits: maxDigits,
      useGrouping: hass?.locale?.number_format !== "none",
    }).format(Number(value));
  } catch {
    return String(value);
  }
}

function formatState(hass, stateObj) {
  if (!stateObj) return "-";
  if (typeof hass?.formatEntityState === "function") {
    try {
      return hass.formatEntityState(stateObj);
    } catch {
      // Fall through to manual formatting
    }
  }
  const unit = stateObj.attributes?.unit_of_measurement;
  const n = Number(stateObj.state);
  if (Number.isFinite(n) && stateObj.state !== "") {
    const formatted = formatNumber(hass, n, 1);
    return unit ? `${formatted} ${unit}` : formatted;
  }
  return unit ? `${stateObj.state} ${unit}` : String(stateObj.state);
}

function formatTime(hass, isoString) {
  if (!isoString) return "";
  const dt = new Date(isoString);
  if (Number.isNaN(dt.getTime())) return "";
  const lang = hass?.locale?.language || hass?.language || "en";
  const tf = hass?.locale?.time_format;
  const opts = { hour: "2-digit", minute: "2-digit" };
  if (tf === "12") opts.hour12 = true;
  else if (tf === "24") opts.hour12 = false;
  if (hass?.locale?.time_zone === "server" && hass?.config?.time_zone) {
    opts.timeZone = hass.config.time_zone;
  }
  try {
    return new Intl.DateTimeFormat(lang, opts).format(dt);
  } catch {
    return dt.toLocaleTimeString();
  }
}

function formatShortDay(hass, isoString) {
  const dt = new Date(isoString);
  if (Number.isNaN(dt.getTime())) return String(isoString || "").slice(0, 10);
  const lang = hass?.locale?.language || hass?.language || "en";
  try {
    const label = new Intl.DateTimeFormat(lang, { weekday: "short", day: "numeric" }).format(dt);
    return label.charAt(0).toUpperCase() + label.slice(1);
  } catch {
    return String(isoString).slice(5, 10);
  }
}

function formatLongDate(hass, dateStr) {
  if (!dateStr) return "";
  const dt = new Date(dateStr.includes("T") ? dateStr : `${dateStr}T12:00:00`);
  if (Number.isNaN(dt.getTime())) return dateStr;
  const lang = hass?.locale?.language || hass?.language || "en";
  try {
    const label = new Intl.DateTimeFormat(lang, {
      weekday: "long",
      day: "numeric",
      month: "long",
    }).format(dt);
    return label.charAt(0).toUpperCase() + label.slice(1);
  } catch {
    return dateStr;
  }
}

function resolveDeviceId(hass, config) {
  if (config?.device_id) return config.device_id;
  if (config?.entity && hass?.entities?.[config.entity]?.device_id) {
    return hass.entities[config.entity].device_id;
  }
  return null;
}

function findFirstDeviceId(hass) {
  if (!hass) return "";
  const entry = Object.values(hass.entities || {}).find(
    (e) => e && e.platform === DOMAIN && e.device_id && !e.disabled_by
  );
  if (entry) return entry.device_id;
  const dev = Object.values(hass.devices || {}).find(
    (d) =>
      d &&
      Array.isArray(d.identifiers) &&
      d.identifiers.some((pair) => Array.isArray(pair) && pair[0] === DOMAIN)
  );
  return dev?.id || "";
}

function fireEvent(node, type, detail = {}) {
  node.dispatchEvent(new CustomEvent(type, { bubbles: true, composed: true, detail }));
}

function airQualityTone(kind, value) {
  if (value === undefined || value === null) {
    return { color: "var(--disabled-color, #bdbdbd)", limit: 50, maxScale: 75, status: "neutral" };
  }
  if (kind === "pm10") {
    const status = value > 50 ? "error" : value >= 38 ? "warning" : "ok";
    const color =
      status === "error"
        ? "var(--error-color, #db4437)"
        : status === "warning"
          ? "var(--warning-color, #ffa600)"
          : "var(--tile-color)";
    return { color, limit: 50, maxScale: 75, status };
  }
  if (kind === "pm25") {
    const status = value > 25 ? "error" : value >= 18 ? "warning" : "ok";
    const color =
      status === "error"
        ? "var(--error-color, #db4437)"
        : status === "warning"
          ? "var(--warning-color, #ffa600)"
          : "var(--tile-color)";
    return { color, limit: 25, maxScale: 40, status };
  }
  const status = value > 180 ? "error" : value >= 135 ? "warning" : "ok";
  const color =
    status === "error"
      ? "var(--error-color, #db4437)"
      : status === "warning"
        ? "var(--warning-color, #ffa600)"
        : "var(--tile-color)";
  return { color, limit: 180, maxScale: 240, status };
}

function hydroTrendMeta(trend) {
  if (trend === "+") {
    return {
      icon: "mdi:trending-up",
      labelKey: "hydro_rising",
      color: "var(--warning-color, #ffa600)",
    };
  }
  if (trend === "-") {
    return {
      icon: "mdi:trending-down",
      labelKey: "hydro_falling",
      color: "var(--secondary-text-color, #727272)",
    };
  }
  return {
    icon: "mdi:trending-neutral",
    labelKey: "hydro_stable",
    color: "var(--secondary-text-color, #727272)",
  };
}

/**
 * Native Home Assistant design-system styles matching design-tokens.md verbatim:
 * tile header, big value, ha-badge chips, ha-alert banners, 42px card features,
 * ha-control-select segmented control, and ha-dialog / ha-adaptive-dialog sheets.
 */
function buildCardStyles() {
  return `
    :host {
      display: block;
      --tile-color: var(--state-inactive-color, #9e9e9e);
      --radius: var(--ha-card-features-border-radius, var(--ha-border-radius-lg, 12px));
    }

    *, *::before, *::after {
      box-sizing: border-box;
    }

    ha-card {
      height: 100%;
      overflow: hidden;
    }

    .card {
      display: flex;
      flex-direction: column;
      gap: var(--ha-space-3, 12px);
      padding: var(--ha-space-3, 12px) var(--ha-space-4, 16px) var(--ha-space-4, 16px);
      container-type: inline-size;
      font-family: var(--ha-font-family-body, Roboto, Noto, sans-serif);
      color: var(--primary-text-color, #212121);
      -webkit-font-smoothing: antialiased;
    }

    .card.compact {
      gap: var(--ha-space-2, 8px);
      padding: var(--ha-space-3, 12px);
    }

    button {
      font: inherit;
      color: inherit;
      background: none;
      border: none;
      margin: 0;
      padding: 0;
      text-align: inherit;
      cursor: pointer;
      -webkit-tap-highlight-color: transparent;
    }

    button:disabled {
      cursor: not-allowed;
    }

    svg {
      display: block;
      fill: currentColor;
    }

    /* Empty / unconfigured state */
    .empty {
      display: flex;
      align-items: center;
      gap: var(--ha-space-3, 12px);
      min-height: 56px;
    }

    /* Native Tile Header + Big Value */
    .tile {
      width: 100%;
      display: flex;
      align-items: center;
      gap: 10px;
      min-height: 56px;
      padding: 4px 0;
      border-radius: var(--ha-card-border-radius, var(--ha-border-radius-lg, 12px));
      outline: none;
    }

    .tile:focus-visible {
      box-shadow: 0 0 0 2px var(--tile-color);
    }

    .tile-icon {
      position: relative;
      flex: none;
      width: 36px;
      height: 36px;
      overflow: hidden;
      display: flex;
      align-items: center;
      justify-content: center;
      border-radius: var(--ha-tile-icon-border-radius, var(--ha-border-radius-pill, 9999px));
      color: var(--tile-color);
      --mdc-icon-size: 24px;
    }

    .tile-icon::before {
      content: "";
      position: absolute;
      inset: 0;
      background: var(--tile-color);
      opacity: 0.2;
      transition: opacity 180ms ease-in-out;
    }

    .tile:hover .tile-icon::before {
      opacity: 0.35;
    }

    .tile-icon > * {
      position: relative;
    }

    .tile-info {
      flex: 1;
      min-width: 0;
      display: flex;
      flex-direction: column;
      justify-content: center;
      gap: 1px;
    }

    .primary,
    .secondary {
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .primary {
      font-size: var(--ha-font-size-m, 14px);
      font-weight: var(--ha-font-weight-medium, 500);
      line-height: 20px;
      letter-spacing: 0.1px;
      color: var(--primary-text-color, #212121);
    }

    .secondary {
      font-size: var(--ha-font-size-s, 12px);
      line-height: 16px;
      letter-spacing: 0.4px;
      color: var(--secondary-text-color, #727272);
      font-variant-numeric: tabular-nums;
    }

    .tile-value {
      flex: none;
      display: flex;
      flex-direction: column;
      align-items: flex-end;
      gap: 2px;
    }

    .value {
      display: flex;
      align-items: baseline;
      gap: 2px;
      line-height: var(--ha-line-height-condensed, 1.2);
    }

    .value .number {
      font-size: var(--ha-font-size-3xl, 28px);
      font-weight: var(--ha-font-weight-normal, 400);
      font-variant-numeric: tabular-nums;
      color: var(--primary-text-color, #212121);
    }

    .compact .value .number {
      font-size: var(--ha-font-size-2xl, 24px);
    }

    .value .unit {
      font-size: var(--ha-font-size-l, 16px);
      color: var(--secondary-text-color, #727272);
    }

    .tile-time {
      font-size: var(--ha-font-size-xs, 10px);
      line-height: 12px;
      letter-spacing: 0.2px;
      color: var(--secondary-text-color, #727272);
      font-variant-numeric: tabular-nums;
    }

    /* Native Alerts (like ha-alert: 0.12 tint layer, no extra border) */
    .alerts {
      display: flex;
      flex-direction: column;
      gap: var(--ha-space-2, 8px);
    }

    .alert {
      position: relative;
      width: 100%;
      display: flex;
      align-items: center;
      min-height: 44px;
      padding: var(--ha-space-3, 12px);
      border-radius: var(--ha-border-radius-lg, 12px);
      overflow: hidden;
      outline: none;
    }

    .alert::before {
      content: "";
      position: absolute;
      inset: 0;
      background: var(--alert-color);
      opacity: 0.12;
      pointer-events: none;
      transition: opacity 180ms ease-in-out;
    }

    .alert:hover::before {
      opacity: 0.18;
    }

    .alert:focus-visible {
      box-shadow: 0 0 0 2px var(--alert-color);
    }

    .alert > * {
      position: relative;
    }

    .alert ha-icon {
      flex: none;
      color: var(--alert-color);
      --mdc-icon-size: 20px;
    }

    .alert .alert-chevron {
      color: var(--secondary-text-color, #727272);
      --mdc-icon-size: 18px;
    }

    .alert .text {
      flex: 1;
      min-width: 0;
      margin-inline: var(--ha-space-2, 8px);
      line-height: var(--ha-line-height-condensed, 1.2);
      color: var(--primary-text-color, #212121);
      display: flex;
      flex-direction: column;
      gap: 2px;
    }

    .alert .title {
      font-size: var(--ha-font-size-s, 12px);
      font-weight: var(--ha-font-weight-bold, 700);
    }

    .alert .desc {
      font-size: var(--ha-font-size-s, 12px);
      color: var(--secondary-text-color, #727272);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .alert.info { --alert-color: var(--info-color, #039be5); }
    .alert.warning { --alert-color: var(--warning-color, #ffa600); }
    .alert.error { --alert-color: var(--error-color, #db4437); }
    .alert.success { --alert-color: var(--success-color, #43a047); }

    /* Native Badges (like ha-badge inside a card) */
    .badges {
      display: flex;
      flex-wrap: wrap;
      gap: var(--ha-space-2, 8px);
    }

    .badge {
      position: relative;
      overflow: hidden;
      display: inline-flex;
      align-items: center;
      gap: var(--ha-space-2, 8px);
      min-height: 40px;
      min-width: 40px;
      padding: 4px var(--ha-space-3, 12px);
      border-radius: var(--ha-badge-border-radius, 18px);
      border: var(--ha-card-border-width, 1px) solid var(--ha-card-border-color, var(--divider-color, #e0e0e0));
      background: transparent;
      outline: none;
    }

    .compact .badge {
      min-height: 36px;
      padding: 2px 10px;
    }

    .badge::before {
      content: "";
      position: absolute;
      inset: 0;
      background: var(--primary-text-color, #212121);
      opacity: 0;
      pointer-events: none;
      transition: opacity 180ms ease-in-out;
    }

    .badge:hover::before {
      opacity: 0.04;
    }

    .badge:focus-visible {
      box-shadow: 0 0 0 2px var(--tile-color);
    }

    .badge > * {
      position: relative;
    }

    .badge ha-icon {
      --mdc-icon-size: 18px;
      margin-inline-start: -4px;
      color: var(--badge-color, var(--secondary-text-color, #727272));
      flex: none;
    }

    .badge-info {
      display: flex;
      flex-direction: column;
      align-items: flex-start;
      gap: 1px;
      min-width: 0;
    }

    .badge .label {
      font-size: var(--ha-font-size-xs, 10px);
      font-weight: var(--ha-font-weight-medium, 500);
      line-height: 11px;
      letter-spacing: 0.1px;
      color: var(--secondary-text-color, #727272);
    }

    .badge .content {
      font-size: var(--ha-font-size-s, 12px);
      font-weight: var(--ha-font-weight-medium, 500);
      line-height: 1.2;
      letter-spacing: 0.1px;
      color: var(--primary-text-color, #212121);
      font-variant-numeric: tabular-nums;
      white-space: nowrap;
    }

    .badge-dot {
      width: 8px;
      height: 8px;
      border-radius: var(--ha-border-radius-circle, 50%);
      background: var(--badge-color, var(--secondary-text-color, #727272));
      flex: none;
    }

    /* Aligned mini-cards grid for current weather conditions (native HA card border + tile rhythm) */
    .metrics-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: var(--ha-space-2, 8px);
    }

    .metrics-grid.cols-1 {
      grid-template-columns: 1fr;
    }

    .metric-card {
      position: relative;
      overflow: hidden;
      display: flex;
      align-items: center;
      gap: 10px;
      min-height: 54px;
      min-width: 0;
      padding: var(--ha-space-2, 8px) var(--ha-space-3, 12px);
      border-radius: var(--radius);
      border: var(--ha-card-border-width, 1px) solid var(--ha-card-border-color, var(--divider-color, #e0e0e0));
      background: transparent;
      outline: none;
    }

    .compact .metric-card {
      min-height: 46px;
      gap: var(--ha-space-2, 8px);
      padding: 6px 10px;
    }

    .metric-card::before {
      content: "";
      position: absolute;
      inset: 0;
      background: var(--primary-text-color, #212121);
      opacity: 0;
      pointer-events: none;
      transition: opacity 180ms ease-in-out;
    }

    .metric-card:hover::before {
      opacity: 0.04;
    }

    .metric-card:focus-visible {
      box-shadow: 0 0 0 2px var(--tile-color);
    }

    .metric-card > * {
      position: relative;
    }

    .metric-card ha-icon {
      flex: none;
      --mdc-icon-size: 20px;
      color: var(--secondary-text-color, #727272);
    }

    .metric-info {
      flex: 1;
      min-width: 0;
      display: flex;
      flex-direction: column;
      gap: 1px;
    }

    .metric-label {
      font-size: var(--ha-font-size-s, 12px);
      line-height: 15px;
      letter-spacing: 0.2px;
      color: var(--secondary-text-color, #727272);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .metric-value {
      font-size: var(--ha-font-size-m, 14px);
      font-weight: var(--ha-font-weight-medium, 500);
      line-height: 18px;
      color: var(--primary-text-color, #212121);
      font-variant-numeric: tabular-nums;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .metric-sub {
      font-size: var(--ha-font-size-xs, 10px);
      line-height: 13px;
      letter-spacing: 0.2px;
      color: var(--secondary-text-color, #727272);
      font-variant-numeric: tabular-nums;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    /* Subtle group block */
    .block {
      display: flex;
      flex-direction: column;
      gap: var(--ha-space-2, 8px);
      padding-top: var(--ha-space-3, 12px);
      border-top: var(--ha-card-border-width, 1px) solid var(--divider-color, rgba(0, 0, 0, 0.12));
    }

    .block:first-child {
      padding-top: 0;
      border-top: none;
    }

    .block-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: var(--ha-space-2, 8px);
      min-height: 24px;
    }

    .block-title {
      margin: 0;
      font-size: var(--ha-font-size-s, 12px);
      font-weight: var(--ha-font-weight-medium, 500);
      line-height: 16px;
      letter-spacing: 0.4px;
      color: var(--secondary-text-color, #727272);
    }

    .inline-action {
      position: relative;
      overflow: hidden;
      display: inline-flex;
      align-items: center;
      gap: var(--ha-space-1, 4px);
      min-height: 32px;
      padding: 0 var(--ha-space-2, 8px);
      margin-inline-end: -8px;
      border-radius: var(--ha-border-radius-md, 8px);
      font-size: var(--ha-font-size-s, 12px);
      font-weight: var(--ha-font-weight-medium, 500);
      color: var(--secondary-text-color, #727272);
      outline: none;
    }

    .inline-action::before {
      content: "";
      position: absolute;
      inset: 0;
      background: var(--disabled-color, #bdbdbd);
      opacity: 0;
      pointer-events: none;
      transition: opacity 180ms ease-in-out;
    }

    .inline-action:hover::before {
      opacity: 0.2;
    }

    .inline-action:focus-visible {
      box-shadow: 0 0 0 2px var(--tile-color);
    }

    .inline-action > * {
      position: relative;
    }

    .inline-action ha-icon {
      --mdc-icon-size: 16px;
    }

    /* Native Segmented Control (like ha-control-select) */
    .segmented {
      position: relative;
      display: flex;
      gap: 4px;
      padding: 4px;
      height: 40px;
      border-radius: var(--ha-border-radius-lg, 12px);
    }

    .segmented::before {
      content: "";
      position: absolute;
      inset: 0;
      border-radius: inherit;
      background: var(--disabled-color, #bdbdbd);
      opacity: 0.2;
      pointer-events: none;
    }

    .option {
      position: relative;
      flex: 1;
      min-width: 0;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      border-radius: calc(var(--ha-border-radius-lg, 12px) - 4px);
      font-size: var(--ha-font-size-m, 14px);
      font-weight: var(--ha-font-weight-medium, 500);
      color: var(--primary-text-color, #212121);
      outline: none;
    }

    .option::before {
      content: "";
      position: absolute;
      inset: 0;
      border-radius: inherit;
      background: var(--tile-color);
      opacity: 0;
      pointer-events: none;
      transition: opacity 80ms ease-in-out;
    }

    .option:hover::before {
      opacity: 0.2;
    }

    .option:focus-visible {
      box-shadow: inset 0 0 0 2px var(--tile-color);
    }

    .option.selected {
      color: var(--text-primary-color, #ffffff);
    }

    .option.selected::before {
      opacity: 1;
    }

    .option span {
      position: relative;
    }

    /* Native Weather Forecast Strip (mirrors hui-weather-forecast-card) */
    .forecast-strip {
      display: grid;
      grid-auto-flow: column;
      grid-auto-columns: minmax(58px, 1fr);
      gap: var(--ha-space-1, 4px);
      overflow-x: auto;
      scrollbar-width: thin;
    }

    .forecast-col {
      position: relative;
      overflow: hidden;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: space-between;
      gap: 4px;
      min-height: 92px;
      padding: var(--ha-space-2, 8px) var(--ha-space-1, 4px);
      border-radius: var(--radius);
      outline: none;
    }

    .forecast-col::before {
      content: "";
      position: absolute;
      inset: 0;
      background: var(--disabled-color, #bdbdbd);
      opacity: 0;
      pointer-events: none;
      transition: opacity 180ms ease-in-out;
    }

    .forecast-col:hover::before {
      opacity: 0.2;
    }

    .forecast-col:focus-visible {
      box-shadow: inset 0 0 0 2px var(--tile-color);
    }

    .forecast-col > * {
      position: relative;
    }

    .fc-day {
      font-size: var(--ha-font-size-s, 12px);
      font-weight: var(--ha-font-weight-medium, 500);
      line-height: 16px;
      color: var(--primary-text-color, #212121);
      text-align: center;
      white-space: nowrap;
    }

    .fc-period {
      display: block;
      font-size: var(--ha-font-size-xs, 10px);
      font-weight: var(--ha-font-weight-normal, 400);
      line-height: 12px;
      color: var(--secondary-text-color, #727272);
    }

    .fc-icon {
      --mdc-icon-size: 24px;
      color: var(--state-icon-color, #44739e);
      margin: 2px 0;
    }

    .fc-high {
      font-size: var(--ha-font-size-m, 14px);
      font-weight: var(--ha-font-weight-medium, 500);
      line-height: 18px;
      color: var(--primary-text-color, #212121);
      font-variant-numeric: tabular-nums;
    }

    .fc-low {
      font-size: var(--ha-font-size-s, 12px);
      line-height: 14px;
      color: var(--secondary-text-color, #727272);
      font-variant-numeric: tabular-nums;
    }

    .fc-prob {
      font-size: var(--ha-font-size-xs, 10px);
      line-height: 12px;
      color: var(--info-color, #039be5);
      font-variant-numeric: tabular-nums;
      min-height: 12px;
    }

    .fc-placeholder {
      font-size: var(--ha-font-size-s, 12px);
      color: var(--secondary-text-color, #727272);
      padding: var(--ha-space-1, 4px) 0;
    }

    /* Native 42px Card Feature Rows & Buttons (design-tokens.md Features pattern) */
    .features {
      display: flex;
      flex-direction: column;
      gap: var(--ha-space-2, 8px);
    }

    .feature-grid {
      display: grid;
      grid-template-columns: 1fr;
      gap: var(--ha-space-2, 8px);
    }

    .feature-row {
      position: relative;
      overflow: hidden;
      width: 100%;
      min-height: 42px;
      display: flex;
      align-items: center;
      gap: 10px;
      padding: var(--ha-space-2, 8px) var(--ha-space-3, 12px);
      border-radius: var(--radius);
      border: var(--ha-card-border-width, 1px) solid var(--ha-card-border-color, var(--divider-color, #e0e0e0));
      background: transparent;
      color: var(--primary-text-color, #212121);
      --mdc-icon-size: 20px;
      outline: none;
    }

    .feature-row::before {
      content: "";
      position: absolute;
      inset: 0;
      background: var(--primary-text-color, #212121);
      opacity: 0;
      pointer-events: none;
      transition: opacity 180ms ease-in-out;
    }

    .feature-row:hover::before {
      opacity: 0.04;
    }

    .feature-row:focus-visible {
      box-shadow: 0 0 0 2px var(--tile-color);
    }

    .feature-row > * {
      position: relative;
    }

    .feature-icon {
      flex: none;
      color: var(--feature-icon-color, var(--secondary-text-color, #727272));
    }

    .feature-text {
      flex: 1;
      min-width: 0;
      display: flex;
      flex-direction: column;
      gap: 2px;
    }

    .feature-val {
      flex: none;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-size: var(--ha-font-size-m, 14px);
      font-weight: var(--ha-font-weight-medium, 500);
      font-variant-numeric: tabular-nums;
      color: var(--feature-val-color, var(--primary-text-color, #212121));
    }

    .feature-chevron {
      flex: none;
      --mdc-icon-size: 18px;
      color: var(--secondary-text-color, #727272);
    }

    .bulletin-preview {
      margin: 0;
      font-size: var(--ha-font-size-s, 12px);
      line-height: 16px;
      color: var(--secondary-text-color, #727272);
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }

    /* Weather radar frame */
    .radar-frame {
      position: relative;
      display: block;
      width: 100%;
      border-radius: var(--radius);
      overflow: hidden;
      border: var(--ha-card-border-width, 1px) solid var(--ha-card-border-color, var(--divider-color, #e0e0e0));
      outline: none;
    }

    .radar-frame::before {
      content: "";
      position: absolute;
      inset: 0;
      background: var(--disabled-color, #bdbdbd);
      opacity: 0.15;
      pointer-events: none;
    }

    .radar-frame:focus-visible {
      box-shadow: 0 0 0 2px var(--tile-color);
    }

    .radar-img {
      position: relative;
      display: block;
      width: 100%;
      aspect-ratio: 16 / 10;
      object-fit: contain;
    }

    .radar-img.dark-mosaic {
      filter: invert(0.88) hue-rotate(180deg);
    }

    .radar-scrim {
      position: absolute;
      left: 0;
      right: 0;
      bottom: 0;
      padding: var(--ha-space-4, 16px) var(--ha-space-3, 12px) var(--ha-space-2, 8px);
      background: linear-gradient(to top, rgba(0, 0, 0, 0.38), transparent);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: var(--ha-space-2, 8px);
      color: var(--text-primary-color, #ffffff);
      font-size: var(--ha-font-size-s, 12px);
      font-weight: var(--ha-font-weight-medium, 500);
      pointer-events: none;
    }

    .radar-scrim ha-icon {
      --mdc-icon-size: 16px;
    }

    /* Air quality mini-cards (native HA border + slim EU limit progress bar) */
    .aq-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(94px, 1fr));
      gap: var(--ha-space-2, 8px);
    }

    .aq-tile {
      position: relative;
      overflow: hidden;
      display: flex;
      flex-direction: column;
      gap: 6px;
      min-height: 76px;
      padding: 8px;
      border-radius: var(--radius);
      border: var(--ha-card-border-width, 1px) solid var(--ha-card-border-color, var(--divider-color, #e0e0e0));
      background: transparent;
      outline: none;
    }

    .aq-tile::before {
      content: "";
      position: absolute;
      inset: 0;
      background: var(--primary-text-color, #212121);
      opacity: 0;
      pointer-events: none;
      transition: opacity 180ms ease-in-out;
    }

    .aq-tile:hover::before {
      opacity: 0.04;
    }

    .aq-tile:focus-visible {
      box-shadow: 0 0 0 2px var(--tile-color);
    }

    .aq-tile > * {
      position: relative;
    }

    .aq-top {
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: var(--ha-space-1, 4px);
    }

    .aq-name {
      font-size: var(--ha-font-size-s, 12px);
      font-weight: var(--ha-font-weight-medium, 500);
      color: var(--secondary-text-color, #727272);
    }

    .aq-limit {
      font-size: var(--ha-font-size-xs, 10px);
      color: var(--secondary-text-color, #727272);
      font-variant-numeric: tabular-nums;
      white-space: nowrap;
    }

    .aq-reading {
      display: flex;
      align-items: baseline;
      gap: 3px;
      font-variant-numeric: tabular-nums;
      line-height: var(--ha-line-height-condensed, 1.2);
    }

    .aq-val {
      font-size: var(--ha-font-size-l, 16px);
      font-weight: var(--ha-font-weight-medium, 500);
      color: var(--primary-text-color, #212121);
    }

    .aq-unit {
      font-size: var(--ha-font-size-xs, 10px);
      color: var(--secondary-text-color, #727272);
    }

    .aq-bar {
      position: relative;
      height: 4px;
      border-radius: var(--ha-border-radius-pill, 9999px);
      overflow: visible;
    }

    .aq-bar::before {
      content: "";
      position: absolute;
      inset: 0;
      border-radius: inherit;
      background: var(--disabled-color, #bdbdbd);
      opacity: 0.35;
    }

    .aq-bar-fill {
      position: relative;
      display: block;
      height: 100%;
      width: var(--bar-pct, 0%);
      border-radius: inherit;
      background: var(--bar-color, var(--tile-color));
    }

    .aq-bar-limit {
      position: absolute;
      top: -2px;
      bottom: -2px;
      left: var(--limit-pct, 66%);
      width: 1.5px;
      background: var(--secondary-text-color, #727272);
      opacity: 0.6;
    }

    /* Avalanche 5-segment scale inside outlined HA mini-card */
    .av-tile {
      position: relative;
      overflow: hidden;
      display: flex;
      flex-direction: column;
      gap: 6px;
      min-height: 52px;
      padding: var(--ha-space-2, 8px) var(--ha-space-3, 12px);
      border-radius: var(--radius);
      border: var(--ha-card-border-width, 1px) solid var(--ha-card-border-color, var(--divider-color, #e0e0e0));
      background: transparent;
      outline: none;
    }

    .av-tile::before {
      content: "";
      position: absolute;
      inset: 0;
      background: var(--primary-text-color, #212121);
      opacity: 0;
      pointer-events: none;
      transition: opacity 180ms ease-in-out;
    }

    .av-tile:hover::before {
      opacity: 0.04;
    }

    .av-tile:focus-visible {
      box-shadow: 0 0 0 2px var(--tile-color);
    }

    .av-tile > * {
      position: relative;
    }

    .av-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: var(--ha-space-2, 8px);
    }

    .av-scale {
      display: grid;
      grid-template-columns: repeat(5, 1fr);
      gap: 4px;
    }

    .av-seg {
      position: relative;
      height: 4px;
      border-radius: var(--ha-border-radius-pill, 9999px);
      overflow: hidden;
    }

    .av-seg::before {
      content: "";
      position: absolute;
      inset: 0;
      background: var(--disabled-color, #bdbdbd);
      opacity: 0.35;
    }

    .av-seg.filled::before {
      background: var(--av-color, var(--tile-color));
      opacity: 1;
    }

    .trend-inline {
      display: inline-flex;
      align-items: center;
      gap: 2px;
      font-size: var(--ha-font-size-s, 12px);
      font-weight: var(--ha-font-weight-medium, 500);
      color: var(--trend-color, var(--secondary-text-color, #727272));
    }

    .trend-inline ha-icon {
      --mdc-icon-size: 16px;
    }

    /* Native HA Feature Button (for dialog actions) */
    .button {
      position: relative;
      overflow: hidden;
      z-index: 0;
      height: 40px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      padding: 0 var(--ha-space-4, 16px);
      border-radius: var(--radius);
      font-size: var(--ha-font-size-m, 14px);
      font-weight: var(--ha-font-weight-medium, 500);
      color: var(--primary-text-color, #212121);
      --mdc-icon-size: 18px;
      outline: none;
    }

    .button::before {
      content: "";
      position: absolute;
      inset: 0;
      background: var(--disabled-color, #bdbdbd);
      opacity: 0.2;
      transition: opacity 180ms ease-in-out;
      pointer-events: none;
    }

    .button:hover:not(:disabled)::before {
      opacity: 0.3;
    }

    .button.tonal::before {
      background: var(--tile-color);
    }

    .button.tonal {
      color: var(--tile-color);
    }

    .button:focus-visible {
      box-shadow: 0 0 0 2px var(--tile-color);
    }

    .button > * {
      position: relative;
    }

    /* Native Dialogs and Bottom Sheets (design-tokens.md lines 274-288 + modern-web-guidance) */
    dialog {
      width: min(580px, 95vw);
      max-height: min(80vh, 720px);
      padding: 0;
      border: none;
      overflow: hidden;
      border-radius: var(--ha-dialog-border-radius, var(--ha-border-radius-3xl, 24px));
      background: var(--ha-dialog-surface-background, var(--card-background-color, #ffffff));
      color: var(--primary-text-color, #212121);
      box-shadow: var(--ha-box-shadow-l, 0 16px 32px -6px rgba(0, 0, 0, 0.2));
      font-family: var(--ha-font-family-body, Roboto, Noto, sans-serif);
    }

    dialog[open] {
      display: flex;
      flex-direction: column;
    }

    dialog:modal {
      overscroll-behavior: contain;
    }

    dialog::backdrop {
      background: rgba(0, 0, 0, 0.32);
      overflow: hidden;
      overscroll-behavior: contain;
    }

    .dialog-header {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: var(--ha-space-3, 12px);
      padding: 24px 24px 12px;
    }

    .dialog-title {
      margin: 0;
      font-size: var(--ha-font-size-2xl, 24px);
      line-height: var(--ha-line-height-condensed, 1.2);
      font-weight: var(--ha-font-weight-normal, 400);
      color: var(--primary-text-color, #212121);
    }

    .dialog-close {
      position: relative;
      overflow: hidden;
      flex: none;
      width: 40px;
      height: 40px;
      margin: -6px -8px 0 0;
      border-radius: var(--ha-border-radius-pill, 9999px);
      display: inline-flex;
      align-items: center;
      justify-content: center;
      color: var(--secondary-text-color, #727272);
      --mdc-icon-size: 20px;
      outline: none;
    }

    .dialog-close::before {
      content: "";
      position: absolute;
      inset: 0;
      background: var(--disabled-color, #bdbdbd);
      opacity: 0;
      pointer-events: none;
      transition: opacity 180ms ease-in-out;
    }

    .dialog-close:hover::before {
      opacity: 0.25;
    }

    .dialog-close:focus-visible {
      box-shadow: 0 0 0 2px var(--tile-color);
    }

    .dialog-close > * {
      position: relative;
    }

    .dialog-content {
      padding: 0 24px 24px;
      overflow: auto;
      display: flex;
      flex-direction: column;
      gap: var(--ha-space-4, 16px);
      font-size: var(--ha-font-size-m, 14px);
      line-height: var(--ha-line-height-normal, 1.6);
    }

    .dialog-section-title {
      margin: 0 0 var(--ha-space-1, 4px);
      font-size: var(--ha-font-size-s, 12px);
      font-weight: var(--ha-font-weight-medium, 500);
      letter-spacing: 0.4px;
      color: var(--secondary-text-color, #727272);
    }

    .dialog-block {
      margin: 0;
      white-space: pre-line;
      color: var(--primary-text-color, #212121);
    }

    .dialog-day {
      padding: var(--ha-space-3, 12px);
      border-radius: var(--radius);
      border: var(--ha-card-border-width, 1px) solid var(--ha-card-border-color, var(--divider-color, #e0e0e0));
      display: flex;
      flex-direction: column;
      gap: var(--ha-space-1, 4px);
    }

    .dialog-day-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: var(--ha-space-2, 8px);
      font-size: var(--ha-font-size-m, 14px);
      font-weight: var(--ha-font-weight-medium, 500);
    }

    .dialog-radar-img {
      width: 100%;
      height: auto;
      border-radius: var(--ha-border-radius-lg, 12px);
      display: block;
    }

    .dialog-radar-img.dark-mosaic {
      filter: invert(0.88) hue-rotate(180deg);
    }

    .dialog-table {
      width: 100%;
      border-collapse: collapse;
      font-size: var(--ha-font-size-m, 14px);
    }

    .dialog-table th,
    .dialog-table td {
      text-align: left;
      padding: var(--ha-space-2, 8px) var(--ha-space-1, 4px);
      border-bottom: 1px solid var(--divider-color, rgba(0, 0, 0, 0.12));
    }

    .dialog-table th {
      font-size: var(--ha-font-size-s, 12px);
      font-weight: var(--ha-font-weight-medium, 500);
      color: var(--secondary-text-color, #727272);
    }

    .dialog-dot {
      display: inline-block;
      width: 8px;
      height: 8px;
      border-radius: var(--ha-border-radius-circle, 50%);
      margin-inline-end: var(--ha-space-2, 8px);
      background: var(--dot-color, var(--disabled-color, #bdbdbd));
    }

    .dialog-footer {
      display: flex;
      justify-content: flex-end;
      gap: var(--ha-space-2, 8px);
      padding: 0 24px 20px;
    }

    .dialog-footer:empty {
      display: none;
    }

    /* Container-aware breakpoints (inside .card container-type: inline-size) */
    @container (min-width: 380px) {
      .metrics-grid:not(.cols-1):not(.cols-2) {
        grid-template-columns: repeat(3, minmax(0, 1fr));
      }
    }

    @container (min-width: 420px) {
      .feature-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
    }

    @container (min-width: 540px) {
      .metrics-grid:not(.cols-1):not(.cols-2):not(.cols-3) {
        grid-template-columns: repeat(4, minmax(0, 1fr));
      }
    }

    @container (min-width: 560px) {
      .radar-img {
        aspect-ratio: 16 / 9;
      }
    }

    /* Native HA mobile bottom-sheet breakpoint (870px wide or 500px tall) */
    @media (max-width: 870px), (max-height: 500px) {
      dialog {
        width: 100vw;
        max-width: 100vw;
        margin: auto 0 0;
        max-height: 90vh;
        border-radius: var(--ha-border-radius-2xl, 20px) var(--ha-border-radius-2xl, 20px) 0 0;
        padding-bottom: var(--safe-area-inset-bottom, env(safe-area-inset-bottom, 0px));
      }
    }

    @media (prefers-reduced-motion: reduce) {
      * {
        animation-duration: 1ms !important;
        transition-duration: 1ms !important;
      }
    }
  `;
}

class ArpaVenetoMeteoCard extends HTMLElement {
  static getConfigElement() {
    return document.createElement(EDITOR_TYPE);
  }

  static getStubConfig(hass) {
    const deviceId = findFirstDeviceId(hass);
    return deviceId ? { device_id: deviceId } : {};
  }

  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = { ...DEFAULTS };
    this._hass = null;
    this._detached = false;
    this._activeForecastMode = "daily";
    this._radarCollapsed = false;
    this._forecasts = { daily: null, twice_daily: null };
    this._unsubDaily = null;
    this._unsubTwice = null;
    this._subscribedEntityId = null;
    this._cacheEntitiesRef = null;
    this._cacheDeviceId = null;
    this._cacheFallback = null;
    this._entityCache = null;
    this._domReady = false;
  }

  setConfig(config) {
    if (!config || typeof config !== "object") {
      throw new Error("Invalid configuration");
    }
    this._config = { ...DEFAULTS, ...config };
    this._activeForecastMode =
      this._config.forecast_type === "twice_daily" ? "twice_daily" : "daily";
    this._radarCollapsed = Boolean(this._config.radar_collapsed);
    this._entityCache = null;
    this._ensureDom();
    this._syncForecastSubscriptions();
    this._render();
  }

  set hass(hass) {
    const old = this._hass;
    this._hass = hass;
    this._ensureDom();
    if (!old || this._changed(old, hass)) {
      if (!old || old.entities !== hass.entities) {
        this._entityCache = null;
      }
      this._syncForecastSubscriptions();
      this._render();
    }
  }

  get hass() {
    return this._hass;
  }

  connectedCallback() {
    this._ensureDom();
    if (this._detached) {
      this._syncForecastSubscriptions();
      this._render();
    }
    this._detached = false;
  }

  disconnectedCallback() {
    this._unsubscribeForecasts();
    this._detached = true;
  }

  getCardSize() {
    let size = 2;
    if (this._config.show_metrics) size += 2;
    if (this._config.show_forecast) size += 3;
    if (this._config.show_radar && !this._radarCollapsed) size += 4;
    if (this._config.show_bulletin) size += 1;
    if (this._config.show_air_quality) size += 2;
    if (this._config.show_pollen) size += 1;
    if (this._config.show_hydrology || this._config.show_avalanche) size += 1;
    return size;
  }

  getGridOptions() {
    return {
      columns: 12,
      min_columns: 6,
    };
  }

  _changed(old, hass) {
    if (
      old.entities !== hass.entities ||
      old.locale !== hass.locale ||
      old.language !== hass.language ||
      old.themes !== hass.themes
    ) {
      return true;
    }
    const watched = this._getEntityIndex(hass).allEntityIds;
    return watched.some((id) => old.states?.[id] !== hass.states?.[id]);
  }

  _getEntityIndex(hass = this._hass) {
    const deviceId = resolveDeviceId(hass, this._config);
    const fallback = this._config.entity || "";
    if (
      this._entityCache &&
      this._cacheEntitiesRef === hass?.entities &&
      this._cacheDeviceId === deviceId &&
      this._cacheFallback === fallback
    ) {
      return this._entityCache;
    }

    const byKey = new Map();
    const pollenIds = [];
    const allEntityIds = [];

    if (hass) {
      const registry = hass.entities || {};
      for (const entry of Object.values(registry)) {
        if (!entry || entry.device_id !== deviceId || entry.disabled_by) continue;
        const entityId = entry.entity_id;
        allEntityIds.push(entityId);
        const domain = entityId.split(".")[0];
        const tkey = entry.translation_key;

        if (tkey) {
          const composite = `${domain}.${tkey}`;
          const list = byKey.get(composite) || [];
          list.push(entityId);
          byKey.set(composite, list);
        } else if (domain === "weather") {
          const list = byKey.get("weather.arpav_weather") || [];
          list.push(entityId);
          byKey.set("weather.arpav_weather", list);
        } else if (domain === "image") {
          const list = byKey.get("image.radar") || [];
          list.push(entityId);
          byKey.set("image.radar", list);
        } else if (domain === "sensor") {
          pollenIds.push(entityId);
        }
      }

      if (!byKey.has("weather.arpav_weather") && fallback) {
        byKey.set("weather.arpav_weather", [fallback]);
        allEntityIds.push(fallback);
      }
    }

    this._cacheEntitiesRef = hass?.entities || null;
    this._cacheDeviceId = deviceId;
    this._cacheFallback = fallback;
    this._entityCache = { deviceId, byKey, pollenIds, allEntityIds };
    return this._entityCache;
  }

  _getContext() {
    const hass = this._hass;
    const index = this._getEntityIndex(hass);
    const map = {};
    const pollenSpecies = [];

    if (hass) {
      for (const [key, ids] of index.byKey.entries()) {
        let picked = null;
        for (const entityId of ids) {
          const stateObj = hass.states?.[entityId];
          if (!stateObj || stateObj.attributes?.restored === true) continue;
          if (!picked || (!isLiveState(picked.stateObj) && isLiveState(stateObj))) {
            picked = { entityId, stateObj };
          }
        }
        if (picked) {
          map[key] = picked;
        }
      }

      for (const entityId of index.pollenIds) {
        const stateObj = hass.states?.[entityId];
        if (
          stateObj &&
          stateObj.attributes?.restored !== true &&
          stateObj.attributes?.source === "pollen_station" &&
          stateObj.attributes?.species_code
        ) {
          pollenSpecies.push({ entityId, stateObj });
        }
      }
    }

    const device = index.deviceId ? hass?.devices?.[index.deviceId] : null;
    return {
      deviceId: index.deviceId,
      device,
      map,
      pollenSpecies,
      allEntityIds: index.allEntityIds,
    };
  }

  _ensureDom() {
    if (this._domReady) return;
    this._domReady = true;

    const style = document.createElement("style");
    style.textContent = buildCardStyles();

    const card = document.createElement("ha-card");
    const body = document.createElement("div");
    body.className = "card";
    card.appendChild(body);

    const dialog = document.createElement("dialog");
    dialog.setAttribute("closedby", "any");
    dialog.setAttribute("aria-labelledby", "arpav-dialog-title");
    dialog.innerHTML = `
      <div class="dialog-header">
        <h1 id="arpav-dialog-title" class="dialog-title"></h1>
        <button type="button" class="dialog-close" data-action="close-dialog" aria-label="Close">
          <ha-icon icon="mdi:close" aria-hidden="true"></ha-icon>
        </button>
      </div>
      <div class="dialog-content"></div>
      <div class="dialog-footer"></div>
    `;

    // Fallback light-dismiss for Safari where closedBy is not yet supported
    if (typeof HTMLDialogElement !== "undefined" && !("closedBy" in HTMLDialogElement.prototype)) {
      let pressedOutside = false;
      const isOutside = (ev) => {
        const rect = dialog.getBoundingClientRect();
        return (
          ev.clientX < rect.left ||
          ev.clientX > rect.right ||
          ev.clientY < rect.top ||
          ev.clientY > rect.bottom
        );
      };
      dialog.addEventListener("pointerdown", (ev) => {
        pressedOutside = isOutside(ev);
      });
      dialog.addEventListener("pointerup", (ev) => {
        if (pressedOutside && isOutside(ev)) dialog.close();
      });
    }

    dialog.addEventListener("close", () => {
      dialog.returnValue = "";
    });

    dialog.addEventListener("click", (ev) => {
      const btn = ev.target.closest("button[data-action]");
      if (!btn) return;
      const action = btn.dataset.action;
      if (action === "close-dialog") {
        dialog.close();
      } else if (action === "more-info" && btn.dataset.entityId) {
        const entityId = btn.dataset.entityId;
        dialog.close();
        this._openMoreInfo(entityId);
      }
    });

    body.addEventListener("click", (ev) => this._handleBodyClick(ev));

    this.shadowRoot.append(style, card, dialog);
    this._bodyEl = body;
    this._dialogEl = dialog;
  }

  _syncForecastSubscriptions() {
    if (!this._hass || !this._config.show_forecast) {
      this._unsubscribeForecasts();
      return;
    }
    const { map } = this._getContext();
    const weatherEntry = map["weather.arpav_weather"];
    const weatherEntityId = weatherEntry?.entityId || null;

    if (!weatherEntityId) {
      this._unsubscribeForecasts();
      return;
    }

    const needDaily =
      this._config.forecast_type === "daily" || this._config.forecast_type === "both";
    const needTwice =
      this._config.forecast_type === "twice_daily" || this._config.forecast_type === "both";

    if (this._subscribedEntityId !== weatherEntityId) {
      this._unsubscribeForecasts();
      this._subscribedEntityId = weatherEntityId;
    }

    if (!this._hass.connection || typeof this._hass.connection.subscribeMessage !== "function") {
      const attrs = weatherEntry.stateObj?.attributes || {};
      if (Array.isArray(attrs.forecast_daily)) this._forecasts.daily = attrs.forecast_daily;
      else if (Array.isArray(attrs.forecast)) this._forecasts.daily = attrs.forecast;
      if (Array.isArray(attrs.forecast_twice_daily)) {
        this._forecasts.twice_daily = attrs.forecast_twice_daily;
      }
      return;
    }

    if (needDaily && !this._unsubDaily) {
      this._subscribeForecastType(weatherEntityId, "daily");
    } else if (!needDaily && this._unsubDaily) {
      this._safeUnsub(this._unsubDaily);
      this._unsubDaily = null;
    }

    if (needTwice && !this._unsubTwice) {
      this._subscribeForecastType(weatherEntityId, "twice_daily");
    } else if (!needTwice && this._unsubTwice) {
      this._safeUnsub(this._unsubTwice);
      this._unsubTwice = null;
    }
  }

  _subscribeForecastType(entityId, forecastType) {
    const subPromise = this._hass.connection.subscribeMessage(
      (event) => {
        if (this._subscribedEntityId !== entityId) return;
        this._forecasts[forecastType] = Array.isArray(event?.forecast) ? event.forecast : [];
        this._render();
      },
      {
        type: "weather/subscribe_forecast",
        forecast_type: forecastType,
        entity_id: entityId,
      }
    );

    subPromise.catch(() => {
      if (forecastType === "daily") this._unsubDaily = null;
      if (forecastType === "twice_daily") this._unsubTwice = null;
    });

    if (forecastType === "daily") this._unsubDaily = subPromise;
    else this._unsubTwice = subPromise;
  }

  _safeUnsub(unsubPromise) {
    if (!unsubPromise) return;
    Promise.resolve(unsubPromise)
      .then((unsub) => {
        if (typeof unsub === "function") unsub();
      })
      .catch(() => {});
  }

  _unsubscribeForecasts() {
    this._safeUnsub(this._unsubDaily);
    this._safeUnsub(this._unsubTwice);
    this._unsubDaily = null;
    this._unsubTwice = null;
    this._subscribedEntityId = null;
  }

  _render() {
    if (!this._bodyEl) return;
    const hass = this._hass;
    const cfg = this._config;
    const ctx = this._getContext();
    const weatherEntry = ctx.map["weather.arpav_weather"];
    const wState = weatherEntry?.stateObj;
    const cond = wState && isLiveState(wState) ? wState.state : null;

    // Single --tile-color token driving icon tint, active segment, and focus ring
    const customColor = colorVar(cfg.color);
    const tileColor =
      customColor ||
      (cond
        ? CONDITION_META[cond]?.color || "var(--state-icon-color, #44739e)"
        : "var(--state-inactive-color, #9e9e9e)");
    this.style.setProperty("--tile-color", tileColor);

    this._bodyEl.className = cfg.compact ? "card compact" : "card";

    if (!hass || (!ctx.deviceId && !weatherEntry)) {
      this._bodyEl.innerHTML = `
        <div class="empty">
          <span class="tile-icon">
            <ha-icon icon="mdi:weather-partly-cloudy" aria-hidden="true"></ha-icon>
          </span>
          <div class="tile-info">
            <span class="primary">${escapeHtml(t(hass, "select_device_title"))}</span>
            <span class="secondary">${escapeHtml(t(hass, "select_device_hint"))}</span>
          </div>
        </div>
      `;
      return;
    }

    const blocks = [];
    if (cfg.show_header) blocks.push(this._renderHeader(ctx));
    if (cfg.show_alerts) {
      const html = this._renderAlerts(ctx);
      if (html) blocks.push(html);
    }
    if (cfg.show_metrics) {
      const html = this._renderMetrics(ctx);
      if (html) blocks.push(html);
    }
    if (cfg.show_forecast && weatherEntry) {
      blocks.push(this._renderForecast(ctx));
    }
    if (cfg.show_radar) {
      const html = this._renderRadar(ctx);
      if (html) blocks.push(html);
    }
    if (cfg.show_bulletin) {
      const html = this._renderBulletin(ctx);
      if (html) blocks.push(html);
    }
    if (cfg.show_air_quality) {
      const html = this._renderAirQuality(ctx);
      if (html) blocks.push(html);
    }
    if (cfg.show_pollen) {
      const html = this._renderPollen(ctx);
      if (html) blocks.push(html);
    }
    if (cfg.show_hydrology) {
      const html = this._renderHydrology(ctx);
      if (html) blocks.push(html);
    }
    if (cfg.show_avalanche) {
      const html = this._renderAvalanche(ctx);
      if (html) blocks.push(html);
    }

    this._bodyEl.innerHTML = blocks.join("");
  }

  _renderHeader(ctx) {
    const hass = this._hass;
    const cfg = this._config;
    const weatherEntry = ctx.map["weather.arpav_weather"];
    const wState = weatherEntry?.stateObj;
    const tempSensor = ctx.map["sensor.temperature"]?.stateObj;
    const min24 = numericState(ctx.map["sensor.temperature_min_24h"]?.stateObj);
    const max24 = numericState(ctx.map["sensor.temperature_max_24h"]?.stateObj);
    const apparent =
      numericState(ctx.map["sensor.apparent_temperature"]?.stateObj) ??
      (typeof wState?.attributes?.apparent_temperature === "number"
        ? wState.attributes.apparent_temperature
        : undefined);

    const condition = wState && isLiveState(wState) ? wState.state : null;
    const meta = CONDITION_META[condition] || { icon: "mdi:weather-partly-cloudy" };

    const rawName =
      cfg.name ||
      wState?.attributes?.station_name ||
      ctx.device?.name_by_user ||
      ctx.device?.name ||
      t(hass, "select_device_title");
    const displayName = String(rawName).replace(/^ARPA Veneto\s*-\s*/i, "");

    const condLabel =
      wState && isLiveState(wState) ? formatState(hass, wState) : t(hass, "device_unavailable");
    const zoneName = wState?.attributes?.zone_name || ctx.device?.model || "";
    const observedTime = formatTime(hass, wState?.attributes?.observed_at);

    const tempVal =
      typeof wState?.attributes?.temperature === "number"
        ? wState.attributes.temperature
        : numericState(tempSensor);
    const tempUnit =
      wState?.attributes?.temperature_unit ||
      tempSensor?.attributes?.unit_of_measurement ||
      "°C";

    const secondaryParts = [condLabel, zoneName].filter(Boolean);
    const rangeParts = [];
    if (min24 !== undefined && max24 !== undefined) {
      rangeParts.push(
        `${t(hass, "min_short")} ${formatNumber(hass, min24, 1)}° - ${t(hass, "max_short")} ${formatNumber(hass, max24, 1)}°`
      );
    }
    if (apparent !== undefined && !cfg.compact) {
      rangeParts.push(`${t(hass, "feels_like")} ${formatNumber(hass, apparent, 1)}°`);
    }

    const targetEntity = weatherEntry?.entityId || ctx.map["sensor.temperature"]?.entityId || "";

    return `
      <button type="button" class="tile" data-action="more-info" data-entity-id="${escapeHtml(targetEntity)}">
        <span class="tile-icon">
          <ha-icon icon="${escapeHtml(meta.icon)}" aria-hidden="true"></ha-icon>
        </span>
        <span class="tile-info">
          <span class="primary">${escapeHtml(displayName)}</span>
          <span class="secondary">${escapeHtml(secondaryParts.join(" - "))}</span>
          ${rangeParts.length ? `<span class="secondary">${escapeHtml(rangeParts.join(" - "))}</span>` : ""}
        </span>
        <span class="tile-value">
          <span class="value">
            <span class="number">${escapeHtml(tempVal !== undefined ? formatNumber(hass, tempVal, 1) : "-")}</span>
            ${tempVal !== undefined ? `<span class="unit">${escapeHtml(tempUnit)}</span>` : ""}
          </span>
          ${observedTime ? `<span class="tile-time">${escapeHtml(observedTime)}</span>` : ""}
        </span>
      </button>
    `;
  }

  _renderAlerts(ctx) {
    const hass = this._hass;
    const alerts = [];

    const wAlert = ctx.map["binary_sensor.weather_alert"];
    if (wAlert?.stateObj?.state === "on") {
      const attrs = wAlert.stateObj.attributes || {};
      const desc = [attrs.alert, attrs.special_phenomena].filter(Boolean).join(" - ");
      alerts.push({
        kind: "warning",
        icon: "mdi:alert-octagon",
        title: t(hass, "alert_weather"),
        desc,
        action: ctx.map["sensor.bulletin_summary"] ? "open-bulletin" : "more-info",
        entityId: wAlert.entityId,
      });
    }

    const pm10Alert = ctx.map["binary_sensor.pm10_exceedance"];
    if (pm10Alert?.stateObj?.state === "on") {
      const attrs = pm10Alert.stateObj.attributes || {};
      const desc =
        attrs.pm10_daily != null
          ? `${formatNumber(hass, attrs.pm10_daily, 1)} µg/m³ (${t(hass, "aq_limit")} ${attrs.limit_ug_m3 || 50})`
          : "";
      alerts.push({
        kind: "error",
        icon: "mdi:smog",
        title: t(hass, "alert_pm10"),
        desc,
        action: "more-info",
        entityId: pm10Alert.entityId,
      });
    }

    const o3Alert = ctx.map["binary_sensor.ozone_exceedance"];
    if (o3Alert?.stateObj?.state === "on") {
      const attrs = o3Alert.stateObj.attributes || {};
      const desc =
        attrs.ozone_hourly != null
          ? `${formatNumber(hass, attrs.ozone_hourly, 1)} µg/m³ (${t(hass, "aq_threshold")} ${attrs.threshold_ug_m3 || 180})`
          : "";
      alerts.push({
        kind: "error",
        icon: "mdi:alert-circle",
        title: t(hass, "alert_ozone"),
        desc,
        action: "more-info",
        entityId: o3Alert.entityId,
      });
    }

    if (!alerts.length) return "";

    return `
      <div class="alerts">
        ${alerts
          .map(
            (a) => `
          <button
            type="button"
            class="alert ${escapeHtml(a.kind)}"
            data-action="${escapeHtml(a.action)}"
            data-entity-id="${escapeHtml(a.entityId)}"
          >
            <ha-icon icon="${escapeHtml(a.icon)}" aria-hidden="true"></ha-icon>
            <span class="text">
              <span class="title">${escapeHtml(a.title)}</span>
              ${a.desc ? `<span class="desc">${escapeHtml(a.desc)}</span>` : ""}
            </span>
            <ha-icon class="alert-chevron" icon="mdi:chevron-right" aria-hidden="true"></ha-icon>
          </button>
        `
          )
          .join("")}
      </div>
    `;
  }

  _renderMetrics(ctx) {
    const hass = this._hass;
    const cfg = this._config;
    const items = [];
    const addMetric = (entityId, icon, label, value, sub = "") => {
      items.push({ entityId, icon, label, value, sub });
    };

    const wEntry = ctx.map["weather.arpav_weather"];
    const wAttrs = wEntry?.stateObj?.attributes || {};

    if (cfg.show_metric_humidity) {
      const hum = ctx.map["sensor.humidity"];
      if (hum && isLiveState(hum.stateObj)) {
        addMetric(hum.entityId, "mdi:water-percent", t(hass, "metric_humidity"), formatState(hass, hum.stateObj));
      } else if (typeof wAttrs.humidity === "number") {
        addMetric(wEntry.entityId, "mdi:water-percent", t(hass, "metric_humidity"), `${formatNumber(hass, wAttrs.humidity, 0)}%`);
      }
    }

    if (cfg.show_metric_wind) {
      const wind = ctx.map["sensor.wind_speed"];
      const bearing = ctx.map["sensor.wind_bearing"];
      const gust = ctx.map["sensor.wind_gust_24h"];
      if (wind && isLiveState(wind.stateObj)) {
        const cardinal = bearing?.stateObj?.attributes?.cardinal || "";
        const subParts = [];
        if (cardinal) subParts.push(cardinal);
        if (gust && isLiveState(gust.stateObj)) {
          subParts.push(`${t(hass, "metric_gust")} ${formatState(hass, gust.stateObj)}`);
        }
        addMetric(wind.entityId, "mdi:weather-windy", t(hass, "metric_wind"), formatState(hass, wind.stateObj), subParts.join(" - "));
      }
    }

    if (cfg.show_metric_precipitation) {
      const rainToday = ctx.map["sensor.precipitation_today"];
      const rainRate = ctx.map["sensor.precipitation_intensity"];
      const rainProb = ctx.map["sensor.precipitation_probability"];
      if (rainToday && isLiveState(rainToday.stateObj)) {
        const subParts = [];
        const rateVal = numericState(rainRate?.stateObj);
        if (rateVal !== undefined && rateVal > 0) subParts.push(formatState(hass, rainRate.stateObj));
        if (rainProb && isLiveState(rainProb.stateObj)) subParts.push(formatState(hass, rainProb.stateObj));
        addMetric(rainToday.entityId, "mdi:weather-rainy", t(hass, "metric_rain"), formatState(hass, rainToday.stateObj), subParts.join(" - "));
      } else if (rainProb && isLiveState(rainProb.stateObj)) {
        addMetric(rainProb.entityId, "mdi:weather-rainy", t(hass, "metric_rain_prob"), formatState(hass, rainProb.stateObj));
      }
    }

    if (cfg.show_metric_pressure) {
      const press = ctx.map["sensor.pressure"];
      if (press && isLiveState(press.stateObj)) {
        addMetric(press.entityId, "mdi:gauge", t(hass, "metric_pressure"), formatState(hass, press.stateObj));
      }
    }

    if (cfg.show_metric_dew_point) {
      const dp = ctx.map["sensor.dew_point"];
      if (dp && isLiveState(dp.stateObj)) {
        addMetric(dp.entityId, "mdi:thermometer-water", t(hass, "metric_dew_point"), formatState(hass, dp.stateObj));
      }
    }

    if (cfg.show_metric_solar_uv) {
      const solar = ctx.map["sensor.solar_radiation"];
      const uv = ctx.map["sensor.uv_index"];
      if (solar && isLiveState(solar.stateObj)) {
        const sub =
          uv && isLiveState(uv.stateObj)
            ? `${t(hass, "metric_uv")} ${formatNumber(hass, numericState(uv.stateObj), 1)}`
            : "";
        addMetric(solar.entityId, "mdi:white-balance-sunny", t(hass, "metric_solar"), formatState(hass, solar.stateObj), sub);
      } else if (uv && isLiveState(uv.stateObj)) {
        addMetric(uv.entityId, "mdi:sun-wireless", t(hass, "metric_uv"), formatNumber(hass, numericState(uv.stateObj), 1));
      }
    }

    if (cfg.show_metric_visibility) {
      const vis = ctx.map["sensor.visibility"];
      if (vis && isLiveState(vis.stateObj)) {
        addMetric(vis.entityId, "mdi:eye", t(hass, "metric_visibility"), formatState(hass, vis.stateObj));
      }
    }

    if (cfg.show_metric_snow) {
      const snowDepth = ctx.map["sensor.snow_depth"];
      const snowLine = ctx.map["sensor.snow_line"];
      const altBits = [];
      if (wAttrs.temperature_1500m) altBits.push(`1500m ${wAttrs.temperature_1500m}°`);
      if (wAttrs.temperature_2000m) altBits.push(`2000m ${wAttrs.temperature_2000m}°`);
      if (wAttrs.temperature_3000m) altBits.push(`3000m ${wAttrs.temperature_3000m}°`);

      if (snowDepth && isLiveState(snowDepth.stateObj)) {
        const sub = snowLine && isLiveState(snowLine.stateObj) ? snowLine.stateObj.state : "";
        addMetric(snowDepth.entityId, "mdi:snowflake", t(hass, "metric_snow"), formatState(hass, snowDepth.stateObj), sub);
      } else if (snowLine && isLiveState(snowLine.stateObj)) {
        addMetric(snowLine.entityId, "mdi:elevation-rise", t(hass, "metric_snow_line"), snowLine.stateObj.state);
      }
      if (altBits.length && wEntry) {
        addMetric(wEntry.entityId, "mdi:elevation-rise", t(hass, "altitude_temps"), altBits[0], altBits.slice(1).join(" - "));
      }
    }

    if (cfg.show_metric_leaf_wetness) {
      const leaf = ctx.map["sensor.leaf_wetness"];
      if (leaf && isLiveState(leaf.stateObj)) {
        addMetric(leaf.entityId, "mdi:leaf", t(hass, "metric_leaf"), formatState(hass, leaf.stateObj));
      }
    }

    if (!items.length) return "";

    const colsClass = items.length <= 3 ? ` cols-${items.length}` : "";

    return `
      <div class="metrics-grid${colsClass}">
        ${items
          .map(
            (m) => `
          <button type="button" class="metric-card" data-action="more-info" data-entity-id="${escapeHtml(m.entityId)}">
            <ha-icon icon="${escapeHtml(m.icon)}" aria-hidden="true"></ha-icon>
            <span class="metric-info">
              <span class="metric-label">${escapeHtml(m.label)}</span>
              <span class="metric-value">${escapeHtml(m.value)}</span>
              ${m.sub ? `<span class="metric-sub">${escapeHtml(m.sub)}</span>` : ""}
            </span>
          </button>
        `
          )
          .join("")}
      </div>
    `;
  }

  _renderForecast(ctx) {
    const hass = this._hass;
    const cfg = this._config;
    const weatherEntry = ctx.map["weather.arpav_weather"];
    const weatherEntityId = weatherEntry?.entityId || "";

    const mode =
      cfg.forecast_type === "both"
        ? this._activeForecastMode
        : cfg.forecast_type === "twice_daily"
          ? "twice_daily"
          : "daily";

    const rawItems = this._forecasts[mode];
    const maxCount =
      mode === "twice_daily"
        ? Math.max(4, Math.min(14, Number(cfg.forecast_days || 5) * 2))
        : Math.max(2, Math.min(7, Number(cfg.forecast_days || 5)));

    let contentHtml = "";
    if (rawItems === null) {
      contentHtml = `<div class="fc-placeholder">${escapeHtml(t(hass, "forecast_loading"))}</div>`;
    } else if (!rawItems.length) {
      contentHtml = `<div class="fc-placeholder">${escapeHtml(t(hass, "forecast_empty"))}</div>`;
    } else {
      const items = rawItems.slice(0, maxCount);
      contentHtml = `
        <div class="forecast-strip">
          ${items
            .map((fc) => {
              const cMeta = CONDITION_META[fc.condition] || { icon: "mdi:weather-partly-cloudy" };
              const dayLabel = formatShortDay(hass, fc.datetime);
              const periodLabel =
                mode === "twice_daily"
                  ? fc.is_daytime
                    ? t(hass, "forecast_afternoon")
                    : t(hass, "forecast_morning")
                  : "";
              const high =
                typeof fc.temperature === "number" ? `${formatNumber(hass, fc.temperature, 0)}°` : "-";
              const low =
                typeof fc.templow === "number" ? `${formatNumber(hass, fc.templow, 0)}°` : "";
              const prob =
                typeof fc.precipitation_probability === "number" && fc.precipitation_probability > 0
                  ? `${fc.precipitation_probability}%`
                  : "";

              return `
                <button
                  type="button"
                  class="forecast-col"
                  data-action="more-info"
                  data-entity-id="${escapeHtml(weatherEntityId)}"
                >
                  <span class="fc-day">
                    ${escapeHtml(dayLabel)}
                    ${periodLabel ? `<span class="fc-period">${escapeHtml(periodLabel)}</span>` : ""}
                  </span>
                  <ha-icon class="fc-icon" icon="${escapeHtml(cMeta.icon)}" aria-hidden="true"></ha-icon>
                  <span class="fc-high">${escapeHtml(high)}</span>
                  ${low ? `<span class="fc-low">${escapeHtml(low)}</span>` : ""}
                  <span class="fc-prob">${escapeHtml(prob)}</span>
                </button>
              `;
            })
            .join("")}
        </div>
      `;
    }

    const switcherHtml =
      cfg.forecast_type === "both"
        ? `
          <div class="segmented" role="group" aria-label="${escapeHtml(t(hass, "section_forecast"))}">
            <button type="button" class="option${mode === "daily" ? " selected" : ""}" data-action="set-forecast-mode" data-mode="daily" aria-pressed="${mode === "daily" ? "true" : "false"}">
              <span>${escapeHtml(t(hass, "forecast_daily"))}</span>
            </button>
            <button type="button" class="option${mode === "twice_daily" ? " selected" : ""}" data-action="set-forecast-mode" data-mode="twice_daily" aria-pressed="${mode === "twice_daily" ? "true" : "false"}">
              <span>${escapeHtml(t(hass, "forecast_twice_daily"))}</span>
            </button>
          </div>
        `
        : "";

    return `
      <div class="block">
        ${switcherHtml}
        ${contentHtml}
      </div>
    `;
  }

  _renderRadar(ctx) {
    const hass = this._hass;
    const radarEntry = ctx.map["image.radar"];
    if (!radarEntry || !isLiveState(radarEntry.stateObj)) return "";
    const attrs = radarEntry.stateObj.attributes || {};
    const rawImgSrc = attrs.entity_picture;
    if (!rawImgSrc) return "";

    const imgSrc = this._buildRadarSrc(rawImgSrc, radarEntry.stateObj.state);
    const sourceKey =
      attrs.radar_source === "teolo"
        ? "radar_teolo"
        : attrs.radar_source === "concordia"
          ? "radar_concordia"
          : "radar_mosaic";
    const sourceLabel = t(hass, sourceKey);
    const updatedTime = formatTime(hass, radarEntry.stateObj.state);
    const mosaicDarkCls = hass?.themes?.darkMode && sourceKey === "radar_mosaic" ? " dark-mosaic" : "";

    if (this._radarCollapsed) {
      return `
        <div class="block">
          <button type="button" class="feature-row" data-action="toggle-radar" aria-expanded="false">
            <ha-icon class="feature-icon" icon="mdi:radar" aria-hidden="true"></ha-icon>
            <span class="feature-text">
              <span class="primary">${escapeHtml(t(hass, "section_radar"))}</span>
              <span class="secondary">${escapeHtml([sourceLabel, updatedTime].filter(Boolean).join(" - "))}</span>
            </span>
            <ha-icon class="feature-chevron" icon="mdi:chevron-down" aria-hidden="true"></ha-icon>
          </button>
        </div>
      `;
    }

    return `
      <div class="block">
        <div class="block-head">
          <h2 class="block-title">${escapeHtml(t(hass, "section_radar"))}</h2>
          <button type="button" class="inline-action" data-action="toggle-radar" aria-expanded="true">
            <span>${escapeHtml(t(hass, "radar_hide"))}</span>
            <ha-icon icon="mdi:chevron-up" aria-hidden="true"></ha-icon>
          </button>
        </div>
        <button
          type="button"
          class="radar-frame"
          data-action="open-radar"
          data-entity-id="${escapeHtml(radarEntry.entityId)}"
          aria-label="${escapeHtml(t(hass, "radar_expand"))}"
        >
          <img
            class="radar-img${mosaicDarkCls}"
            src="${escapeHtml(imgSrc)}"
            alt="${escapeHtml(`${t(hass, "radar_alt")} - ${sourceLabel}`)}"
            loading="lazy"
          />
          <span class="radar-scrim">
            <span>${escapeHtml([sourceLabel, updatedTime].filter(Boolean).join(" - "))}</span>
            <ha-icon icon="mdi:arrow-expand-all" aria-hidden="true"></ha-icon>
          </span>
        </button>
      </div>
    `;
  }

  _renderBulletin(ctx) {
    const hass = this._hass;
    const bulEntry = ctx.map["sensor.bulletin_summary"];
    if (!bulEntry || !isLiveState(bulEntry.stateObj)) return "";
    const attrs = bulEntry.stateObj.attributes || {};
    const preview = attrs.general_evolution || attrs.alert || bulEntry.stateObj.state || "";
    if (!preview) return "";

    const code = attrs.bulletin_code || "";
    const issued = formatTime(hass, attrs.updated_at || attrs.issued_at);
    const meta = [t(hass, "section_bulletin"), code, issued].filter(Boolean).join(" - ");

    return `
      <div class="block">
        <button
          type="button"
          class="feature-row"
          data-action="open-bulletin"
          data-entity-id="${escapeHtml(bulEntry.entityId)}"
        >
          <ha-icon class="feature-icon" icon="mdi:text-box-outline" aria-hidden="true"></ha-icon>
          <span class="feature-text">
            <span class="primary">${escapeHtml(meta)}</span>
            <span class="bulletin-preview">${escapeHtml(preview)}</span>
          </span>
          <ha-icon class="feature-chevron" icon="mdi:chevron-right" aria-hidden="true"></ha-icon>
        </button>
      </div>
    `;
  }

  _renderAirQuality(ctx) {
    const hass = this._hass;
    const tiles = [];

    const addAq = (kind, name, primary, sub) => {
      const val = numericState(primary.stateObj);
      const tone = airQualityTone(kind, val);
      const pct = val !== undefined ? Math.min(100, Math.round((val / tone.maxScale) * 100)) : 0;
      const limitPct = Math.round((tone.limit / tone.maxScale) * 100);
      tiles.push({
        entityId: primary.entityId,
        name,
        value: formatNumber(hass, val, 1),
        unit: primary.stateObj.attributes?.unit_of_measurement || "µg/m³",
        color: tone.color,
        pct,
        limitPct,
        limitLabel: `${t(hass, kind === "ozone" ? "aq_threshold" : "aq_limit")} ${tone.limit}`,
        sub,
      });
    };

    const pm10Daily = ctx.map["sensor.pm10_daily"];
    const pm10Hourly = ctx.map["sensor.pm10_hourly"];
    if (
      (pm10Daily && isLiveState(pm10Daily.stateObj)) ||
      (pm10Hourly && isLiveState(pm10Hourly.stateObj))
    ) {
      const primary = pm10Daily && isLiveState(pm10Daily.stateObj) ? pm10Daily : pm10Hourly;
      const sub =
        primary === pm10Daily && pm10Hourly && isLiveState(pm10Hourly.stateObj)
          ? `${t(hass, "aq_hourly")} ${formatNumber(hass, numericState(pm10Hourly.stateObj), 1)}`
          : primary.stateObj.attributes?.source_name || "";
      addAq("pm10", "PM10", primary, sub);
    }

    const pm25Daily = ctx.map["sensor.pm25_daily"];
    const pm25Hourly = ctx.map["sensor.pm25_hourly"];
    if (
      (pm25Daily && isLiveState(pm25Daily.stateObj)) ||
      (pm25Hourly && isLiveState(pm25Hourly.stateObj))
    ) {
      const primary = pm25Daily && isLiveState(pm25Daily.stateObj) ? pm25Daily : pm25Hourly;
      const sub =
        primary === pm25Daily && pm25Hourly && isLiveState(pm25Hourly.stateObj)
          ? `${t(hass, "aq_hourly")} ${formatNumber(hass, numericState(pm25Hourly.stateObj), 1)}`
          : primary.stateObj.attributes?.source_name || "";
      addAq("pm25", "PM2.5", primary, sub);
    }

    const o3 = ctx.map["sensor.ozone"];
    if (o3 && isLiveState(o3.stateObj)) {
      const maxDay = o3.stateObj.attributes?.daily_max;
      const sub =
        typeof maxDay === "number"
          ? `${t(hass, "aq_daily_max")} ${formatNumber(hass, maxDay, 1)}`
          : o3.stateObj.attributes?.source_name || "";
      addAq("ozone", "O3", o3, sub);
    }

    if (!tiles.length) return "";

    return `
      <div class="block">
        <div class="block-head">
          <h2 class="block-title">${escapeHtml(t(hass, "section_air_quality"))}</h2>
        </div>
        <div class="aq-grid">
          ${tiles
            .map(
              (c) => `
            <button
              type="button"
              class="aq-tile"
              data-action="more-info"
              data-entity-id="${escapeHtml(c.entityId)}"
            >
              <span class="aq-top">
                <span class="aq-name">${escapeHtml(c.name)}</span>
                <span class="aq-limit">${escapeHtml(c.limitLabel)}</span>
              </span>
              <span class="aq-reading">
                <span class="aq-val">${escapeHtml(c.value)}</span>
                <span class="aq-unit">${escapeHtml(c.unit)}</span>
              </span>
              <span class="aq-bar" aria-hidden="true">
                <span class="aq-bar-fill" style="--bar-color: ${escapeHtml(c.color)}; --bar-pct: ${c.pct}%;"></span>
                <span class="aq-bar-limit" style="--limit-pct: ${c.limitPct}%;"></span>
              </span>
              ${c.sub ? `<span class="secondary">${escapeHtml(c.sub)}</span>` : ""}
            </button>
          `
            )
            .join("")}
        </div>
      </div>
    `;
  }

  _renderPollen(ctx) {
    const hass = this._hass;
    const pollenEntry = ctx.map["sensor.pollen_risk"];
    if (!pollenEntry || !isLiveState(pollenEntry.stateObj)) return "";

    const level = pollenEntry.stateObj.state;
    const levelColor = POLLEN_LEVEL_COLORS[level] || "var(--secondary-text-color, #727272)";
    const levelLabel = formatState(hass, pollenEntry.stateObj);
    const attrs = pollenEntry.stateObj.attributes || {};
    const speciesMap = attrs.species || {};

    const speciesEntityByName = new Map();
    for (const sp of ctx.pollenSpecies) {
      const spName = sp.stateObj.attributes?.species_name;
      if (spName) speciesEntityByName.set(spName, sp.entityId);
    }

    const speciesList = Object.entries(speciesMap)
      .map(([slug, info]) => ({
        slug,
        name: info.name || slug,
        risk: info.risk || "absent",
        value: typeof info.value === "number" ? info.value : null,
        entityId: speciesEntityByName.get(info.name) || pollenEntry.entityId,
      }))
      .sort((a, b) => {
        const diff = (POLLEN_RANK[b.risk] || 0) - (POLLEN_RANK[a.risk] || 0);
        if (diff !== 0) return diff;
        return (b.value ?? -1) - (a.value ?? -1);
      });

    const activeFirst = speciesList.filter((s) => s.risk !== "absent" || (s.value ?? 0) > 0);
    const displayed = (activeFirst.length ? activeFirst : speciesList).slice(0, 6);
    const subtitle = [attrs.station_name, attrs.period].filter(Boolean).join(" - ");

    return `
      <div class="block">
        <button
          type="button"
          class="feature-row"
          data-action="open-pollen"
          data-entity-id="${escapeHtml(pollenEntry.entityId)}"
        >
          <ha-icon class="feature-icon" icon="mdi:flower-pollen" style="--feature-icon-color: ${escapeHtml(levelColor)};" aria-hidden="true"></ha-icon>
          <span class="feature-text">
            <span class="primary">${escapeHtml(t(hass, "section_pollen"))}</span>
            ${subtitle ? `<span class="secondary">${escapeHtml(subtitle)}</span>` : ""}
          </span>
          <span class="feature-val" style="--feature-val-color: ${escapeHtml(levelColor)};">${escapeHtml(levelLabel)}</span>
          <ha-icon class="feature-chevron" icon="mdi:chevron-right" aria-hidden="true"></ha-icon>
        </button>
        ${
          displayed.length
            ? `
          <div class="badges">
            ${displayed
              .map((sp) => {
                const elevated = sp.risk === "moderate" || sp.risk === "high";
                const dotColor = POLLEN_LEVEL_COLORS[sp.risk] || "var(--secondary-text-color, #727272)";
                const shortName = sp.name.split("(")[0].trim();
                const valText = sp.value !== null ? formatNumber(hass, sp.value, 1) : "";
                return `
                  <button
                    type="button"
                    class="badge"
                    data-action="more-info"
                    data-entity-id="${escapeHtml(sp.entityId)}"
                  >
                    ${elevated ? `<span class="badge-dot" style="--badge-color: ${escapeHtml(dotColor)};" aria-hidden="true"></span>` : ""}
                    <span class="badge-info">
                      <span class="content">${escapeHtml(shortName)}${valText ? ` - ${escapeHtml(valText)}` : ""}</span>
                    </span>
                  </button>
                `;
              })
              .join("")}
          </div>
        `
            : ""
        }
      </div>
    `;
  }

  _renderHydrology(ctx) {
    const hass = this._hass;
    const levelEntry = ctx.map["sensor.river_level"];
    const dischargeEntry = ctx.map["sensor.river_discharge"];
    const hasLevel = levelEntry && isLiveState(levelEntry.stateObj);
    const hasDischarge = dischargeEntry && isLiveState(dischargeEntry.stateObj);
    if (!hasLevel && !hasDischarge) return "";

    const rows = [];
    if (hasLevel) {
      const attrs = levelEntry.stateObj.attributes || {};
      const trend = hydroTrendMeta(attrs.trend);
      const stationLabel = attrs.hydro_station_name || t(hass, "hydro_level");
      rows.push(`
        <button
          type="button"
          class="feature-row"
          data-action="more-info"
          data-entity-id="${escapeHtml(levelEntry.entityId)}"
        >
          <ha-icon class="feature-icon" icon="mdi:waves-arrow-up" aria-hidden="true"></ha-icon>
          <span class="feature-text">
            <span class="primary">${escapeHtml(stationLabel)}</span>
            <span class="trend-inline" style="--trend-color: ${escapeHtml(trend.color)};">
              <ha-icon icon="${escapeHtml(trend.icon)}" aria-hidden="true"></ha-icon>
              <span>${escapeHtml(t(hass, trend.labelKey))}</span>
            </span>
          </span>
          <span class="feature-val">${escapeHtml(formatState(hass, levelEntry.stateObj))}</span>
        </button>
      `);
    }

    if (hasDischarge) {
      rows.push(`
        <button
          type="button"
          class="feature-row"
          data-action="more-info"
          data-entity-id="${escapeHtml(dischargeEntry.entityId)}"
        >
          <ha-icon class="feature-icon" icon="mdi:water-pump" aria-hidden="true"></ha-icon>
          <span class="feature-text">
            <span class="primary">${escapeHtml(t(hass, "hydro_discharge"))}</span>
            <span class="secondary">${escapeHtml(t(hass, "section_hydrology"))}</span>
          </span>
          <span class="feature-val">${escapeHtml(formatState(hass, dischargeEntry.stateObj))}</span>
        </button>
      `);
    }

    return `
      <div class="block">
        <div class="feature-grid">${rows.join("")}</div>
      </div>
    `;
  }

  _renderAvalanche(ctx) {
    const hass = this._hass;
    const areas = [
      { key: "avalanche_dolomiti", entry: ctx.map["sensor.avalanche_dolomiti"] },
      { key: "avalanche_prealpi", entry: ctx.map["sensor.avalanche_prealpi"] },
    ].filter((a) => a.entry && isLiveState(a.entry.stateObj));

    if (!areas.length) return "";

    return `
      <div class="block">
        <div class="block-head">
          <h2 class="block-title">${escapeHtml(t(hass, "section_avalanche"))}</h2>
        </div>
        <div class="feature-grid">
          ${areas
            .map(({ key, entry }) => {
              const avMeta = AVALANCHE_LEVEL_META[entry.stateObj.state] || AVALANCHE_LEVEL_META.not_issued;
              const segs = [1, 2, 3, 4, 5]
                .map(
                  (i) =>
                    `<span class="av-seg${i <= avMeta.level ? " filled" : ""}" style="--av-color: ${escapeHtml(avMeta.color)};"></span>`
                )
                .join("");
              return `
                <button
                  type="button"
                  class="av-tile"
                  data-action="open-avalanche"
                  data-entity-id="${escapeHtml(entry.entityId)}"
                >
                  <span class="av-head">
                    <span class="primary">${escapeHtml(t(hass, key))}</span>
                    <span class="secondary">${escapeHtml(formatState(hass, entry.stateObj))}</span>
                  </span>
                  <span class="av-scale" aria-hidden="true">${segs}</span>
                </button>
              `;
            })
            .join("")}
        </div>
      </div>
    `;
  }

  _handleBodyClick(ev) {
    const btn = ev.target.closest("button[data-action]");
    if (!btn) return;
    const action = btn.dataset.action;
    const entityId = btn.dataset.entityId;

    if (action === "more-info" && entityId) {
      this._openMoreInfo(entityId);
    } else if (action === "set-forecast-mode") {
      const next = btn.dataset.mode;
      if ((next === "daily" || next === "twice_daily") && next !== this._activeForecastMode) {
        this._activeForecastMode = next;
        this._render();
      }
    } else if (action === "toggle-radar") {
      this._radarCollapsed = !this._radarCollapsed;
      this._render();
    } else if (action === "open-radar") {
      this._openRadarDialog();
    } else if (action === "open-bulletin") {
      this._openBulletinDialog();
    } else if (action === "open-pollen") {
      this._openPollenDialog();
    } else if (action === "open-avalanche") {
      this._openAvalancheDialog(entityId);
    }
  }

  _openMoreInfo(entityId) {
    if (!entityId) return;
    fireEvent(this, "hass-more-info", { entityId });
  }

  _showDialog(title, contentHtml, moreInfoEntityId) {
    if (!this._dialogEl) return;
    const hass = this._hass;
    const titleEl = this._dialogEl.querySelector(".dialog-title");
    const closeEl = this._dialogEl.querySelector(".dialog-close");
    const contentEl = this._dialogEl.querySelector(".dialog-content");
    const footerEl = this._dialogEl.querySelector(".dialog-footer");

    titleEl.textContent = title;
    closeEl.setAttribute("aria-label", t(hass, "close"));
    contentEl.innerHTML = contentHtml;
    footerEl.innerHTML = moreInfoEntityId
      ? `
        <button type="button" class="button tonal" data-action="more-info" data-entity-id="${escapeHtml(moreInfoEntityId)}">
          <ha-icon icon="mdi:open-in-new" aria-hidden="true"></ha-icon>
          <span>${escapeHtml(t(hass, "open_more_info"))}</span>
        </button>
      `
      : "";

    if (!this._dialogEl.open) {
      this._dialogEl.showModal();
    }
  }

  _buildRadarSrc(rawUrl, stateVersion) {
    if (!rawUrl) return "";
    let url = rawUrl;
    if (typeof this._hass?.hassUrl === "function" && url.startsWith("/")) {
      url = this._hass.hassUrl(url);
    }
    if (url.startsWith("data:") || !stateVersion) return url;
    const sep = url.includes("?") ? "&" : "?";
    return `${url}${sep}v=${encodeURIComponent(stateVersion)}`;
  }

  _openRadarDialog() {
    const ctx = this._getContext();
    const radarEntry = ctx.map["image.radar"];
    if (!radarEntry) return;
    const attrs = radarEntry.stateObj.attributes || {};
    const imgSrc = this._buildRadarSrc(attrs.entity_picture, radarEntry.stateObj.state);
    if (!imgSrc) return;

    const sourceKey =
      attrs.radar_source === "teolo"
        ? "radar_teolo"
        : attrs.radar_source === "concordia"
          ? "radar_concordia"
          : "radar_mosaic";
    const title = `${t(this._hass, "section_radar")} - ${t(this._hass, sourceKey)}`;
    const mosaicDarkCls = this._hass?.themes?.darkMode && sourceKey === "radar_mosaic" ? " dark-mosaic" : "";
    const html = `<img class="dialog-radar-img${mosaicDarkCls}" src="${escapeHtml(imgSrc)}" alt="${escapeHtml(title)}" />`;
    this._showDialog(title, html, radarEntry.entityId);
  }

  _openBulletinDialog() {
    const hass = this._hass;
    const ctx = this._getContext();
    const bulEntry = ctx.map["sensor.bulletin_summary"];
    if (!bulEntry) return;
    const attrs = bulEntry.stateObj.attributes || {};
    const blocks = [];

    const alertText = [attrs.alert, attrs.special_phenomena].filter(Boolean).join("\n");
    if (alertText) {
      blocks.push(`
        <div class="alert warning">
          <ha-icon icon="mdi:alert-octagon" aria-hidden="true"></ha-icon>
          <div class="text">
            <span class="title">${escapeHtml(t(hass, "bulletin_alert"))}</span>
            <p class="dialog-block">${escapeHtml(alertText)}</p>
          </div>
        </div>
      `);
    }

    if (attrs.general_evolution) {
      blocks.push(`
        <div>
          <h2 class="dialog-section-title">${escapeHtml(t(hass, "bulletin_general"))}</h2>
          <p class="dialog-block">${escapeHtml(attrs.general_evolution)}</p>
        </div>
      `);
    }

    const days = Array.isArray(attrs.daily_forecasts) ? attrs.daily_forecasts : [];
    if (days.length) {
      blocks.push(`
        <div>
          <h2 class="dialog-section-title">${escapeHtml(t(hass, "bulletin_daily"))}</h2>
          <div class="features">
            ${days
              .map(
                (d) => `
              <div class="dialog-day">
                <div class="dialog-day-head">
                  <span>${escapeHtml(formatLongDate(hass, d.date))}</span>
                  ${d.reliability ? `<span class="secondary">${escapeHtml(t(hass, "bulletin_reliability"))}: ${escapeHtml(d.reliability)}</span>` : ""}
                </div>
                <p class="dialog-block">${escapeHtml(d.text)}</p>
              </div>
            `
              )
              .join("")}
          </div>
        </div>
      `);
    }

    const code = attrs.bulletin_code ? ` (${attrs.bulletin_code})` : "";
    this._showDialog(`${t(hass, "section_bulletin")}${code}`, blocks.join(""), bulEntry.entityId);
  }

  _openPollenDialog() {
    const hass = this._hass;
    const ctx = this._getContext();
    const pollenEntry = ctx.map["sensor.pollen_risk"];
    if (!pollenEntry) return;
    const attrs = pollenEntry.stateObj.attributes || {};
    const species = Object.values(attrs.species || {}).sort(
      (a, b) => (POLLEN_RANK[b.risk] || 0) - (POLLEN_RANK[a.risk] || 0)
    );

    const rowsHtml = species
      .map((sp) => {
        const dotColor = POLLEN_LEVEL_COLORS[sp.risk] || "var(--disabled-color, #bdbdbd)";
        const val =
          typeof sp.value === "number" ? `${formatNumber(hass, sp.value, 1)} granuli/m³` : "-";
        return `
          <tr>
            <td>${escapeHtml(sp.name || "")}</td>
            <td><span class="dialog-dot" style="--dot-color: ${escapeHtml(dotColor)};"></span>${escapeHtml(sp.risk_label || t(hass, `pollen_${sp.risk}`))}</td>
            <td style="font-variant-numeric: tabular-nums;">${escapeHtml(val)}</td>
          </tr>
        `;
      })
      .join("");

    const commentHtml = attrs.comment
      ? `
        <div>
          <h2 class="dialog-section-title">${escapeHtml(t(hass, "pollen_comment"))}</h2>
          <p class="dialog-block">${escapeHtml(attrs.comment)}</p>
        </div>
      `
      : "";

    const meta = [attrs.station_name, attrs.period].filter(Boolean).join(" - ");
    const html = `
      ${meta ? `<p class="dialog-block secondary">${escapeHtml(meta)}</p>` : ""}
      ${
        rowsHtml
          ? `
        <table class="dialog-table">
          <thead>
            <tr>
              <th scope="col">${escapeHtml(t(hass, "pollen_details"))}</th>
              <th scope="col">${escapeHtml(t(hass, "section_pollen"))}</th>
              <th scope="col">granuli/m³</th>
            </tr>
          </thead>
          <tbody>${rowsHtml}</tbody>
        </table>
      `
          : ""
      }
      ${commentHtml}
    `;
    this._showDialog(t(hass, "section_pollen"), html, pollenEntry.entityId);
  }

  _openAvalancheDialog(preferredEntityId) {
    const hass = this._hass;
    const ctx = this._getContext();
    const entry =
      (preferredEntityId &&
        Object.values(ctx.map).find((e) => e.entityId === preferredEntityId)) ||
      ctx.map["sensor.avalanche_dolomiti"] ||
      ctx.map["sensor.avalanche_prealpi"];
    if (!entry) return;
    const attrs = entry.stateObj.attributes || {};
    const blocks = [];

    const addBlock = (titleKey, text) => {
      if (!text) return;
      blocks.push(`
        <div>
          <h2 class="dialog-section-title">${escapeHtml(t(hass, titleKey))}</h2>
          <p class="dialog-block">${escapeHtml(text)}</p>
        </div>
      `);
    };

    addBlock("avalanche_fresh_snow", attrs.fresh_snow);
    addBlock("avalanche_locations", attrs.dangerous_locations);
    addBlock("avalanche_situation", attrs.situation);
    addBlock("avalanche_forecast", attrs.forecast);
    addBlock("avalanche_guidance", attrs.guidance);

    this._showDialog(
      `${t(hass, "section_avalanche")} - ${formatState(hass, entry.stateObj)}`,
      blocks.join("") || `<p class="dialog-block">${escapeHtml(formatState(hass, entry.stateObj))}</p>`,
      entry.entityId
    );
  }
}

/**
 * Ensure Home Assistant's ha-form custom element is loaded before rendering
 * the visual editor (card-api.md section 4).
 */
async function loadHaForm() {
  if (window.customElements.get("ha-form")) return;
  const helpers = await window.loadCardHelpers?.();
  const card = await helpers?.createCardElement({ type: "entities", entities: [] });
  await card?.constructor?.getConfigElement?.();
}

/**
 * Native Home Assistant ha-form visual editor for ARPA Veneto Meteo Card.
 */
class ArpaVenetoMeteoCardEditor extends HTMLElement {
  constructor() {
    super();
    this._config = null;
    this._hass = null;
    this._form = null;
    this._lastLang = null;
  }

  setConfig(config) {
    this._config = { ...(config || {}) };
    this._render();
  }

  set hass(hass) {
    const prevLang = this._lastLang;
    this._hass = hass;
    const nextLang = hass?.locale?.language || hass?.language || "en";
    if (!this._form || prevLang !== nextLang) {
      this._lastLang = nextLang;
      this._render();
    } else {
      this._form.hass = hass;
    }
  }

  get hass() {
    return this._hass;
  }

  connectedCallback() {
    loadHaForm()
      .then(() => window.customElements.whenDefined("ha-form"))
      .then(() => this._render())
      .catch(() => {});
  }

  _buildSchema(hass) {
    return [
      {
        name: "device_id",
        required: true,
        selector: { device: { filter: { integration: DOMAIN } } },
      },
      {
        type: "grid",
        name: "",
        schema: [
          { name: "name", selector: { text: {} } },
          { name: "color", selector: { ui_color: { include_none: true } } },
        ],
      },
      { name: "compact", selector: { boolean: {} } },
      {
        name: "sections",
        type: "expandable",
        flatten: true,
        expanded: true,
        title: t(hass, "editor_sections"),
        schema: [
          { name: "show_header", selector: { boolean: {} } },
          { name: "show_alerts", selector: { boolean: {} } },
          { name: "show_metrics", selector: { boolean: {} } },
          { name: "show_forecast", selector: { boolean: {} } },
          {
            type: "grid",
            name: "",
            schema: [
              {
                name: "forecast_type",
                selector: {
                  select: {
                    mode: "dropdown",
                    options: [
                      { value: "daily", label: t(hass, "editor_forecast_type_daily") },
                      { value: "twice_daily", label: t(hass, "editor_forecast_type_twice") },
                      { value: "both", label: t(hass, "editor_forecast_type_both") },
                    ],
                  },
                },
              },
              {
                name: "forecast_days",
                selector: { number: { min: 2, max: 7, step: 1, mode: "box" } },
              },
            ],
          },
          { name: "show_radar", selector: { boolean: {} } },
          { name: "radar_collapsed", selector: { boolean: {} } },
          { name: "show_bulletin", selector: { boolean: {} } },
          { name: "show_air_quality", selector: { boolean: {} } },
          { name: "show_pollen", selector: { boolean: {} } },
          { name: "show_hydrology", selector: { boolean: {} } },
          { name: "show_avalanche", selector: { boolean: {} } },
        ],
      },
      {
        name: "metrics",
        type: "expandable",
        flatten: true,
        expanded: false,
        title: t(hass, "editor_metrics"),
        schema: [
          { name: "show_metric_humidity", selector: { boolean: {} } },
          { name: "show_metric_wind", selector: { boolean: {} } },
          { name: "show_metric_precipitation", selector: { boolean: {} } },
          { name: "show_metric_pressure", selector: { boolean: {} } },
          { name: "show_metric_dew_point", selector: { boolean: {} } },
          { name: "show_metric_solar_uv", selector: { boolean: {} } },
          { name: "show_metric_visibility", selector: { boolean: {} } },
          { name: "show_metric_snow", selector: { boolean: {} } },
          { name: "show_metric_leaf_wetness", selector: { boolean: {} } },
        ],
      },
    ];
  }

  _render() {
    if (!this._hass || !this._config || !window.customElements.get("ha-form")) return;
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.addEventListener("value-changed", (ev) => {
        const config = {
          type: this._config.type || `custom:${CARD_TYPE}`,
          ...ev.detail.value,
        };
        // Keep emitted YAML minimal by omitting defaults and empty values
        for (const [key, value] of Object.entries(DEFAULTS)) {
          if (key !== "device_id" && config[key] === value) {
            delete config[key];
          }
        }
        for (const key of Object.keys(config)) {
          if (key !== "type" && (config[key] === "" || config[key] === undefined)) {
            delete config[key];
          }
        }
        this._config = config;
        fireEvent(this, "config-changed", { config });
      });
      this.appendChild(this._form);
    }

    this._form.hass = this._hass;
    this._form.data = { ...DEFAULTS, ...this._config };
    this._form.schema = this._buildSchema(this._hass);
    this._form.computeLabel = (schema) => t(this._hass, `editor_${schema.name}`, schema.name);
    this._form.computeHelper = (schema) => t(this._hass, `helper_${schema.name}`, null);
  }
}

/**
 * Register card and editor after Home Assistant's customElements registry swap
 * (card-api.md section 5).
 */
const defineElements = () => {
  const registry = window.customElements;
  if (!registry.get(CARD_TYPE)) registry.define(CARD_TYPE, ArpaVenetoMeteoCard);
  if (!registry.get(EDITOR_TYPE)) registry.define(EDITOR_TYPE, ArpaVenetoMeteoCardEditor);
};

if (window.customElements.get("home-assistant") || window.customElements.get("hc-main")) {
  defineElements();
} else {
  Promise.race([
    window.customElements.whenDefined("home-assistant"),
    window.customElements.whenDefined("hc-main"),
    new Promise((resolve) => setTimeout(resolve, 30000)),
  ]).then(defineElements);
}

window.customCards = window.customCards || [];
if (!window.customCards.some((c) => c.type === CARD_TYPE)) {
  window.customCards.push({
    type: CARD_TYPE,
    name: "ARPA Veneto Meteo",
    description:
      "Configurable ARPA Veneto weather, forecasts, radar, bulletin, air quality, pollen, hydrology and avalanche card.",
    preview: true,
    documentationURL: "https://github.com/fabioscarparo/ha-arpav-meteo#dashboard-card",
  });
}
