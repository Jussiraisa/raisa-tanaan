/* Fiilis TV keepalive v110 — TV pysyy päällä, ei mustaa nurkkalaatikkoa.
   LG laskee vain ruudulla näkyvän videon. Yläreunassa on taustanvärinen
   ohut kaista (sama sävy kuin sivu), joka vaihtaa pikseleitä. Audio +
   wake lock + webOS-aktiviteetti + reload ~4 min.
   Lataa: <script src="lg-keepalive.js?v=110" defer></script> */
(function () {
  if (window.__fiilisKeepAlive) return;
  window.__fiilisKeepAlive = true;

  var BUILD = "110";
  var RELOAD_MS = 4 * 60 * 1000;

  var STYLE = [
    "#fiilisKeepAliveVideo{",
    "position:fixed;left:0;top:0;width:100vw;height:14px;",
    "opacity:1;pointer-events:none;border:0;outline:none;z-index:2147483000;",
    "object-fit:cover;background:transparent;}"
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

  function parseRgb(str) {
    var m = /rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/.exec(str || "");
    if (!m) return [239, 214, 176];
    return [+m[1], +m[2], +m[3]];
  }

  function pageRgb() {
    try {
      var el = document.body || document.documentElement;
      var c = getComputedStyle(el).backgroundColor;
      return parseRgb(c);
    } catch (e) {
      return [239, 214, 176];
    }
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
    var c = document.createElement("canvas");
    c.width = 640;
    c.height = 36;
    var ctx = c.getContext("2d", { alpha: false });
    if (!ctx || !c.captureStream) return false;
    function paint() {
      var rgb = pageRgb();
      ctx.fillStyle = "rgb(" + rgb[0] + "," + rgb[1] + "," + rgb[2] + ")";
      ctx.fillRect(0, 0, 640, 36);
      var t = Date.now() / 180;
      var x = (t % 640) | 0;
      var d = ((Date.now() / 700) | 0) % 2 ? 2 : -2;
      ctx.fillStyle = "rgb(" + (rgb[0] + d) + "," + (rgb[1] + d) + "," + (rgb[2] + d) + ")";
      ctx.fillRect(x, 0, 8, 36);
    }
    paint();
    v.srcObject = c.captureStream(8);
    setInterval(paint, 120);
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
      osc.frequency.value = 38;
      osc.type = "sine";
      osc.connect(gain);
      gain.connect(ac.destination);
      osc.start();
      setInterval(function () {
        try { if (ac.state === "suspended") ac.resume(); } catch (e) {}
      }, 15000);
    } catch (e) {}
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

  function webosHold() {
    try {
      if (!(window.webOS && webOS.service && webOS.service.request)) return;
      webOS.service.request("luna://com.palm.power/com/palm/power", {
        method: "activityStart",
        parameters: { id: "fiilis-keepalive", duration_ms: 300000 },
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
    var v = makeVideo();
    function kick() {
      if (!v.srcObject) attachCanvas(v);
      playHard(v);
      requestWake();
      webosHold();
    }
    v.addEventListener("pause", function () { setTimeout(kick, 200); });
    v.addEventListener("ended", kick);
    document.addEventListener("visibilitychange", function () {
      if (!document.hidden) kick();
    });
    startAudio();
    kick();
    setTimeout(kick, 500);
    setInterval(kick, 8000);
    setInterval(requestWake, 40000);
    setInterval(webosHold, 120000);
    setTimeout(softReload, RELOAD_MS);
  }

  if (document.body) boot();
  else document.addEventListener("DOMContentLoaded", boot);
})();
