/* Fiilis TV: pidä näyttö hereillä (LG / Android TV kello & ambient).
   Täysi peitto + liikkuva äänetön video + lähes äänetön AudioContext.
   Lataa: <script src="lg-keepalive.js?v=107"></script> */
(function () {
  if (window.__fiilisKeepAlive) return;
  window.__fiilisKeepAlive = true;

  var STYLE = [
    "#fiilisKeepAliveVideo{",
    "position:fixed;inset:0;width:100vw;height:100vh;z-index:2147483000;",
    "opacity:0.03;pointer-events:none;border:0;outline:none;object-fit:cover;",
    "background:#000;}",
    "#fiilisKeepAliveCorner{",
    "position:fixed;right:0;bottom:0;width:96px;height:54px;z-index:2147483001;",
    "opacity:0.08;pointer-events:none;border:0;outline:none;object-fit:cover;}"
  ].join("");

  function injectStyle() {
    if (document.getElementById("fiilisKeepAliveStyle")) return;
    var s = document.createElement("style");
    s.id = "fiilisKeepAliveStyle";
    s.textContent = STYLE;
    (document.head || document.documentElement).appendChild(s);
  }

  function makeVideo(id, sources) {
    var old = document.getElementById(id);
    if (old) old.parentNode && old.parentNode.removeChild(old);
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
    for (var i = 0; i < sources.length; i++) {
      var src = document.createElement("source");
      src.src = sources[i].src;
      src.type = sources[i].type;
      v.appendChild(src);
    }
    document.body.appendChild(v);
    return v;
  }

  function playHard(v) {
    try {
      v.muted = true;
      var p = v.play();
      if (p && p.catch) p.catch(function () {});
    } catch (e) {}
  }

  function attachCanvas(v) {
    try {
      var c = document.createElement("canvas");
      c.width = 160; c.height = 90;
      var ctx = c.getContext("2d", { alpha: false });
      if (!ctx || !c.captureStream) return false;
      function paint() {
        var t = Date.now() / 1000;
        for (var y = 0; y < 90; y += 6) {
          for (var x = 0; x < 160; x += 6) {
            var n = (Math.sin(x / 18 + t * 2) + Math.cos(y / 14 + t * 1.5) + 2) * 3;
            ctx.fillStyle = "rgb(" + (2 + (n | 0)) + "," + (1 + ((n * 0.7) | 0)) + ",1)";
            ctx.fillRect(x, y, 6, 6);
          }
        }
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
      if (!AC) return;
      var ac = new AC();
      var osc = ac.createOscillator();
      var gain = ac.createGain();
      // Lähes äänetön — silti "audiosoitto" monelle TV:lle
      gain.gain.value = 0.00001;
      osc.frequency.value = 40;
      osc.connect(gain);
      gain.connect(ac.destination);
      osc.start();
      function resume() {
        try {
          if (ac.state === "suspended") ac.resume();
        } catch (e) {}
      }
      resume();
      setInterval(resume, 20000);
      document.addEventListener("visibilitychange", resume);
      window.addEventListener("focus", resume);
    } catch (e) {}
  }

  function requestWake() {
    try {
      if (navigator.wakeLock && navigator.wakeLock.request) {
        navigator.wakeLock.request("screen").catch(function () {});
      }
    } catch (e) {}
  }

  function boot() {
    injectStyle();
    // Poista vanha 2px-video jos oli
    var legacy = document.getElementById("lgKeepAlive");
    if (legacy && legacy.parentNode) legacy.parentNode.removeChild(legacy);

    var bust = "v=107";
    var sources = [
      { src: "lg-keepalive.webm?" + bust, type: "video/webm" },
      { src: "lg-keepalive.mp4?" + bust, type: "video/mp4" }
    ];

    // 1) lähes näkymätön täysi peitto (liikkuva video)
    var full = makeVideo("fiilisKeepAliveVideo", sources);
    // 2) pieni nurkkavideo varmistuksena (näkyy compositorille)
    var corner = makeVideo("fiilisKeepAliveCorner", sources);

    function kick() {
      playHard(full);
      playHard(corner);
      requestWake();
      try {
        if (full.readyState >= 2 && full.currentTime > 0.2) {
          /* ok */
        }
      } catch (e) {}
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
    // Satunnainen seek pitää dekooderin elossa
    setInterval(function () {
      try {
        if (full.readyState >= 2 && full.duration && isFinite(full.duration)) {
          var t = (full.currentTime + 0.35) % Math.max(full.duration - 0.05, 0.1);
          full.currentTime = t;
        }
      } catch (e) {}
      kick();
    }, 12000);

    startAudio();
    kick();
    setTimeout(kick, 500);
    setTimeout(kick, 2000);
    setTimeout(function () {
      if (full.readyState < 2) attachCanvas(full);
      if (corner.readyState < 2) attachCanvas(corner);
      kick();
    }, 3500);
    setInterval(requestWake, 50000);
  }

  if (document.body) boot();
  else document.addEventListener("DOMContentLoaded", boot);
})();
