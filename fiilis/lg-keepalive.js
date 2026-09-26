/* Fiilis TV keepalive v117
   LG sammuttaa ruudun, jos video on piilossa tai vain nurkassa.
   Muistokuva on iso toistuva video (sama kuva), joten televisio
   näkee toiston eikä nurkkaan tule laatikkoa.
   Jos selaimesta puuttuu canvas-video, sama alue toistaa pienen
   hiekanvärisen videon kuvan päällä, läpikuultavana.
   Lataa: <script src="lg-keepalive.js?v=117" defer></script> */
(function () {
  if (window.__fiilisKeepAlive) return;
  window.__fiilisKeepAlive = true;

  var BUILD = "117";
  var RELOAD_MS = 12 * 60 * 1000;

  var STYLE = [
    "#fiilisKeepAliveVideo{",
    "position:fixed!important;left:0!important;top:0!important;",
    "width:100vw!important;height:100vh!important;",
    "min-width:100vw!important;min-height:100vh!important;",
    "max-width:none!important;max-height:none!important;",
    "margin:0!important;padding:0!important;border:0!important;",
    "object-fit:cover!important;z-index:0!important;pointer-events:none!important;",
    "background:#F3E6CE!important;opacity:1!important;visibility:visible!important;",
    "transform:none!important;filter:none!important;}",
    ".tv{position:relative!important;z-index:1!important;background:#F3E6CE!important;}",
    ".nav{z-index:30!important;}"
  ].join("");

  function injectStyle() {
    var old = document.getElementById("fiilisKeepAliveStyle");
    if (old && old.parentNode) old.parentNode.removeChild(old);
    var s = document.createElement("style");
    s.id = "fiilisKeepAliveStyle";
    s.textContent = STYLE;
    (document.head || document.documentElement).appendChild(s);
  }

  function removeOld() {
    ["fiilisKeepAliveCorner", "fiilisKeepAliveFrame", "fiilisKeepAliveStrip", "lgKeepAlive"].forEach(function (id) {
      var el = document.getElementById(id);
      if (el && el.parentNode) el.parentNode.removeChild(el);
    });
  }

  function host() {
    return document.body;
  }

  function makeVideo(parent) {
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
    if (parent.firstChild) parent.insertBefore(v, parent.firstChild);
    else parent.appendChild(v);
    return v;
  }

  function playHard(v) {
    try {
      v.muted = true;
      v.volume = 0;
      var p = v.play();
      if (p && p.catch) p.catch(function () {});
    } catch (e) {}
  }

  function coverDraw(ctx, img, w, h) {
    var iw = img.naturalWidth || img.width;
    var ih = img.naturalHeight || img.height;
    if (!iw || !ih) return false;
    var scale = Math.max(w / iw, h / ih);
    var dw = iw * scale;
    var dh = ih * scale;
    ctx.drawImage(img, (w - dw) / 2, (h - dh) / 2, dw, dh);
    return true;
  }

  function attachCanvas(v, parent) {
    if (!window.HTMLCanvasElement || !HTMLCanvasElement.prototype.captureStream) return false;
    var c = document.createElement("canvas");
    var ctx = c.getContext("2d", { alpha: false });
    if (!ctx) return false;
    var img = document.getElementById("photo");
    var revealed = false;
    function size() {
      var r = parent.getBoundingClientRect();
      var w = Math.max(960, Math.round(r.width) || 1280);
      var h = Math.max(540, Math.round(r.height) || 720);
      if (w > 1920) w = 1920;
      if (h > 1080) h = 1080;
      if (c.width !== w) c.width = w;
      if (c.height !== h) c.height = h;
    }
    function paint() {
      size();
      ctx.fillStyle = "#EFD6B0";
      ctx.fillRect(0, 0, c.width, c.height);
      var drew = img && img.complete && coverDraw(ctx, img, c.width, c.height);
      var n = (Date.now() / 400 | 0) % 2;
      ctx.fillStyle = n ? "#EFD6B1" : "#EFD6AF";
      ctx.fillRect(1, 1, 3, 3);
      if (drew && !revealed) {
        revealed = true;
        v.style.opacity = "1";
      }
    }
    paint();
    var stream;
    try { stream = c.captureStream(8); } catch (e) { return false; }
    if (!stream) return false;
    try { v.srcObject = stream; } catch (e) { return false; }
    try { v.removeAttribute("src"); } catch (e2) {}
    setInterval(paint, 250);
    if (img) img.addEventListener("load", paint);
    playHard(v);
    return true;
  }

  function startAudio() {
    try {
      var AC = window.AudioContext || window.webkitAudioContext;
      if (!AC) return;
      var ac = new AC();
      var osc = ac.createOscillator();
      var gain = ac.createGain();
      gain.gain.value = 0.00002;
      osc.frequency.value = 40;
      osc.connect(gain);
      gain.connect(ac.destination);
      osc.start();
      setInterval(function () {
        try { if (ac.state === "suspended") ac.resume(); } catch (e) {}
      }, 12000);
    } catch (e) {}
  }

  function requestWake() {
    try {
      if (navigator.wakeLock && navigator.wakeLock.request) {
        navigator.wakeLock.request("screen").catch(function () {});
      }
    } catch (e) {}
  }

  function webosHold() {
    try {
      if (!(window.webOS && webOS.service && webOS.service.request)) return;
      webOS.service.request("luna://com.palm.power/com/palm/power", {
        method: "activityStart",
        parameters: { id: "fiilis-keepalive", duration_ms: 900000 },
        onSuccess: function () {},
        onFailure: function () {}
      });
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
    removeOld();
    var parent = host();
    var v = makeVideo(parent);
    var mp4 = "keepalive.mp4?v=" + BUILD;
    v.src = mp4;
    v.loop = true;
    playHard(v);
    /* LG webOS screensaver only treats a real full-screen video as active media reliably. */
    var canvasOn = false;
    v.style.opacity = "1";
    v.style.position = "fixed";
    v.style.left = "0";
    v.style.top = "0";
    v.style.width = "100vw";
    v.style.height = "100vh";
    v.style.transform = "none";

    function kick() {
      if (v.ended || v.paused || v.readyState < 2) {
        if (!v.srcObject) {
          if (!v.getAttribute("src")) v.src = mp4;
        }
        playHard(v);
      } else {
        playHard(v);
      }
      requestWake();
      webosHold();
    }
    v.addEventListener("pause", function () { setTimeout(kick, 200); });
    v.addEventListener("ended", function () { playHard(v); });
    v.addEventListener("error", function () {
      if (!v.srcObject) {
        v.src = mp4 + "&r=" + Date.now();
        playHard(v);
      }
    });
    document.addEventListener("visibilitychange", function () {
      if (!document.hidden) kick();
    });
    startAudio();
    kick();
    setTimeout(kick, 500);
    setTimeout(kick, 2000);
    setInterval(kick, 5000);
    setInterval(requestWake, 25000);
    setInterval(webosHold, 90000);
    setTimeout(softReload, RELOAD_MS);
  }

  if (document.body) boot();
  else document.addEventListener("DOMContentLoaded", boot);
})();
