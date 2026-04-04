# -*- coding: utf-8 -*-
"""
Lightweight HTTP WebIF server — no external deps, stdlib only.
Python 2: BaseHTTPServer / Python 3: http.server
"""
from __future__ import absolute_import, print_function, division

import os
import threading
import json
import time

try:
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from urllib.parse import urlparse, parse_qs
except ImportError:
    from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
    from urlparse import urlparse, parse_qs

from ..utils.logger import log


class _Handler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        log.debug("WebIF: " + fmt % args)

    def do_GET(self):
        parsed = urlparse(self.path)
        path   = parsed.path.rstrip("/") or "/"
        params = parse_qs(parsed.query)

        if path == "/":
            self._serve_html()
        elif path == "/api/status":
            self._serve_status()
        elif path == "/api/screenshot":
            fmt = params.get("fmt", ["PNG"])[0].upper()
            self._api_screenshot(fmt)
        elif path == "/api/start":
            self._api_start()
        elif path == "/api/stop":
            self._api_stop()
        elif path == "/api/captures":
            self._api_captures()
        elif path.startswith("/download/"):
            self._serve_file(path[len("/download/"):])
        else:
            self._send_json({"error": "not found"}, 404)

    def _api_screenshot(self, fmt="PNG"):
        try:
            self.server._ctx["do_screenshot"](fmt)
            self._send_json({"ok": True, "fmt": fmt})
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _api_start(self):
        try:
            self.server._ctx["do_start_rec"]()
            self._send_json({"ok": True, "recording": True})
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _api_stop(self):
        try:
            self.server._ctx["do_stop_rec"]()
            self._send_json({"ok": True, "recording": False})
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _serve_status(self):
        rec = self.server._ctx["get_recorder"]()
        is_rec = rec is not None and rec.is_alive()
        elapsed = 0
        if is_rec and hasattr(rec, "elapsed"):
            elapsed = int(rec.elapsed())
        captures = self.server._ctx["storage"].list_captures()
        self._send_json({
            "recording": is_rec,
            "elapsed":   elapsed,
            "captures":  len(captures),
        })

    def _api_captures(self):
        items = self.server._ctx["storage"].list_captures()
        self._send_json({"captures": items[:50]})

    def _serve_file(self, name):
        storage = self.server._ctx["storage"]
        for item in storage.list_captures():
            if item["name"] == name:
                try:
                    with open(item["path"], "rb") as f:
                        data = f.read()
                    ext  = name.rsplit(".", 1)[-1].lower()
                    mime = {"png": "image/png", "jpg": "image/jpeg",
                            "jpeg": "image/jpeg", "mp4": "video/mp4",
                            "avi": "video/avi", "mkv": "video/webm",
                            "zip": "application/zip"}.get(ext, "application/octet-stream")
                    self.send_response(200)
                    self.send_header("Content-Type", mime)
                    self.send_header("Content-Length", str(len(data)))
                    self.send_header("Content-Disposition",
                                     'attachment; filename="{}"'.format(name))
                    self.end_headers()
                    self.wfile.write(data)
                    return
                except Exception as e:
                    self._send_json({"error": str(e)}, 500)
                    return
        self._send_json({"error": "file not found"}, 404)

    def _send_json(self, obj, code=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _serve_html(self):
        html = _WEBIF_HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html)))
        self.end_headers()
        self.wfile.write(html)


class WebIFServer(threading.Thread):

    def __init__(self, port, storage, get_recorder,
                 do_screenshot, do_start_rec, do_stop_rec):
        super(WebIFServer, self).__init__()
        self.daemon = True
        self._port  = port
        self._ctx   = {
            "storage":       storage,
            "get_recorder":  get_recorder,
            "do_screenshot": do_screenshot,
            "do_start_rec":  do_start_rec,
            "do_stop_rec":   do_stop_rec,
        }
        self._httpd = None

    def is_running(self):
        return self._httpd is not None

    def run(self):
        self._httpd = HTTPServer(("0.0.0.0", self._port), _Handler)
        self._httpd._ctx = self._ctx
        log.info("WebIF listening on 0.0.0.0:{}".format(self._port))
        self._httpd.serve_forever()

    def stop(self):
        if self._httpd:
            self._httpd.shutdown()
            self._httpd = None


_WEBIF_HTML = r"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>E2 Screen Recorder</title>
<style>
:root,[data-theme="light"]{--bg:#f7f6f2;--surface:#f9f8f5;--surface-2:#fff;--border:#d4d1ca;--text:#28251d;--muted:#7a7974;--primary:#01696f;--primary-h:#0c4e54;--error:#a12c7b;--success:#437a22;--rec:#cc2222;--shadow:0 4px 16px rgba(0,0,0,.08);--radius:0.6rem;--font:'Segoe UI',system-ui,sans-serif}
[data-theme="dark"]{--bg:#111110;--surface:#1c1b19;--surface-2:#242320;--border:#393836;--text:#cdccca;--muted:#797876;--primary:#4f98a3;--primary-h:#227f8b;--error:#d163a7;--success:#6daa45;--rec:#ff4444;--shadow:0 4px 24px rgba(0,0,0,.4)}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{font-family:var(--font);font-size:15px;color:var(--text);background:var(--bg);min-height:100dvh}
header{background:var(--surface);border-bottom:1px solid var(--border);padding:14px 20px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:100;box-shadow:var(--shadow)}
.logo{display:flex;align-items:center;gap:10px;font-weight:700;font-size:16px;color:var(--primary)}
.header-actions{display:flex;gap:8px}
button{cursor:pointer;border:none;border-radius:var(--radius);font:inherit;font-size:14px;padding:8px 16px;transition:.18s ease}
.btn-primary{background:var(--primary);color:#fff}.btn-primary:hover{background:var(--primary-h)}
.btn-ghost{background:transparent;color:var(--muted);border:1px solid var(--border)}.btn-ghost:hover{background:var(--surface-2);color:var(--text)}
.btn-danger{background:#c0392b;color:#fff}.btn-danger:hover{background:#96281b}
.btn-sm{padding:6px 12px;font-size:13px}
main{max-width:960px;margin:0 auto;padding:24px 16px;display:grid;gap:20px}
.card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:20px;box-shadow:var(--shadow)}
.card h2{font-size:13px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin-bottom:14px}
.status-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}
.stat{background:var(--surface-2);border:1px solid var(--border);border-radius:var(--radius);padding:14px;text-align:center}
.stat-val{font-size:26px;font-weight:700;color:var(--text);font-variant-numeric:tabular-nums}
.stat-lbl{font-size:11px;color:var(--muted);margin-top:4px;text-transform:uppercase;letter-spacing:.04em}
.rec-badge{display:inline-flex;align-items:center;gap:6px;background:rgba(204,34,34,.15);color:var(--rec);border:1px solid rgba(204,34,34,.3);border-radius:999px;padding:4px 12px;font-size:13px;font-weight:600}
.dot{width:8px;height:8px;border-radius:50%;background:var(--rec);animation:blink 1s ease-in-out infinite}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.2}}
.actions-row{display:flex;flex-wrap:wrap;gap:10px}
.fmt-select{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:12px}
.fmt-btn{padding:6px 14px;border-radius:999px;font-size:13px;border:1px solid var(--border);background:transparent;color:var(--muted)}
.fmt-btn.active{background:var(--primary);color:#fff;border-color:var(--primary)}
.captures-list{display:grid;gap:8px;max-height:340px;overflow-y:auto}
.capture-item{display:flex;align-items:center;justify-content:space-between;background:var(--surface-2);border:1px solid var(--border);border-radius:calc(var(--radius)*.7);padding:10px 14px;gap:10px}
.cap-info{flex:1;min-width:0}.cap-name{font-size:13px;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.cap-meta{font-size:11px;color:var(--muted);margin-top:2px}
.cap-actions{display:flex;gap:6px;flex-shrink:0}
.toast{position:fixed;bottom:20px;right:20px;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:12px 18px;box-shadow:var(--shadow);font-size:13px;transform:translateY(80px);opacity:0;transition:.3s ease;z-index:999;max-width:300px}
.toast.show{transform:translateY(0);opacity:1}.toast.ok{border-left:3px solid var(--success)}.toast.err{border-left:3px solid var(--error)}
.empty-state{text-align:center;padding:40px 20px;color:var(--muted);font-size:14px}
@media(max-width:600px){.actions-row button{flex:1}.stat-val{font-size:20px}}
</style>
</head>
<body>
<header>
  <div class="logo">
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/><circle cx="12" cy="10" r="3"/></svg>
    E2 Screen Recorder
  </div>
  <div class="header-actions">
    <button class="btn-ghost btn-sm" onclick="toggleTheme()" id="themeBtn">&#9788;</button>
    <button class="btn-ghost btn-sm" onclick="refreshAll()">&#8635; Refresh</button>
  </div>
</header>
<main>
  <div class="card">
    <h2>Status</h2>
    <div class="status-grid">
      <div class="stat"><div class="stat-val" id="recStatus">&mdash;</div><div class="stat-lbl">Recording</div></div>
      <div class="stat"><div class="stat-val" id="elapsed">&mdash;</div><div class="stat-lbl">Elapsed</div></div>
      <div class="stat"><div class="stat-val" id="capCount">&mdash;</div><div class="stat-lbl">Captures</div></div>
    </div>
  </div>
  <div class="card">
    <h2>Screenshot</h2>
    <div class="fmt-select" id="fmtBtns">
      <button class="fmt-btn active" data-fmt="PNG">PNG</button>
      <button class="fmt-btn" data-fmt="JPEG">JPEG</button>
      <button class="fmt-btn" data-fmt="BMP">BMP</button>
    </div>
    <div class="actions-row">
      <button class="btn-primary" onclick="takeScreenshot()">&#128247; Take Screenshot</button>
    </div>
  </div>
  <div class="card">
    <h2>Video Recording</h2>
    <div class="actions-row">
      <button class="btn-primary" onclick="startRec()">&#127909; Start Recording</button>
      <button class="btn-danger"  onclick="stopRec()">&#9209; Stop Recording</button>
    </div>
  </div>
  <div class="card">
    <h2>Captures</h2>
    <div class="captures-list" id="capturesList"><div class="empty-state">Loading...</div></div>
  </div>
</main>
<div class="toast" id="toast"></div>
<script>
'use strict';
let _fmt='PNG';
document.querySelectorAll('.fmt-btn').forEach(b=>b.addEventListener('click',()=>{document.querySelectorAll('.fmt-btn').forEach(x=>x.classList.remove('active'));b.classList.add('active');_fmt=b.dataset.fmt;}));
function toggleTheme(){const h=document.documentElement;const t=h.getAttribute('data-theme')==='dark'?'light':'dark';h.setAttribute('data-theme',t);}
async function api(url){try{const r=await fetch(url,{cache:'no-store'});return await r.json();}catch(e){return{error:String(e)};}}
function toast(msg,type='ok'){const el=document.getElementById('toast');el.textContent=msg;el.className='toast '+type+' show';setTimeout(()=>el.classList.remove('show'),3500);}
async function takeScreenshot(){const r=await api('/api/screenshot?fmt='+_fmt);if(r.ok)toast('Screenshot saved ('+_fmt+')','ok');else toast('Error: '+(r.error||'?'),'err');setTimeout(loadCaptures,800);}
async function startRec(){const r=await api('/api/start');if(r.ok)toast('Recording started','ok');else toast('Error: '+(r.error||'?'),'err');updateStatus();}
async function stopRec(){const r=await api('/api/stop');if(r.ok)toast('Recording stopped','ok');else toast('Error: '+(r.error||'?'),'err');updateStatus();setTimeout(loadCaptures,1200);}
function fmtTime(s){const m=Math.floor(s/60),sec=s%60;return String(m).padStart(2,'0')+':'+String(sec).padStart(2,'0');}
function fmtBytes(b){if(b<1024)return b+'B';if(b<1048576)return(b/1024).toFixed(1)+'KB';return(b/1048576).toFixed(1)+'MB';}
async function updateStatus(){const d=await api('/api/status');if(d.error){document.getElementById('recStatus').textContent='ERR';return;}const el=document.getElementById('recStatus');if(d.recording){el.innerHTML='<span class="rec-badge"><span class="dot"></span>REC</span>';}else{el.textContent='Idle';}document.getElementById('elapsed').textContent=d.recording?fmtTime(d.elapsed):'&mdash;';document.getElementById('capCount').textContent=d.captures;}
async function loadCaptures(){const d=await api('/api/captures');const el=document.getElementById('capturesList');if(!d.captures||!d.captures.length){el.innerHTML='<div class="empty-state">No captures yet.</div>';return;}el.innerHTML=d.captures.map(c=>{const date=new Date(c.mtime*1000).toLocaleString();const icon=c.name.startsWith('shot_')?'&#128444;':'&#127909;';return'<div class="capture-item"><div class="cap-info"><div class="cap-name">'+icon+' '+c.name+'</div><div class="cap-meta">'+fmtBytes(c.size)+' &bull; '+date+'</div></div><div class="cap-actions"><a href="/download/'+encodeURIComponent(c.name)+'" download><button class="btn-ghost btn-sm">&#8681; Download</button></a></div></div>';}).join('');}
function refreshAll(){updateStatus();loadCaptures();toast('Refreshed','ok');}
setInterval(updateStatus,2000);
updateStatus();loadCaptures();
</script>
</body>
</html>"""
