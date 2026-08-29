#!/usr/bin/env python3
"""NAS Selective Sync UI — web UI for managing Syncthing .stignore whitelists."""

import argparse
import http.server
import json
import os
import pathlib
import re
import shutil
import subprocess
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime
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
    max-width: 800px;
}
.listing-table {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    table-layout: fixed;
}
.listing-table thead th {
    position: sticky;
    top: 0;
    z-index: 5;
    background: var(--bg);
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--fg-dim);
    padding: 6px 8px;
    border-bottom: 1px solid rgba(255,255,255,0.06);
}
.listing-table thead th a {
    color: var(--fg-dim);
    text-decoration: none;
    cursor: pointer;
}
.listing-table thead th a:hover { color: var(--accent); }
.listing-table thead th a.active { color: var(--accent); }
.listing-table tbody td {
    padding: 8px 8px;
    font-size: 14px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.listing-table th:first-child, .listing-table td:first-child { padding-left: 16px; }
.listing-table th:last-child, .listing-table td:last-child { padding-right: 16px; }
.listing-table .col-icon { width: 24px; text-align: center; font-size: 13px; }
.listing-table .col-name { text-align: left; }
.listing-table .col-size { width: 80px; text-align: right; font-size: 13px; }
.listing-table .col-mtime { width: 164px; font-size: 12px; }
.listing-table .col-state { width: 104px; text-align: right; }
.listing-table .col-size, .listing-table .col-mtime {
    color: var(--fg-dim);
    font-variant-numeric: tabular-nums;
}
tr.entry { cursor: pointer; transition: background 0.1s; }
tr.entry:nth-child(odd) { background: rgba(255,255,255,0.02); }
tr.entry:nth-child(even) { background: rgba(255,255,255,0.05); }
tr.entry:hover { background: var(--hover); }
tr.entry.selected { background: rgba(255,255,255,0.18); outline: 1px solid rgba(255,255,255,0.25); outline-offset: -1px; }
a.name-link { text-decoration: none; color: inherit; }
tr.entry.state-remote .col-name { color: var(--blue); }
tr.entry.state-partial .col-name { color: var(--blue); }
tr.entry.state-synced .col-name { color: var(--green); }
tr.entry.state-inherited .col-name { color: var(--green); }
tr.entry.state-local .col-name { color: var(--red); }
tr.entry.state-stale .col-name { color: var(--green); }
.entry .badge {
    font-size: 11px;
    padding: 2px 8px;
    border-radius: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.entry.state-remote .badge { background: rgba(78,168,222,0.15); color: var(--blue); }
.entry.state-partial .badge { background: transparent; border: 1px solid rgba(87,204,153,0.45); color: var(--green); padding: 1px 7px; }
.entry.state-synced .badge { background: rgba(87,204,153,0.15); color: var(--green); }
.entry.state-inherited .badge { background: rgba(87,204,153,0.10); color: var(--green); opacity: 0.7; }
.entry.state-local .badge { background: rgba(231,111,81,0.15); color: var(--red); }
.entry.state-stale .badge { background: rgba(87,204,153,0.10); color: var(--green); }
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
#unmanaged-note {
    background: rgba(231,111,81,0.12);
    border-bottom: 1px solid rgba(231,111,81,0.3);
    color: var(--red);
    padding: 8px 16px;
    font-size: 12px;
    flex-shrink: 0;
}
.pending-title { margin-top: 28px; }
.pending-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 12px 16px;
    border-radius: 6px;
    margin-bottom: 4px;
    background: rgba(78,168,222,0.06);
}
.pending-info { display: flex; flex-direction: column; }
.pending-item .accept-btn {
    padding: 8px 16px;
    border: none;
    border-radius: 4px;
    font-family: inherit;
    font-size: 13px;
    cursor: pointer;
}
a.folder-item.selected { background: rgba(255,255,255,0.18); outline: 1px solid rgba(255,255,255,0.25); outline-offset: -1px; }
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
    } else if (s === 'partial') {
        html += '<div class="ctx-item" onclick="doSync()">Sync entire directory</div>';
    } else if (s === 'synced') {
        html += '<div class="ctx-item danger" onclick="doUnsync()">Stop syncing</div>';
        if (ctxEntry.isDir) html += '<div class="ctx-item" onclick="doRename()">Rename</div>';
    } else if (s === 'inherited') {
        html += '<div class="ctx-item" style="color:var(--fg-dim);cursor:default">Synced via parent folder</div>';
    } else if (s === 'local') {
        html += '<div class="ctx-item" onclick="doSync()">Start syncing</div>';
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

document.addEventListener('click', e => {
    if (!$ctx.contains(e.target)) hideCtx();
    const acc = e.target.closest ? e.target.closest('.accept-btn') : null;
    if (acc) {
        doAccept(acc.dataset.id, acc.dataset.label, acc.dataset.suggested);
        return;
    }
    const row = e.target.closest ? e.target.closest('tr.entry') : null;
    if (row && row.dataset.href) {
        e.preventDefault();
        location.href = row.dataset.href;
    }
});

function doAccept(id, label, suggested) {
    document.getElementById('accept-msg').textContent =
        'Local path for "' + (label || id) + '" (created if missing):';
    const inp = document.getElementById('accept-input');
    inp.value = suggested || '';
    const btn = document.getElementById('accept-btn');
    btn.onclick = async () => {
        const path = inp.value.trim();
        if (!path) return;
        closeModals();
        try {
            await postApi('/api/folders/accept', { folder: id, label: label, path: path });
            location.reload();
        } catch (err) { status('Error: ' + err.message); alert('Error: ' + err.message); }
    };
    document.getElementById('accept-modal').classList.add('active');
    setTimeout(() => { inp.focus(); inp.select(); }, 50);
}

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
    const stale = entry.state === 'stale';
    document.getElementById('confirm-title').textContent = stale ? 'Remove stale entry' : 'Stop syncing';
    document.getElementById('confirm-msg').textContent = stale
        ? 'Remove "' + entry.path + '" from whitelist? (No local copy exists.)'
        : 'Remove "' + entry.path + '" from whitelist? The local copy will be deleted.';
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

function kbSelect(el) {
    ctxEntry = {
        path: el.dataset.path,
        isDir: el.dataset.dir === 'true',
        state: el.dataset.state,
        name: el.dataset.name
    };
}

document.addEventListener('keydown', e => {
    if (e.key === 'Escape') { closeModals(); hideCtx(); return; }

    // Modal keyboard shortcuts
    const confirmModal = document.getElementById('confirm-modal');
    if (confirmModal.classList.contains('active')) {
        if (e.key === 'Enter' || e.key === 'y') {
            e.preventDefault();
            document.getElementById('confirm-btn').click();
        }
        return;
    }
    const renameModal = document.getElementById('rename-modal');
    if (renameModal.classList.contains('active')) {
        if (e.key === 'Enter') {
            e.preventDefault();
            document.getElementById('rename-btn').click();
        }
        return;
    }
    const acceptModal = document.getElementById('accept-modal');
    if (acceptModal.classList.contains('active')) {
        if (e.key === 'Enter') {
            e.preventDefault();
            document.getElementById('accept-btn').click();
        }
        return;
    }

    // h always works (even in empty directories)
    if (e.key === 'h') {
        const bc = document.querySelectorAll('#breadcrumb a:not(.current)');
        if (bc.length) {
            e.preventDefault();
            location.href = bc[bc.length - 1].href;
        }
        return;
    }

    // Navigation — works on both .entry (listing) and .folder-item (picker)
    const items = Array.from(document.querySelectorAll('.entry, .folder-item'));
    if (!items.length) return;
    const cur = document.querySelector('.entry.selected, .folder-item.selected');
    let idx = cur ? items.indexOf(cur) : -1;
    if (e.key === 'j') {
        e.preventDefault();
        idx = Math.min(idx + 1, items.length - 1);
        if (cur) cur.classList.remove('selected');
        items[idx].classList.add('selected');
        items[idx].scrollIntoView({ block: 'nearest' });
    } else if (e.key === 'k') {
        e.preventDefault();
        idx = Math.max(idx <= 0 ? 0 : idx - 1, 0);
        if (cur) cur.classList.remove('selected');
        items[idx].classList.add('selected');
        items[idx].scrollIntoView({ block: 'nearest' });
    } else if (e.key === 'l' || e.key === 'Enter') {
        const href = cur && (cur.href || cur.dataset.href);
        if (href) {
            e.preventDefault();
            location.href = href;
        }
    } else if (e.key === 's') {
        if (!cur) return;
        const s = cur.dataset.state;
        if (s === 'remote' || s === 'local' || s === 'partial') {
            e.preventDefault();
            kbSelect(cur);
            doSync();
        }
    } else if (e.key === 'x') {
        if (!cur) return;
        const s = cur.dataset.state;
        if (s === 'synced' || s === 'stale') {
            e.preventDefault();
            kbSelect(cur);
            doUnsync();
        }
    } else if (e.key === 'r') {
        if (!cur) return;
        if (cur.dataset.state === 'synced' && cur.dataset.dir === 'true') {
            e.preventDefault();
            kbSelect(cur);
            doRename();
        }
    }
});

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
        '<div class="modal-overlay" id="accept-modal">\n'
        '  <div class="modal">\n'
        '    <h3>Accept folder</h3>\n'
        '    <p id="accept-msg"></p>\n'
        '    <input type="text" id="accept-input">\n'
        '    <div class="modal-buttons">\n'
        '      <button class="btn-cancel" onclick="closeModals()">Cancel</button>\n'
        '      <button class="btn-confirm" id="accept-btn">Create &amp; accept</button>\n'
        '    </div>\n'
        '  </div>\n'
        '</div>\n'
        f'<script>\n{folder_js}{_JS}</script>\n'
        '</body>\n</html>'
    )


def _fmt_size(size, is_dir=False):
    """Human-readable file size, or em-dash for dirs/unknown."""
    if is_dir or size is None:
        return "\u2014"
    if size < 1024:
        return f"{size} B"
    if size < 1048576:
        return f"{size / 1024:.1f} KiB"
    if size < 1073741824:
        return f"{size / 1048576:.1f} MiB"
    return f"{size / 1073741824:.1f} GiB"


def _fmt_time(value):
    """Render an ISO timestamp as 'Aug 14, 2026 1:49pm', or em-dash."""
    if not value:
        return "\u2014"
    try:
        dt = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return "\u2014"
    ampm = "am" if dt.hour < 12 else "pm"
    hour = dt.hour % 12 or 12
    return f"{dt.strftime('%b %d, %Y')} {hour}:{dt.minute:02d}{ampm}"


# Valid ?sort= values; absence/anything else means the default listing.
_SORTS = ("name-desc", "name-asc", "mtime-desc", "mtime-asc", "size-desc", "size-asc")


def _mtime_epoch(value):
    """Epoch seconds for an ISO timestamp, or None if missing/invalid."""
    try:
        return datetime.fromisoformat(value).timestamp()
    except (TypeError, ValueError):
        return None


def _null_last_key(value, desc):
    """Sort key for an optional numeric value; missing sorts last either way."""
    if value is None:
        return (1, 0)
    return (0, -value if desc else value)


def _render_picker(folders, pending=()):
    """Generate folder picker body HTML.

    `pending` is a list of {id, label, devices, suggested_path} dicts for
    folders other devices have offered but this machine hasn't accepted yet.
    """
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
    if pending:
        html += '<h2 class="pending-title">Pending invitations</h2>\n'
        html += (
            '<p>Folders other devices offered to share. Accepting creates the '
            'local directory with a speek-managed .stignore — nothing syncs '
            'until you whitelist it.</p>\n'
        )
        for p in pending:
            label = p["label"] or p["id"]
            html += (
                '<div class="pending-item">'
                '<div class="pending-info">'
                f'<span class="folder-label">{_h(label)}</span>'
                f'<span class="folder-path">offered by {_h(p["devices"])}</span>'
                '</div>'
                f'<button class="btn-confirm accept-btn"'
                f' data-id="{_h(p["id"])}"'
                f' data-label="{_h(p["label"])}"'
                f' data-suggested="{_h(p["suggested_path"])}">Accept…</button>'
                '</div>\n'
            )
    html += '</div>'
    return html


def _render_listing(folder_id, folder_label, rel, entries, sort="", managed=True):
    """Generate breadcrumb + entry list body HTML.

    managed=False renders a read-only browse: a notice banner, no Status
    column, no badges, and no state attributes (which disables the context
    menu and the sync/unsync/rename keyboard actions client-side).
    """
    qid = urllib.parse.quote(folder_id, safe="")
    # The default listing keeps a clean URL; an explicit sort rides along as a
    # query string on every directory link so it survives navigation.
    sort_qs = "?sort=" + urllib.parse.quote(sort) if sort else ""

    def dir_href(relpath):
        href = "/" + qid + "/"
        if relpath:
            href += urllib.parse.quote(relpath, safe="/") + "/"
        return href + sort_qs

    # Breadcrumb
    bc = '<div id="breadcrumb">'
    bc += '<a href="/">speek</a><span>/</span>'
    if rel:
        bc += f'<a href="{_h(dir_href(""))}">{_h(folder_label)}</a>'
        parts = rel.split("/")
        accum = ""
        for i, part in enumerate(parts):
            accum = (accum + "/" + part) if accum else part
            bc += '<span>/</span>'
            if i == len(parts) - 1:
                bc += f'<a class="current">{_h(part)}</a>'
            else:
                bc += f'<a href="{_h(dir_href(accum))}">{_h(part)}</a>'
    else:
        bc += f'<a class="current">{_h(folder_label)}</a>'
    bc += '</div>\n'

    # Listing — a real <table> so header and row columns always align
    base = "/" + qid + "/" + (urllib.parse.quote(rel, safe="/") + "/" if rel else "")

    def header_cell(css, label, key=None):
        """A <th>; sortable columns cycle none -> descending -> ascending -> none."""
        if key is None:
            return f'<th class="{css}">{label}</th>'
        if sort == key + '-desc':
            nxt, arrow = key + '-asc', ' \u2193'
        elif sort == key + '-asc':
            nxt, arrow = '', ' \u2191'
        else:
            nxt, arrow = key + '-desc', ''
        href = base + ('?sort=' + nxt if nxt else '')
        active = ' class="active"' if arrow else ''
        return f'<th class="{css}"><a href="{_h(href)}"{active}>{label}{arrow}</a></th>'

    notice = ''
    if not managed:
        notice = (
            '<div id="unmanaged-note">Read-only: this folder\'s .stignore is not '
            'speek-managed.</div>\n'
        )

    ls = '<div id="listing">\n<table class="listing-table">\n'
    ls += (
        '<thead>\n'
        '<tr class="listing-header">'
        + header_cell('col-icon', '')
        + header_cell('col-name', 'Name', 'name')
        + header_cell('col-size', 'Size', 'size')
        + header_cell('col-mtime', 'Modified', 'mtime')
        + (header_cell('col-state', 'Status') if managed else '')
        + '</tr>\n'
        '</thead>\n<tbody>\n'
    )
    ncols = 5 if managed else 4
    if not entries:
        ls += f'<tr class="empty-row"><td colspan="{ncols}" class="empty-msg">Empty directory</td></tr>\n'
    else:
        for e in entries:
            href = dir_href(e["rel_path"]) if e["is_dir"] else None
            cls = f' state-{e["state"]}' if e["state"] else ''
            attrs = f' data-dir="{str(e["is_dir"]).lower()}"' + (
                f' data-href="{_h(href)}"' if href else ''
            )
            if managed:
                attrs += (
                    f' data-path="{_h(e["rel_path"])}"'
                    f' data-state="{_h(e["state"])}"'
                    f' data-name="{_h(e["name"])}"'
                    ' oncontextmenu="showCtx(event,this)"'
                )
            icon = '&#128193;' if e["is_dir"] else '&#128196;'
            if href:
                name_cell = (
                    f'<a class="name-link" href="{_h(href)}">{_h(e["name"])}</a>'
                )
            else:
                name_cell = _h(e["name"])
            state_cell = (
                f'<td class="col-state"><span class="badge">{_h(e["state"])}</span></td>'
                if managed
                else ''
            )
            ls += (
                f'<tr class="entry{cls}"{attrs}>'
                f'<td class="col-icon">{icon}</td>'
                f'<td class="col-name" title="{_h(e["name"])}">{name_cell}</td>'
                f'<td class="col-size">{_h(_fmt_size(e.get("size"), e["is_dir"]))}</td>'
                f'<td class="col-mtime">{_h(_fmt_time(e.get("mtime")))}</td>'
                f'{state_cell}'
                '</tr>\n'
            )
    ls += '</tbody>\n</table>\n</div>\n'

    return bc + notice + ls + '<div id="status"></div>'


# ---------------------------------------------------------------------------
# StignoreManager
# ---------------------------------------------------------------------------

# The speek .stignore layout has two explicit sections. Everything above the
# managed marker is the user's to hand-edit (ordinary ignore patterns like
# node_modules — Syncthing ignores are first-match-wins, so patterns up there
# override the whitelist and apply even inside whitelisted directories).
# Everything below it is rewritten wholesale by speek: whitelist negations
# followed by the catch-all. Adding the managed marker by hand is how an
# existing .stignore opts in to speek management.
USER_MARKER = "# ==== USER_DEFINED_SECTION (edit freely) ===="
MANAGED_MARKER = "# ==== SPEEK_MANAGED_SECTION (DO_NOT_EDIT) ===="


def validate_speek_managed(lines) -> str | None:
    """Return None if .stignore conforms to the speek-managed layout, else why not.

    Valid means: both section markers present in order, and the managed section
    contains only `!/path` whitelist entries followed by a final catch-all
    (`*`/`**`), blanks aside. The whitelist must precede the catch-all —
    Syncthing ignores are first-match-wins, so entries after it would be dead.
    The user section above the marker is free-form.
    """
    stripped = [ln.strip() for ln in lines]
    if USER_MARKER not in stripped:
        return "no user-section marker"
    if MANAGED_MARKER not in stripped:
        return "no managed-section marker"
    idx = stripped.index(MANAGED_MARKER)
    if stripped.index(USER_MARKER) > idx:
        return "user section must come before the managed section"
    saw_catchall = False
    for ln in stripped[idx + 1 :]:
        if not ln:
            continue
        if ln in ("*", "**"):
            saw_catchall = True
        elif ln.startswith("!/"):
            if saw_catchall:
                return f"whitelist entry after the catch-all: {ln}"
        else:
            return f"unexpected line in managed section: {ln}"
    if not saw_catchall:
        return "managed section has no catch-all pattern"
    return None


def skeleton_stignore() -> list:
    """The .stignore a brand-new speek folder starts with: default-deny,
    empty whitelist, empty user section."""
    return [USER_MARKER, "", MANAGED_MARKER, "", "*"]


class StignoreManager:
    """Manages a Syncthing .stignore whitelist via the REST API."""

    def __init__(self, syncthing: 'SyncthingClient', folder_id: str, local_path: str):
        self.syncthing = syncthing
        self.folder_id = folder_id
        self.local_path = pathlib.Path(local_path).expanduser()
        self._cached_parse = None

    def is_managed(self) -> bool:
        """True if this folder's .stignore conforms to the speek layout."""
        return (
            validate_speek_managed(self.syncthing.get_ignores(self.folder_id)) is None
        )

    def _parse(self):
        """Parse .stignore into (preamble_lines, whitelist_set, catchall_lines).

        The preamble is the whole user section including the managed marker as
        its last line. Result is cached until _write().
        """
        if self._cached_parse is not None:
            return self._cached_parse
        lines = self.syncthing.get_ignores(self.folder_id)

        preamble = []
        whitelist = set()
        catchall = []
        section = "preamble"

        for line in lines:
            if section == "preamble":
                preamble.append(line)
                if line.strip() == MANAGED_MARKER:
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

        # No marker found (only reachable through a race — mutations on
        # unmanaged folders are refused upstream): graft the structure onto
        # the existing content in memory, wrapping it as the user section.
        # Nothing is written back until a whitelist mutation happens.
        if section == "preamble":
            if not any(line.strip() for line in preamble):
                preamble = [USER_MARKER, ""]
            preamble.append(MANAGED_MARKER)
            catchall = ["*"]

        self._cached_parse = (preamble, whitelist, catchall)
        return preamble, whitelist, catchall

    def _write(self, preamble, whitelist, catchall):
        """Write .stignore via Syncthing API."""
        self._cached_parse = None
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

    def _reject_root(self, path: str):
        """Backstop: the folder root must never be a remove/rename target,
        regardless of what upstream validation let through."""
        if os.path.normpath(path.strip("/")) in ("", "."):
            raise ValueError("Refusing to operate on the folder root")

    def remove(self, path: str):
        self._reject_root(path)
        preamble, whitelist, catchall = self._parse()
        # Remove exact match and any children
        whitelist = {w for w in whitelist if w != path and not w.startswith(path + "/")}
        self._write(preamble, whitelist, catchall)
        # Delete local copy
        local = self.local_path / path
        if local.is_symlink():
            local.unlink()
        elif local.is_dir():
            shutil.rmtree(str(local))
        elif local.exists():
            local.unlink()

    def rename(self, old_path: str, new_path: str):
        self._reject_root(old_path)
        self._reject_root(new_path)
        preamble, whitelist, catchall = self._parse()
        # Update whitelist entries
        updated = set()
        for w in whitelist:
            if w == old_path:
                updated.add(new_path)
            elif w.startswith(old_path + "/"):
                updated.add(new_path + w[len(old_path) :])
            else:
                updated.add(w)
        # Rename local directory
        local_old = self.local_path / old_path
        local_new = self.local_path / new_path
        if not local_old.exists():
            raise FileNotFoundError(
                f"Local copy not found: {old_path}. Wait for sync to complete before renaming."
            )
        if local_new.exists() or local_new.is_symlink():
            raise FileExistsError(f"Target already exists: {new_path}")
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
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp_body = resp.read()
            return json.loads(resp_body) if resp_body else None

    def get_folders(self) -> list:
        """Return list of {id, label, path} from Syncthing config."""
        folders = self._request("GET", "/rest/config/folders") or []
        return [
            {"id": f["id"], "label": f.get("label", ""), "path": f["path"]}
            for f in folders
        ]

    def browse(self, folder_id: str, prefix: str = "") -> list:
        """Return entries from db/browse for a folder (flat, one level)."""
        path = "/rest/db/browse?folder=" + urllib.parse.quote(folder_id) + "&levels=0"
        if prefix:
            path += "&prefix=" + urllib.parse.quote(prefix)
        return self._request("GET", path) or []

    def get_ignores(self, folder_id: str) -> list:
        """Return the raw .stignore lines for a folder."""
        data = self._request(
            "GET", "/rest/db/ignores?folder=" + urllib.parse.quote(folder_id)
        )
        return (data.get("ignore") or []) if data else []

    def set_ignores(self, folder_id: str, lines: list):
        """Replace .stignore content for a folder."""
        self._request(
            "POST",
            "/rest/db/ignores?folder=" + urllib.parse.quote(folder_id),
            body={"ignore": lines},
        )

    def completion(self, folder_id: str) -> dict:
        """Return aggregate completion for a folder across all devices."""
        return (
            self._request(
                "GET", "/rest/db/completion?folder=" + urllib.parse.quote(folder_id)
            )
            or {}
        )

    def trigger_scan(self, folder_id: str):
        """Ask Syncthing to rescan a folder."""
        self._request("POST", "/rest/db/scan?folder=" + urllib.parse.quote(folder_id))

    def pending_folders(self) -> dict:
        """Return folders offered by other devices, keyed by folder id."""
        return self._request("GET", "/rest/cluster/pending/folders") or {}

    def get_device_names(self) -> dict:
        """Return {deviceID: display name} for all configured devices."""
        devices = self._request("GET", "/rest/config/devices") or []
        return {d["deviceID"]: d.get("name") or d["deviceID"][:7] for d in devices}

    def default_folder_path(self) -> str:
        """Return the configured default path for new folders ('' if unset)."""
        data = self._request("GET", "/rest/config/defaults/folder") or {}
        return data.get("path") or ""

    def add_folder(self, folder_id: str, label: str, path: str, device_ids: list):
        """Add (accept) a folder, shared with the given devices."""
        self._request(
            "POST",
            "/rest/config/folders",
            body={
                "id": folder_id,
                "label": label,
                "path": path,
                "type": "sendreceive",
                "devices": [{"deviceID": d} for d in device_ids],
            },
        )


# ---------------------------------------------------------------------------
# HTTP Handler
# ---------------------------------------------------------------------------


class NasUIHandler(http.server.BaseHTTPRequestHandler):
    """Stateless request handler — every request is self-contained."""

    syncthing: SyncthingClient  # set once by main()

    def log_message(self, format, *args):
        pass  # suppress per-request logging

    def log_error(self, format, *args):
        import sys

        sys.stderr.write(f"{format % args}\n")

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
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length else {}
        except ValueError:
            raise ValueError("Invalid request body") from None
        if not isinstance(body, dict):
            # ValueError, not TypeError: the do_POST wrapper maps it to a 400.
            raise ValueError("Invalid request body")  # noqa: TRY004
        return body

    # -- Security guards -----------------------------------------------------
    # speek holds the Syncthing API key and can delete/rename files on disk, so
    # it must not be drivable by a web page the user happens to have open. These
    # bring it to parity with Syncthing's own passwordless-GUI protections.

    ALLOWED_HOSTNAMES = ("127.0.0.1", "localhost", "::1")

    def handle(self):
        """Suppress tracebacks from clients that disconnect mid-response
        (browser speculative connections and aborted prefetches do this
        constantly)."""
        try:
            super().handle()
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True

    def parse_request(self):
        """Central guard: every verb gets the Host check, and every verb except
        GET/HEAD gets the CSRF check. Running this here (rather than in each
        do_* method) means a future handler cannot ship unguarded, and adding
        do_OPTIONS by accident cannot void the no-preflight-answered invariant
        the CSRF defense relies on."""
        if not super().parse_request():
            return False
        if not self._check_host():
            return False
        if self.command not in ("GET", "HEAD") and not self._check_csrf():
            return False
        return True

    def _hostname_ok(self, value):
        """True if a Host/Origin authority is an allowed hostname (port ignored)."""
        if not value:
            return False
        value = value.strip()
        if ":" in value and "[" not in value and value.count(":") > 1:
            hostname = value  # unbracketed IPv6 literal; no port possible
        else:
            try:
                hostname = urllib.parse.urlsplit("//" + value).hostname or ""
            except ValueError:
                return False
        return hostname.lower().rstrip(".") in self.ALLOWED_HOSTNAMES

    def _check_host(self):
        """Reject non-loopback Host headers to defeat DNS rebinding."""
        if not self._hostname_ok(self.headers.get("Host", "")):
            self._send_error(403, "Forbidden: invalid Host header")
            return False
        return True

    def _check_csrf(self):
        """Reject cross-origin state-changing requests.

        Requiring a JSON content type forces a CORS preflight for any
        cross-origin caller; this server never answers OPTIONS, so the real
        request is never sent. Simple-request forgery (an HTML form or a
        text/plain fetch, which skip preflight) is refused here outright.
        Origin and Fetch-metadata are checked too as defense in depth.
        """
        ctype = self.headers.get("Content-Type", "").split(";")[0].strip().lower()
        if ctype != "application/json":
            self._send_error(403, "Forbidden: Content-Type must be application/json")
            return False
        site = self.headers.get("Sec-Fetch-Site")
        if site is not None and site not in ("same-origin", "none"):
            self._send_error(403, "Forbidden: cross-site request")
            return False
        origin = self.headers.get("Origin")
        if origin is not None:
            # A same-origin request's Origin authority is exactly the request's
            # Host authority (scheme aside), so require that — not merely "some
            # loopback host on some port", which would trust every other local
            # web app (e.g. a dev server on another port).
            parsed = urllib.parse.urlsplit(origin)
            host = self.headers.get("Host", "")
            if (
                parsed.scheme not in ("http", "https")
                or not self._hostname_ok(parsed.netloc)
                or parsed.netloc.lower() != host.strip().lower()
            ):
                self._send_error(403, "Forbidden: cross-origin request")
                return False
        return True

    def _validate_path(self, path: str) -> str:
        """Normalize a relative path; returns "" for the folder root.

        normpath collapses interior ".." segments, so after it only a leading
        ".." can remain — that (an escape above the root) is the one thing to
        reject. The root itself normalizes to "" and is a valid GET target;
        the POST handlers refuse empty paths themselves, and StignoreManager
        has its own root backstop.
        """
        normalized = os.path.normpath(path.strip("/"))
        if normalized == ".":
            return ""
        if normalized == ".." or normalized.startswith("../"):
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

    def _resolve_managed(self, folder_id):
        """Resolve a folder for a mutation; sends the error response and
        returns None unless the folder exists and is speek-managed."""
        if not folder_id:
            self._send_error(400, "folder required")
            return None
        result = self._resolve_folder(folder_id)
        if result is None:
            self._send_error(404, "Unknown folder")
            return None
        _, stignore = result
        if not stignore.is_managed():
            self._send_error(409, "This folder's .stignore is not speek-managed")
            return None
        return result

    def _pending_list(self):
        """Pending folder offers for the picker; empty on any API hiccup."""
        try:
            pending = self.syncthing.pending_folders()
            if not pending:
                return []
            names = self.syncthing.get_device_names()
            base = self.syncthing.default_folder_path()
        except Exception:
            return []
        items = []
        for fid, info in sorted(pending.items()):
            offered = info.get("offeredBy") or {}
            label = next(
                (m.get("label") for m in offered.values() if m.get("label")), ""
            )
            devices = ", ".join(names.get(d, d[:7]) for d in sorted(offered))
            # Label and id are remote-controlled — never let them steer the
            # suggested path (a label of "../x" or "/etc/x" must not escape
            # the base directory).
            leaf = re.sub(r"[^A-Za-z0-9 ._-]", "_", label or fid).strip()
            if leaf.strip(".") == "":
                leaf = "folder"
            suggested = os.path.join(base, leaf) if base else ""
            items.append(
                {
                    "id": fid,
                    "label": label,
                    "devices": devices or "unknown device",
                    "suggested_path": suggested,
                }
            )
        return items

    def _build_entries(self, folder_id, stignore, rel, sort="", managed=True):
        """Build the entry list for a directory listing.

        With managed=False (the .stignore is not speek-managed) no whitelist
        logic runs at all: every entry gets an empty state and the caller
        renders a read-only listing without badges or actions.
        """
        syncthing_path = stignore.local_path
        whitelist = stignore.get_whitelist() if managed else []

        def entry_state(item_rel, is_dir, local_exists):
            if not managed:
                return ""
            wl_status = stignore.whitelist_status(item_rel)
            if wl_status == "direct":
                return "synced"
            if wl_status == "inherited":
                return "inherited"
            if is_dir and any(w.startswith(item_rel + "/") for w in whitelist):
                # Not synced itself, but something below it is — this also
                # covers a dir that only exists locally because of that child
                # (e.g. blender/ exists because blender/addons is synced),
                # which must not show as "local".
                return "partial"
            return "local" if local_exists else "remote"

        # Primary source: Syncthing global index
        browse_entries = self.syncthing.browse(folder_id, rel)

        # Hide Syncthing internals at folder root
        if not rel:
            browse_entries = [
                e
                for e in browse_entries
                if e.get("name") not in (".stignore", ".stfolder")
            ]

        browse_entries.sort(
            key=lambda e: (
                e.get("type") != "FILE_INFO_TYPE_DIRECTORY",
                e["name"].lower(),
            )
        )

        entries = []
        seen = set()
        for item in browse_entries:
            name = item["name"]
            seen.add(name)
            item_rel = (rel + "/" + name) if rel else name
            is_dir = item.get("type") == "FILE_INFO_TYPE_DIRECTORY"

            state = entry_state(item_rel, is_dir, (syncthing_path / item_rel).exists())

            entries.append(
                {
                    "name": name,
                    "rel_path": item_rel,
                    "is_dir": is_dir,
                    "state": state,
                    "size": item.get("size"),
                    "mtime": item.get("modTime"),
                }
            )

        # Merge local-only entries not in global index
        local_dir = syncthing_path / rel if rel else syncthing_path
        if local_dir.is_dir():
            try:
                local_items = sorted(
                    local_dir.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())
                )
            except PermissionError:
                local_items = []
            for item in local_items:
                name = item.name
                if name in seen or (not rel and name in (".stignore", ".stfolder")):
                    continue
                seen.add(name)
                item_rel = (rel + "/" + name) if rel else name
                is_dir = item.is_dir()
                try:
                    st = item.stat()
                    size = st.st_size
                    mtime = datetime.fromtimestamp(st.st_mtime).astimezone().isoformat()
                except OSError:
                    size = None
                    mtime = None
                state = entry_state(item_rel, is_dir, True)
                entries.append(
                    {
                        "name": name,
                        "rel_path": item_rel,
                        "is_dir": is_dir,
                        "state": state,
                        "size": size,
                        "mtime": mtime,
                    }
                )

        # Detect stale whitelist entries
        for w in whitelist:
            if rel:
                if not w.startswith(rel + "/"):
                    continue
                remainder = w[len(rel) + 1 :]
            else:
                remainder = w
            name = remainder.split("/")[0]
            if name not in seen:
                seen.add(name)
                item_rel = (rel + "/" + name) if rel else name
                is_dir = "/" in remainder or any(
                    w2.startswith(item_rel + "/") for w2 in whitelist
                )
                entries.append(
                    {
                        "name": name,
                        "rel_path": item_rel,
                        "is_dir": is_dir,
                        "state": "stale",
                        "size": None,
                        "mtime": None,
                    }
                )

        # Sort: remote first, then partial/synced/inherited, then local, then
        # stale; dirs before files; within that, the requested column (default:
        # name ascending). Two passes — the stable outer sort preserves the
        # column order within each group.
        state_order = {
            "remote": 0,
            "partial": 1,
            "synced": 2,
            "inherited": 3,
            "local": 4,
            "stale": 5,
        }
        key, _, order = sort.partition("-")
        desc = order == "desc"
        entries.sort(
            key=lambda e: e["name"].lower(), reverse=desc if key == "name" else False
        )
        if key == "mtime":
            entries.sort(
                key=lambda e: _null_last_key(_mtime_epoch(e.get("mtime")), desc)
            )
        elif key == "size":
            entries.sort(key=lambda e: _null_last_key(e.get("size"), desc))
        entries.sort(key=lambda e: (state_order.get(e["state"], 9), not e["is_dir"]))
        return entries

    # -- Routing -------------------------------------------------------------
    # do_GET/do_POST are thin wrappers so no handler can leak a raw traceback:
    # a wedged/down Syncthing or filesystem surprise becomes a 502, a bad
    # request body a 400, instead of a dropped connection.

    def do_GET(self):
        try:
            self._route_get()
        except Exception as e:
            self._send_error(502, f"Internal error: {e}")

    def do_POST(self):
        try:
            self._route_post()
        except ValueError as e:
            self._send_error(400, str(e))
        except Exception as e:
            self._send_error(502, f"Internal error: {e}")

    def _route_get(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/":
            folders = self.syncthing.get_folders()
            self._send_html(
                _render_page("speek", _render_picker(folders, self._pending_list()))
            )
            return

        if path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
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
            qs = urllib.parse.parse_qs(parsed.query)
            sort = qs.get("sort", [""])[0]
            if sort not in _SORTS:
                sort = ""
            managed = stignore.is_managed()
            entries = self._build_entries(folder_id, stignore, rel, sort, managed)
        except Exception as e:
            self._send_error(502, f"Syncthing API error: {e}")
            return

        folder_label = folder.get("label") or folder["id"]
        body = _render_listing(folder_id, folder_label, rel, entries, sort, managed)
        self._send_html(
            _render_page(f"speek({folder_label})", body, folder_id=folder_id)
        )

    def _route_post(self):
        path = urllib.parse.urlparse(self.path).path

        if path == "/api/whitelist/add":
            self._handle_add()
        elif path == "/api/whitelist/remove":
            self._handle_remove()
        elif path == "/api/rename":
            self._handle_rename()
        elif path == "/api/folders/accept":
            self._handle_accept()
        else:
            self._send_error(404, "Not found")

    # -- API handlers --------------------------------------------------------

    def _handle_completion(self, folder_id):
        try:
            data = self.syncthing.completion(folder_id)
            self._send_json(
                {
                    "completion": data.get("completion", 0),
                    "needItems": data.get("needItems", 0),
                    "needBytes": data.get("needBytes", 0),
                }
            )
        except Exception as e:
            self._send_error(502, f"Syncthing API error: {e}")

    def _handle_add(self):
        body = self._read_body()
        folder_id = body.get("folder", "")
        result = self._resolve_managed(folder_id)
        if result is None:
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
        result = self._resolve_managed(folder_id)
        if result is None:
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
        result = self._resolve_managed(folder_id)
        if result is None:
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
        except (FileNotFoundError, FileExistsError) as e:
            self._send_error(409, str(e))
            return
        try:
            self.syncthing.trigger_scan(folder_id)
        except Exception:
            pass
        self._send_json({"ok": True})

    def _handle_accept(self):
        """Accept a pending folder offer: create the local directory, write a
        speek-managed skeleton .stignore, then add the folder to Syncthing.
        Writing the skeleton BEFORE Syncthing learns about the folder means it
        is born default-deny — there is no window where everything would sync.
        """
        body = self._read_body()
        folder_id = body.get("folder", "")
        raw_path = str(body.get("path") or "")
        if not folder_id or not raw_path:
            self._send_error(400, "folder and path required")
            return
        if not folder_id.isprintable() or len(folder_id) > 256:
            self._send_error(400, "Invalid folder id")
            return
        try:
            offer = self.syncthing.pending_folders().get(folder_id)
        except Exception as e:
            self._send_error(502, f"Syncthing API error: {e}")
            return
        if offer is None:
            self._send_error(404, "No pending offer for that folder")
            return
        offered_by = offer.get("offeredBy") or {}
        # Syncthing's config prepare silently drops folder devices that aren't
        # in the device list, which would leave the folder shared with nobody
        # and the offer stuck in pending — refuse up front instead.
        devices = sorted(set(offered_by) & set(self.syncthing.get_device_names()))
        if not devices:
            self._send_error(
                400, "Offering device is not in the device list; add it first"
            )
            return
        label = str(body.get("label") or "") or next(
            (m.get("label") for m in offered_by.values() if m.get("label")), ""
        )
        local = pathlib.Path(raw_path).expanduser()
        if not local.is_absolute():
            self._send_error(400, "Path must be absolute")
            return
        if ".." in local.parts:
            self._send_error(400, "Path must not contain '..'")
            return
        if local.exists():
            if not local.is_dir():
                self._send_error(400, "Path exists and is not a directory")
                return
            # A leftover skeleton .stignore from a failed accept is fine —
            # anything else means we'd be adopting an existing directory.
            if any(c.name != ".stignore" for c in local.iterdir()):
                self._send_error(400, "Directory is not empty")
                return
        else:
            try:
                local.mkdir(parents=True)
            except OSError as e:
                self._send_error(400, f"Cannot create directory: {e}")
                return
        (local / ".stignore").write_text("\n".join(skeleton_stignore()) + "\n")
        try:
            self.syncthing.add_folder(folder_id, label, str(local), devices)
        except Exception as e:
            self._send_error(502, f"Syncthing API error: {e}")
            return
        self._send_json({"ok": True})


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="NAS Selective Sync UI")
    parser.add_argument(
        "--api-key",
        default=None,
        help="Syncthing REST API key (default: from `syncthing cli config gui apikey get`)",
    )
    parser.add_argument(
        "--syncthing-url",
        default="http://127.0.0.1:8384",
        help="Syncthing base URL (default: http://127.0.0.1:8384)",
    )
    parser.add_argument("--port", type=int, default=8080, help="Port (default: 8080)")
    parser.add_argument(
        "--bind", default="127.0.0.1", help="Bind address (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--allow-host",
        action="append",
        default=[],
        metavar="HOSTNAME",
        help="Additional Host header value to accept (repeatable); needed when "
        "a reverse proxy forwards the original Host, e.g. speek.example.com",
    )
    parser.add_argument(
        "--no-open", action="store_true", help="Don't open the browser automatically"
    )
    args = parser.parse_args()

    extra_hosts = [h.lower() for h in args.allow_host]
    if args.bind.lower() not in NasUIHandler.ALLOWED_HOSTNAMES:
        # Without this the server would answer every request with a Host-check
        # 403 and nothing would point at --bind as the cause.
        extra_hosts.append(args.bind.lower())
        print(
            "WARNING: binding to a non-loopback address exposes an UNAUTHENTICATED\n"
            "         file-deletion/rename API to the network. This is unsupported;\n"
            "         see THREAT_MODEL.md. Prefer an authenticating reverse proxy\n"
            "         with speek bound to loopback (plus --allow-host if the proxy\n"
            "         forwards the original Host header)."
        )
    if extra_hosts:
        NasUIHandler.ALLOWED_HOSTNAMES = NasUIHandler.ALLOWED_HOSTNAMES + tuple(
            extra_hosts
        )

    if args.api_key is None:
        print(
            "warning: no api key given, so defaulting to `syncthing cli config gui apikey get`"
        )
        try:
            result = subprocess.run(
                ["syncthing", "cli", "config", "gui", "apikey", "get"],
                capture_output=True,
                text=True,
                check=True,
            )
        except (OSError, subprocess.CalledProcessError) as e:
            detail = getattr(e, "stderr", "") or str(e)
            parser.error(f"Could not get API key from syncthing cli: {detail.strip()}")
        args.api_key = result.stdout.strip()

    syncthing = SyncthingClient(args.api_key, args.syncthing_url)
    try:
        folders = syncthing.get_folders()
    except Exception as e:
        parser.error(f"Cannot reach Syncthing at {args.syncthing_url}: {e}")
    print(f"Connected to Syncthing \u2014 {len(folders)} folder(s) available")

    NasUIHandler.syncthing = syncthing

    server = http.server.ThreadingHTTPServer((args.bind, args.port), NasUIHandler)
    # A wildcard bind is not a browsable address; visit via loopback.
    browse_host = "127.0.0.1" if args.bind in ("0.0.0.0", "::") else args.bind
    print(f"speek \u2192 http://{browse_host}:{args.port}")
    if not args.no_open:
        webbrowser.open(f"http://{browse_host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()


if __name__ == "__main__":
    main()
