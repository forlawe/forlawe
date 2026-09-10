/* Push v2 — alarm-like, works closed, multi-browser, slow internet optimized, premium */
(function(){
  "use strict";

  window.hmsPush = {
    isSupported: function(){
      return ('serviceWorker' in navigator) && ('PushManager' in window) && ('Notification' in window);
    },

    getBrowser: function(){
      var ua = navigator.userAgent.toLowerCase();
      if(ua.indexOf("edg") !== -1) return "edge";
      if(ua.indexOf("opr") !== -1 || ua.indexOf("opera") !== -1) return "opera";
      if(ua.indexOf("samsungbrowser") !== -1) return "samsung";
      if(ua.indexOf("ucbrowser") !== -1 || ua.indexOf("uc browser") !== -1) return "uc";
      if(ua.indexOf("firefox") !== -1 || ua.indexOf("fxios") !== -1) return "firefox";
      if(ua.indexOf("safari") !== -1 && ua.indexOf("chrome") === -1) return "safari";
      if(ua.indexOf("chrome") !== -1) return "chrome";
      return "unknown";
    },

    // Convert VAPID public key
    urlBase64ToUint8Array: function(base64String){
      var padding = "=".repeat((4 - base64String.length % 4) % 4);
      var base64 = (base64String + padding).replace(/\-/g, "+").replace(/_/g, "/");
      var rawData = atob(base64);
      var outputArray = new Uint8Array(rawData.length);
      for(var i=0;i<rawData.length;i++) outputArray[i]=rawData.charCodeAt(i);
      return outputArray;
    },

    buf2base64: function(buf){
      var binary = ""; var bytes = new Uint8Array(buf);
      for(var i=0;i<bytes.byteLength;i++) binary+=String.fromCharCode(bytes[i]);
      return btoa(binary);
    },

    enable: function(accessKey){
      var self = this;
      if(!self.isSupported()){
        alert("Push not supported on this browser.\n\nProvision for feature phones & old browsers:\n- Main TV in waiting hall will call your number\n- Voice announcements in 4 languages\n- USSD *xxx# to check queue\n- Ask staff for help\n\nNo app install needed.");
        return Promise.reject("not supported");
      }

      if(Notification.permission === "denied"){
        alert("Notifications blocked in browser settings.\n\nTo enable:\nChrome: Settings > Privacy > Notifications > Allow\nFirefox: Settings > Privacy > Permissions > Notifications\nSafari: Settings > Websites > Notifications\n\nMeanwhile Main TV + voice will call you.");
        return Promise.reject("denied");
      }

      // Safari needs PWA installed
      var browser = self.getBrowser();
      if(browser === "safari"){
        var isStandalone = window.matchMedia && window.matchMedia("(display-mode: standalone)").matches || window.navigator.standalone;
        if(!isStandalone){
          alert("iPhone Safari: To get alarm-like notifications when closed:\n1. Tap Share button\n2. Add to Home Screen\n3. Open from home screen\n4. Then enable notifications\n\nThis is Apple requirement. Android Chrome works without install.");
          // Still try
        }
      }

      return Notification.requestPermission().then(function(perm){
        if(perm !== "granted") throw new Error("permission not granted");

        var vapidUrl = "/api/v1/push/vapid-public";
        if(accessKey) vapidUrl += "?access_key=" + encodeURIComponent(accessKey);

        return fetch(vapidUrl).then(function(r){return r.json();}).then(function(data){
          var publicKey = data.public_key;
          if(!publicKey) throw new Error("VAPID not configured on server");

          return navigator.serviceWorker.ready.then(function(reg){
            return reg.pushManager.subscribe({
              userVisibleOnly: true,
              applicationServerKey: self.urlBase64ToUint8Array(publicKey)
            }).then(function(sub){
              var payload = {
                endpoint: sub.endpoint,
                keys: {
                  p256dh: self.buf2base64(sub.getKey("p256dh")),
                  auth: self.buf2base64(sub.getKey("auth"))
                },
                device_info: navigator.userAgent,
                access_key: accessKey || null
              };

              return fetch("/api/v1/push/subscribe", {
                method: "POST",
                headers: {"Content-Type":"application/json"},
                body: JSON.stringify(payload)
              }).then(function(r){return r.json();}).then(function(res){
                if(res.ok){
                  try { localStorage.setItem("hms-push-ok","1"); } catch(e){}
                  // Show test notification
                  if(reg.showNotification){
                    reg.showNotification("✅ Alarm Mode ON", {
                      body: "You will be notified even when app closed, like alarm! Works on slow internet.",
                      icon: "/branding/logo",
                      badge: "/static/icons/icon-192.png",
                      vibrate: [200,100,200],
                      tag: "hs-enabled"
                    });
                  }
                  return res;
                } else {
                  throw new Error(res.error || "subscribe failed");
                }
              });
            });
          });
        });
      });
    },

    disable: function(){
      if(!('serviceWorker' in navigator)) return Promise.resolve();
      return navigator.serviceWorker.ready.then(function(reg){
        return reg.pushManager.getSubscription().then(function(sub){
          if(!sub) return;
          var endpoint = sub.endpoint;
          return sub.unsubscribe().then(function(){
            return fetch("/api/v1/push/unsubscribe", {
              method: "POST",
              headers: {"Content-Type":"application/json"},
              body: JSON.stringify({endpoint:endpoint})
            });
          });
        });
      });
    },

    test: function(){
      return fetch("/api/v1/push/test", {method:"POST"}).then(function(r){return r.json();}).then(function(data){
        if(data.ok){
          alert("✅ Test push queued! Close the app now — you should get notification even when closed, like alarm.");
        } else {
          alert("Test failed: " + (data.error || "unknown") + "\n\nMake sure you enabled push first.");
        }
        return data;
      });
    }
  };

  // Auto-register SW for all browsers
  if('serviceWorker' in navigator){
    navigator.serviceWorker.register("/sw.js", {scope:"/"}).then(function(reg){
      // Check for updates
      reg.addEventListener("updatefound", function(){
        var newWorker = reg.installing;
        newWorker.addEventListener("statechange", function(){
          if(newWorker.state === "installed" && navigator.serviceWorker.controller){
            // New version available — show banner
            var banner = document.createElement("div");
            banner.style.cssText = "position:fixed;bottom:20px;left:50%;transform:translateX(-50%);background:#000;color:#FFD700;padding:12px 20px;border-radius:999px;font-weight:700;z-index:9999;box-shadow:0 4px 20px rgba(0,0,0,0.3)";
            banner.innerHTML = "🔄 New version available <button onclick='window.location.reload()' style='margin-left:10px;background:#FFD700;color:#000;border:none;padding:6px 12px;border-radius:999px;font-weight:800'>Update</button>";
            document.body.appendChild(banner);
          }
        });
      });
    }).catch(function(){});

    // Listen for SYNC_QUEUE message from SW
    navigator.serviceWorker.addEventListener("message", function(event){
      var msg = event.data || {};
      if(msg.type === "SYNC_QUEUE"){
        try {
          var raw = localStorage.getItem("hms-sync-queue");
          if(raw){
            var queue = JSON.parse(raw);
            if(queue.length > 0){
              // Try sync via app.js trySyncQueue
              if(window.hmsQueueSubmit){
                // Triggered
              }
            }
          }
        } catch(e){}
      }
    });
  }

  // Feature phone & old browser detection — show provision note
  window.hmsFeaturePhoneCheck = function(){
    var ua = navigator.userAgent.toLowerCase();
    var isOld = !('fetch' in window) || !('Promise' in window) || ua.indexOf("opera mini") !== -1 || ua.indexOf("kaios") !== -1;
    if(isOld){
      console.log("Feature phone or old browser detected — provision: Main TV + voice + USSD, no push");
      // Show banner for feature phones
      var banner = document.getElementById("feature-phone-banner");
      if(banner) banner.style.display = "block";
    }
  };
})();
