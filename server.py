#!/usr/bin/env python3
"""Karbordi: lightweight LAN file transfer server for Windows and Android."""
from __future__ import annotations

import json
import mimetypes
import os
import secrets
import socket
import threading
import urllib.parse
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "KarbordiFiles"
SHARED_DIR = DATA_DIR / "Shared"
RECEIVED_DIR = DATA_DIR / "Received"
for folder in (SHARED_DIR, RECEIVED_DIR):
    folder.mkdir(parents=True, exist_ok=True)

ACCESS_CODE = f"{secrets.randbelow(1_000_000):06d}"
SESSION_TOKEN = secrets.token_urlsafe(32)
PORT = int(os.environ.get("KARBORDI_PORT", "8765"))
MAX_UPLOAD_BYTES = 20 * 1024 * 1024 * 1024  # 20 GiB per file


def local_addresses():
    found = set()
    try:
        for item in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = item[4][0]
            if not ip.startswith("127."):
                found.add(ip)
    except OSError:
        pass
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("192.0.2.1", 80))
        ip = sock.getsockname()[0]
        if not ip.startswith("127."):
            found.add(ip)
        sock.close()
    except OSError:
        pass
    return sorted(found)


PAGE = r"""<!doctype html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#123c35">
<title>کاربُردی | انتقال فایل</title>
<style>
:root{color-scheme:light;--ink:#173a34;--muted:#60736e;--line:#dce7e2;--paper:#f4f8f5;--green:#176b53;--gold:#c49a48}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font-family:Tahoma,"Segoe UI",sans-serif;line-height:1.7}
header{background:linear-gradient(125deg,#123c35,#205c4d);color:white;padding:24px 18px 28px;border-bottom:4px solid var(--gold)}
.wrap{max-width:940px;margin:auto;padding:0 16px}header .wrap{display:flex;align-items:center;gap:14px}.mark{width:48px;height:48px;border:1px solid #d7c18a;border-radius:14px;display:grid;place-items:center;font-size:25px;color:#f0d99e}
h1{font-size:23px;margin:0}header p{margin:3px 0 0;color:#d6e7df;font-size:13px}
main{padding:22px 0 40px}.card{background:white;border:1px solid var(--line);border-radius:16px;padding:20px;margin-bottom:16px;box-shadow:0 5px 18px #173a3408}
h2{font-size:17px;margin:0 0 12px}.sub{font-size:13px;color:var(--muted);margin:0 0 14px}
button,.btn{border:0;border-radius:10px;padding:11px 16px;background:var(--green);color:white;font:inherit;font-size:14px;cursor:pointer;display:inline-flex;align-items:center;justify-content:center;gap:8px}
button:disabled{opacity:.55;cursor:wait}.secondary{background:#edf4f0;color:var(--ink);border:1px solid var(--line)}
input[type=password]{width:100%;padding:12px;border:1px solid #cbd9d2;border-radius:10px;font:inherit;margin:7px 0 12px}
.actions{display:flex;flex-wrap:wrap;gap:9px}.status{font-size:13px;color:var(--muted);margin-top:10px;overflow-wrap:anywhere}
.drop{border:1.5px dashed #a7c2b5;border-radius:13px;padding:22px;text-align:center;background:#f8fbf9}
input[type=file]{max-width:100%;margin:12px 0}
.files{display:grid;gap:9px}.file{display:flex;align-items:center;gap:12px;border:1px solid var(--line);border-radius:12px;padding:11px 12px;min-width:0}.fileicon{font-size:23px}.fileinfo{flex:1;min-width:0}.filename{font-size:14px;overflow-wrap:anywhere}.meta{font-size:12px;color:var(--muted)}.file a{white-space:nowrap;text-decoration:none}
.sectionhead{display:flex;justify-content:space-between;gap:12px;align-items:center}.sectionhead h2{margin:0 0 12px}
.hidden{display:none!important}.progress{height:6px;background:#e4eee8;border-radius:9px;overflow:hidden;margin-top:10px}.bar{height:100%;width:0;background:var(--gold);transition:width .15s}
footer{text-align:center;color:var(--muted);font-size:12px;padding:5px 0 24px}
@media(min-width:700px){.columns{display:grid;grid-template-columns:1fr 1fr;gap:16px}.columns .card{margin-bottom:16px}}
</style></head>
<body>
<header><div class="wrap"><div class="mark">↔</div><div><h1>کاربُردی</h1><p>انتقال مستقیم فایل در شبکه محلی</p></div></div></header>
<main class="wrap">
<section class="card" id="loginCard"><h2>اتصال به دستگاه میزبان</h2><p class="sub">کد شش‌رقمی نمایش‌داده‌شده در پنجره برنامه ویندوز را وارد کنید.</p>
<form id="loginForm"><input id="code" type="password" inputmode="numeric" pattern="[0-9]{6}" maxlength="6" placeholder="کد اتصال" autocomplete="one-time-code" required><button type="submit">ورود به فضای انتقال</button></form><div class="status" id="loginStatus" role="status"></div></section>
<div id="workspace" class="hidden">
<div class="columns">
<section class="card"><h2>ارسال فایل به میزبان</h2><p class="sub">فایل از گوشی یا رایانه شما به پوشه Received دستگاه میزبان فرستاده می‌شود.</p>
<div class="drop"><div>فایل‌ها را انتخاب کنید</div><input id="picker" type="file" multiple><div class="actions" style="justify-content:center"><button id="uploadBtn" type="button">ارسال فایل‌ها</button></div></div>
<div class="progress"><div class="bar" id="bar"></div></div><div class="status" id="uploadStatus" role="status"></div>
</section>
<section class="card"><div class="sectionhead"><h2>فایل‌های قابل دریافت</h2><button class="secondary" id="refreshBtn" type="button">تازه‌سازی</button></div>
<p class="sub">فایل‌های پوشه Shared و فایل‌های دریافت‌شده در پوشه Received.</p><div id="fileList" class="files"><div class="status">در حال دریافت فهرست…</div></div>
</section></div>
<section class="card"><h2>روش استفاده</h2><p class="sub">برای فرستادن فایل از ویندوز میزبان به دستگاه‌های دیگر، فایل را داخل پوشه <b>KarbordiFiles/Shared</b> کپی کنید و فهرست را تازه‌سازی کنید. فایل‌های دریافتی در پوشه <b>KarbordiFiles/Received</b> ذخیره می‌شوند. برای انتقال بین دو رایانه و گوشی، همه را به همان شبکه Wi-Fi وصل کنید.</p></section>
</div></main><footer class="wrap">کاربُردی · انتقال فایل بدون فضای ابری</footer>
<script>
const $=id=>document.getElementById(id);
async function api(path,options={}){const r=await fetch(path,{credentials:'same-origin',...options});if(!r.ok){let t='خطا در ارتباط';try{t=(await r.json()).error||t}catch{}throw Error(t)}return r}
async function loadFiles(){const box=$('fileList');box.innerHTML='<div class="status">در حال بارگذاری…</div>';try{const r=await api('/api/files');const data=await r.json();box.innerHTML='';if(!data.files.length){box.innerHTML='<div class="status">هنوز فایلی برای دریافت وجود ندارد.</div>';return}
for(const f of data.files){const row=document.createElement('div');row.className='file';const icon=document.createElement('div');icon.className='fileicon';icon.textContent='▤';const info=document.createElement('div');info.className='fileinfo';const name=document.createElement('div');name.className='filename';name.textContent=f.name;const meta=document.createElement('div');meta.className='meta';meta.textContent=(f.folder==='Shared'?'پوشه اشتراکی':'دریافت‌شده')+' · '+f.size;info.append(name,meta);const a=document.createElement('a');a.className='btn';a.href='/download?folder='+encodeURIComponent(f.folder)+'&name='+encodeURIComponent(f.name);a.textContent='دریافت';row.append(icon,info,a);box.append(row)}
}catch(e){box.innerHTML='<div class="status">'+e.message+'</div>'}}
$('loginForm').addEventListener('submit',async e=>{e.preventDefault();$('loginStatus').textContent='در حال بررسی کد…';try{await api('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code:$('code').value})});$('loginCard').classList.add('hidden');$('workspace').classList.remove('hidden');loadFiles()}catch(err){$('loginStatus').textContent=err.message}});
$('uploadBtn').addEventListener('click',async()=>{const files=[...$('picker').files];if(!files.length){$('uploadStatus').textContent='ابتدا یک یا چند فایل انتخاب کنید.';return}
$('uploadBtn').disabled=true;let done=0;for(const f of files){$('uploadStatus').textContent='در حال ارسال: '+f.name+' ('+(done+1)+' از '+files.length+')';try{await new Promise((resolve,reject)=>{const x=new XMLHttpRequest();x.open('POST','/upload?name='+encodeURIComponent(f.name));x.withCredentials=true;x.setRequestHeader('Content-Type','application/octet-stream');x.upload.onprogress=e=>{if(e.lengthComputable)$('bar').style.width=Math.round((done+e.loaded/e.total)/files.length*100)+'%'};x.onload=()=>x.status>=200&&x.status<300?resolve():reject(Error('ارسال فایل ناموفق بود: '+f.name));x.onerror=()=>reject(Error('ارتباط قطع شد'));x.send(f)}) ;done++}catch(err){$('uploadStatus').textContent=err.message;$('uploadBtn').disabled=false;return}}
$('bar').style.width='100%';$('uploadStatus').textContent=done+' فایل با موفقیت ارسال شد.';$('picker').value='';$('uploadBtn').disabled=false;loadFiles()});
$('refreshBtn').addEventListener('click',loadFiles);
</script></body></html>"""


class TransferHandler(BaseHTTPRequestHandler):
    server_version = "Karbordi/1.0"

    def log_message(self, fmt, *args):
        print("[کاربُردی] " + (fmt % args))

    def send_json(self, status, payload, headers=None):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        if headers:
            for key, value in headers.items():
                self.send_header(key, value)
        self.end_headers()
        self.wfile.write(data)

    def authorized(self):
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie", ""))
            return secrets.compare_digest(cookie.get("karbordi_session", {}).value, SESSION_TOKEN)
        except (AttributeError, KeyError):
            return False

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        if parsed.path == "/":
            body = PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        if not self.authorized():
            self.send_json(401, {"error": "ابتدا با کد اتصال وارد شوید."})
            return
        if parsed.path == "/api/files":
            files = []
            for folder_name, folder in (("Shared", SHARED_DIR), ("Received", RECEIVED_DIR)):
                for path in sorted(folder.iterdir(), key=lambda p: p.name.casefold()):
                    if path.is_file() and not path.name.startswith(".") and not path.name.endswith(".part"):
                        try:
                            size = path.stat().st_size
                            files.append({"name": path.name, "folder": folder_name, "size": self.pretty_size(size)})
                        except OSError:
                            pass
            self.send_json(200, {"files": files})
            return
        if parsed.path == "/download":
            name = query.get("name", [""])[0]
            folder_name = query.get("folder", [""])[0]
            folder = SHARED_DIR if folder_name == "Shared" else RECEIVED_DIR if folder_name == "Received" else None
            if folder is None or not name or Path(name).name != name:
                self.send_json(400, {"error": "درخواست فایل معتبر نیست."})
                return
            path = folder / name
            try:
                if not path.is_file():
                    self.send_json(404, {"error": "فایل پیدا نشد."})
                    return
                size = path.stat().st_size
                mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
                quoted = urllib.parse.quote(path.name)
                self.send_response(200)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Length", str(size))
                self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{quoted}")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                with path.open("rb") as f:
                    while True:
                        chunk = f.read(1024 * 1024)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
            except (OSError, BrokenPipeError):
                pass
            return
        self.send_json(404, {"error": "مسیر پیدا نشد."})

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/login":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length > 4096:
                    self.send_json(413, {"error": "درخواست بیش از حد بزرگ است."})
                    return
                data = json.loads(self.rfile.read(length).decode("utf-8"))
                code = str(data.get("code", ""))
            except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
                self.send_json(400, {"error": "کد اتصال را وارد کنید."})
                return
            if not secrets.compare_digest(code, ACCESS_CODE):
                self.send_json(403, {"error": "کد اتصال نادرست است."})
                return
            self.send_json(200, {"ok": True}, {"Set-Cookie": f"karbordi_session={SESSION_TOKEN}; HttpOnly; SameSite=Strict; Path=/"})
            return
        if not self.authorized():
            self.send_json(401, {"error": "نشست معتبر نیست؛ صفحه را تازه‌سازی کنید."})
            return
        if parsed.path != "/upload":
            self.send_json(404, {"error": "مسیر پیدا نشد."})
            return
        name = urllib.parse.parse_qs(parsed.query).get("name", [""])[0]
        if not name or name in (".", "..") or Path(name).name != name or any(ord(c) < 32 for c in name) or "/" in name or "\\" in name:
            self.send_json(400, {"error": "نام فایل معتبر نیست."})
            return
        try:
            length = int(self.headers.get("Content-Length", "-1"))
        except ValueError:
            length = -1
        if length < 0 or length > MAX_UPLOAD_BYTES:
            self.send_json(413, {"error": "حجم فایل قابل قبول نیست (حداکثر ۲۰ گیگابایت)."})
            return
        target = RECEIVED_DIR / name
        temp = RECEIVED_DIR / (name + "." + secrets.token_hex(5) + ".part")
        try:
            remaining = length
            with temp.open("wb") as f:
                while remaining:
                    chunk = self.rfile.read(min(1024 * 1024, remaining))
                    if not chunk:
                        raise ConnectionError("upload interrupted")
                    f.write(chunk)
                    remaining -= len(chunk)
            # Avoid silently overwriting an existing received file.
            final = target
            if final.exists():
                stem, suffix = target.stem, target.suffix
                n = 2
                while (RECEIVED_DIR / f"{stem} ({n}){suffix}").exists():
                    n += 1
                final = RECEIVED_DIR / f"{stem} ({n}){suffix}"
            temp.replace(final)
            self.send_json(201, {"ok": True, "name": final.name})
        except (OSError, ConnectionError) as exc:
            try:
                temp.unlink(missing_ok=True)
            except OSError:
                pass
            if not self.wfile.closed:
                try:
                    self.send_json(500, {"error": "ذخیره فایل ناموفق بود."})
                except OSError:
                    pass

    @staticmethod
    def pretty_size(size):
        if size < 1024:
            return f"{size} بایت"
        if size < 1024**2:
            return f"{size / 1024:.1f} کیلوبایت"
        if size < 1024**3:
            return f"{size / 1024**2:.1f} مگابایت"
        return f"{size / 1024**3:.2f} گیگابایت"


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main():
    try:
        server = Server(("0.0.0.0", PORT), TransferHandler)
    except OSError as exc:
        print(f"خطا: پورت {PORT} قابل استفاده نیست: {exc}")
        input("برای خروج Enter را بزنید...")
        return
    print("=" * 56)
    print("  کاربُردی | سرور انتقال فایل")
    print("=" * 56)
    print(f"کد اتصال: {ACCESS_CODE}")
    print("آدرس‌های اتصال در شبکه محلی:")
    addresses = local_addresses()
    if addresses:
        for ip in addresses:
            print(f"  http://{ip}:{PORT}")
    else:
        print(f"  http://IP-این-کامپیوتر:{PORT}")
    print(f"\nپوشه ارسال به دیگران: {SHARED_DIR}")
    print(f"پوشه فایل‌های دریافتی: {RECEIVED_DIR}")
    print("\nاین پنجره را باز نگه دارید. برای توقف Ctrl+C را بزنید.")
    print("کد اتصال را فقط در اختیار افراد مورداعتماد بگذارید.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nدر حال توقف...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
