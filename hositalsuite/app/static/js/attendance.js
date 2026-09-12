/* Clock-in: GPS + cheat marks + offline queue. Voice reminder stays on. */
(function () {
  var KEY = "hms-att-q";

  function csrf() {
    var el = document.querySelector('input[name="_csrf"]');
    return el ? el.value : "";
  }
  function queue() {
    try { return JSON.parse(localStorage.getItem(KEY) || "[]"); }
    catch (e) { return []; }
  }
  function saveQueue(items) {
    localStorage.setItem(KEY, JSON.stringify(items));
  }
  function markMocked(pos) {
    try {
      return !!(pos && pos.coords && pos.coords.mocked === true);
    } catch (e) { return false; }
  }
  function fill(prefix, pos) {
    var lat = document.getElementById(prefix + "-lat");
    var lng = document.getElementById(prefix + "-lng");
    var acc = document.getElementById(prefix + "-acc");
    var mock = document.getElementById(prefix + "-mocked");
    var when = document.getElementById(prefix + "-when");
    if (lat) lat.value = pos.coords.latitude.toFixed(6);
    if (lng) lng.value = pos.coords.longitude.toFixed(6);
    if (acc) acc.value = Math.round(pos.coords.accuracy || 0);
    if (mock) mock.value = markMocked(pos) ? "1" : "0";
    if (when) when.value = new Date().toISOString();
  }
  function speak(text) {
    if (window.hmsVoice && window.hmsVoice.speak) window.hmsVoice.speak(text);
  }
  function enqueue(kind, form, prefix) {
    var items = queue();
    items.push({
      kind: kind,
      at: new Date().toISOString(),
      payload: {
        lat: (document.getElementById(prefix + "-lat") || {}).value || "",
        lng: (document.getElementById(prefix + "-lng") || {}).value || "",
        accuracy: (document.getElementById(prefix + "-acc") || {}).value || "",
        mocked: (document.getElementById(prefix + "-mocked") || {}).value || "0",
        client_at: (document.getElementById(prefix + "-when") || {}).value || new Date().toISOString()
      }
    });
    saveQueue(items);
    speak(kind === "out" ? "Saved. We will sign you out when the phone is back online."
                         : "Saved. We will sign you in when the phone is back online.");
    var hint = document.getElementById("gps-hint");
    if (hint) hint.textContent = "No internet. This tap is saved on the phone and will send when you are back online.";
    var btn = form.querySelector("button[type=submit]");
    if (btn) { btn.disabled = true; btn.textContent = "Saved on this phone"; }
  }
  function flush() {
    if (!navigator.onLine) return;
    var items = queue();
    if (!items.length) return;
    fetch("/attendance/sync", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": csrf()
      },
      body: JSON.stringify({ items: items })
    }).then(function (r) { return r.json(); }).then(function (body) {
      if (body && body.ok) {
        saveQueue([]);
        if (window.location.pathname.indexOf("/attendance") === 0) {
          window.location.reload();
        }
      }
    }).catch(function () {});
  }
  function bind(formId, prefix, kind, spoken) {
    var form = document.getElementById(formId);
    if (!form) return;
    form.addEventListener("submit", function (ev) {
      if (form.dataset.ready === "1") {
        speak(spoken);
        return;
      }
      ev.preventDefault();
      var hint = document.getElementById("gps-hint");
      if (hint) hint.textContent = "Finding your place…";
      function go(pos) {
        if (pos) fill(prefix, pos);
        else {
          var when = document.getElementById(prefix + "-when");
          if (when) when.value = new Date().toISOString();
        }
        if (!navigator.onLine) {
          enqueue(kind, form, prefix);
          return;
        }
        form.dataset.ready = "1";
        speak(spoken);
        form.submit();
      }
      if (!navigator.geolocation) {
        go(null);
        return;
      }
      navigator.geolocation.getCurrentPosition(go, function () { go(null); },
        { enableHighAccuracy: true, timeout: 8000, maximumAge: 15000 });
    });
  }
  bind("in-form", "in", "in", "Signing you in.");
  bind("out-form", "out", "out", "Signing you out. Thank you.");

  /* Find the phone as soon as Location is on — do not wait for the tap. */
  (function prefetch() {
    var hint = document.getElementById("gps-hint");
    var prefix = document.getElementById("in-form") ? "in"
               : (document.getElementById("out-form") ? "out" : null);
    if (!prefix || !navigator.geolocation) return;
    if (hint) hint.textContent = "Turn on Location. This page will find you by itself.";
    var watchId = null;
    function ok(pos) {
      fill(prefix, pos);
      if (hint) hint.textContent = "Place found. Tap the big button when you are ready.";
      if (watchId != null) navigator.geolocation.clearWatch(watchId);
    }
    function wait() {
      if (hint && !(document.getElementById(prefix + "-lat") || {}).value) {
        hint.textContent = "Turn on Location. This page will find you by itself.";
      }
    }
    navigator.geolocation.getCurrentPosition(ok, wait,
      { enableHighAccuracy: true, timeout: 8000, maximumAge: 5000 });
    watchId = navigator.geolocation.watchPosition(ok, wait,
      { enableHighAccuracy: true, timeout: 12000, maximumAge: 5000 });
    setTimeout(function () {
      if (watchId != null) navigator.geolocation.clearWatch(watchId);
    }, 120000);
    if (navigator.permissions && navigator.permissions.query) {
      navigator.permissions.query({ name: "geolocation" }).then(function (p) {
        p.onchange = function () {
          if (p.state === "granted") {
            navigator.geolocation.getCurrentPosition(ok, wait,
              { enableHighAccuracy: true, timeout: 8000, maximumAge: 0 });
          }
        };
      }).catch(function () {});
    }
  })();

  window.addEventListener("online", flush);
  if (document.readyState === "complete") flush();
  else window.addEventListener("load", flush);
})();
