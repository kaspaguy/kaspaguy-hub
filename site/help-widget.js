/* KaspaChat help widget: an "Ask about Kaspa" button and panel. Answers come from /api/help on the same site
   (kc-helpbot), which sends a human-reviewed FAQ answer or a fixed reply. No third-party code, no cookies, no storage.
   Use: <script src="/help-widget.js" data-privacy="/privacy" defer></script>. Colours follow the page's
   --accent/--panel/... variables. */
(function () {
  "use strict";
  var API = "/api/help", MAX = 1000;
  var PRIVACY = (document.currentScript && document.currentScript.getAttribute("data-privacy")) || "";
  var CSS = [
    ":host{all:initial;font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:var(--text,#14171a)}",
    "*{box-sizing:border-box}",
    ".fab{position:fixed;right:20px;bottom:20px;z-index:2147483000;display:flex;align-items:center;gap:8px;",
    "padding:11px 16px;border:0;border-radius:999px;background:var(--accent,#0f766e);color:var(--accent-ink,#fff);",
    "font:600 15px/1 inherit;font-family:inherit;cursor:pointer;box-shadow:0 4px 16px rgba(0,0,0,.18)}",
    ".fab:focus-visible,button:focus-visible,textarea:focus-visible,a:focus-visible{outline:3px solid var(--accent,#0f766e);outline-offset:2px}",
    ".fab svg{width:18px;height:18px}",
    ".panel{position:fixed;right:20px;bottom:20px;z-index:2147483001;width:380px;max-height:min(640px,calc(100vh - 40px));",
    "display:flex;flex-direction:column;background:var(--panel,#fff);color:var(--text,#14171a);border:1px solid var(--line,#e2e4e6);",
    "border-radius:14px;box-shadow:0 12px 40px rgba(0,0,0,.25);overflow:hidden}",
    ".panel[hidden],.fab[hidden]{display:none}",
    "header{display:flex;align-items:center;justify-content:space-between;padding:12px 14px;border-bottom:1px solid var(--line,#e2e4e6)}",
    "header b{font-size:15px}",
    ".x{border:0;background:none;color:var(--muted,#5d6670);font-size:22px;line-height:1;cursor:pointer;padding:2px 6px;border-radius:6px}",
    ".log{flex:1;overflow-y:auto;padding:14px;display:flex;flex-direction:column;gap:12px;min-height:120px}",
    ".intro{color:var(--muted,#5d6670);font-size:14px;margin:0}",
    ".q{align-self:flex-end;max-width:85%;background:var(--accent,#0f766e);color:var(--accent-ink,#fff);padding:8px 12px;",
    "border-radius:12px 12px 2px 12px;white-space:pre-wrap;overflow-wrap:anywhere}",
    ".a{align-self:flex-start;max-width:100%;background:var(--soft,#e6f4f1);padding:10px 12px;border-radius:12px 12px 12px 2px}",
    ".a p{margin:0;white-space:pre-wrap;overflow-wrap:anywhere}",
    ".tag{font-size:12px;font-weight:600;color:var(--accent,#0f766e);margin:0 0 4px}",
    ".about{font-size:13px;color:var(--muted,#5d6670);margin:0 0 6px}",
    ".src{margin:8px 0 0;padding:0;list-style:none;font-size:13px}",
    ".src a{color:var(--accent,#0f766e);overflow-wrap:anywhere}",
    ".rel{margin:8px 0 0;display:flex;flex-direction:column;gap:6px}",
    ".rel button{text-align:left;border:1px solid var(--line,#e2e4e6);background:var(--panel,#fff);color:var(--text,#14171a);",
    "border-radius:8px;padding:6px 10px;font:inherit;font-size:14px;cursor:pointer}",
    ".vote{display:flex;align-items:center;gap:6px;margin-top:8px;font-size:13px;color:var(--muted,#5d6670)}",
    ".vote button{border:1px solid var(--line,#e2e4e6);background:var(--panel,#fff);border-radius:8px;padding:2px 8px;font-size:15px;cursor:pointer}",
    ".wait{color:var(--muted,#5d6670);font-style:italic}",
    "form{border-top:1px solid var(--line,#e2e4e6);padding:10px 12px 8px}",
    ".row{display:flex;gap:8px;align-items:flex-end}",
    "textarea{flex:1;resize:none;min-height:42px;max-height:120px;padding:9px 10px;border:1px solid var(--line,#e2e4e6);border-radius:10px;",
    "background:var(--bg,#f7f7f5);color:var(--text,#14171a);font:inherit}",
    ".send{border:0;border-radius:10px;padding:10px 14px;background:var(--accent,#0f766e);color:var(--accent-ink,#fff);font:600 14px/1 inherit;font-family:inherit;cursor:pointer}",
    ".send:disabled{opacity:.5;cursor:default}",
    ".meta{display:flex;justify-content:space-between;gap:8px;margin-top:6px;font-size:12px;color:var(--muted,#5d6670)}",
    ".meta .over{color:var(--danger,#b42318)}",
    ".fine{margin:4px 0 0;font-size:12px;color:var(--muted,#5d6670)}.fine a{color:inherit}",
    "@media (max-width:520px){.panel{inset:0;width:auto;max-height:none;border-radius:0;border:0}.fab{right:14px;bottom:14px}}"
  ].join("");

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  function post(path, body) {
    return fetch(API + path, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body),
                              credentials: "same-origin"})
      .then(function (r) { return r.json().catch(function () { return {}; }).then(function (j) { j._status = r.status; return j; }); });
  }

  function start() {
    var host = el("div");
    host.id = "kc-help";
    document.body.appendChild(host);
    var root = host.attachShadow({mode: "open"});
    var style = el("style");
    style.textContent = CSS;
    root.appendChild(style);

    var fab = el("button", "fab");
    fab.type = "button";
    fab.setAttribute("aria-haspopup", "dialog");
    fab.setAttribute("aria-expanded", "false");
    fab.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">' +
      '<path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z"/></svg>';
    fab.appendChild(document.createTextNode("Ask about Kaspa"));

    var panel = el("div", "panel");
    panel.hidden = true;
    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-label", "KaspaChat help");
    var head = el("header");
    head.appendChild(el("b", null, "KaspaChat help"));
    var close = el("button", "x", "×");
    close.type = "button";
    close.setAttribute("aria-label", "Close");
    head.appendChild(close);
    var log = el("div", "log");
    log.setAttribute("aria-live", "polite");
    log.appendChild(el("p", "intro", "Ask a question about Kaspa or KaspaChat. I answer from a human-reviewed FAQ, " +
                                     "and say so when it doesn't cover your question."));
    var form = el("form");
    var row = el("div", "row");
    var box = el("textarea");
    box.rows = 1;
    box.placeholder = "Type your question…";
    box.setAttribute("aria-label", "Your question");
    var send = el("button", "send", "Ask");
    send.type = "submit";
    row.appendChild(box);
    row.appendChild(send);
    var meta = el("div", "meta");
    var note = el("span", null, "Answers come from a human-reviewed FAQ. Not financial advice.");
    var count = el("span", null, "0/" + MAX);
    meta.appendChild(note);
    meta.appendChild(count);
    form.appendChild(row);
    form.appendChild(meta);
    var fine = el("p", "fine", "Questions are kept for 30 days to improve the FAQ. Please don't include personal details. ");
    if (/^\/[\w\/#-]*$/.test(PRIVACY)) {
      var pl = el("a", null, "Privacy");
      pl.href = PRIVACY;
      fine.appendChild(pl);
    }
    form.appendChild(fine);
    panel.appendChild(head);
    panel.appendChild(log);
    panel.appendChild(form);
    root.appendChild(fab);
    root.appendChild(panel);

    var busy = false;
    function open() {
      panel.hidden = false; fab.hidden = true; fab.setAttribute("aria-expanded", "true"); box.focus();
    }
    function shut() {
      panel.hidden = true; fab.hidden = false; fab.setAttribute("aria-expanded", "false"); fab.focus();
    }
    function sync() {
      var n = box.value.length;
      count.textContent = n + "/" + MAX;
      count.className = n > MAX ? "over" : "";
      send.disabled = busy || !box.value.trim() || n > MAX;
      box.style.height = "auto";
      box.style.height = Math.min(box.scrollHeight, 120) + "px";
    }
    function scroll() { log.scrollTop = log.scrollHeight; }

    function answer(j) {
      var a = el("div", "a");
      if (j.faq) {
        a.appendChild(el("p", "tag", "From the reviewed FAQ"));
        a.appendChild(el("p", "about", j.faq.question));
      }
      a.appendChild(el("p", null, j.reply || "Something went wrong. Please try again."));
      var srcs = ((j.faq && j.faq.sources) || []).filter(function (u) { return /^https:\/\//.test(u); });
      if (srcs.length) {
        var ul = el("ul", "src");
        ul.appendChild(el("li", null, "Sources:"));
        srcs.slice(0, 4).forEach(function (u) {
          var li = el("li"), link = el("a", null, u.replace(/^https:\/\//, ""));
          link.href = u; link.target = "_blank"; link.rel = "noopener noreferrer";
          li.appendChild(link); ul.appendChild(li);
        });
        a.appendChild(ul);
      }
      if ((j.related || []).length) {
        var rel = el("div", "rel");
        rel.appendChild(el("span", "about", "Closest questions in the FAQ:"));
        j.related.forEach(function (q) {
          var b = el("button", null, q);
          b.type = "button";
          b.addEventListener("click", function () { ask(q); });
          rel.appendChild(b);
        });
        a.appendChild(rel);
      }
      if (j.id) {
        var v = el("div", "vote");
        v.appendChild(el("span", null, "Did this help?"));
        [["up", "👍", "Yes"], ["down", "👎", "No"]].forEach(function (x) {
          var b = el("button", null, x[1]);
          b.type = "button";
          b.setAttribute("aria-label", x[2]);
          b.addEventListener("click", function () {
            post("/feedback", {id: j.id, vote: x[0]}).catch(function () {});
            v.textContent = "Thanks for the feedback.";
          });
          v.appendChild(b);
        });
        a.appendChild(v);
      }
      return a;
    }

    function ask(text) {
      text = text.trim();
      if (!text || text.length > MAX || busy) return;
      busy = true;
      sync();
      log.appendChild(el("div", "q", text));
      var wait = el("p", "wait", "Looking it up…");
      log.appendChild(wait);
      scroll();
      post("", {message: text})
        .then(function (j) { log.replaceChild(answer(j), wait); })
        .catch(function () { log.replaceChild(answer({reply: "I couldn't reach the help bot. Please try again."}), wait); })
        .then(function () { busy = false; sync(); scroll(); box.focus(); });
    }

    fab.addEventListener("click", open);
    close.addEventListener("click", shut);
    panel.addEventListener("keydown", function (e) { if (e.key === "Escape") shut(); });
    box.addEventListener("input", sync);
    box.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); form.requestSubmit ? form.requestSubmit() : submit(e); }
    });
    function submit(e) {
      e.preventDefault();
      if (busy || send.disabled) return;
      var t = box.value; box.value = ""; sync(); ask(t);
    }
    form.addEventListener("submit", submit);
    sync();
  }

  fetch(API + "/status", {credentials: "same-origin"})
    .then(function (r) { return r.ok ? r.json() : {enabled: false}; })
    .then(function (s) {
      if (!s.enabled) return;
      if (document.body) start(); else document.addEventListener("DOMContentLoaded", start);
    })
    .catch(function () {});
})();
