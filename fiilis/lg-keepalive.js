/* Fiilis TV keepalive v109 — TV pysyy päällä, ei näkyvää nurkkavideota.
   Video on ruudun ulkopuolella (dekooderi elossa). AudioContext + wake lock +
   pehmeä reload ~9 min nollaa LG:n kellon idle-ajastimen.
   Lataa: <script src="lg-keepalive.js?v=109" defer></script> */
(function () {
  if (window.__fiilisKeepAlive) return;
  window.__fiilisKeepAlive = true;

  var BUILD = "109";
  var RELOAD_MS = 9 * 60 * 1000;

  var STYLE = [
    "#fiilisKeepAliveVideo{",
    "position:fixed;left:-800px;top:-800px;width:64px;height:36px;",
    "opacity:0;pointer-events:none;border:0;outline:none;",
    "z-index:-1;background:transparent;}"
  ].join("");

  function injectStyle() {
    var old = document.getElementById("fiilisKeepAliveStyle");
    if (old && old.parentNode) old.parentNode.removeChild(old);
    var s = document.createElement("style");
    s.id = "fiilisKeepAliveStyle";
    s.textContent = STYLE;
    (document.head || document.documentElement).appendChild(s);
  }

  function removeVisible() {
    ["fiilisKeepAliveCorner", "fiilisKeepAliveFrame", "lgKeepAlive"].forEach(function (id) {
      var el = document.getElementById(id);
      if (el && el.parentNode) el.parentNode.removeChild(el);
    });
  }

  function makeVideo() {
    var old = document.getElementById("fiilisKeepAliveVideo");
    if (old && old.parentNode) old.parentNode.removeChild(old);
    var v = document.createElement("video");
    v.id = "fiilisKeepAliveVideo";
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
      c.width = 64;
      c.height = 36;
      var ctx = c.getContext("2d", { alpha: false });
      if (!ctx || !c.captureStream) return false;
      function paint() {
        var t = Date.now() / 1000;
        ctx.fillStyle = "#111";
        ctx.fillRect(0, 0, 64, 36);
        ctx.fillStyle = "#222";
        ctx.fillRect((t * 8) % 64, 8, 4, 4);
      }
      paint();
      while (v.firstChild) v.removeChild(v.firstChild);
      v.removeAttribute("src");
      v.srcObject = c.captureStream(8);
      setInterval(paint, 120);
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
    removeVisible();
    var full = makeVideo();

    function kick() {
      playHard(full);
      requestWake();
    }

    full.addEventListener("error", function () { attachCanvas(full); });
    full.addEventListener("pause", function () { setTimeout(kick, 200); });
    full.addEventListener("ended", kick);
    document.addEventListener("visibilitychange", function () {
      if (!document.hidden) kick();
    });
    window.addEventListener("focus", kick);

    setInterval(function () {
      try {
        if (full.readyState >= 2 && full.duration && isFinite(full.duration) && full.duration > 1) {
          full.currentTime = (full.currentTime + 0.4) % (full.duration - 0.05);
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
      kick();
    }, 3000);
    setInterval(requestWake, 40000);
    setTimeout(softReload, RELOAD_MS);
  }

  if (document.body) boot();
  else document.addEventListener("DOMContentLoaded", boot);
})();
