(function () {
  "use strict";

  const MAP_EXTENT = { lonMin: 19, latMin: 41, lonMax: 180, latMax: 82 };
  const OPEN_METEO = "https://api.open-meteo.com/v1/forecast";
  const RUSSIA_CENTER = [61, 96];
  const RUSSIA_ZOOM = 3;

  var tg = null;
  var mapLanding = null;
  var mapCity = null;
  var TELEGRAM_BOT_URL = window.TELEGRAM_BOT_URL || "https://t.me/Russianweather1_bot";

  let cities = [];
  let cityEmblems = {};

  function lonLatToPercent(lon, lat) {
    var lonMin = MAP_EXTENT.lonMin, latMin = MAP_EXTENT.latMin, lonMax = MAP_EXTENT.lonMax, latMax = MAP_EXTENT.latMax;
    var x = ((lon - lonMin) / (lonMax - lonMin)) * 100;
    var y = ((latMax - lat) / (latMax - latMin)) * 100;
    return { x: x, y: y };
  }

  function weatherCodeToDesc(code) {
    var map = { 0: "Ясно", 1: "Преимущественно ясно", 2: "Переменная облачность", 3: "Пасмурно", 45: "Туман", 48: "Изморозь", 51: "Морось", 53: "Морось", 55: "Морось", 61: "Дождь", 63: "Дождь", 65: "Ливень", 71: "Снег", 73: "Снег", 75: "Снегопад", 77: "Снежные зёрна", 80: "Ливень", 81: "Ливень", 82: "Ливень", 85: "Снег", 86: "Снег", 95: "Гроза", 96: "Гроза с градом", 99: "Гроза с градом" };
    return map[code] || "Облачно";
  }

  function weatherCodeToEmoji(code) {
    if (code == null) return "\u{1F321}";
    if (code === 0) return "\u{1F31E}";
    if (code >= 1 && code <= 3) return "\u{2601}";
    if (code === 45 || code === 48) return "\u{1F32B}";
    if (code >= 51 && code <= 67) return "\u{1F327}";
    if (code >= 71 && code <= 77) return "\u{2744}";
    if (code >= 80 && code <= 82) return "\u{1F326}";
    if (code >= 85 && code <= 86) return "\u{2744}";
    if (code >= 95 && code <= 99) return "\u{26C8}";
    return "\u{2601}";
  }

  function getBaseUrl() {
    var base = document.querySelector("base");
    if (base && base.href) {
      var u = new URL(base.href);
      return u.origin + u.pathname.replace(/\/?index\.html$/, "").replace(/\/?$/, "/");
    }
    var path = window.location.pathname;
    var idx = path.lastIndexOf("/");
    return window.location.origin + (idx >= 0 ? path.substring(0, idx + 1) : "/");
  }

  function getAssetsBase() {
    return getBaseUrl() + "assets/";
  }

  function loadCities() {
    var base = getBaseUrl();
    return fetch(base + "cities.json").then(function (r) {
      if (!r.ok) throw new Error("Не удалось загрузить список городов");
      return r.json();
    }).then(function (data) {
      cities = data;
      return cities;
    });
  }

  function loadEmblems() {
    var base = getBaseUrl();
    return fetch(base + "emblems.json").then(function (r) {
      if (!r.ok) return {};
      return r.json();
    }).then(function (data) {
      cityEmblems = data || {};
      return cityEmblems;
    }).catch(function () { return {}; });
  }

  /** Поиск городов по названию (name_ru или slug). Возвращает массив подходящих городов. */
  function findCitiesByQuery(q) {
    if (!q || !cities.length) return [];
    var norm = q.trim().toLowerCase();
    if (norm.length < 1) return [];
    return cities.filter(function (c) {
      return (c.name_ru && c.name_ru.toLowerCase().indexOf(norm) !== -1) ||
        (c.slug && c.slug.toLowerCase().indexOf(norm.replace(/\s+/g, "_")) !== -1);
    });
  }

  function fetchJsonWithRetry(url, maxAttempts) {
    var attempts = typeof maxAttempts === "number" && maxAttempts > 0 ? maxAttempts : 3;
    function attempt(n) {
      return fetch(url).then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      }).catch(function (err) {
        if (n >= attempts - 1) throw err;
        return new Promise(function (resolve) {
          setTimeout(function () {
            resolve(attempt(n + 1));
          }, 500 * (n + 1));
        });
      });
    }
    return attempt(0);
  }

  function fetchWeather(lat, lon, timezone) {
    var params = new URLSearchParams({
      latitude: lat,
      longitude: lon,
      timezone: timezone,
      current: "temperature_2m,relative_humidity_2m,weather_code,surface_pressure,wind_speed_10m,apparent_temperature",
      daily: "temperature_2m_max,temperature_2m_min,weather_code",
      forecast_days: 2
    });
    var url = OPEN_METEO + "?" + params.toString();
    return fetchJsonWithRetry(url, 3);
  }

  function hPaToMmHg(hPa) {
    return hPa != null ? Math.round(hPa * 0.750062) : null;
  }

  function escapeHtml(s) {
    var div = document.createElement("div");
    div.textContent = s;
    return div.innerHTML;
  }

  function cityImageCandidates(slug) {
    return [
      "historic_" + slug + ".png",
      "historic_" + slug + "_2.png",
      "historic_" + slug + "_3.png",
      "historic_" + slug + "_4.png",
      "historic_" + slug + "_5.png",
      "historic_" + slug + "_6.png",
      "historic_" + slug + "_7.png",
      "historic_" + slug + "_8.png",
      "historic_" + slug + "_9.png",
      "historic_" + slug + "_10.png",
      "landmark_" + slug + "_1.png",
      "landmark_" + slug + "_2.png",
      "landmark_" + slug + "_3.png",
      "city_" + slug + "_1.png",
      "city_" + slug + "_2.png",
      "city_" + slug + "_3.png",
      "city_" + slug + "_4.png",
      "city_" + slug + "_5.png",
      "city_" + slug + "_6.png"
    ];
  }

  /** Официальный символ города: герб (из emblems.json) или нейтральный символ. */
  function getCitySymbol(slug) {
    var url = cityEmblems[slug];
    if (url) {
      return "<img src=\"" + url.replace(/"/g, "&quot;") + "\" class=\"city-marker-emblem\" alt=\"\" loading=\"lazy\" onerror=\"this.outerHTML='&#127963;';\">";
    }
    return "\u{1F3DB}";
  }

  function getCitySymbolRaw(slug) {
    var url = cityEmblems[slug];
    if (url) return "<img src=\"" + url.replace(/"/g, "&quot;") + "\" class=\"city-marker-emblem city-marker-emblem-inline\" alt=\"\" loading=\"lazy\" onerror=\"this.outerHTML='&#127963;';\">";
    return "\u{1F3DB}";
  }

  function openMapApp(citySlug) {
    var base = getBaseUrl();
    var mapBase = base.replace(/\/weather_app\/?$/, "/map_app/");
    var url = mapBase + (citySlug ? ("?city=" + encodeURIComponent(citySlug)) : "");
    if (tg && tg.openLink) {
      tg.openLink(url);
    } else {
      window.open(url, "_blank", "noopener");
    }
  }

  function setLogoLink() {
    var link = document.getElementById("logoLinkApp");
    if (link) link.href = TELEGRAM_BOT_URL;
  }

  function fetchCurrentTemp(lat, lon) {
    var url = OPEN_METEO + "?" + new URLSearchParams({
      latitude: lat,
      longitude: lon,
      current: "temperature_2m"
    }).toString();
    return fetchJsonWithRetry(url, 2).then(function (d) {
      return d.current && d.current.temperature_2m != null ? Math.round(d.current.temperature_2m) : null;
    }).catch(function () { return null; });
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

  function destroyLandingMap() {
    if (mapLanding) {
      mapLanding.remove();
      mapLanding = null;
    }
  }

  function destroyCityMap() {
    if (mapCity) {
      mapCity.remove();
      mapCity = null;
    }
  }

  function initLandingMap() {
    var el = document.getElementById("landingMap");
    if (!el || !cities.length) return;
    mapLanding = L.map("landingMap", {
      zoomControl: true,
      attributionControl: true,
      minZoom: 2,
      maxZoom: 14
    }).setView(RUSSIA_CENTER, RUSSIA_ZOOM);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "&copy; OpenStreetMap"
    }).addTo(mapLanding);
    mapLanding.attributionControl.setPrefix("\u{1F1F7}\u{1F1FA} ");
    mapLanding.setMaxBounds(L.latLngBounds([41, 19], [82, 180]));
    cities.forEach(function (c) {
      var tempStr = "—°";
      var icon = L.divIcon({
        className: "city-marker-div",
        html: makeMarkerHtml(c.name_ru, tempStr, getCitySymbol(c.slug)),
        iconSize: [140, 72],
        iconAnchor: [70, 70]
      });
      var m = L.marker([c.lat, c.lon], { icon: icon });
      var weatherUrl = "#/city/" + encodeURIComponent(c.slug);
      var popupHtml = "<div class=\"popup-title\">" + getCitySymbolRaw(c.slug) + " " + escapeHtml(c.name_ru) + "</div>" +
        "<div class=\"popup-temp\">— °C</div>" +
        "<div class=\"popup-actions\"><a href=\"" + weatherUrl + "\">Погода</a></div>";
      m.bindPopup(popupHtml);
      m.addTo(mapLanding);
      fetchCurrentTemp(c.lat, c.lon).then(function (t) {
        var str = (t != null ? (t > 0 ? "+" : "") + t + "°" : "—°");
        m.setIcon(L.divIcon({
          className: "city-marker-div",
          html: makeMarkerHtml(c.name_ru, str, getCitySymbol(c.slug)),
          iconSize: [140, 72],
          iconAnchor: [70, 70]
        }));
        var newTempText = (t != null ? (t > 0 ? "+" : "") + t + " °C" : "—");
        m.setPopupContent("<div class=\"popup-title\">" + getCitySymbolRaw(c.slug) + " " + escapeHtml(c.name_ru) + "</div>" +
          "<div class=\"popup-temp\">" + newTempText + "</div>" +
          "<div class=\"popup-actions\"><a href=\"" + weatherUrl + "\">Погода</a></div>");
      });
    });
  }

  function initCityMap(city) {
    var el = document.getElementById("cityMap");
    if (!el || !city) return;
    mapCity = L.map("cityMap", {
      zoomControl: true,
      attributionControl: true,
      minZoom: 2,
      maxZoom: 14
    }).setView([city.lat, city.lon], 6);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "&copy; OpenStreetMap"
    }).addTo(mapCity);
    mapCity.attributionControl.setPrefix("\u{1F1F7}\u{1F1FA} ");
    mapCity.setMaxBounds(L.latLngBounds([41, 19], [82, 180]));
    L.circleMarker([city.lat, city.lon], {
      radius: 14,
      color: "#e74c3c",
      weight: 2,
      fillColor: "#ff6b4a",
      fillOpacity: 0.95
    }).bindPopup("<div class=\"popup-title\">" + escapeHtml(city.name_ru) + "</div>").addTo(mapCity);
  }

  function renderHome() {
    destroyLandingMap();
    destroyCityMap();
    var fragment = document.createDocumentFragment();
    var landing = document.createElement("div");
    landing.className = "landing";
    landing.innerHTML =
      "<a href=\"#\" id=\"logoLinkApp\" class=\"app-logo\" target=\"_blank\" rel=\"noopener\">" +
      "<svg viewBox=\"0 0 40 40\" fill=\"none\"><path d=\"M20 4C11.16 4 4 11.16 4 20s7.16 16 16 16 16-7.16 16-16S28.84 4 20 4z\" fill=\"#0ea5e9\" opacity=\"0.2\"/><path d=\"M20 8c-6.63 0-12 5.37-12 12s5.37 12 12 12 12-5.37 12-12S26.63 8 20 8z\" fill=\"#0ea5e9\"/><circle cx=\"20\" cy=\"16\" r=\"4\" fill=\"#fbbf24\"/><path d=\"M14 24c0-3.31 2.69-6 6-6s6 2.69 6 6\" stroke=\"#94a3b8\" stroke-width=\"1.5\" fill=\"none\"/><ellipse cx=\"20\" cy=\"28\" rx=\"6\" ry=\"2\" fill=\"#94a3b8\" opacity=\"0.6\"/></svg>" +
      "<span>Погода России</span></a>" +
      "<div class=\"hero\">Погода по городам России</div>" +
      "<p class=\"desc\">Мы бот, который упрощает поиск погоды. Выберите город на карте или в списке — на карте видна температура, карту можно двигать и масштабировать.</p>" +
      "<div class=\"search-wrap\">" +
      "<input type=\"text\" id=\"landingSearch\" class=\"search-input\" placeholder=\"Поиск города...\" autocomplete=\"off\">" +
      "<button type=\"button\" id=\"landingSearchBtn\" class=\"search-btn\" aria-label=\"Найти город\">\u{1F50D}</button>" +
      "</div>" +
      "<div class=\"map-section\"><h3>Карта России</h3><div class=\"map-wrap map-landing\" id=\"landingMap\"></div></div>" +
      "<a href=\"#/cities\" class=\"btn-city\">Выбрать город</a>";
    fragment.appendChild(landing);
    document.getElementById("app").innerHTML = "";
    document.getElementById("app").appendChild(fragment);
    setLogoLink();
    setTimeout(function () {
      initLandingMap();
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
      if (input) {
        input.addEventListener("keydown", function (e) {
          if (e.key === "Enter") { e.preventDefault(); goToCity(); }
        });
      }
    })();
  }

  function renderCities() {
    destroyLandingMap();
    destroyCityMap();
    var fragment = document.createDocumentFragment();
    var header = document.createElement("div");
    header.className = "header";
    header.innerHTML = "<a href=\"#/\" class=\"back-link visible\">← Назад</a><h1>Выбор города</h1>";
    fragment.appendChild(header);
    var searchWrap = document.createElement("div");
    searchWrap.className = "search-wrap";
    searchWrap.innerHTML =
      "<input type=\"text\" id=\"citiesSearch\" class=\"search-input\" placeholder=\"Поиск города...\" autocomplete=\"off\">" +
      "<button type=\"button\" id=\"citiesSearchBtn\" class=\"search-btn\" aria-label=\"Найти город\">\u{1F50D}</button>";
    fragment.appendChild(searchWrap);
    var ul = document.createElement("ul");
    ul.className = "city-list";
    ul.id = "cityListUl";
    fragment.appendChild(ul);
    var app = document.getElementById("app");
    app.innerHTML = "";
    app.appendChild(fragment);

    function fillCityList(filterQuery) {
      var listEl = document.getElementById("cityListUl");
      if (!listEl) return;
      var toShow = !filterQuery || filterQuery.length < 1
        ? cities
        : findCitiesByQuery(filterQuery);
      listEl.innerHTML = "";
      toShow.forEach(function (c) {
        var li = document.createElement("li");
        var a = document.createElement("a");
        a.href = "#/city/" + encodeURIComponent(c.slug);
        a.innerHTML = "<span class=\"city-emoji\" data-slug=\"" + escapeHtml(c.slug) + "\">" + getCitySymbolRaw(c.slug) + "</span><span>" + escapeHtml(c.name_ru) + "</span><div class=\"temp\" data-slug=\"" + escapeHtml(c.slug) + "\">—</div>";
        li.appendChild(a);
        listEl.appendChild(li);
      });
      toShow.forEach(function (c) {
        fetch(OPEN_METEO + "?" + new URLSearchParams({ latitude: c.lat, longitude: c.lon, current: "temperature_2m,weather_code" }).toString()).then(function (r) { return r.json(); }).then(function (data) {
          var cur = data.current;
          var t = cur && cur.temperature_2m;
          var code = cur && cur.weather_code;
          var tempEl = app.querySelector(".temp[data-slug=\"" + c.slug + "\"]");
          if (tempEl && t != null) tempEl.textContent = (t > 0 ? "+" : "") + Math.round(t) + "°C";
        }).catch(function () {});
      });
    }

    fillCityList("");

    (function setupCitiesSearch() {
      var input = document.getElementById("citiesSearch");
      var btn = document.getElementById("citiesSearchBtn");
      function applySearch() {
        var q = input && input.value ? input.value.trim() : "";
        fillCityList(q);
        if (q) {
          var found = findCitiesByQuery(q);
          if (found.length === 1) window.location.hash = "#/city/" + encodeURIComponent(found[0].slug);
        }
      }
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

  function setCityImageWithFallback(imgEl, slug) {
    var assetsBase = getAssetsBase();
    var candidates = cityImageCandidates(slug);
    var currentIndex = 0;

    imgEl.alt = "Исторический центр";
    imgEl.className = "historic-block";

    function showFrom(startIndex, step) {
      if (!candidates || !candidates.length) {
        imgEl.classList.add("err");
        imgEl.alt = "";
        imgEl.src = "";
        imgEl.textContent = "Красивый исторический центр";
        return;
      }
      var attempts = 0;
      var dir = step >= 0 ? 1 : -1;
      function tryIndex(idx) {
        if (attempts >= candidates.length) {
          imgEl.classList.add("err");
          imgEl.alt = "";
          imgEl.src = "";
          imgEl.textContent = "Красивый исторический центр";
          return;
        }
        var wrapped = ((idx % candidates.length) + candidates.length) % candidates.length;
        imgEl.onerror = function () {
          attempts += 1;
          tryIndex(wrapped + dir);
        };
        imgEl.onload = function () {
          imgEl.onerror = null;
          currentIndex = wrapped;
        };
        imgEl.src = assetsBase + candidates[wrapped];
      }
      tryIndex(startIndex);
    }

    function goTo(delta) {
      if (!candidates || !candidates.length) return;
      var start = currentIndex + delta;
      showFrom(start, delta);
    }

    var parent = imgEl.parentNode;
    if (parent) {
      var prevBtn = parent.querySelector(".photo-nav-prev");
      var nextBtn = parent.querySelector(".photo-nav-next");
      if (prevBtn) prevBtn.addEventListener("click", function () { goTo(-1); });
      if (nextBtn) nextBtn.addEventListener("click", function () { goTo(1); });
    }

    showFrom(0, 1);
  }

  function renderCity(slug) {
    destroyLandingMap();
    destroyCityMap();
    var city = cities.find(function (c) { return c.slug === slug; });
    if (!city) {
      document.getElementById("app").innerHTML = "<p class=\"error-msg\">Город не найден.</p>";
      return;
    }
    var fragment = document.createDocumentFragment();
    var header = document.createElement("div");
    header.className = "header header-city";
    header.innerHTML = "<a href=\"#/cities\" class=\"back-link visible\">← Назад</a>" +
      "<span class=\"header-city-symbol\" aria-hidden=\"true\">" + getCitySymbol(slug) + "</span>" +
      "<h1>" + escapeHtml(city.name_ru) + "</h1>";
    fragment.appendChild(header);

    var photoWrap = document.createElement("div");
    photoWrap.className = "city-photo-wrap";
    var prevBtn = document.createElement("button");
    prevBtn.type = "button";
    prevBtn.className = "photo-nav photo-nav-prev";
    prevBtn.setAttribute("aria-label", "Предыдущее фото");
    prevBtn.innerHTML = "‹";
    var nextBtn = document.createElement("button");
    nextBtn.type = "button";
    nextBtn.className = "photo-nav photo-nav-next";
    nextBtn.setAttribute("aria-label", "Следующее фото");
    nextBtn.innerHTML = "›";
    var historicImg = document.createElement("img");
    photoWrap.appendChild(prevBtn);
    photoWrap.appendChild(historicImg);
    photoWrap.appendChild(nextBtn);
    fragment.appendChild(photoWrap);
    setCityImageWithFallback(historicImg, slug);

    var currentBlock = document.createElement("div");
    currentBlock.className = "current-weather loading";
    currentBlock.textContent = "Загрузка погоды...";
    fragment.appendChild(currentBlock);

    var dayBlock = document.createElement("div");
    dayBlock.className = "day-forecast";
    dayBlock.innerHTML = "<strong>Прогноз на 2 дня</strong>";
    fragment.appendChild(dayBlock);

    var mapSection = document.createElement("div");
    mapSection.className = "map-section";
    mapSection.innerHTML =
      "<h3>На карте России</h3>" +
      "<p class=\"desc\" style=\"margin-bottom:8px;font-size:0.9rem;\">Карту можно двигать, приближать и отдалять.</p>" +
      "<div class=\"map-wrap\" id=\"cityMap\"></div>";
    fragment.appendChild(mapSection);

    document.getElementById("app").innerHTML = "";
    document.getElementById("app").appendChild(fragment);

    setTimeout(function () {
      initCityMap(city);
    }, 50);

    function loadCityWeather() {
      fetchWeather(city.lat, city.lon, city.timezone).then(function (data) {
        var cur = data.current;
        if (cur) {
          var pressureMm = hPaToMmHg(cur.surface_pressure);
          currentBlock.className = "current-weather";
          currentBlock.innerHTML =
            "<div class=\"temp-main\">" + (cur.temperature_2m > 0 ? "+" : "") + Math.round(cur.temperature_2m) + "°C</div>" +
            "<div class=\"desc\">" + escapeHtml(weatherCodeToDesc(cur.weather_code)) + "</div>" +
            "<div class=\"details\">" +
            "Ощущается: " + (cur.apparent_temperature != null ? (cur.apparent_temperature > 0 ? "+" : "") + Math.round(cur.apparent_temperature) + "°C" : "—") + " · " +
            "Влажность: " + (cur.relative_humidity_2m != null ? cur.relative_humidity_2m + "%" : "—") + " · " +
            "Ветер: " + (cur.wind_speed_10m != null ? cur.wind_speed_10m + " м/с" : "—") + " · " +
            "Давление: " + (pressureMm != null ? pressureMm + " мм рт. ст." : "—") +
            "</div>";
        }
        var daily = data.daily;
        if (daily && daily.time && daily.temperature_2m_max && daily.weather_code) {
          var times = daily.time, maxT = daily.temperature_2m_max, minT = daily.temperature_2m_min, codes = daily.weather_code;
          var html = "<strong>Прогноз на 2 дня</strong>";
          for (var i = 0; i < times.length; i++) {
            var d = new Date(times[i]);
            var dayLabel = i === 0 ? "Сегодня" : (i === 1 ? "Завтра" : (d.getDate() + "." + (d.getMonth() + 1)));
            var tempStr = (maxT[i] != null && minT[i] != null) ? (maxT[i] > 0 ? "+" : "") + Math.round(maxT[i]) + "° / " + (minT[i] > 0 ? "+" : "") + Math.round(minT[i]) + "°" : "—";
            html += "<div class=\"day-forecast\"><span class=\"slot\">" + escapeHtml(dayLabel) + "</span><span class=\"temp\">" + tempStr + "</span><span>" + escapeHtml(weatherCodeToDesc(codes[i])) + "</span></div>";
          }
          dayBlock.innerHTML = html;
        }
      }).catch(function () {
        currentBlock.className = "current-weather error-msg";
        currentBlock.innerHTML =
          "<p>Не удалось загрузить погоду. Проверьте интернет.</p>" +
          "<button type=\"button\" class=\"retry-btn\">Повторить</button>";
        var btn = currentBlock.querySelector(".retry-btn");
        if (btn) {
          btn.addEventListener("click", function () {
            currentBlock.className = "current-weather loading";
            currentBlock.textContent = "Повторная попытка загрузки...";
            loadCityWeather();
          });
        }
      });
    }

    loadCityWeather();
  }

  function route() {
    var hash = window.location.hash || "#/";
    if (hash === "#/" || hash === "#") {
      renderHome();
      return;
    }
    var citiesMatch = hash.match(/^#\/cities\/?$/);
    if (citiesMatch) {
      if (cities.length) renderCities();
      else loadCities().then(renderCities).catch(function (e) {
        document.getElementById("app").innerHTML = "<p class=\"error-msg\">" + escapeHtml(e.message) + "</p>";
      });
      return;
    }
    var cityMatch = hash.match(/^#\/city\/([^/]+)/);
    if (cityMatch) {
      renderCity(decodeURIComponent(cityMatch[1]));
      return;
    }
    renderHome();
  }

  window.addEventListener("hashchange", route);
  tg = window.Telegram && window.Telegram.WebApp;
  if (tg) {
    tg.ready();
    tg.expand();
    try {
      if (tg.themeParams) {
        var tp = tg.themeParams;
        if (tp.bg_color) document.body.style.setProperty("--bg", tp.bg_color);
        if (tp.text_color) document.body.style.setProperty("--text", tp.text_color);
        if (tp.hint_color) document.body.style.setProperty("--hint", tp.hint_color);
        if (tp.link_color) document.body.style.setProperty("--link", tp.link_color);
        if (tp.button_color) document.body.style.setProperty("--accent", tp.button_color);
        if (tp.secondary_bg_color) document.body.style.setProperty("--card-bg", tp.secondary_bg_color);
      }
      if (tg.setHeaderColor) tg.setHeaderColor(tg.themeParams && tg.themeParams.bg_color ? tg.themeParams.bg_color : "#1a1a2e");
      if (tg.setBackgroundColor) tg.setBackgroundColor(tg.themeParams && tg.themeParams.bg_color ? tg.themeParams.bg_color : "#1a1a2e");
    } catch (e) {}
    var start = tg.initDataUnsafe && tg.initDataUnsafe.start_param;
    if (start && start.length) window.location.hash = "#/city/" + encodeURIComponent(start);
  }

  (function setupFullscreenToggle() {
    var btn = document.getElementById("fullscreenToggleApp");
    if (!btn) return;
    var active = false;
    function apply(on) {
      active = on;
      document.body.classList.toggle("fullscreen-app", on);
      btn.textContent = on ? "↙" : "⛶";
      if (tg && tg.expand && on) {
        try { tg.expand(); } catch (e) {}
      }
    }
    btn.addEventListener("click", function () {
      if (!document.fullscreenElement && document.documentElement.requestFullscreen) {
        document.documentElement.requestFullscreen().catch(function () {});
        apply(true);
      } else if (document.fullscreenElement && document.exitFullscreen) {
        document.exitFullscreen().catch(function () {});
        apply(false);
      } else {
        apply(!active);
      }
    });
  })();
  loadCities().then(function () {
    return loadEmblems();
  }).then(function () {
    var start = tg && tg.initDataUnsafe && tg.initDataUnsafe.start_param;
    if (start && start.length) window.location.hash = "#/city/" + encodeURIComponent(start);
    route();
  }).catch(function (e) {
    document.getElementById("app").innerHTML = "<p class=\"error-msg\">" + escapeHtml(e.message) + "</p>";
  });
})();
