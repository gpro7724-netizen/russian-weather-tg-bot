(function () {
  "use strict";

  var tg = window.Telegram && window.Telegram.WebApp;
  if (tg) {
    tg.ready();
    tg.expand();
  }

  var OPEN_METEO = "https://api.open-meteo.com/v1/forecast";
  var TELEGRAM_BOT_URL = window.TELEGRAM_BOT_URL || "https://t.me/Russianweather1_bot";
  var OPENWEATHER_TILE_KEY = (window.OPENWEATHER_TILE_KEY || "").trim();
  var OPENWEATHER_TILE_BASE = "https://tile.openweathermap.org/map";
  var map = null;
  var slugToMarker = {};
  var citiesData = [];
  var cityEmblems = {};
  var mapWeatherState = null;

  function getBaseUrl() {
    var path = window.location.pathname;
    var idx = path.lastIndexOf("/");
    return window.location.origin + (idx >= 0 ? path.substring(0, idx + 1) : "/");
  }

  function setLogoLink() {
    var link = document.getElementById("logoLink");
    if (link) link.href = TELEGRAM_BOT_URL;
  }

  function loadCities() {
    var url = getBaseUrl() + "../weather_app/cities.json";
    return fetch(url).then(function (r) {
      if (!r.ok) throw new Error("Не удалось загрузить список городов");
      return r.json();
    });
  }

  function loadEmblems() {
    var url = getBaseUrl() + "../weather_app/emblems.json";
    return fetch(url).then(function (r) {
      if (!r.ok) return {};
      return r.json();
    }).then(function (data) {
      cityEmblems = data || {};
      return cityEmblems;
    }).catch(function () { return {}; });
  }

  function createWeatherTileLayersForMap() {
    if (!OPENWEATHER_TILE_KEY) return null;
    var key = OPENWEATHER_TILE_KEY;
    var common = {
      attribution: "&copy; OpenWeatherMap",
      opacity: 0.6
    };
    return {
      precipitation: L.tileLayer(OPENWEATHER_TILE_BASE + "/precipitation_new/{z}/{x}/{y}.png?appid=" + key, common),
      wind: L.tileLayer(OPENWEATHER_TILE_BASE + "/wind_new/{z}/{x}/{y}.png?appid=" + key, common),
      temperature: L.tileLayer(OPENWEATHER_TILE_BASE + "/temp_new/{z}/{x}/{y}.png?appid=" + key, common)
    };
  }

  function switchWeatherLayer(mapInstance, state, mode) {
    if (!mapInstance || !state || !state.layers) return;
    if (state.active && mapInstance.hasLayer(state.active)) {
      mapInstance.removeLayer(state.active);
    }
    var layer = state.layers[mode];
    if (!layer) return;
    layer.addTo(mapInstance);
    state.active = layer;
    state.mode = mode;
  }

  function setupWeatherModeControls(containerId, mapInstance, state) {
    var root = document.getElementById(containerId);
    if (!root) return;
    var buttons = root.querySelectorAll("[data-mode]");

    function setActiveButton(mode) {
      buttons.forEach(function (btn) {
        var m = btn.getAttribute("data-mode");
        if (m === mode) btn.classList.add("active");
        else btn.classList.remove("active");
      });
    }

    if (!state || !state.layers) {
      root.classList.add("disabled");
    }

    buttons.forEach(function (btn) {
      btn.addEventListener("click", function () {
        var mode = btn.getAttribute("data-mode");
        if (!state || !state.layers) return;
        switchWeatherLayer(mapInstance, state, mode);
        setActiveButton(mode);
      });
    });

    if (state && state.layers) {
      var initial = state.mode || "temperature";
      switchWeatherLayer(mapInstance, state, initial);
      setActiveButton(initial);
    }
  }
  function fetchCurrentTemp(lat, lon) {
    return fetch(OPEN_METEO + "?" + new URLSearchParams({
      latitude: lat,
      longitude: lon,
      current: "temperature_2m"
    }).toString()).then(function (r) { return r.json(); }).then(function (d) {
      return d.current && d.current.temperature_2m != null ? Math.round(d.current.temperature_2m) : null;
    }).catch(function () { return null; });
  }

  function escapeHtml(s) {
    var div = document.createElement("div");
    div.textContent = s;
    return div.innerHTML;
  }

  function getCitySymbol(slug) {
    var url = cityEmblems[slug];
    if (url) return "<img src=\"" + url.replace(/"/g, "&quot;") + "\" class=\"city-marker-emblem\" alt=\"\" loading=\"lazy\" onerror=\"this.outerHTML='&#127963;';\">";
    return "\u{1F3DB}";
  }

  function getCitySymbolPopup(slug) {
    var url = cityEmblems[slug];
    if (url) return "<img src=\"" + url.replace(/"/g, "&quot;") + "\" class=\"city-marker-emblem-inline\" alt=\"\" loading=\"lazy\" onerror=\"this.outerHTML='&#127963;';\">";
    return "\u{1F3DB}";
  }

  function makeMarkerHtml(name, tempStr, symbol) {
    var sym = symbol !== undefined && symbol !== null ? symbol : "\u{1F3DB}";
    return "<div class=\"city-marker-wrap\">" +
      "<div class=\"city-marker-symbol\">" + sym + "</div>" +
      "<div class=\"city-marker-temp\">" + escapeHtml(tempStr) + "</div>" +
      "<div class=\"city-marker-name\">" + escapeHtml(name) + "</div>" +
      "<div class=\"city-marker-dot\"></div>" +
      "</div>";
  }

  function initMap(cities) {
    citiesData = cities;
    setLogoLink();

    map = L.map("map", {
      zoomControl: true,
      attributionControl: true
    }).setView([61, 96], 3);

    // Подложка с атрибуцией: только флаг РФ и OpenStreetMap (без флага Украины)
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 8,
      minZoom: 2,
      attribution: "&copy; <a href=\"https://www.openstreetmap.org/copyright\">OpenStreetMap</a> contributors"
    }).addTo(map);

    map.attributionControl.setPrefix("\uD83C\uDDF7\uD83C\uDDFA ");

    if (OPENWEATHER_TILE_KEY) {
      mapWeatherState = {
        layers: createWeatherTileLayersForMap(),
        active: null,
        mode: "temperature"
      };
    } else {
      mapWeatherState = null;
    }

    var weatherUrlBase = getBaseUrl().replace(/\/map_app\/?$/, "/") + "weather_app/index.html#/city/";

    cities.forEach(function (c) {
      var tempStr = "—°";
      var icon = L.divIcon({
        className: "city-marker-div",
        html: makeMarkerHtml(c.name_ru, tempStr, getCitySymbol(c.slug)),
        iconSize: [110, 58],
        iconAnchor: [55, 56]
      });

      var m = L.marker([c.lat, c.lon], { icon: icon });

      var popupHtml =
        "<div class=\"popup-title\">" + getCitySymbolPopup(c.slug) + " " + escapeHtml(c.name_ru) + "</div>" +
        "<div class=\"popup-temp\">— °C</div>" +
        "<div class=\"popup-actions\"><a href=\"" + weatherUrlBase + encodeURIComponent(c.slug) + "\" data-slug=\"" + c.slug + "\">Открыть погоду</a></div>";

      m.bindPopup(popupHtml);
      m.addTo(map);
      slugToMarker[c.slug] = { marker: m, city: c };

      fetchCurrentTemp(c.lat, c.lon).then(function (t) {
        var str = (t != null ? (t > 0 ? "+" : "") + t + "°" : "—°");
        m.setIcon(L.divIcon({
          className: "city-marker-div",
          html: makeMarkerHtml(c.name_ru, str, getCitySymbol(c.slug)),
          iconSize: [110, 58],
          iconAnchor: [55, 56]
        }));
        var newTempText = (t != null ? (t > 0 ? "+" : "") + t + " °C" : "—");
        var newPopupHtml =
          "<div class=\"popup-title\">" + getCitySymbolPopup(c.slug) + " " + escapeHtml(c.name_ru) + "</div>" +
          "<div class=\"popup-temp\">" + newTempText + "</div>" +
          "<div class=\"popup-actions\"><a href=\"" + weatherUrlBase + encodeURIComponent(c.slug) + "\" data-slug=\"" + c.slug + "\">Открыть погоду</a></div>";
        m.setPopupContent(newPopupHtml);
      });
    });

    var params = new URLSearchParams(window.location.search);
    var citySlug = params.get("city");
    if (citySlug && slugToMarker[citySlug]) {
      var rec = slugToMarker[citySlug];
      map.setView(rec.marker.getLatLng(), 5);
      rec.marker.openPopup();
    }

    map.on("popupopen", function (e) {
      var popupNode = e.popup.getElement();
      if (!popupNode) return;
      var link = popupNode.querySelector("a[data-slug]");
      if (!link) return;

      link.addEventListener("click", function (ev) {
        ev.preventDefault();
        var href = link.getAttribute("href");
        if (tg && tg.openLink) {
          tg.openLink(href);
        } else {
          window.location.href = href;
        }
      }, { once: true });
    });

    setupMapSearch();
  }

  function findCitiesByQuery(q) {
    if (!q || !citiesData.length) return [];
    var norm = q.trim().toLowerCase();
    if (norm.length < 1) return [];
    return citiesData.filter(function (c) {
      return (c.name_ru && c.name_ru.toLowerCase().indexOf(norm) !== -1) ||
        (c.slug && c.slug.toLowerCase().indexOf(norm.replace(/\s+/g, "_")) !== -1);
    });

    setupWeatherModeControls("mapModes", map, mapWeatherState);
  }

  function setupMapSearch() {
    var input = document.getElementById("mapSearchInput");
    var btn = document.getElementById("mapSearchBtn");
    function goToCity() {
      var q = input && input.value ? input.value.trim() : "";
      if (!q || !map) return;
      var found = findCitiesByQuery(q);
      if (found.length > 0 && slugToMarker[found[0].slug]) {
        var rec = slugToMarker[found[0].slug];
        map.setView(rec.marker.getLatLng(), 6);
        rec.marker.openPopup();
        if (input) input.value = "";
      } else if (input) {
        input.placeholder = "Город не найден";
        input.value = "";
        setTimeout(function () { input.placeholder = "Поиск города..."; }, 1500);
      }
    }
    if (btn) btn.addEventListener("click", goToCity);
    if (input) input.addEventListener("keydown", function (e) {
      if (e.key === "Enter") { e.preventDefault(); goToCity(); }
    });
  }

  loadCities().then(function (cities) {
    return loadEmblems().then(function () { return cities; });
  }).then(initMap)
    .catch(function (e) {
      console.error(e);
      document.getElementById("map").innerHTML =
        "<p style=\"padding:12px;font-size:0.9rem;color:#c0392b;\">Не удалось загрузить карту городов.</p>";
    });
})();
