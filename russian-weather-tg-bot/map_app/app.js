(function () {
  "use strict";

  var tg = window.Telegram && window.Telegram.WebApp;
  if (tg) {
    tg.ready();
    tg.expand();
  }

  var OPEN_METEO = "https://api.open-meteo.com/v1/forecast";
  var TELEGRAM_BOT_URL = window.TELEGRAM_BOT_URL || "https://t.me/Russianweather1_bot";

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

  function makeMarkerHtml(name, tempStr) {
    return "<div class=\"city-marker-wrap\">" +
      "<div class=\"city-marker-temp\">" + escapeHtml(tempStr) + "</div>" +
      "<div class=\"city-marker-name\">" + escapeHtml(name) + "</div>" +
      "<div class=\"city-marker-dot\"></div>" +
      "</div>";
  }

  function initMap(cities) {
    setLogoLink();

    var map = L.map("map", {
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
    var slugToMarker = {};

    cities.forEach(function (c) {
      var tempStr = "—°";
      var icon = L.divIcon({
        className: "city-marker-div",
        html: makeMarkerHtml(c.name_ru, tempStr),
        iconSize: [110, 58],
        iconAnchor: [55, 56]
      });

      var m = L.marker([c.lat, c.lon], { icon: icon });

      var popupHtml =
        "<div class=\"popup-title\">" + escapeHtml(c.name_ru) + "</div>" +
        "<div class=\"popup-temp\">— °C</div>" +
        "<div class=\"popup-actions\"><a href=\"" + weatherUrlBase + encodeURIComponent(c.slug) + "\" data-slug=\"" + c.slug + "\">Открыть погоду</a></div>";

      m.bindPopup(popupHtml);
      m.addTo(map);
      slugToMarker[c.slug] = { marker: m, city: c };

      fetchCurrentTemp(c.lat, c.lon).then(function (t) {
        var str = (t != null ? (t > 0 ? "+" : "") + t + "°" : "—°");
        m.setIcon(L.divIcon({
          className: "city-marker-div",
          html: makeMarkerHtml(c.name_ru, str),
          iconSize: [110, 58],
          iconAnchor: [55, 56]
        }));
        var newTempText = (t != null ? (t > 0 ? "+" : "") + t + " °C" : "—");
        var newPopupHtml =
          "<div class=\"popup-title\">" + escapeHtml(c.name_ru) + "</div>" +
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
  }

  loadCities()
    .then(initMap)
    .catch(function (e) {
      console.error(e);
      document.getElementById("map").innerHTML =
        "<p style=\"padding:12px;font-size:0.9rem;color:#c0392b;\">Не удалось загрузить карту городов.</p>";
    });
})();
