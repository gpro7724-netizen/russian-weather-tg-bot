(function () {
  "use strict";

  const MAP_EXTENT = { lonMin: 19, latMin: 41, lonMax: 180, latMax: 82 };
  const OPEN_METEO = "https://api.open-meteo.com/v1/forecast";
  const MAP_RUSSIA_URL = "assets/map_russia.png";

  let cities = [];

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

  function fetchWeather(lat, lon, timezone) {
    var params = new URLSearchParams({
      latitude: lat,
      longitude: lon,
      timezone: timezone,
      current: "temperature_2m,relative_humidity_2m,weather_code,surface_pressure,wind_speed_10m,apparent_temperature",
      daily: "temperature_2m_max,temperature_2m_min,weather_code",
      forecast_days: 2
    });
    return fetch(OPEN_METEO + "?" + params.toString()).then(function (r) {
      if (!r.ok) throw new Error("Не удалось загрузить погоду");
      return r.json();
    });
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
      "landmark_" + slug + "_1.png",
      "landmark_" + slug + "_2.png",
      "city_" + slug + "_1.png",
      "city_" + slug + "_2.png"
    ];
  }

  function renderHome() {
    var fragment = document.createDocumentFragment();
    var landing = document.createElement("div");
    landing.className = "landing";
    landing.innerHTML =
      "<div class=\"hero\">Погода по городам России</div>" +
      "<p class=\"desc\">Мы бот, который упрощает поиск погоды. Выберите город — получите актуальную погоду, фото исторического центра и место на карте России.</p>" +
      "<div class=\"map-section\"><h3>Карта России</h3><div class=\"map-wrap map-landing\"><img src=\"" + MAP_RUSSIA_URL + "\" alt=\"Карта России\" width=\"600\" height=\"450\"></div></div>" +
      "<a href=\"#/cities\" class=\"btn-city\">Выбрать город</a>";
    fragment.appendChild(landing);
    document.getElementById("app").innerHTML = "";
    document.getElementById("app").appendChild(fragment);
  }

  function renderCities() {
    var fragment = document.createDocumentFragment();
    var header = document.createElement("div");
    header.className = "header";
    header.innerHTML = "<a href=\"#/\" class=\"back-link visible\">← Назад</a><h1>Выбор города</h1>";
    fragment.appendChild(header);
    var ul = document.createElement("ul");
    ul.className = "city-list";
    cities.forEach(function (c) {
      var li = document.createElement("li");
      var a = document.createElement("a");
      a.href = "#/city/" + encodeURIComponent(c.slug);
      a.innerHTML = "<span>" + escapeHtml(c.name_ru) + "</span><div class=\"temp\" data-slug=\"" + escapeHtml(c.slug) + "\">—</div>";
      li.appendChild(a);
      ul.appendChild(li);
    });
    fragment.appendChild(ul);
    var app = document.getElementById("app");
    app.innerHTML = "";
    app.appendChild(fragment);
    cities.forEach(function (c) {
      fetch(OPEN_METEO + "?" + new URLSearchParams({ latitude: c.lat, longitude: c.lon, current: "temperature_2m" }).toString()).then(function (r) { return r.json(); }).then(function (data) {
        var t = data.current && data.current.temperature_2m;
        var el = app.querySelector(".temp[data-slug=\"" + c.slug + "\"]");
        if (el && t != null) el.textContent = (t > 0 ? "+" : "") + Math.round(t) + "°C";
      }).catch(function () {});
    });
  }

  function setCityImageWithFallback(imgEl, slug) {
    var assetsBase = getAssetsBase();
    var candidates = cityImageCandidates(slug);
    var idx = 0;
    imgEl.alt = "Исторический центр";
    imgEl.className = "historic-block";
    function tryNext() {
      if (idx >= candidates.length) {
        imgEl.classList.add("err");
        imgEl.alt = "";
        imgEl.src = "";
        imgEl.textContent = "Красивый исторический центр";
        return;
      }
      imgEl.src = assetsBase + candidates[idx];
      idx += 1;
    }
    imgEl.onerror = function () { tryNext(); };
    imgEl.onload = function () { imgEl.onerror = null; };
    tryNext();
  }

  function renderCity(slug) {
    var city = cities.find(function (c) { return c.slug === slug; });
    if (!city) {
      document.getElementById("app").innerHTML = "<p class=\"error-msg\">Город не найден.</p>";
      return;
    }
    var fragment = document.createDocumentFragment();
    var header = document.createElement("div");
    header.className = "header";
    header.innerHTML = "<a href=\"#/cities\" class=\"back-link visible\">← Назад</a><h1>" + escapeHtml(city.name_ru) + "</h1>";
    fragment.appendChild(header);

    var historicImg = document.createElement("img");
    setCityImageWithFallback(historicImg, slug);
    fragment.appendChild(historicImg);

    var currentBlock = document.createElement("div");
    currentBlock.className = "current-weather loading";
    currentBlock.textContent = "Загрузка погоды...";
    fragment.appendChild(currentBlock);

    var dayBlock = document.createElement("div");
    dayBlock.className = "day-forecast";
    dayBlock.innerHTML = "<strong>Прогноз на 2 дня</strong>";
    fragment.appendChild(dayBlock);

    var pc = lonLatToPercent(city.lon, city.lat);
    var mapSection = document.createElement("div");
    mapSection.className = "map-section";
    mapSection.innerHTML =
      "<h3>На карте России</h3>" +
      "<div class=\"map-wrap\">" +
      "<img src=\"" + MAP_RUSSIA_URL + "\" alt=\"Карта России\" width=\"700\" height=\"450\">" +
      "<span class=\"map-marker\" style=\"left:" + pc.x + "%;top:" + pc.y + "%\"></span>" +
      "</div>";
    fragment.appendChild(mapSection);

    document.getElementById("app").innerHTML = "";
    document.getElementById("app").appendChild(fragment);

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
      currentBlock.textContent = "Не удалось загрузить погоду. Проверьте интернет.";
    });
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
  var tg = window.Telegram && window.Telegram.WebApp;
  if (tg) {
    tg.ready();
    tg.expand();
    try {
      if (tg.themeParams) {
        var tp = tg.themeParams;
        if (tp.bg_color) document.body.style.setProperty("--bg", tp.bg_color);
        if (tp.text_color) document.body.style.setProperty("--text", tp.text_color);
      }
      if (tg.setHeaderColor) tg.setHeaderColor(tg.themeParams && tg.themeParams.bg_color ? tg.themeParams.bg_color : "#1a1a2e");
      if (tg.setBackgroundColor) tg.setBackgroundColor(tg.themeParams && tg.themeParams.bg_color ? tg.themeParams.bg_color : "#1a1a2e");
    } catch (e) {}
    var start = tg.initDataUnsafe && tg.initDataUnsafe.start_param;
    if (start && start.length) window.location.hash = "#/city/" + encodeURIComponent(start);
  }
  loadCities().then(function () {
    var start = tg && tg.initDataUnsafe && tg.initDataUnsafe.start_param;
    if (start && start.length) window.location.hash = "#/city/" + encodeURIComponent(start);
    route();
  }).catch(function (e) {
    document.getElementById("app").innerHTML = "<p class=\"error-msg\">" + escapeHtml(e.message) + "</p>";
  });
})();
