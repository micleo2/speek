#!/usr/bin/env python3
"""NAS Selective Sync UI — web UI for managing Syncthing .stignore whitelists."""

import http.server
import pathlib
import json
import argparse
import shutil
import os
import tempfile
import urllib.parse

# ---------------------------------------------------------------------------
# Embedded frontend
# ---------------------------------------------------------------------------

HTML_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>peek({{SYNCTHING_PATH}})</title>
<style>
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
#breadcrumb span {
    color: var(--fg-dim);
    font-size: 14px;
}
#breadcrumb a {
    color: var(--accent);
    text-decoration: none;
    font-size: 14px;
    cursor: pointer;
    padding: 2px 4px;
    border-radius: 3px;
}
#breadcrumb a:hover { background: var(--hover); }
#breadcrumb a.current { color: var(--fg); cursor: default; }

#listing {
    flex: 1;
    overflow-y: auto;
    padding: 8px 0;
    max-width: 800px;
}
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
.entry.state-remote .badge { background: rgba(78,168,222,0.15); color: var(--blue); }
.entry.state-synced .badge { background: rgba(87,204,153,0.15); color: var(--green); }
.entry.state-inherited .badge { background: rgba(87,204,153,0.10); color: var(--green); opacity: 0.7; }
.entry.state-local .badge { background: rgba(231,111,81,0.15); color: var(--red); }

#status {
    background: var(--bg2);
    padding: 8px 16px;
    font-size: 12px;
    color: var(--fg-dim);
    border-top: 1px solid rgba(255,255,255,0.08);
    flex-shrink: 0;
    min-height: 32px;
}

/* Context menu */
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

/* Modal */
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
</style>
</head>
<body>

<div id="breadcrumb"></div>
<div id="listing"></div>
<div id="status"></div>

<div id="ctx-menu"><!-- filled by JS --></div>

<div class="modal-overlay" id="confirm-modal">
  <div class="modal">
    <h3 id="confirm-title">Confirm</h3>
    <p id="confirm-msg"></p>
    <div class="modal-buttons">
      <button class="btn-cancel" onclick="closeModals()">Cancel</button>
      <button class="btn-danger" id="confirm-btn">Confirm</button>
    </div>
  </div>
</div>

<div class="modal-overlay" id="rename-modal">
  <div class="modal">
    <h3>Rename</h3>
    <p id="rename-msg"></p>
    <input type="text" id="rename-input">
    <div class="modal-buttons">
      <button class="btn-cancel" onclick="closeModals()">Cancel</button>
      <button class="btn-confirm" id="rename-btn">Rename</button>
    </div>
  </div>
</div>

<script>
let currentPath = '';
let entries = [];
let ctxEntry = null;

const $listing = document.getElementById('listing');
const $breadcrumb = document.getElementById('breadcrumb');
const $status = document.getElementById('status');
const $ctx = document.getElementById('ctx-menu');

function status(msg) {
    $status.textContent = msg;
    clearTimeout(status._t);
    status._t = setTimeout(() => { $status.textContent = ''; }, 4000);
}

async function api(method, path, body) {
    const opts = { method };
    if (body) {
        opts.headers = { 'Content-Type': 'application/json' };
        opts.body = JSON.stringify(body);
    }
    const r = await fetch(path, opts);
    if (!r.ok) {
        const t = await r.text();
        throw new Error(t || r.statusText);
    }
    return r.json();
}

function renderBreadcrumb() {
    let html = '';
    const parts = currentPath ? currentPath.split('/') : [];
    html += `<a onclick="navigate('')">(root)</a>`;
    let accum = '';
    for (let i = 0; i < parts.length; i++) {
        accum += (accum ? '/' : '') + parts[i];
        html += `<span>/</span>`;
        if (i === parts.length - 1) {
            html += `<a class="current">${esc(parts[i])}</a>`;
        } else {
            const p = accum;
            html += `<a onclick="navigate('${escAttr(p)}')">${esc(parts[i])}</a>`;
        }
    }
    $breadcrumb.innerHTML = html;
}

function stateIcon(state) {
    if (state === 'synced') return '&#9679;';
    if (state === 'local') return '&#9679;';
    return '&#9675;';
}

function renderListing() {
    if (entries.length === 0) {
        $listing.innerHTML = '<div class="empty-msg">Empty directory</div>';
        return;
    }
    let html = '';
    for (const e of entries) {
        const cls = `state-${e.state}`;
        html += `<div class="entry ${cls}" data-path="${escAttr(e.rel_path)}" data-dir="${e.is_dir}" data-state="${e.state}" data-name="${escAttr(e.name)}"`;
        if (e.is_dir) {
            html += ` onclick="navigate('${escAttr(e.rel_path)}')"`;
        }
        html += ` oncontextmenu="showCtx(event, this)">`;
        html += `<span class="icon">${e.is_dir ? '&#128193;' : '&#128196;'}</span>`;
        html += `<span class="name">${esc(e.name)}</span>`;
        if (e.state !== 'remote') {
            html += `<span class="badge">${e.state}</span>`;
        }
        html += `</div>`;
    }
    $listing.innerHTML = html;
}

async function navigate(path) {
    currentPath = path;
    renderBreadcrumb();
    try {
        const data = await api('GET', '/api/ls?path=' + encodeURIComponent(path));
        entries = data.entries;
        renderListing();
    } catch (err) {
        $listing.innerHTML = `<div class="empty-msg">Error: ${esc(err.message)}</div>`;
        status('Error: ' + err.message);
    }
}

function showCtx(ev, el) {
    ev.preventDefault();
    ev.stopPropagation();
    const path = el.dataset.path;
    const isDir = el.dataset.dir === 'true';
    const state = el.dataset.state;
    const name = el.dataset.name;
    ctxEntry = { path, isDir, state, name };

    let html = '';
    if (state === 'remote') {
        html += `<div class="ctx-item" onclick="doSync()">Start syncing</div>`;
    } else if (state === 'synced') {
        html += `<div class="ctx-item danger" onclick="doUnsync()">Stop syncing</div>`;
        if (isDir) html += `<div class="ctx-item" onclick="doRename()">Rename</div>`;
    } else if (state === 'inherited') {
        html += `<div class="ctx-item" style="color:var(--fg-dim);cursor:default">Synced via parent folder</div>`;
    } else if (state === 'local') {
        html += `<div class="ctx-item" onclick="doSync()">Start syncing</div>`;
    }
    if (!html) {
        hideCtx();
        return;
    }
    $ctx.innerHTML = html;
    $ctx.style.display = 'block';
    // Position
    let x = ev.clientX, y = ev.clientY;
    const rect = $ctx.getBoundingClientRect();
    if (x + 200 > window.innerWidth) x = window.innerWidth - 200;
    if (y + 150 > window.innerHeight) y = window.innerHeight - 150;
    $ctx.style.left = x + 'px';
    $ctx.style.top = y + 'px';
}

function hideCtx() {
    $ctx.style.display = 'none';
}

document.addEventListener('click', (e) => {
    if (!$ctx.contains(e.target)) hideCtx();
});

async function doSync() {
    const entry = ctxEntry;
    hideCtx();
    if (!entry) return;
    try {
        await api('POST', '/api/whitelist/add', { path: entry.path });
        status('Added to sync: ' + entry.path);
        navigate(currentPath);
    } catch (err) {
        status('Error: ' + err.message);
    }
}

function doUnsync() {
    const entry = ctxEntry;
    hideCtx();
    if (!entry) return;
    document.getElementById('confirm-title').textContent = 'Stop syncing';
    document.getElementById('confirm-msg').textContent =
        `Remove "${entry.path}" from whitelist? The local copy will be deleted.`;
    const btn = document.getElementById('confirm-btn');
    btn.onclick = async () => {
        closeModals();
        try {
            await api('POST', '/api/whitelist/remove', { path: entry.path });
            status('Removed from sync: ' + entry.path);
            navigate(currentPath);
        } catch (err) {
            status('Error: ' + err.message);
        }
    };
    document.getElementById('confirm-modal').classList.add('active');
}

function doRename() {
    const entry = ctxEntry;
    hideCtx();
    if (!entry) return;
    document.getElementById('rename-msg').textContent = `Rename "${entry.name}":`;
    const inp = document.getElementById('rename-input');
    inp.value = entry.name;
    const btn = document.getElementById('rename-btn');
    btn.onclick = async () => {
        const newName = inp.value.trim();
        if (!newName || newName === entry.name) { closeModals(); return; }
        closeModals();
        // Build new path: same parent, new name
        const parts = entry.path.split('/');
        parts[parts.length - 1] = newName;
        const newPath = parts.join('/');
        try {
            await api('POST', '/api/rename', { old_path: entry.path, new_path: newPath });
            status('Renamed: ' + entry.name + ' → ' + newName);
            navigate(currentPath);
        } catch (err) {
            status('Error: ' + err.message);
        }
    };
    document.getElementById('rename-modal').classList.add('active');
    setTimeout(() => { inp.focus(); inp.select(); }, 50);
}

function closeModals() {
    document.querySelectorAll('.modal-overlay').forEach(m => m.classList.remove('active'));
}

document.addEventListener('keydown', e => {
    if (e.key === 'Escape') closeModals();
});

function esc(s) {
    return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
function escAttr(s) {
    return s.replace(/\\/g,'\\\\').replace(/'/g,"\\'").replace(/"/g,'&quot;');
}

// Boot
navigate('');
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# StignoreManager
# ---------------------------------------------------------------------------

class StignoreManager:
    """Parses and manages a Syncthing .stignore whitelist file."""

    DEFAULT_CONTENT = "#include globalstignore.txt\n\n# -- Whitelists\n\n*\n"
    HEADER_MARKER = "# -- Whitelists"

    def __init__(self, syncthing_path: str):
        self.syncthing_path = pathlib.Path(syncthing_path)
        self.stignore_path = self.syncthing_path / ".stignore"
        self._ensure_exists()

    def _ensure_exists(self):
        self.syncthing_path.mkdir(parents=True, exist_ok=True)
        if not self.stignore_path.exists():
            self._write_raw(self.DEFAULT_CONTENT)

    def _parse(self):
        """Parse .stignore into (preamble_lines, whitelist_set, catchall_lines)."""
        text = self.stignore_path.read_text()
        lines = text.splitlines()

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
        """Write .stignore atomically."""
        lines = list(preamble)
        for path in sorted(whitelist):
            lines.append("!/" + path)
        lines.append("")
        lines.extend(catchall)
        content = "\n".join(lines) + "\n"
        self._write_raw(content)

    def _write_raw(self, content: str):
        """Atomic write via temp file + os.replace."""
        fd, tmp = tempfile.mkstemp(dir=str(self.syncthing_path), suffix=".stignore.tmp")
        try:
            os.write(fd, content.encode())
            os.close(fd)
            os.replace(tmp, str(self.stignore_path))
        except Exception:
            os.close(fd) if not os.get_inheritable(fd) else None
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

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
        local = self.syncthing_path / path
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
        local_old = self.syncthing_path / old_path
        local_new = self.syncthing_path / new_path
        if not local_old.exists():
            raise FileNotFoundError(
                f"Local copy not found: {old_path}. Wait for sync to complete before renaming."
            )
        local_new.parent.mkdir(parents=True, exist_ok=True)
        os.rename(str(local_old), str(local_new))
        self._write(preamble, updated, catchall)


# ---------------------------------------------------------------------------
# HTTP Handler
# ---------------------------------------------------------------------------

class NasUIHandler(http.server.BaseHTTPRequestHandler):
    """Routes requests to the appropriate handler."""

    nfs_path: pathlib.Path
    stignore: StignoreManager

    def log_message(self, format, *args):
        # Quieter logging
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

    def _validate_path(self, path: str) -> str:
        """Normalize and validate a relative path. Returns normalized path or raises."""
        path = path.strip("/")
        if not path:
            return ""
        normalized = os.path.normpath(path)
        if normalized.startswith("..") or os.path.isabs(normalized):
            raise ValueError("Invalid path")
        # Reject any component that is ..
        for part in normalized.split(os.sep):
            if part == "..":
                raise ValueError("Invalid path")
        return normalized

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length)) if length else {}

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/":
            self._send_html(HTML_PAGE.replace("{{SYNCTHING_PATH}}", str(self.stignore.syncthing_path)))
        elif path == "/api/ls":
            self._handle_ls(parsed)
        elif path == "/api/whitelist":
            self._handle_whitelist()
        else:
            self._send_error(404, "Not found")

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

    def _handle_ls(self, parsed):
        qs = urllib.parse.parse_qs(parsed.query)
        raw_path = qs.get("path", [""])[0]
        try:
            rel = self._validate_path(raw_path)
        except ValueError:
            self._send_error(400, "Invalid path")
            return

        syncthing_path = self.stignore.syncthing_path
        nfs_target = self.nfs_path / rel if rel else self.nfs_path
        local_target = syncthing_path / rel if rel else syncthing_path
        if not nfs_target.is_dir() and not local_target.is_dir():
            self._send_error(404, "Directory not found")
            return

        entries = []
        if nfs_target.is_dir():
            try:
                items = sorted(nfs_target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
            except PermissionError:
                self._send_error(403, "Permission denied")
                return
        else:
            items = []

        seen = set()
        for item in items:
            name = item.name
            if name.startswith("."):
                continue
            seen.add(name)
            item_rel = (rel + "/" + name) if rel else name
            is_dir = item.is_dir()

            state = "remote"
            wl_status = self.stignore.whitelist_status(item_rel)
            local_exists = (syncthing_path / item_rel).exists()
            if wl_status == "direct":
                state = "synced"
            elif wl_status == "inherited":
                state = "inherited"
            elif local_exists:
                state = "local"

            has_children = False
            if is_dir:
                try:
                    has_children = any(True for _ in item.iterdir())
                except PermissionError:
                    pass

            entries.append({
                "name": name,
                "rel_path": item_rel,
                "is_dir": is_dir,
                "state": state,
                "has_children": has_children,
            })

        # Merge local-only entries from Syncthing folder
        local_dir = syncthing_path / rel if rel else syncthing_path
        if local_dir.is_dir():
            try:
                local_items = sorted(local_dir.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
            except PermissionError:
                local_items = []
            for item in local_items:
                name = item.name
                if name.startswith(".") or name in seen:
                    continue
                item_rel = (rel + "/" + name) if rel else name
                is_dir = item.is_dir()
                has_children = False
                if is_dir:
                    try:
                        has_children = any(True for _ in item.iterdir())
                    except PermissionError:
                        pass
                wl_status = self.stignore.whitelist_status(item_rel)
                if wl_status == "direct":
                    state = "synced"
                elif wl_status == "inherited":
                    state = "inherited"
                else:
                    state = "local"
                entries.append({
                    "name": name,
                    "rel_path": item_rel,
                    "is_dir": is_dir,
                    "state": state,
                    "has_children": has_children,
                })

        self._send_json({"entries": entries})

    def _handle_whitelist(self):
        self._send_json({"whitelist": self.stignore.get_whitelist()})

    def _handle_add(self):
        body = self._read_body()
        raw = body.get("path", "")
        try:
            path = self._validate_path(raw)
        except ValueError:
            self._send_error(400, "Invalid path")
            return
        if not path:
            self._send_error(400, "Path required")
            return
        self.stignore.add(path)
        self._send_json({"ok": True})

    def _handle_remove(self):
        body = self._read_body()
        raw = body.get("path", "")
        try:
            path = self._validate_path(raw)
        except ValueError:
            self._send_error(400, "Invalid path")
            return
        if not path:
            self._send_error(400, "Path required")
            return
        self.stignore.remove(path)
        self._send_json({"ok": True})

    def _handle_rename(self):
        body = self._read_body()
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
            self.stignore.rename(old, new)
        except FileNotFoundError as e:
            self._send_error(409, str(e))
            return
        self._send_json({"ok": True})


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="NAS Selective Sync UI")
    parser.add_argument("--nfs", required=True, help="Path to readonly NFS mount")
    parser.add_argument("--syncthing", required=True, help="Path to local Syncthing folder")
    parser.add_argument("--port", type=int, default=8080, help="Port (default: 8080)")
    parser.add_argument("--bind", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
    args = parser.parse_args()

    nfs = pathlib.Path(args.nfs)
    if not nfs.is_dir():
        parser.error(f"NFS path not found: {args.nfs}")

    stignore = StignoreManager(args.syncthing)

    NasUIHandler.nfs_path = nfs
    NasUIHandler.stignore = stignore

    server = http.server.HTTPServer((args.bind, args.port), NasUIHandler)
    print(f"NAS Sync UI → http://{args.bind}:{args.port}")
    print(f"  NFS:       {nfs}")
    print(f"  Syncthing: {stignore.syncthing_path}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()


if __name__ == "__main__":
    main()
