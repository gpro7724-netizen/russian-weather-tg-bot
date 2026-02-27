(function () {
  "use strict";

  var tg = window.Telegram && window.Telegram.WebApp;
  if (tg) {
    tg.ready();
    tg.expand();
  }

  function getBaseUrl() {
    var path = window.location.pathname;
    var idx = path.lastIndexOf("/");
    return window.location.origin + (idx >= 0 ? path.substring(0, idx + 1) : "/");
  }

  function loadCities() {
    // Используем общий список городов из weather_app
    var url = getBaseUrl() + "../weather_app/cities.json";
    return fetch(url).then(function (r) {
      if (!r.ok) throw new Error("Не удалось загрузить список городов");
      return r.json();
    });
  }

  function initMap(cities) {
    var map = L.map("map", {
      zoomControl: true,
      attributionControl: true
    }).setView([61, 96], 3);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 8,
      minZoom: 2,
      attribution: "&copy; OpenStreetMap contributors"
    }).addTo(map);

    var slugToMarker = {};

    cities.forEach(function (c) {
      var m = L.circleMarker([c.lat, c.lon], {
        radius: 5,
        color: "#e74c3c",
        weight: 2,
        fillColor: "#ff6b4a",
        fillOpacity: 0.9
      });

      var weatherUrl = "../weather_app/index.html#/city/" + encodeURIComponent(c.slug);
      var popupHtml =
        "<div class=\"popup-title\">" + c.name_ru + "</div>" +
        "<div class=\"popup-actions\"><a href=\"" + weatherUrl + "\" data-slug=\"" + c.slug + "\">Погода</a></div>";

      m.bindPopup(popupHtml);
      m.addTo(map);
      slugToMarker[c.slug] = m;
    });

    // Центровка по городу, если задан ?city=slug
    var params = new URLSearchParams(window.location.search);
    var citySlug = params.get("city");
    if (citySlug && slugToMarker[citySlug]) {
      var marker = slugToMarker[citySlug];
      map.setView(marker.getLatLng(), 5);
      marker.openPopup();
    }

    // Открытие погоды внутри Telegram WebApp, если возможно
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

