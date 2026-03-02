#!/usr/bin/env python3
"""NAS Selective Sync UI — web UI for managing Syncthing .stignore whitelists."""

import http.server
import pathlib
import json
import argparse
import shutil
import os
import urllib.parse
import urllib.request
import urllib.error
from html import escape as _h


# ---------------------------------------------------------------------------
# HTML rendering
# ---------------------------------------------------------------------------

_CSS = """\
:root {
    --bg: #1a1a2e;
    --bg2: #16213e;
    --bg3: #0f3460;
    --fg: #e0e0e0;
    --fg-dim: #888;
    --blue: #4ea8de;
    --green: #57cc99;
    --red: #e76f51;
    --accent: #4ea8de;
    --hover: rgba(255,255,255,0.12);
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: 'SF Mono', 'Cascadia Code', 'Consolas', monospace;
    background: var(--bg);
    color: var(--fg);
    height: 100vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    user-select: none;
}
#breadcrumb {
    background: var(--bg2);
    padding: 10px 16px;
    display: flex;
    align-items: center;
    gap: 4px;
    border-bottom: 1px solid rgba(255,255,255,0.08);
    flex-shrink: 0;
    flex-wrap: wrap;
}
#breadcrumb span { color: var(--fg-dim); font-size: 14px; }
#breadcrumb a {
    color: var(--accent);
    text-decoration: none;
    font-size: 14px;
    padding: 2px 4px;
    border-radius: 3px;
}
#breadcrumb a:hover { background: var(--hover); }
#breadcrumb a.current { color: var(--fg); cursor: default; pointer-events: none; }
#listing {
    flex: 1;
    overflow-y: auto;
    padding: 8px 0;
    max-width: 800px;
}
a.entry { text-decoration: none; color: inherit; }
.entry {
    display: flex;
    align-items: center;
    padding: 8px 16px;
    cursor: pointer;
    gap: 10px;
    font-size: 14px;
    transition: background 0.1s;
}
.entry:nth-child(odd) { background: rgba(255,255,255,0.02); }
.entry:nth-child(even) { background: rgba(255,255,255,0.05); }
.entry:hover { background: var(--hover); }
.entry .icon { width: 20px; text-align: center; flex-shrink: 0; }
.entry .name { flex: 1; }
.entry .badge {
    font-size: 11px;
    padding: 2px 8px;
    border-radius: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.entry.state-remote .name { color: var(--blue); }
.entry.state-synced .name { color: var(--green); }
.entry.state-inherited .name { color: var(--green); }
.entry.state-local .name { color: var(--red); }
.entry.state-stale .name { color: var(--green); }
.entry.state-syncing .name { color: var(--blue); }
.entry.state-remote .badge { background: rgba(78,168,222,0.15); color: var(--blue); }
.entry.state-synced .badge { background: rgba(87,204,153,0.15); color: var(--green); }
.entry.state-inherited .badge { background: rgba(87,204,153,0.10); color: var(--green); opacity: 0.7; }
.entry.state-local .badge { background: rgba(231,111,81,0.15); color: var(--red); }
.entry.state-stale .badge { background: rgba(87,204,153,0.10); color: var(--green); }
.entry.state-syncing .badge { background: rgba(78,168,222,0.15); color: var(--blue); }
#status {
    background: var(--bg2);
    padding: 8px 16px;
    font-size: 12px;
    color: var(--fg-dim);
    border-top: 1px solid rgba(255,255,255,0.08);
    flex-shrink: 0;
    min-height: 32px;
}
#ctx-menu {
    display: none;
    position: fixed;
    background: var(--bg3);
    border: 1px solid rgba(255,255,255,0.15);
    border-radius: 6px;
    padding: 4px 0;
    min-width: 180px;
    z-index: 100;
    box-shadow: 0 8px 24px rgba(0,0,0,0.4);
}
#ctx-menu .ctx-item {
    padding: 8px 16px;
    font-size: 13px;
    cursor: pointer;
    color: var(--fg);
}
#ctx-menu .ctx-item:hover { background: var(--hover); }
#ctx-menu .ctx-item.danger { color: var(--red); }
.modal-overlay {
    display: none;
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,0.6);
    z-index: 200;
    align-items: center;
    justify-content: center;
}
.modal-overlay.active { display: flex; }
.modal {
    background: var(--bg2);
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 8px;
    padding: 24px;
    max-width: 420px;
    width: 90%;
}
.modal h3 { margin-bottom: 12px; font-size: 16px; }
.modal p { font-size: 13px; color: var(--fg-dim); margin-bottom: 16px; line-height: 1.5; }
.modal input[type=text] {
    width: 100%;
    padding: 8px 10px;
    background: var(--bg);
    border: 1px solid rgba(255,255,255,0.15);
    border-radius: 4px;
    color: var(--fg);
    font-family: inherit;
    font-size: 14px;
    margin-bottom: 16px;
    outline: none;
}
.modal input[type=text]:focus { border-color: var(--accent); }
.modal-buttons { display: flex; gap: 8px; justify-content: flex-end; }
.modal-buttons button {
    padding: 8px 16px;
    border: none;
    border-radius: 4px;
    font-family: inherit;
    font-size: 13px;
    cursor: pointer;
}
.btn-cancel { background: rgba(255,255,255,0.08); color: var(--fg); }
.btn-cancel:hover { background: rgba(255,255,255,0.12); }
.btn-confirm { background: var(--accent); color: #000; font-weight: 600; }
.btn-confirm:hover { opacity: 0.9; }
.btn-danger { background: var(--red); color: #fff; font-weight: 600; }
.btn-danger:hover { opacity: 0.9; }
.empty-msg {
    padding: 40px 16px;
    text-align: center;
    color: var(--fg-dim);
    font-size: 14px;
}
#folder-picker { padding: 40px 16px; max-width: 600px; }
#folder-picker h2 { font-size: 18px; margin-bottom: 8px; }
#folder-picker p { font-size: 13px; color: var(--fg-dim); margin-bottom: 20px; }
a.folder-item {
    display: flex;
    flex-direction: column;
    padding: 12px 16px;
    border-radius: 6px;
    margin-bottom: 4px;
    transition: background 0.1s;
    text-decoration: none;
    color: inherit;
}
a.folder-item:hover { background: var(--hover); }
.folder-item .folder-label { font-size: 14px; color: var(--fg); }
.folder-item .folder-path { font-size: 12px; color: var(--fg-dim); margin-top: 2px; }
"""

_JS = """\
let ctxEntry = null;
const $status = document.getElementById('status');
const $ctx = document.getElementById('ctx-menu');
let syncPollId = null;
let wasSyncing = false;

function status(msg) {
    if (!$status) return;
    $status.textContent = msg;
    clearTimeout(status._t);
    status._t = setTimeout(() => { $status.textContent = ''; }, 4000);
}

function formatBytes(b) {
    if (b < 1024) return b + ' B';
    if (b < 1048576) return (b / 1024).toFixed(1) + ' KiB';
    if (b < 1073741824) return (b / 1048576).toFixed(1) + ' MiB';
    return (b / 1073741824).toFixed(1) + ' GiB';
}

async function postApi(path, body) {
    const r = await fetch(path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
    });
    if (!r.ok) {
        const t = await r.text();
        throw new Error(t || r.statusText);
    }
    return r.json();
}

async function pollCompletion() {
    try {
        const r = await fetch('/api/completion?folder=' + encodeURIComponent(FOLDER));
        if (!r.ok) return;
        const data = await r.json();
        if (data.completion >= 100) {
            if ($status) $status.textContent = '';
            if (wasSyncing) { wasSyncing = false; location.reload(); }
        } else {
            wasSyncing = true;
            if ($status) $status.textContent = 'Syncing \u2014 ' + Math.floor(data.completion) + '% (' + data.needItems + ' items, ' + formatBytes(data.needBytes) + ' remaining)';
        }
    } catch {}
}

function startSyncPoll() {
    if (syncPollId) return;
    pollCompletion();
    syncPollId = setInterval(pollCompletion, 1500);
}

function showCtx(ev, el) {
    ev.preventDefault();
    ev.stopPropagation();
    ctxEntry = {
        path: el.dataset.path,
        isDir: el.dataset.dir === 'true',
        state: el.dataset.state,
        name: el.dataset.name
    };
    let html = '';
    const s = ctxEntry.state;
    if (s === 'remote') {
        html += '<div class="ctx-item" onclick="doSync()">Start syncing</div>';
    } else if (s === 'synced') {
        html += '<div class="ctx-item danger" onclick="doUnsync()">Stop syncing</div>';
        if (ctxEntry.isDir) html += '<div class="ctx-item" onclick="doRename()">Rename</div>';
    } else if (s === 'inherited') {
        html += '<div class="ctx-item" style="color:var(--fg-dim);cursor:default">Synced via parent folder</div>';
    } else if (s === 'local') {
        html += '<div class="ctx-item" onclick="doSync()">Start syncing</div>';
    } else if (s === 'syncing') {
        html += '<div class="ctx-item danger" onclick="doUnsync()">Stop syncing</div>';
    } else if (s === 'stale') {
        html += '<div class="ctx-item danger" onclick="doUnsync()">Remove from whitelist</div>';
    }
    if (!html) { hideCtx(); return; }
    $ctx.innerHTML = html;
    $ctx.style.display = 'block';
    let x = ev.clientX, y = ev.clientY;
    if (x + 200 > window.innerWidth) x = window.innerWidth - 200;
    if (y + 150 > window.innerHeight) y = window.innerHeight - 150;
    $ctx.style.left = x + 'px';
    $ctx.style.top = y + 'px';
}

function hideCtx() { $ctx.style.display = 'none'; }

document.addEventListener('click', e => { if (!$ctx.contains(e.target)) hideCtx(); });

async function doSync() {
    const entry = ctxEntry; hideCtx();
    if (!entry) return;
    try {
        await postApi('/api/whitelist/add', { folder: FOLDER, path: entry.path });
        status('Added to sync: ' + entry.path);
        location.reload();
    } catch (err) { status('Error: ' + err.message); }
}

function doUnsync() {
    const entry = ctxEntry; hideCtx();
    if (!entry) return;
    document.getElementById('confirm-title').textContent = 'Stop syncing';
    document.getElementById('confirm-msg').textContent =
        'Remove "' + entry.path + '" from whitelist? The local copy will be deleted.';
    const btn = document.getElementById('confirm-btn');
    btn.onclick = async () => {
        closeModals();
        try {
            await postApi('/api/whitelist/remove', { folder: FOLDER, path: entry.path });
            status('Removed from sync: ' + entry.path);
            location.reload();
        } catch (err) { status('Error: ' + err.message); }
    };
    document.getElementById('confirm-modal').classList.add('active');
}

function doRename() {
    const entry = ctxEntry; hideCtx();
    if (!entry) return;
    document.getElementById('rename-msg').textContent = 'Rename "' + entry.name + '":';
    const inp = document.getElementById('rename-input');
    inp.value = entry.name;
    const btn = document.getElementById('rename-btn');
    btn.onclick = async () => {
        const newName = inp.value.trim();
        if (!newName || newName === entry.name) { closeModals(); return; }
        closeModals();
        const parts = entry.path.split('/');
        parts[parts.length - 1] = newName;
        const newPath = parts.join('/');
        try {
            await postApi('/api/rename', { folder: FOLDER, old_path: entry.path, new_path: newPath });
            status('Renamed: ' + entry.name + ' \u2192 ' + newName);
            location.reload();
        } catch (err) { status('Error: ' + err.message); }
    };
    document.getElementById('rename-modal').classList.add('active');
    setTimeout(() => { inp.focus(); inp.select(); }, 50);
}

function closeModals() {
    document.querySelectorAll('.modal-overlay').forEach(m => m.classList.remove('active'));
}

document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModals(); });

if (typeof FOLDER !== 'undefined') startSyncPoll();
"""


def _render_page(title, body_html, folder_id=None):
    """Wrap content in full HTML page with CSS, modals, and JS."""
    folder_js = f"const FOLDER = {json.dumps(folder_id)};\n" if folder_id else ""
    return (
        '<!DOCTYPE html>\n<html lang="en">\n<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f'<title>{_h(title)}</title>\n'
        f'<style>{_CSS}</style>\n'
        '</head>\n<body>\n'
        f'{body_html}\n'
        '<div id="ctx-menu"></div>\n'
        '<div class="modal-overlay" id="confirm-modal">\n'
        '  <div class="modal">\n'
        '    <h3 id="confirm-title">Confirm</h3>\n'
        '    <p id="confirm-msg"></p>\n'
        '    <div class="modal-buttons">\n'
        '      <button class="btn-cancel" onclick="closeModals()">Cancel</button>\n'
        '      <button class="btn-danger" id="confirm-btn">Confirm</button>\n'
        '    </div>\n'
        '  </div>\n'
        '</div>\n'
        '<div class="modal-overlay" id="rename-modal">\n'
        '  <div class="modal">\n'
        '    <h3>Rename</h3>\n'
        '    <p id="rename-msg"></p>\n'
        '    <input type="text" id="rename-input">\n'
        '    <div class="modal-buttons">\n'
        '      <button class="btn-cancel" onclick="closeModals()">Cancel</button>\n'
        '      <button class="btn-confirm" id="rename-btn">Rename</button>\n'
        '    </div>\n'
        '  </div>\n'
        '</div>\n'
        f'<script>\n{folder_js}{_JS}</script>\n'
        '</body>\n</html>'
    )


def _render_picker(folders):
    """Generate folder picker body HTML."""
    html = '<div id="folder-picker">\n'
    html += '<h2>Select a Syncthing folder</h2>\n'
    html += '<p>Choose which folder to manage:</p>\n'
    for f in folders:
        label = f.get("label") or f["id"]
        href = '/' + urllib.parse.quote(f["id"], safe="") + '/'
        html += (
            f'<a href="{_h(href)}" class="folder-item">'
            f'<span class="folder-label">{_h(label)}</span>'
            f'<span class="folder-path">{_h(f["path"])}</span>'
            f'</a>\n'
        )
    html += '</div>'
    return html


def _render_listing(folder_id, folder_label, rel, entries):
    """Generate breadcrumb + entry list body HTML."""
    qid = urllib.parse.quote(folder_id, safe="")

    # Breadcrumb
    bc = '<div id="breadcrumb">'
    bc += '<a href="/">peek</a><span>/</span>'
    if rel:
        bc += f'<a href="/{_h(qid)}/">{_h(folder_label)}</a>'
        parts = rel.split("/")
        accum = ""
        for i, part in enumerate(parts):
            accum = (accum + "/" + part) if accum else part
            bc += '<span>/</span>'
            if i == len(parts) - 1:
                bc += f'<a class="current">{_h(part)}</a>'
            else:
                href = '/' + qid + '/' + urllib.parse.quote(accum, safe="/") + '/'
                bc += f'<a href="{_h(href)}">{_h(part)}</a>'
    else:
        bc += f'<a class="current">{_h(folder_label)}</a>'
    bc += '</div>\n'

    # Listing
    ls = '<div id="listing">'
    if not entries:
        ls += '<div class="empty-msg">Empty directory</div>'
    else:
        for e in entries:
            cls = 'state-' + e["state"]
            attrs = (
                f' data-path="{_h(e["rel_path"])}"'
                f' data-dir="{str(e["is_dir"]).lower()}"'
                f' data-state="{_h(e["state"])}"'
                f' data-name="{_h(e["name"])}"'
                f' oncontextmenu="showCtx(event,this)"'
            )
            icon = '&#128193;' if e["is_dir"] else '&#128196;'
            badge = f'<span class="badge">{_h(e["state"])}</span>'
            inner = (
                f'<span class="icon">{icon}</span>'
                f'<span class="name">{_h(e["name"])}</span>{badge}'
            )
            if e["is_dir"]:
                href = '/' + qid + '/' + urllib.parse.quote(e["rel_path"], safe="/") + '/'
                ls += f'<a href="{_h(href)}" class="entry {cls}"{attrs}>{inner}</a>'
            else:
                ls += f'<div class="entry {cls}"{attrs}>{inner}</div>'
    ls += '</div>\n'

    return bc + ls + '<div id="status"></div>'


# ---------------------------------------------------------------------------
# StignoreManager
# ---------------------------------------------------------------------------

class StignoreManager:
    """Manages a Syncthing .stignore whitelist via the REST API."""

    DEFAULT_LINES = ["#include globalstignore.txt", "", "# -- Whitelists", "", "*"]
    HEADER_MARKER = "# -- Whitelists"

    def __init__(self, syncthing: 'SyncthingClient', folder_id: str, local_path: str):
        self.syncthing = syncthing
        self.folder_id = folder_id
        self.local_path = pathlib.Path(local_path).expanduser()
        self._ensure_initialized()

    def _ensure_initialized(self):
        """Ensure .stignore has the whitelist structure."""
        lines = self.syncthing.get_ignores(self.folder_id)
        if not any(line.strip() == self.HEADER_MARKER for line in lines):
            self.syncthing.set_ignores(self.folder_id, self.DEFAULT_LINES)

    def _parse(self):
        """Parse .stignore into (preamble_lines, whitelist_set, catchall_lines)."""
        lines = self.syncthing.get_ignores(self.folder_id)

        preamble = []
        whitelist = set()
        catchall = []
        section = "preamble"

        for line in lines:
            if section == "preamble":
                preamble.append(line)
                if line.strip() == self.HEADER_MARKER:
                    section = "whitelist"
            elif section == "whitelist":
                stripped = line.strip()
                if stripped == "*" or stripped == "**":
                    catchall.append(line)
                    section = "catchall"
                elif stripped.startswith("!/"):
                    whitelist.add(stripped[2:])  # strip !/
                elif stripped == "":
                    pass  # skip blank lines in whitelist section
                else:
                    # Unknown line in whitelist section, preserve in preamble
                    preamble.append(line)
            elif section == "catchall":
                catchall.append(line)

        # If we never found the header, create a minimal structure
        if section == "preamble":
            preamble.append("")
            preamble.append(self.HEADER_MARKER)
            catchall = ["*"]

        return preamble, whitelist, catchall

    def _write(self, preamble, whitelist, catchall):
        """Write .stignore via Syncthing API."""
        lines = list(preamble)
        for path in sorted(whitelist):
            lines.append("!/" + path)
        lines.append("")
        lines.extend(catchall)
        self.syncthing.set_ignores(self.folder_id, lines)

    def get_whitelist(self) -> list:
        _, whitelist, _ = self._parse()
        return sorted(whitelist)

    def whitelist_status(self, path: str) -> str:
        """Return 'direct', 'inherited', or '' for a path."""
        _, whitelist, _ = self._parse()
        for w in whitelist:
            if path == w:
                return "direct"
            if path.startswith(w + "/"):
                return "inherited"
        return ""

    def is_whitelisted(self, path: str) -> bool:
        return self.whitelist_status(path) != ""

    def add(self, path: str):
        preamble, whitelist, catchall = self._parse()
        # If a parent is already whitelisted, no-op
        for w in list(whitelist):
            if path == w or path.startswith(w + "/"):
                return
        # If adding a parent, remove children it covers
        whitelist = {w for w in whitelist if not w.startswith(path + "/")}
        whitelist.add(path)
        self._write(preamble, whitelist, catchall)

    def remove(self, path: str):
        preamble, whitelist, catchall = self._parse()
        # Remove exact match and any children
        whitelist = {w for w in whitelist if w != path and not w.startswith(path + "/")}
        self._write(preamble, whitelist, catchall)
        # Delete local copy
        local = self.local_path / path
        if local.is_dir():
            shutil.rmtree(str(local))
        elif local.exists():
            local.unlink()

    def rename(self, old_path: str, new_path: str):
        preamble, whitelist, catchall = self._parse()
        # Update whitelist entries
        updated = set()
        for w in whitelist:
            if w == old_path:
                updated.add(new_path)
            elif w.startswith(old_path + "/"):
                updated.add(new_path + w[len(old_path):])
            else:
                updated.add(w)
        # Rename local directory
        local_old = self.local_path / old_path
        local_new = self.local_path / new_path
        if not local_old.exists():
            raise FileNotFoundError(
                f"Local copy not found: {old_path}. Wait for sync to complete before renaming."
            )
        local_new.parent.mkdir(parents=True, exist_ok=True)
        os.rename(str(local_old), str(local_new))
        self._write(preamble, updated, catchall)


# ---------------------------------------------------------------------------
# Syncthing REST API client
# ---------------------------------------------------------------------------

class SyncthingClient:
    """Thin wrapper around the Syncthing REST API (stdlib only)."""

    def __init__(self, api_key: str, base_url: str = "http://127.0.0.1:8384"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def _request(self, method: str, path: str, body=None):
        url = self.base_url + path
        headers = {"X-API-Key": self.api_key}
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, method=method, headers=headers, data=data)
        with urllib.request.urlopen(req) as resp:
            resp_body = resp.read()
            return json.loads(resp_body) if resp_body else None

    def get_folders(self) -> list:
        """Return list of {id, label, path} from Syncthing config."""
        folders = self._request("GET", "/rest/config/folders")
        return [{"id": f["id"], "label": f.get("label", ""), "path": f["path"]}
                for f in folders]

    def browse(self, folder_id: str, prefix: str = "") -> list:
        """Return entries from db/browse for a folder (flat, one level)."""
        path = "/rest/db/browse?folder=" + urllib.parse.quote(folder_id) + "&levels=0"
        if prefix:
            path += "&prefix=" + urllib.parse.quote(prefix)
        return self._request("GET", path) or []

    def get_ignores(self, folder_id: str) -> list:
        """Return the raw .stignore lines for a folder."""
        data = self._request("GET", "/rest/db/ignores?folder=" + urllib.parse.quote(folder_id))
        return data.get("ignore", []) if data else []

    def set_ignores(self, folder_id: str, lines: list):
        """Replace .stignore content for a folder."""
        self._request("POST", "/rest/db/ignores?folder=" + urllib.parse.quote(folder_id),
                       body={"ignore": lines})

    def completion(self, folder_id: str) -> dict:
        """Return aggregate completion for a folder across all devices."""
        return self._request("GET", "/rest/db/completion?folder=" + urllib.parse.quote(folder_id))

    def trigger_scan(self, folder_id: str):
        """Ask Syncthing to rescan a folder."""
        self._request("POST", "/rest/db/scan?folder=" + urllib.parse.quote(folder_id))


# ---------------------------------------------------------------------------
# HTTP Handler
# ---------------------------------------------------------------------------

class NasUIHandler(http.server.BaseHTTPRequestHandler):
    """Stateless request handler — every request is self-contained."""

    syncthing: SyncthingClient  # set once by main()

    def log_message(self, format, *args):
        pass

    def _send_json(self, data, code=200):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, code, msg):
        body = msg.encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html):
        body = html.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length)) if length else {}

    def _validate_path(self, path: str) -> str:
        """Normalize and validate a relative path."""
        path = path.strip("/")
        if not path:
            return ""
        normalized = os.path.normpath(path)
        if normalized.startswith("..") or os.path.isabs(normalized):
            raise ValueError("Invalid path")
        for part in normalized.split(os.sep):
            if part == "..":
                raise ValueError("Invalid path")
        return normalized

    def _resolve_folder(self, folder_id):
        """Look up folder, return (folder_info, StignoreManager) or None."""
        folders = self.syncthing.get_folders()
        folder = next((f for f in folders if f["id"] == folder_id), None)
        if folder is None:
            return None
        stignore = StignoreManager(self.syncthing, folder_id, folder["path"])
        return folder, stignore

    def _build_entries(self, folder_id, stignore, rel):
        """Build the entry list for a directory listing."""
        syncthing_path = stignore.local_path
        whitelist = stignore.get_whitelist()

        # Check folder sync status
        try:
            comp = self.syncthing.completion(folder_id)
            folder_synced = comp.get("completion", 0) >= 100
        except Exception:
            folder_synced = True

        # Primary source: Syncthing global index
        browse_entries = self.syncthing.browse(folder_id, rel)

        # Hide Syncthing internals at folder root
        if not rel:
            browse_entries = [e for e in browse_entries
                             if e.get("name") not in (".stignore", ".stfolder")]

        browse_entries.sort(
            key=lambda e: (e.get("type") != "FILE_INFO_TYPE_DIRECTORY", e["name"].lower())
        )

        entries = []
        seen = set()
        for item in browse_entries:
            name = item["name"]
            seen.add(name)
            item_rel = (rel + "/" + name) if rel else name
            is_dir = item.get("type") == "FILE_INFO_TYPE_DIRECTORY"

            state = "remote"
            wl_status = stignore.whitelist_status(item_rel)
            local_exists = (syncthing_path / item_rel).exists()
            if wl_status == "direct":
                state = "synced" if folder_synced else "syncing"
            elif wl_status == "inherited":
                state = "inherited" if folder_synced else "syncing"
            elif local_exists:
                # A dir that only exists because a child is whitelisted
                # (e.g. blender/ exists because blender/addons is synced)
                # should stay remote, not show as local.
                has_wl_child = is_dir and any(
                    w.startswith(item_rel + "/") for w in whitelist
                )
                state = "remote" if has_wl_child else "local"

            entries.append({
                "name": name,
                "rel_path": item_rel,
                "is_dir": is_dir,
                "state": state,
            })

        # Merge local-only entries not in global index
        local_dir = syncthing_path / rel if rel else syncthing_path
        if local_dir.is_dir():
            try:
                local_items = sorted(local_dir.iterdir(),
                                     key=lambda p: (not p.is_dir(), p.name.lower()))
            except PermissionError:
                local_items = []
            for item in local_items:
                name = item.name
                if name in seen or (not rel and name in (".stignore", ".stfolder")):
                    continue
                item_rel = (rel + "/" + name) if rel else name
                is_dir = item.is_dir()
                wl_status = stignore.whitelist_status(item_rel)
                if wl_status == "direct":
                    state = "synced" if folder_synced else "syncing"
                elif wl_status == "inherited":
                    state = "inherited" if folder_synced else "syncing"
                else:
                    has_wl_child = is_dir and any(
                        w.startswith(item_rel + "/") for w in whitelist
                    )
                    state = "remote" if has_wl_child else "local"
                entries.append({
                    "name": name,
                    "rel_path": item_rel,
                    "is_dir": is_dir,
                    "state": state,
                })

        # Detect stale whitelist entries
        for w in stignore.get_whitelist():
            if rel:
                if not w.startswith(rel + "/"):
                    continue
                remainder = w[len(rel) + 1:]
            else:
                remainder = w
            name = remainder.split("/")[0]
            if name not in seen:
                seen.add(name)
                item_rel = (rel + "/" + name) if rel else name
                is_dir = "/" in remainder or any(
                    w2.startswith(item_rel + "/") for w2 in stignore.get_whitelist()
                )
                entries.append({
                    "name": name,
                    "rel_path": item_rel,
                    "is_dir": is_dir,
                    "state": "stale",
                })

        # Sort: remote first, then synced/inherited/syncing, then local, then stale;
        # within each group dirs-first then alphabetical
        state_order = {"remote": 0, "syncing": 1, "synced": 2, "inherited": 3, "local": 4, "stale": 5}
        entries.sort(key=lambda e: (state_order.get(e["state"], 9), not e["is_dir"], e["name"].lower()))
        return entries

    # -- Routing -------------------------------------------------------------

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/":
            folders = self.syncthing.get_folders()
            self._send_html(_render_page("peek", _render_picker(folders)))
            return

        if path.startswith("/api/"):
            if path == "/api/completion":
                qs = urllib.parse.parse_qs(parsed.query)
                folder_id = qs.get("folder", [""])[0]
                if not folder_id:
                    self._send_error(400, "folder required")
                    return
                self._handle_completion(folder_id)
            else:
                self._send_error(404, "Not found")
            return

        # /<folder_id>/sub/path/
        stripped = path.strip("/")
        if not stripped:
            self._send_error(404, "Not found")
            return

        parts = stripped.split("/", 1)
        folder_id = urllib.parse.unquote(parts[0])
        sub_path = urllib.parse.unquote(parts[1]) if len(parts) > 1 else ""

        result = self._resolve_folder(folder_id)
        if result is None:
            self._send_error(404, "Unknown folder")
            return
        folder, stignore = result

        try:
            rel = self._validate_path(sub_path)
        except ValueError:
            self._send_error(400, "Invalid path")
            return

        try:
            entries = self._build_entries(folder_id, stignore, rel)
        except Exception as e:
            self._send_error(502, f"Syncthing API error: {e}")
            return

        folder_label = folder.get("label") or folder["id"]
        body = _render_listing(folder_id, folder_label, rel, entries)
        self._send_html(_render_page(f"peek({folder_label})", body, folder_id=folder_id))

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path

        if path == "/api/whitelist/add":
            self._handle_add()
        elif path == "/api/whitelist/remove":
            self._handle_remove()
        elif path == "/api/rename":
            self._handle_rename()
        else:
            self._send_error(404, "Not found")

    # -- API handlers --------------------------------------------------------

    def _handle_completion(self, folder_id):
        try:
            data = self.syncthing.completion(folder_id)
            self._send_json({
                "completion": data.get("completion", 0),
                "needItems": data.get("needItems", 0),
                "needBytes": data.get("needBytes", 0),
            })
        except Exception as e:
            self._send_error(502, f"Syncthing API error: {e}")

    def _handle_add(self):
        body = self._read_body()
        folder_id = body.get("folder", "")
        if not folder_id:
            self._send_error(400, "folder required")
            return
        result = self._resolve_folder(folder_id)
        if result is None:
            self._send_error(404, "Unknown folder")
            return
        _, stignore = result
        raw = body.get("path", "")
        try:
            path = self._validate_path(raw)
        except ValueError:
            self._send_error(400, "Invalid path")
            return
        if not path:
            self._send_error(400, "Path required")
            return
        stignore.add(path)
        try:
            self.syncthing.trigger_scan(folder_id)
        except Exception:
            pass
        self._send_json({"ok": True})

    def _handle_remove(self):
        body = self._read_body()
        folder_id = body.get("folder", "")
        if not folder_id:
            self._send_error(400, "folder required")
            return
        result = self._resolve_folder(folder_id)
        if result is None:
            self._send_error(404, "Unknown folder")
            return
        _, stignore = result
        raw = body.get("path", "")
        try:
            path = self._validate_path(raw)
        except ValueError:
            self._send_error(400, "Invalid path")
            return
        if not path:
            self._send_error(400, "Path required")
            return
        stignore.remove(path)
        try:
            self.syncthing.trigger_scan(folder_id)
        except Exception:
            pass
        self._send_json({"ok": True})

    def _handle_rename(self):
        body = self._read_body()
        folder_id = body.get("folder", "")
        if not folder_id:
            self._send_error(400, "folder required")
            return
        result = self._resolve_folder(folder_id)
        if result is None:
            self._send_error(404, "Unknown folder")
            return
        _, stignore = result
        try:
            old = self._validate_path(body.get("old_path", ""))
            new = self._validate_path(body.get("new_path", ""))
        except ValueError:
            self._send_error(400, "Invalid path")
            return
        if not old or not new:
            self._send_error(400, "Both old_path and new_path required")
            return
        try:
            stignore.rename(old, new)
        except FileNotFoundError as e:
            self._send_error(409, str(e))
            return
        try:
            self.syncthing.trigger_scan(folder_id)
        except Exception:
            pass
        self._send_json({"ok": True})


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="NAS Selective Sync UI")
    parser.add_argument("--api-key", required=True, help="Syncthing REST API key")
    parser.add_argument("--syncthing-url", default="http://127.0.0.1:8384",
                        help="Syncthing base URL (default: http://127.0.0.1:8384)")
    parser.add_argument("--port", type=int, default=8080, help="Port (default: 8080)")
    parser.add_argument("--bind", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
    args = parser.parse_args()

    syncthing = SyncthingClient(args.api_key, args.syncthing_url)
    try:
        folders = syncthing.get_folders()
    except Exception as e:
        parser.error(f"Cannot reach Syncthing at {args.syncthing_url}: {e}")
    print(f"Connected to Syncthing \u2014 {len(folders)} folder(s) available")

    NasUIHandler.syncthing = syncthing

    server = http.server.HTTPServer((args.bind, args.port), NasUIHandler)
    print(f"peek \u2192 http://{args.bind}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()


if __name__ == "__main__":
    main()
