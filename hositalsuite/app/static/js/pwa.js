/* Add-to-phone. Chrome on Android fires beforeinstallprompt; others get a how-to. */
(function () {
  "use strict";
  if (window.matchMedia && window.matchMedia("(display-mode: standalone)").matches) return;
  if (window.navigator.standalone) return;
  try { if (localStorage.getItem("hs-install-hide") === "1") return; } catch (e) {}

  var bar = document.getElementById("install-bar");
  var how = document.getElementById("install-how");
  var btn = document.getElementById("install-btn");
  var dismiss = document.getElementById("install-dismiss");
  var ok = document.getElementById("install-how-ok");
  if (!bar) return;

  var deferred = null;
  window.addEventListener("beforeinstallprompt", function (e) {
    e.preventDefault();
    deferred = e;
    bar.hidden = false;
  });

  // iPhone / older Android: show the bar after a short wait so the page loads first.
  setTimeout(function () {
    if (!deferred && bar.hidden) bar.hidden = false;
  }, 1800);

  if (btn) btn.addEventListener("click", function () {
    if (deferred && deferred.prompt) {
      deferred.prompt();
      deferred.userChoice.then(function () { bar.hidden = true; deferred = null; });
      return;
    }
    if (how) how.hidden = false;
  });
  if (dismiss) dismiss.addEventListener("click", function () {
    bar.hidden = true;
    try { localStorage.setItem("hs-install-hide", "1"); } catch (e) {}
  });
  if (ok) ok.addEventListener("click", function () { if (how) how.hidden = true; });

  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(function () {});
  }
})();
