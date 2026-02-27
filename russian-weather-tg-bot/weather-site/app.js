/**
 * Погода по городам России — полноценный сайт с интерактивной картой.
 * Карта: Leaflet, перемещение, масштаб, маркеры городов с погодой.
 */
(function () {
  "use strict";

  const OPEN_METEO = "https://api.open-meteo.com/v1/forecast";
  const RUSSIA_CENTER = [61, 96];
  const RUSSIA_ZOOM = 3;
  const RUSSIA_BOUNDS = L.latLngBounds([41, 19], [82, 180]);
  const TELEGRAM_BOT_URL = window.TELEGRAM_BOT_URL || "https://t.me/Russianweather1_bot";

  let cities = [];
  let cityEmblems = {};
  let homeMap = null;
  let cityMap = null;

  function setLogoLink() {
    var link = document.getElementById("logoLink");
    if (link) link.href = TELEGRAM_BOT_URL;
  }

  function getBaseUrl() {
    var path = window.location.pathname;
    var idx = path.lastIndexOf("/");
    return window.location.origin + (idx >= 0 ? path.substring(0, idx + 1) : "/");
  }

  function loadCities() {
    var base = getBaseUrl();
    var url = base + "cities.json";
    return fetch(url).then(function (r) {
      if (!r.ok) throw new Error("Не удалось загрузить список городов");
      return r.json();
    }).then(function (data) {
      cities = data;
      return cities;
    });
  }

  function loadEmblems() {
    var base = getBaseUrl();
    var url = base + "../weather_app/emblems.json";
    return fetch(url).then(function (r) {
      if (!r.ok) return {};
      return r.json();
    }).then(function (data) {
      cityEmblems = data || {};
      return cityEmblems;
    }).catch(function () { return {}; });
  }

  /** Поиск городов по названию (name_ru или slug). */
  function findCitiesByQuery(q) {
    if (!q || !cities.length) return [];
    var norm = q.trim().toLowerCase();
    if (norm.length < 1) return [];
    return cities.filter(function (c) {
      return (c.name_ru && c.name_ru.toLowerCase().indexOf(norm) !== -1) ||
        (c.slug && c.slug.toLowerCase().indexOf(norm.replace(/\s+/g, "_")) !== -1);
    });
  }

  function fetchWeather(lat, lon, timezone) {
    var params = new URLSearchParams({
      latitude: lat,
      longitude: lon,
      timezone: timezone,
      current: "temperature_2m,weather_code,surface_pressure,wind_speed_10m,relative_humidity_2m,apparent_temperature",
      daily: "temperature_2m_max,temperature_2m_min,weather_code,time",
      hourly: "temperature_2m,weather_code",
      forecast_days: 7
    });
    return fetch(OPEN_METEO + "?" + params.toString()).then(function (r) {
      if (!r.ok) throw new Error("Не удалось загрузить погоду");
      return r.json();
    });
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

  function weatherCodeToDesc(code) {
    var map = { 0: "Ясно", 1: "Преимущественно ясно", 2: "Переменная облачность", 3: "Пасмурно", 45: "Туман", 48: "Изморозь", 51: "Морось", 53: "Морось", 55: "Морось", 61: "Дождь", 63: "Дождь", 65: "Ливень", 71: "Снег", 73: "Снег", 75: "Снегопад", 77: "Снежные зёрна", 80: "Ливень", 81: "Ливень", 82: "Ливень", 85: "Снег", 86: "Снег", 95: "Гроза", 96: "Гроза с градом", 99: "Гроза с градом" };
    return map[code] || "Облачно";
  }

  function escapeHtml(s) {
    var div = document.createElement("div");
    div.textContent = s;
    return div.innerHTML;
  }

  function buildDayPartsHtmlForDate(dateStr, hourlyTimes, hourlyTemps, hourlyCodes) {
    if (!dateStr || !hourlyTimes || !hourlyTemps || !hourlyTimes.length) return "";
    function slot(hourRep, label) {
      var bestIndex = -1;
      var bestDelta = 25;
      var datePrefix = dateStr.slice(0, 10);
      for (var i = 0; i < hourlyTimes.length; i++) {
        var tStr = hourlyTimes[i];
        if (!tStr || tStr.slice(0, 10) !== datePrefix) continue;
        if (tStr.length < 13) continue;
        var hh = parseInt(tStr.substr(11, 2), 10);
        if (isNaN(hh)) continue;
        var delta = Math.abs(hh - hourRep);
        if (delta < bestDelta) {
          bestDelta = delta;
          bestIndex = i;
        }
      }
      if (bestIndex === -1) {
        return "<div class=\"day-part-row\"><span class=\"label\">" + escapeHtml(label) + "</span><span class=\"value\">—</span></div>";
      }
      var t = hourlyTemps[bestIndex];
      var code = hourlyCodes && hourlyCodes[bestIndex];
      var tempStr = t != null ? (t > 0 ? "+" : "") + Math.round(t) + "°C" : "—";
      var desc = weatherCodeToDesc(code || 0);
      return "<div class=\"day-part-row\"><span class=\"label\">" + escapeHtml(label) + "</span><span class=\"value\">" + tempStr + ", " + escapeHtml(desc) + "</span></div>";
    }
    return "<div class=\"day-parts-list\">" +
      slot(3, "Ночь") +
      slot(9, "Утро") +
      slot(15, "День") +
      slot(21, "Вечер") +
      "</div>";
  }

  function getCitySymbol(slug) {
    var url = cityEmblems[slug];
    if (url) return "<img src=\"" + url.replace(/"/g, "&quot;") + "\" class=\"city-marker-emblem\" alt=\"\" loading=\"lazy\" onerror=\"this.outerHTML='&#127963;';\">";
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

  function createMap(elId, options) {
    var opts = options || {};
    var center = opts.center || RUSSIA_CENTER;
    var zoom = opts.zoom !== undefined ? opts.zoom : RUSSIA_ZOOM;
    var map = L.map(elId, {
      zoomControl: true,
      attributionControl: true,
      minZoom: 2,
      maxZoom: 14
    }).setView(center, zoom);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "&copy; <a href=\"https://www.openstreetmap.org/copyright\">OpenStreetMap</a>"
    }).addTo(map);

    map.attributionControl.setPrefix("\u{1F1F7}\u{1F1FA} ");

    if (opts.maxBounds) {
      map.setMaxBounds(RUSSIA_BOUNDS);
    }
    return map;
  }

  function initHomeMap(containerId) {
    if (homeMap) {
      homeMap.remove();
      homeMap = null;
    }
    var el = document.getElementById(containerId);
    if (!el) return null;
    homeMap = createMap(containerId, { maxBounds: true });
    homeMap.setMaxBounds(RUSSIA_BOUNDS);

    cities.forEach(function (c) {
      var tempStr = "—°";
      var icon = L.divIcon({
        className: "city-marker-div",
        html: makeMarkerHtml(c.name_ru, tempStr, getCitySymbol(c.slug)),
        iconSize: [110, 58],
        iconAnchor: [55, 56]
      });

      var m = L.marker([c.lat, c.lon], { icon: icon });

      var popupContent = "<div class=\"popup-city-name\">" + escapeHtml(c.name_ru) + "</div>";
      popupContent += "<div class=\"popup-temp\">— °C</div>";
      popupContent += "<a href=\"#/city/" + encodeURIComponent(c.slug) + "\" class=\"popup-link\">Погода</a>";

      m.bindPopup(popupContent);
      m.addTo(homeMap);

      fetchCurrentTemp(c.lat, c.lon).then(function (t) {
        var str = (t != null ? (t > 0 ? "+" : "") + t + "°" : "—°");
        m.setIcon(L.divIcon({
          className: "city-marker-div",
          html: makeMarkerHtml(c.name_ru, str, getCitySymbol(c.slug)),
          iconSize: [110, 58],
          iconAnchor: [55, 56]
        }));
        var newTempText = (t != null ? (t > 0 ? "+" : "") + t + " °C" : "—");
        var newPopupHtml = "<div class=\"popup-city-name\">" + escapeHtml(c.name_ru) + "</div>" +
          "<div class=\"popup-temp\">" + newTempText + "</div>" +
          "<a href=\"#/city/" + encodeURIComponent(c.slug) + "\" class=\"popup-link\">Погода</a>";
        m.setPopupContent(newPopupHtml);
      });
    });

    return homeMap;
  }

  function initCityMap(containerId, city) {
    if (cityMap) {
      cityMap.remove();
      cityMap = null;
    }
    var el = document.getElementById(containerId);
    if (!el || !city) return null;
    cityMap = createMap(containerId, { center: [city.lat, city.lon], zoom: 6 });
    cityMap.setMaxBounds(RUSSIA_BOUNDS);

    L.circleMarker([city.lat, city.lon], {
      radius: 14,
      color: "#0ea5e9",
      weight: 2,
      fillColor: "#38bdf8",
      fillOpacity: 0.95
    }).bindPopup("<div class=\"popup-city-name\">" + escapeHtml(city.name_ru) + "</div>").addTo(cityMap);

    return cityMap;
  }

  function destroyMaps() {
    if (homeMap) {
      homeMap.remove();
      homeMap = null;
    }
    if (cityMap) {
      cityMap.remove();
      cityMap = null;
    }
  }

  function setLoading(show) {
    var loading = document.getElementById("loadingState");
    var content = document.getElementById("content");
    if (loading && content) {
      loading.hidden = !show;
      content.hidden = show;
    }
  }

  function renderLanding() {
    var html =
      "<div class=\"landing\">" +
      "<h1 class=\"hero\">Погода по городам России</h1>" +
      "<p class=\"desc\">Актуальная погода, прогноз и расположение на карте. Выберите город на карте или в списке — карту можно двигать, приближать и отдалять.</p>" +
      "<div class=\"search-wrap\">" +
      "<input type=\"text\" id=\"landingSearch\" class=\"search-input\" placeholder=\"Поиск города...\" autocomplete=\"off\">" +
      "<button type=\"button\" id=\"landingSearchBtn\" class=\"search-btn\" aria-label=\"Найти город\">\u{1F50D}</button>" +
      "</div>" +
      "<div class=\"map-section\"><h2>Интерактивная карта</h2><div class=\"map-wrap\" id=\"homeMap\"></div></div>" +
      "<a href=\"#/cities\" class=\"btn-primary\">Выбрать город из списка</a>" +
      "</div>";
    document.getElementById("content").innerHTML = html;
    document.getElementById("content").hidden = false;
    setTimeout(function () {
      initHomeMap("homeMap");
    }, 50);
    (function setupLandingSearch() {
      var input = document.getElementById("landingSearch");
      var btn = document.getElementById("landingSearchBtn");
      function goToCity() {
        var q = input && input.value ? input.value.trim() : "";
        if (!q) return;
        var found = findCitiesByQuery(q);
        if (found.length > 0) {
          window.location.hash = "#/city/" + encodeURIComponent(found[0].slug);
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
    })();
  }

  function renderCities() {
    var html =
      "<div class=\"page-header\">" +
      "<a href=\"#/\" class=\"back-link\">← Назад</a>" +
      "<h1>Города</h1>" +
      "</div>" +
      "<div class=\"search-wrap\">" +
      "<input type=\"text\" id=\"citiesSearch\" class=\"search-input\" placeholder=\"Поиск города...\" autocomplete=\"off\">" +
      "<button type=\"button\" id=\"citiesSearchBtn\" class=\"search-btn\" aria-label=\"Найти город\">\u{1F50D}</button>" +
      "</div>" +
      "<ul class=\"city-grid\" id=\"cityList\"></ul>";
    document.getElementById("content").innerHTML = html;
    var ul = document.getElementById("cityList");

    function fillCityList(filterQuery) {
      if (!ul) return;
      var toShow = !filterQuery || filterQuery.length < 1 ? cities : findCitiesByQuery(filterQuery);
      ul.innerHTML = "";
      toShow.forEach(function (c) {
        var li = document.createElement("li");
        var a = document.createElement("a");
        a.href = "#/city/" + encodeURIComponent(c.slug);
        a.className = "city-card";
        a.innerHTML = "<span class=\"name\">" + escapeHtml(c.name_ru) + "</span><span class=\"temp\" data-slug=\"" + escapeHtml(c.slug) + "\">—</span>";
        li.appendChild(a);
        ul.appendChild(li);
      });
      toShow.forEach(function (c) {
        fetchCurrentTemp(c.lat, c.lon).then(function (t) {
          var el = document.querySelector(".temp[data-slug=\"" + c.slug + "\"]");
          if (el) el.textContent = t != null ? (t > 0 ? "+" : "") + t + " °C" : "—";
        });
      });
    }
    fillCityList("");

    (function setupCitiesSearch() {
      var input = document.getElementById("citiesSearch");
      var btn = document.getElementById("citiesSearchBtn");
      if (btn) btn.addEventListener("click", function () {
        var q = input && input.value ? input.value.trim() : "";
        if (q) {
          var found = findCitiesByQuery(q);
          if (found.length > 0) window.location.hash = "#/city/" + encodeURIComponent(found[0].slug);
        } else fillCityList("");
      });
      if (input) {
        input.addEventListener("input", function () { fillCityList(input.value.trim()); });
        input.addEventListener("keydown", function (e) {
          if (e.key === "Enter") {
            e.preventDefault();
            var q = input.value.trim();
            var found = findCitiesByQuery(q);
            if (found.length === 1) window.location.hash = "#/city/" + encodeURIComponent(found[0].slug);
            else if (found.length > 1) fillCityList(q);
            else fillCityList("");
          }
        });
      }
    })();
  }

  function renderCity(slug) {
    var city = cities.find(function (c) { return c.slug === slug; });
    if (!city) {
      document.getElementById("content").innerHTML = "<p class=\"error-msg\">Город не найден.</p>";
      return;
    }

    var html =
      "<div class=\"city-page\">" +
      "<div class=\"page-header\">" +
      "<a href=\"#/cities\" class=\"back-link\">← К списку</a>" +
      "</div>" +
      "<div class=\"city-header\"><h1>" + escapeHtml(city.name_ru) + "</h1></div>" +
      "<div class=\"weather-card loading\" id=\"weatherCard\">Загрузка погоды...</div>" +
      "<div class=\"map-section\">" +
      "<h2>На карте России</h2>" +
      "<p class=\"desc\" style=\"margin-bottom:10px;\">Карту можно двигать, приближать и отдалять.</p>" +
      "<div class=\"map-wrap mini\" id=\"cityMap\"></div>" +
      "</div>" +
      "</div>";
    document.getElementById("content").innerHTML = html;

    setTimeout(function () {
      initCityMap("cityMap", city);
    }, 50);

    fetchWeather(city.lat, city.lon, city.timezone).then(function (data) {
      var card = document.getElementById("weatherCard");
      if (!card) return;
      var cur = data.current;
      if (!cur) return;
      var temp = cur.temperature_2m != null ? Math.round(cur.temperature_2m) : null;
      var tempClass = temp != null && temp >= 0 ? "warm" : "cold";
      var tempStr = temp != null ? (temp > 0 ? "+" : "") + temp + " °C" : "—";
      card.className = "weather-card";
      card.innerHTML =
        "<div class=\"temp-main " + tempClass + "\">" + tempStr + "</div>" +
        "<div class=\"desc\">" + escapeHtml(weatherCodeToDesc(cur.weather_code)) + "</div>" +
        "<div class=\"details\">" +
        "Ощущается: " + (cur.apparent_temperature != null ? (cur.apparent_temperature > 0 ? "+" : "") + Math.round(cur.apparent_temperature) + " °C" : "—") + " · " +
        "Влажность: " + (cur.relative_humidity_2m != null ? cur.relative_humidity_2m + "%" : "—") + " · " +
        "Ветер: " + (cur.wind_speed_10m != null ? cur.wind_speed_10m + " м/с" : "—") + " · " +
        "Давление: " + (cur.surface_pressure != null ? Math.round(cur.surface_pressure * 0.750062) + " мм рт. ст." : "—") +
        "</div>";

      var daily = data.daily || {};
      var hourly = data.hourly || {};
      var times = daily.time || [];
      var maxT = daily.temperature_2m_max || [];
      var minT = daily.temperature_2m_min || [];
      var codes = daily.weather_code || [];
      var hourlyTimes = hourly.time || [];
      var hourlyTemps = hourly.temperature_2m || [];
      var hourlyCodes = hourly.weather_code || [];

      if (times.length) {
        // Сегодня: утро / день / вечер / ночь
        var todayHtml = "<div class=\"today-parts\"><div class=\"today-title\">Сегодня по времени суток</div>";
        todayHtml += buildDayPartsHtmlForDate(times[0], hourlyTimes, hourlyTemps, hourlyCodes);
        todayHtml += "</div>";
        card.innerHTML += todayHtml;

        // Прогноз на 7 дней с выбором дня
        var forecastHtml = "<h3 class=\"week-forecast-title\">Прогноз на 7 дней</h3><div class=\"week-calendar\">";
        var maxDays = Math.min(times.length, 7);
        for (var i = 0; i < maxDays; i++) {
          var d = new Date(times[i]);
          var dayLabel = i === 0 ? "Сегодня" : (i === 1 ? "Завтра" : (d.getDate() + "." + (d.getMonth() + 1)));
          forecastHtml += "<button type=\"button\" class=\"week-day-btn\" data-day-index=\"" + i + "\">" + escapeHtml(dayLabel) + "</button>";
        }
        forecastHtml += "</div><div class=\"week-day-details\"></div>";
        card.innerHTML += forecastHtml;

        var buttons = card.querySelectorAll(".week-day-btn");
        var detailsEl = card.querySelector(".week-day-details");
        function activateDay(idx) {
          if (!detailsEl || idx < 0 || idx >= maxDays) return;
          buttons.forEach(function (btn, j) {
            btn.classList.toggle("active", j === idx);
          });
          var maxVal = maxT[idx];
          var minVal = minT[idx];
          var code = codes[idx] || 0;
          var tempStr2 = (maxVal != null && minVal != null)
            ? (maxVal > 0 ? "+" : "") + Math.round(maxVal) + "° / " + (minVal > 0 ? "+" : "") + Math.round(minVal) + "°"
            : "—";
          var summary = "<div class=\"week-day-summary\">Макс/мин: " + tempStr2 + " · " + escapeHtml(weatherCodeToDesc(code)) + "</div>";
          summary += buildDayPartsHtmlForDate(times[idx], hourlyTimes, hourlyTemps, hourlyCodes);
          detailsEl.innerHTML = summary;
        }
        buttons.forEach(function (btn, idx) {
          btn.addEventListener("click", function () { activateDay(idx); });
        });
        if (buttons.length) {
          activateDay(0);
        }
      }
    }).catch(function () {
      var card = document.getElementById("weatherCard");
      if (card) {
        card.className = "weather-card error-msg";
        card.textContent = "Не удалось загрузить погоду.";
      }
    });
  }

  function route() {
    destroyMaps();
    var hash = window.location.hash || "#/";
    if (hash === "#/" || hash === "#") {
      renderLanding();
      return;
    }
    if (hash === "#/cities") {
      renderCities();
      return;
    }
    var m = hash.match(/^#\/city\/([^/]+)/);
    if (m) {
      renderCity(decodeURIComponent(m[1]));
      return;
    }
    renderLanding();
  }

  setLoading(true);
  loadCities()
    .then(function () { return loadEmblems(); })
    .then(function () {
      setLogoLink();
      setLoading(false);
      route();
    })
    .catch(function (e) {
      setLoading(false);
      document.getElementById("content").innerHTML = "<p class=\"error-msg\">" + escapeHtml(e.message) + "</p>";
      document.getElementById("content").hidden = false;
    });

  window.addEventListener("hashchange", route);
})();
