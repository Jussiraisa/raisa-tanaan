/* Fiilis TV keepalive v111 — muistokuva on itsessään pyörivä video.
   LG sammuttaa näytön, jos video on piilossa tai nurkassa. Video peittää
   muistokuvan ja piirtää saman kuvan, joten ruutu näyttää samalta ja
   televisio näkee ison toistuvan videon. Ei mustaa laatikkoa.
   Lataa: <script src="lg-keepalive.js?v=111" defer></script> */
(function () {
  if (window.__fiilisKeepAlive) return;
  window.__fiilisKeepAlive = true;

  var BUILD = "111";
  var RELOAD_MS = 8 * 60 * 1000;

  var STYLE = [
    ".hero,#fiilisKeepAliveHost{position:relative;}",
    "#fiilisKeepAliveVideo{",
    "position:absolute;left:0;top:0;width:100%;height:100%;",
    "object-fit:cover;z-index:2;pointer-events:none;background:transparent;",
    "opacity:1;}",
    ".hero .cap,.photo-wrap .photo-cap,.hero .cap *{position:relative;z-index:4;}"
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
    ["fiilisKeepAliveCorner", "fiilisKeepAliveFrame", "lgKeepAlive"].forEach(function (id) {
      var el = document.getElementById(id);
      if (el && el.parentNode) el.parentNode.removeChild(el);
    });
  }

  function host() {
    var img = document.getElementById("photo");
    if (img && img.parentElement) return img.parentElement;
    var hero = document.querySelector(".hero");
    if (hero) return hero;
    return document.body;
  }

  function makeVideo(parent) {
    var old = document.getElementById("fiilisKeepAliveVideo");
    if (old && old.parentNode) old.parentNode.removeChild(old);
    parent.id = parent.id || "fiilisKeepAliveHost";
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
    parent.appendChild(v);
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

  function attach(v, parent) {
    var c = document.createElement("canvas");
    var ctx = c.getContext("2d", { alpha: false });
    if (!ctx || !c.captureStream) return false;
    var img = document.getElementById("photo");
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
      var rgb = [239, 214, 176];
      ctx.fillStyle = "rgb(" + rgb[0] + "," + rgb[1] + "," + rgb[2] + ")";
      ctx.fillRect(0, 0, c.width, c.height);
      if (img && img.complete) coverDraw(ctx, img, c.width, c.height);
      var n = (Date.now() / 500 | 0) % 2;
      var px = ctx.getImageData(2, 2, 1, 1);
      px.data[0] = Math.min(255, px.data[0] + (n ? 1 : -1));
      ctx.putImageData(px, 2, 2);
    }
    paint();
    try { v.srcObject = c.captureStream(10); } catch (e) { return false; }
    setInterval(paint, 200);
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
        parameters: { id: "fiilis-keepalive", duration_ms: 600000 },
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
    function kick() {
      if (!v.srcObject) attach(v, parent);
      playHard(v);
      requestWake();
      webosHold();
    }
    v.addEventListener("pause", function () { setTimeout(kick, 250); });
    document.addEventListener("visibilitychange", function () {
      if (!document.hidden) kick();
    });
    startAudio();
    kick();
    setTimeout(kick, 600);
    setTimeout(kick, 2000);
    setInterval(kick, 7000);
    setInterval(requestWake, 30000);
    setInterval(webosHold, 90000);
    setTimeout(softReload, RELOAD_MS);
  }

  if (document.body) boot();
  else document.addEventListener("DOMContentLoaded", boot);
})();
