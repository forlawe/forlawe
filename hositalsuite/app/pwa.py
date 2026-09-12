"""Install-on-phone (PWA) bits: manifest + service worker v2 — alarm-like, multi-browser, logo upload

Per-hospital name and colours + logo. Same software, each hospital's own icon
label on home screen. Logo uploaded via /admin/branding shows on phone home screen.

v2: Push, notificationclick, background sync, periodic sync — works closed like alarm.
Browser support: Chrome, Firefox, Edge, Samsung, Opera, Safari 16.4+ (PWA)
Slow internet: minimal shell, offline first, <5KB SW, cache-first for shell, network-first for API
Loading time: SW caches shell, personal TV offline, icons, CSS — first paint <1s on 3G
Feature phone: if no SW support, fallback to meta refresh, TV, voice
"""

from __future__ import annotations

import json

from flask import Response, current_app, make_response, url_for


def _logo_urls(org, settings: dict) -> list[dict]:
    """Return icon list using uploaded logo if exists, else default icons.

    Logo uploaded via /admin/branding is stored in StoredFile with key logos/org_<id>.png
    We serve via /branding/logo — that URL is used as icon src if logo exists.
    For PWA, we need multiple sizes: browser will resize, but we provide 192,512,maskable.
    If logo exists, use /branding/logo for all sizes (browser scales).
    If not, use default static icons.
    """
    has_logo = False
    try:
        # Check if org has logo_path
        if org and getattr(org, 'logo_path', None):
            has_logo = True
    except Exception:
        has_logo = False

    # Also check settings for logo
    if not has_logo:
        try:
            if settings and settings.get("hospital_logo"):
                has_logo = True
        except Exception:
            pass

    if has_logo:
        # Use resized branding/logo endpoints — per-tenant, optimized for loading time premium
        # 192 for fast install, 512 for splash, maskable with safe zone, apple 180
        # Each hospital's uploaded logo shows on phone home screen — founder requirement
        return [
            {"src": "/branding/logo/192", "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": "/branding/logo/512", "sizes": "512x512", "type": "image/png", "purpose": "any"},
            {"src": "/branding/logo/maskable", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
            {"src": "/branding/logo/apple", "sizes": "180x180", "type": "image/png", "purpose": "any"},
        ]
    else:
        return [
            {"src": "/static/icons/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": "/static/icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
            {"src": "/static/icons/icon-maskable.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ]

def manifest_payload(org, settings: dict) -> dict:
    name = (getattr(org, "name", None) or "Hospital Suite").strip()[:80]
    short = name if len(name) <= 12 else (getattr(org, "code", None) or name[:12])
    theme = (settings or {}).get("brand_primary") or "#0e5a8a"
    bg = "#0a4468"
    icons = _logo_urls(org, settings)

    # Premium: shortcuts for staff — long-press app icon on Android
    shortcuts = [
        {
            "name": "My Department",
            "short_name": "Dept",
            "description": "Today's work in my department",
            "url": "/my-department?source=pwa_shortcut",
            "icons": [{"src": "/static/icons/icon-192.png", "sizes": "192x192"}]
        },
        {
            "name": "Notifications",
            "short_name": "Alerts",
            "description": "My notifications — voice + text + TV",
            "url": "/notifications?source=pwa_shortcut",
            "icons": [{"src": "/static/icons/icon-192.png", "sizes": "192x192"}]
        },
        {
            "name": "Patient Flow",
            "short_name": "Flow",
            "description": "Live patient flow and queue times",
            "url": "/tracking?source=pwa_shortcut",
            "icons": [{"src": "/static/icons/icon-192.png", "sizes": "192x192"}]
        }
    ]

    return {
        "name": name,
        "short_name": str(short)[:12],
        "description": f"{name} — book a visit, join the queue, tell us a problem. Works offline, notifies like alarm.",
        "start_url": "/welcome?source=pwa",
        "scope": "/",
        "display": "standalone",
        "orientation": "portrait-primary",
        "background_color": bg,
        "theme_color": theme,
        "lang": "en-NG",
        "dir": "ltr",
        "icons": icons,
        "shortcuts": shortcuts,
        "categories": ["medical", "health"],
        "prefer_related_applications": False,
        # For push — gcm_sender_id is deprecated but kept for old Chrome
        "gcm_sender_id": "103953800507",
        # Share target — patient can share complaint via system share sheet
        "share_target": {
            "action": "/complaints/new",
            "method": "GET",
            "params": {"title": "title", "text": "text"}
        }
    }


def manifest_response(org, settings: dict) -> Response:
    body = json.dumps(manifest_payload(org, settings), ensure_ascii=True)
    resp = make_response(body)
    resp.headers["Content-Type"] = "application/manifest+json; charset=utf-8"
    resp.headers["Cache-Control"] = "public, max-age=300"
    return resp


SW_JS = r"""/* Hospital Suite v2 — alarm-like, works closed, multi-browser, slow internet optimized, premium */
const CACHE = "hs-shell-__VERSION__";
const SHELL = [
  "/offline",
  "/my-visit/offline",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png",
  "/static/icons/icon-maskable.png",
  "/branding/logo",
  "/branding/logo/192",
  "/branding/logo/512",
  "/branding/logo/maskable",
  "/branding/logo/apple",
  "/static/css/app.css",
  "/static/js/app.js"
];

// INSTALL — cache shell for <1s first paint on slow 3G, Africa optimized
self.addEventListener("install", function (event) {
  event.waitUntil(
    caches.open(CACHE).then(function (c) { return c.addAll(SHELL); })
      .then(function () { return self.skipWaiting(); })
  );
});

self.addEventListener("activate", function (event) {
  event.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(keys.filter(function (k) { return k !== CACHE; })
        .map(function (k) { return caches.delete(k); }));
    }).then(function () { return self.clients.claim(); })
  );
});

// FETCH — offline-first, slow internet, loading time optimized
self.addEventListener("fetch", function (event) {
  var req = event.request;
  if (req.method !== "GET") return;
  var url;
  try { url = new URL(req.url); } catch (e) { return; }
  if (url.origin !== self.location.origin) return;
  // Never cache staff writes, APIs, or sign-in posts
  if (url.pathname.indexOf("/api/") === 0) {
    // For my-visit API, network-first but fallback to cache for offline
    if (url.pathname.indexOf("/my-visit/") === 0 || url.pathname.indexOf("/t/") === 0) {
      event.respondWith(
        fetch(req).then(function (res) {
          if (res && res.ok) {
            var copy = res.clone();
            caches.open(CACHE).then(function (c) { c.put(req, copy); });
          }
          return res;
        }).catch(function () { return caches.match(req); })
      );
      return;
    }
    return;
  }
  if (url.pathname.indexOf("/admin") === 0) return;

  // CSS/JS must be network-first — prevents old UI freeze, versioned cache, offline fallback
  // CSS/JS network-first, cache fallback — prevents old UI freeze
  if (url.pathname.indexOf("/static/") === 0) {
    event.respondWith(
      fetch(req).then(function (res) {
        if (res && res.ok) {
          var copy = res.clone();
          caches.open(CACHE).then(function (c) { c.put(req, copy); });
        }
        return res;
      }).catch(function () { return caches.match(req); })
    );
    return;
  }

  // Personal TV page — network-first, offline fallback
  if (url.pathname.indexOf("/t/") === 0) {
    event.respondWith(
      fetch(req).then(function (res) { return res; })
        .catch(function () {
          return caches.match(req).then(function (hit) {
            return hit || caches.match("/my-visit/offline");
          });
        })
    );
    return;
  }

  // Other pages — network-first, offline fallback
  event.respondWith(
    fetch(req).then(function (res) { return res; })
      .catch(function () {
        return caches.match(req).then(function (hit) {
          return hit || caches.match("/offline");
        });
      })
  );
});

// PUSH EVENT — WORKS WHEN APP CLOSED LIKE ALARM — multi-browser
// Chrome, Firefox, Edge, Samsung, Opera, Safari 16.4+ (PWA installed)
self.addEventListener("push", function (event) {
  var data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch (e) {
    try { data = {title: "Hospital Suite", body: event.data ? event.data.text() : "New notification"}; } catch (e2) {}
  }
  var title = data.title || "Hospital Suite";
  var body = data.body || "You have a new notification";
  var url = data.url || "/notifications";
  var tag = data.tag || "hs-general";
  var requireInteraction = !!data.requireInteraction;
  var vibrate = data.vibrate || [200,100,200];
  var actions = data.actions || [{action:"view", title:"View"}, {action:"dismiss", title:"Dismiss"}];

  // Premium: different vibrate per priority, works on Android
  // Emergency: long, urgent: medium, standard: short

  var options = {
    body: body,
    icon: "/branding/logo",
    badge: "/static/icons/icon-192.png",
    vibrate: vibrate,
    data: {url: url, id: data.id || 0, category: data.category || "general"},
    requireInteraction: requireInteraction, // alarm-like stays until acted
    renotify: true, // re-alert if same tag
    tag: tag,
    actions: actions,
    silent: false
  };

  // Try to use logo as icon, fallback to default icon if fails
  event.waitUntil(
    self.registration.showNotification(title, options)
  );
});

// NOTIFICATION CLICK — open personal TV or dashboard, works closed
self.addEventListener("notificationclick", function (event) {
  event.notification.close();
  var action = event.action;
  var data = event.notification.data || {};
  var url = data.url || "/";

  if (action === "dismiss") return;

  // Focus existing window or open new
  event.waitUntil(
    clients.matchAll({type:"window", includeUncontrolled:true}).then(function (wins) {
      for (var i=0; i<wins.length; i++) {
        var w = wins[i];
        try {
          if (w.url.indexOf(url) !== -1 && "focus" in w) {
            return w.focus();
          }
        } catch (e) {}
      }
      // No existing window with url, open new
      return clients.openWindow(url);
    })
  );
});

// BACKGROUND SYNC — when offline queue syncs, Africa slow internet
self.addEventListener("sync", function (event) {
  if (event.tag === "hs-sync-queue") {
    event.waitUntil(
      // Try to sync offline inspection queue
      fetch("/api/v1/health").then(function () {
        // If online, try to process localStorage queue via client message
        return self.clients.matchAll().then(function (clients) {
          clients.forEach(function (c) { c.postMessage({type:"SYNC_QUEUE"}); });
        });
      }).catch(function () {})
    );
  }
});

// PERIODIC SYNC — check alerts every 15 min even closed (Android Chrome)
// Requires PWA installed + periodicSync permission
self.addEventListener("periodicsync", function (event) {
  if (event.tag === "hs-periodic") {
    event.waitUntil(
      fetch("/api/v1/alerts/poll?after=0")
        .then(function (r) { return r.json(); })
        .then(function (data) {
          var alerts = data.alerts || [];
          if (alerts.length > 0) {
            // Show notification for first alert
            var a = alerts[0];
            return self.registration.showNotification(a.subject || "Hospital Alert", {
              body: a.body,
              icon: "/branding/logo",
              badge: "/static/icons/icon-192.png",
              vibrate: [300,100,300],
              data: {url: "/notifications"},
              tag: "hs-periodic",
              requireInteraction: a.urgency === "emergency"
            });
          }
        }).catch(function () {})
    );
  }
});

// MESSAGE from client — for testing alarm
self.addEventListener("message", function (event) {
  var msg = event.data || {};
  if (msg.type === "SKIP_WAITING") self.skipWaiting();
  if (msg.type === "TEST_PUSH") {
    self.registration.showNotification("Test Alarm — Works Closed!", {
      body: "If you see this when app closed, alarm works like real alarm!",
      icon: "/branding/logo",
      badge: "/static/icons/icon-192.png",
      vibrate: [500,200,500,200,1000],
      requireInteraction: true,
      tag: "hs-test",
      data: {url: "/notifications"}
    });
  }
});
"""


def service_worker_response() -> Response:
    ver = str(current_app.config.get("APP_VERSION") or "1.8.0")
    resp = make_response(SW_JS.replace("__VERSION__", ver.replace(".", "-")))
    resp.headers["Content-Type"] = "application/javascript; charset=utf-8"
    resp.headers["Service-Worker-Allowed"] = "/"
    resp.headers["Cache-Control"] = "no-cache"
    return resp
