(function () {
  "use strict";

  var tg = window.Telegram && window.Telegram.WebApp;
  if (tg) {
    tg.ready();
    tg.expand();
  }

  var OPEN_METEO = "https://api.open-meteo.com/v1/forecast";
  var TELEGRAM_BOT_URL = window.TELEGRAM_BOT_URL || "https://t.me/Russianweather1_bot";
  var map = null;
  var slugToMarker = {};
  var citiesData = [];

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
    var symbols = {
      moscow: "\u{1F3DB}", spb: "\u{26F2}", novosibirsk: "\u{1F3AD}", yekaterinburg: "\u{26EA}", kazan: "\u{1F54C}",
      krasnoyarsk: "\u{26F0}", nizhny_novgorod: "\u{1F3D8}", chelyabinsk: "\u{1F3ED}", ufa: "\u{1F4CD}", krasnodar: "\u{1F3D6}",
      samara: "\u{2693}", rostov_on_don: "\u{1F6A4}", omsk: "\u{1F3E2}", voronezh: "\u{1F30A}", perm: "\u{1F3F0}",
      volgograd: "\u{1F4AA}", saratov: "\u{1F3A4}", tyumen: "\u{1F3D7}", tolyatti: "\u{1F697}", mahachkala: "\u{1F54C}",
      barnaul: "\u{1F333}", izhevsk: "\u{2692}", khabarovsk: "\u{1F6E5}", ulyanovsk: "\u{1F4DA}", irkutsk: "\u{1F30A}",
      vladivostok: "\u{1F6A4}", yaroslavl: "\u{1F3D8}", stavropol: "\u{1F3D6}", sevastopol: "\u{2693}", naberezhnye_chelny: "\u{1F54C}",
      tomsk: "\u{1F332}", balashikha: "\u{1F3E0}", kemerovo: "\u{26CF}", orenburg: "\u{1F3D8}", novokuznetsk: "\u{26CF}",
      ryazan: "\u{1F3D8}", donetsk: "\u{1F4CD}", luhansk: "\u{1F4CD}", tula: "\u{2694}", kirov: "\u{1F3D8}", kaliningrad: "\u{1F3F0}",
      bryansk: "\u{1F3D8}", kursk: "\u{1F3D8}", magnitogorsk: "\u{2692}", sochi: "\u{1F3D6}", vladikavkaz: "\u{26F0}", grozny: "\u{1F3D8}",
      tambov: "\u{1F3D8}", ivanovo: "\u{1F3ED}", tver: "\u{1F3D8}", simferopol: "\u{1F3D8}", kostroma: "\u{1F54C}",
      volzhsky: "\u{1F30A}", taganrog: "\u{2693}", sterlitamak: "\u{1F3ED}", komsomolsk_na_amure: "\u{1F6A4}", petrozavodsk: "\u{1F3D6}",
      lipetsk: "\u{2692}", arhangelsk: "\u{2693}", cheboksary: "\u{1F3D8}", kaluga: "\u{1F3D8}", smolensk: "\u{1F3D8}"
    };
    return symbols[slug] || "\u{1F3D8}";
  }

  function makeMarkerHtml(name, tempStr, symbol) {
    var sym = symbol || "\u{1F3D8}";
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
        "<div class=\"popup-title\">" + getCitySymbol(c.slug) + " " + escapeHtml(c.name_ru) + "</div>" +
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
          "<div class=\"popup-title\">" + getCitySymbol(c.slug) + " " + escapeHtml(c.name_ru) + "</div>" +
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

  loadCities()
    .then(initMap)
    .catch(function (e) {
      console.error(e);
      document.getElementById("map").innerHTML =
        "<p style=\"padding:12px;font-size:0.9rem;color:#c0392b;\">Не удалось загрузить карту городов.</p>";
    });
})();
