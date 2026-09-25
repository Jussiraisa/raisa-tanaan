/* Fiilis TV keepalive v108 — LG / Android kello & energiasäästö.
   Liikkuva video (täysi peitto + nurkka) + AudioContext + pehmeä reload ~12 min.
   Lataa: <script src="lg-keepalive.js?v=108" defer></script> */
(function () {
  if (window.__fiilisKeepAlive) return;
  window.__fiilisKeepAlive = true;

  var BUILD = "108";
  var RELOAD_MS = 12 * 60 * 1000;

  var STYLE = [
    "#fiilisKeepAliveVideo{",
    "position:fixed;inset:0;width:100vw;height:100vh;z-index:2147483000;",
    "opacity:0.045;pointer-events:none;border:0;outline:none;object-fit:cover;",
    "background:#000;}",
    "#fiilisKeepAliveCorner{",
    "position:fixed;right:0;bottom:0;width:180px;height:101px;z-index:2147483001;",
    "opacity:0.18;pointer-events:none;border:0;outline:none;object-fit:cover;",
    "background:#000;}",
    "#fiilisKeepAliveFrame{",
    "position:fixed;left:0;bottom:0;width:120px;height:68px;z-index:2147483002;",
    "opacity:0.12;pointer-events:none;border:0;overflow:hidden;}"
  ].join("");

  function injectStyle() {
    if (document.getElementById("fiilisKeepAliveStyle")) return;
    var s = document.createElement("style");
    s.id = "fiilisKeepAliveStyle";
    s.textContent = STYLE;
    (document.head || document.documentElement).appendChild(s);
  }

  function makeVideo(id) {
    var old = document.getElementById(id);
    if (old && old.parentNode) old.parentNode.removeChild(old);
    var v = document.createElement("video");
    v.id = id;
    v.muted = true;
    v.defaultMuted = true;
    v.autoplay = true;
    v.loop = true;
    v.playsInline = true;
    v.setAttribute("muted", "");
    v.setAttribute("autoplay", "");
    v.setAttribute("loop", "");
    v.setAttribute("playsinline", "");
    v.setAttribute("webkit-playsinline", "");
    v.setAttribute("preload", "auto");
    v.setAttribute("aria-hidden", "true");
    v.tabIndex = -1;
    var bust = "v=" + BUILD + "&t=" + (Date.now() / 600000 | 0);
    [
      { src: "lg-keepalive.webm?" + bust, type: "video/webm" },
      { src: "lg-keepalive.mp4?" + bust, type: "video/mp4" }
    ].forEach(function (s) {
      var el = document.createElement("source");
      el.src = s.src;
      el.type = s.type;
      v.appendChild(el);
    });
    document.body.appendChild(v);
    return v;
  }

  function playHard(v) {
    if (!v) return;
    try {
      v.muted = true;
      v.volume = 0;
      var p = v.play();
      if (p && p.catch) p.catch(function () {});
    } catch (e) {}
  }

  function attachCanvas(v) {
    try {
      var c = document.createElement("canvas");
      c.width = 320;
      c.height = 180;
      var ctx = c.getContext("2d", { alpha: false });
      if (!ctx || !c.captureStream) return false;
      function paint() {
        var t = Date.now() / 1000;
        ctx.fillStyle = "#050505";
        ctx.fillRect(0, 0, 320, 180);
        for (var i = 0; i < 8; i++) {
          var x = ((Math.sin(t * 0.7 + i) + 1) * 0.5 * 300) | 0;
          var y = ((Math.cos(t * 0.9 + i * 0.6) + 1) * 0.5 * 160) | 0;
          ctx.fillStyle = "rgb(" + (8 + i) + "," + (6 + i) + "," + (4 + i) + ")";
          ctx.fillRect(x, y, 12, 12);
        }
      }
      paint();
      while (v.firstChild) v.removeChild(v.firstChild);
      v.removeAttribute("src");
      v.srcObject = c.captureStream(10);
      setInterval(paint, 100);
      playHard(v);
      return true;
    } catch (e) {
      return false;
    }
  }

  function startAudio() {
    try {
      var AC = window.AudioContext || window.webkitAudioContext;
      if (!AC) return null;
      var ac = new AC();
      var osc = ac.createOscillator();
      var gain = ac.createGain();
      gain.gain.value = 0.00002;
      osc.frequency.value = 38;
      osc.type = "sine";
      osc.connect(gain);
      gain.connect(ac.destination);
      osc.start();
      function resume() {
        try {
          if (ac.state === "suspended") ac.resume();
        } catch (e) {}
      }
      resume();
      setInterval(resume, 15000);
      document.addEventListener("visibilitychange", resume);
      window.addEventListener("focus", resume);
      return ac;
    } catch (e) {
      return null;
    }
  }

  function requestWake() {
    try {
      if (navigator.wakeLock && navigator.wakeLock.request) {
        navigator.wakeLock.request("screen").then(function (lock) {
          window.__fiilisWakeLock = lock;
        }).catch(function () {});
      }
    } catch (e) {}
  }

  function softReload() {
    try {
      var u = new URL(window.location.href);
      u.searchParams.set("ka", String(Date.now()));
      u.searchParams.set("v", BUILD);
      window.location.replace(u.toString());
    } catch (e) {
      window.location.reload();
    }
  }

  function boot() {
    injectStyle();
    var legacy = document.getElementById("lgKeepAlive");
    if (legacy && legacy.parentNode) legacy.parentNode.removeChild(legacy);

    var full = makeVideo("fiilisKeepAliveVideo");
    var corner = makeVideo("fiilisKeepAliveCorner");

    function kick() {
      playHard(full);
      playHard(corner);
      requestWake();
    }

    full.addEventListener("error", function () { attachCanvas(full); });
    corner.addEventListener("error", function () { attachCanvas(corner); });
    full.addEventListener("pause", function () { setTimeout(kick, 200); });
    corner.addEventListener("pause", function () { setTimeout(kick, 200); });
    full.addEventListener("ended", kick);
    corner.addEventListener("ended", kick);
    document.addEventListener("visibilitychange", function () {
      if (!document.hidden) kick();
    });
    window.addEventListener("focus", kick);

    // Pidä dekooderi elossa seekillä
    setInterval(function () {
      try {
        if (full.readyState >= 2 && full.duration && isFinite(full.duration) && full.duration > 1) {
          full.currentTime = (full.currentTime + 0.4) % (full.duration - 0.05);
        }
        if (corner.readyState >= 2 && corner.duration && isFinite(corner.duration) && corner.duration > 1) {
          corner.currentTime = (corner.currentTime + 0.55) % (corner.duration - 0.05);
        }
      } catch (e) {}
      kick();
    }, 8000);

    startAudio();
    kick();
    setTimeout(kick, 400);
    setTimeout(kick, 1500);
    setTimeout(function () {
      if (full.readyState < 2) attachCanvas(full);
      if (corner.readyState < 2) attachCanvas(corner);
      kick();
    }, 3000);
    setInterval(requestWake, 40000);

    // Nollaa TV:n idle-ajastin pehmeällä reloadilla (~12 min)
    setTimeout(softReload, RELOAD_MS);
  }

  if (document.body) boot();
  else document.addEventListener("DOMContentLoaded", boot);
})();
