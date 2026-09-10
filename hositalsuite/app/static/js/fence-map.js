/* Drag the pin, stretch the circle. Free OpenStreetMap — no Google bill.
   As soon as Location is on, the pin jumps to the phone. Save is still a tap. */
(function () {
  function num(id, fallback) {
    var el = document.getElementById(id);
    var v = el && el.value ? parseFloat(el.value) : NaN;
    return isFinite(v) ? v : fallback;
  }
  function write(id, value) {
    var el = document.getElementById(id);
    if (el) el.value = value;
  }
  function setLabel(id, text) {
    var el = document.getElementById(id || "");
    if (el) el.textContent = text;
  }
  function boot(opts) {
    if (!window.L) return;
    var latId = opts.latId;
    var lngId = opts.lngId;
    var radId = opts.radId;
    var mapId = opts.mapId;
    var host = document.getElementById(mapId);
    if (!host) return;

    var LAGOS = [6.5244, 3.3792];
    var hadPin = isFinite(num(latId, NaN)) && isFinite(num(lngId, NaN));
    var startLat = num(latId, LAGOS[0]);
    var startLng = num(lngId, LAGOS[1]);
    var startR = Math.max(50, Math.min(2000, num(radId, 200) || 200));
    var userMoved = false;
    var watchId = null;
    var located = false;
    var auto = opts.autoLocate !== false;

    var map = L.map(mapId, { scrollWheelZoom: true }).setView([startLat, startLng], 16);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "&copy; OpenStreetMap"
    }).addTo(map);

    var marker = L.marker([startLat, startLng], { draggable: true }).addTo(map);
    var circle = L.circle([startLat, startLng], {
      radius: startR, color: "#0e5a8a", fillColor: "#12b5a5", fillOpacity: 0.18, weight: 2
    }).addTo(map);

    function syncFields() {
      var p = marker.getLatLng();
      write(latId, p.lat.toFixed(6));
      write(lngId, p.lng.toFixed(6));
      write(radId, String(Math.round(circle.getRadius())));
      if (!located) {
        setLabel(opts.labelId, "Circle is " + Math.round(circle.getRadius()) +
          " metres. Drag the pin or the edge.");
      }
    }
    function moveBoth(ll, fromGps) {
      marker.setLatLng(ll);
      circle.setLatLng(ll);
      if (fromGps) located = true;
      syncFields();
      if (fromGps) {
        setLabel(opts.labelId, "Pin is where you are standing. Stretch the circle, then tap Save.");
      }
    }
    function stopWatch() {
      if (watchId != null && navigator.geolocation) {
        navigator.geolocation.clearWatch(watchId);
        watchId = null;
      }
    }
    function applyGps(pos) {
      if (userMoved || !pos || !pos.coords) return;
      var ll = L.latLng(pos.coords.latitude, pos.coords.longitude);
      moveBoth(ll, true);
      map.setView(ll, 17);
      stopWatch();
      if (window.hmsVoice && window.hmsVoice.speak) {
        window.hmsVoice.speak("Pin dropped where you are standing. Stretch the circle, then tap save.");
      }
    }
    function waiting() {
      setLabel(opts.labelId, "Turn on Location. The pin will drop by itself.");
    }

    marker.on("drag", function (ev) {
      userMoved = true;
      stopWatch();
      located = false;
      moveBoth(ev.latlng, false);
    });
    map.on("click", function (ev) {
      userMoved = true;
      stopWatch();
      located = false;
      moveBoth(ev.latlng, false);
    });

    var stretching = false;
    circle.on("mousedown", function (ev) {
      L.DomEvent.stop(ev);
      stretching = true;
      map.dragging.disable();
    });
    map.on("mousemove", function (ev) {
      if (!stretching) return;
      var metres = map.distance(marker.getLatLng(), ev.latlng);
      circle.setRadius(Math.max(50, Math.min(2000, metres)));
      syncFields();
    });
    map.on("mouseup mouseout", function () {
      if (!stretching) return;
      stretching = false;
      map.dragging.enable();
    });

    var rad = document.getElementById(radId);
    if (rad) {
      rad.addEventListener("input", function () {
        var n = parseInt(rad.value, 10);
        if (!isFinite(n)) return;
        circle.setRadius(Math.max(50, Math.min(2000, n)));
        syncFields();
      });
    }
    ["lat", "lng"].forEach(function (kind) {
      var el = document.getElementById(kind === "lat" ? latId : lngId);
      if (!el) return;
      el.addEventListener("change", function () {
        var la = num(latId, startLat);
        var ln = num(lngId, startLng);
        userMoved = true;
        stopWatch();
        moveBoth(L.latLng(la, ln), false);
        map.panTo([la, ln]);
      });
    });

    function askOnce() {
      if (!navigator.geolocation || userMoved) return;
      navigator.geolocation.getCurrentPosition(applyGps, function () {
        if (!located && !userMoved) waiting();
      }, { enableHighAccuracy: true, timeout: 8000, maximumAge: 5000 });
    }
    function startWatch() {
      if (!auto || !navigator.geolocation || userMoved) return;
      waiting();
      askOnce();
      if (watchId != null) return;
      watchId = navigator.geolocation.watchPosition(applyGps, function () {
        if (!located && !userMoved) waiting();
      }, { enableHighAccuracy: true, timeout: 12000, maximumAge: 5000 });
      setTimeout(stopWatch, 120000);
    }

    if (opts.locateBtn) {
      var btn = document.getElementById(opts.locateBtn);
      if (btn && navigator.geolocation) {
        btn.addEventListener("click", function () {
          userMoved = false;
          located = false;
          startWatch();
        });
      }
    }

    if (navigator.permissions && navigator.permissions.query) {
      navigator.permissions.query({ name: "geolocation" }).then(function (p) {
        p.onchange = function () {
          if (p.state === "granted" && !userMoved) startWatch();
        };
      }).catch(function () {});
    }

    setTimeout(function () { map.invalidateSize(); }, 200);
    if (hadPin) syncFields();
    if (auto) startWatch();
  }
  window.hmsFenceMap = { boot: boot };
})();
