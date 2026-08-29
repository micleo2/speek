# speek
basically a glorified .stignore editor. but! while still being able to browse
through the files/folders you ignored. 

## why?
I personally use this so I just have one giant syncthing folder on my NAS that
I can share with all my devices, but only pick and choose what I want, e.g. just
the projects I'm actually working on. This doesn't replace my usage of a networked
drive like Samba or NFS. But I often like being able to still access my files offline.

## WARNING: Security

tldr; this is only meant to be run by a trusted user, on a single user machine,
accessed only on that machine. trying to do anything else is a terrible idea.
More details in [THREAT_MODEL.md](THREAT_MODEL.md).

# AI generated details follow
## Quick start

A single-file web UI for **selective syncing** with [Syncthing](https://syncthing.net/).
Browse a folder's full remote tree and pick which directories actually sync to
this machine — speek manages the `.stignore` whitelist for you.

Typical setup: a NAS holds everything; your machine runs speek and pulls down
only what you whitelist. Unsyncing a path removes it from the whitelist **and
deletes the local copy**. You must accept a folder invitation from the speek
UI in order to use it, since it will set up the .stignore correctly.

```sh
python main.py
```

Requires Python 3.10+ and a local Syncthing. The API key is read via
`syncthing cli config gui apikey get` (or pass `--api-key`). A browser opens at
`http://127.0.0.1:8080`.

Accept new shares from the **Pending invitations** section on the start page —
speek creates the directory with a default-deny `.stignore`, so nothing syncs
until you whitelist it.

## Usage

Right-click an entry (or use the keys below) to start/stop syncing. Statuses:
`remote` (not synced), `partial` (something below it is synced), `synced`,
`inherited` (via a synced parent), `local` (exists locally, not whitelisted),
`stale` (whitelisted but gone remotely). The bottom bar shows live transfer
progress.

| Key | Action |
| --- | --- |
| `j` / `k` | move selection down / up |
| `l` / `Enter` | open directory |
| `h` | go up |
| `s` | start syncing |
| `x` | stop syncing / remove stale entry |
| `r` | rename (synced directories) |

Column headers sort: click for descending, again for ascending, a third time
to reset.

## The `.stignore` format

speek only manages folders whose `.stignore` follows this layout — anything
else is shown read-only until you add the markers by hand:

```
# ==== USER_DEFINED_SECTION (edit freely) ====
(?d)**/node_modules

# ==== SPEEK_MANAGED_SECTION (DO_NOT_EDIT) ====
!/photos
!/projects/blog
*
```

The user section is yours: put ordinary ignore patterns there and they apply
even inside whitelisted directories (Syncthing ignores are first-match-wins).
The managed section is rewritten by speek: whitelist entries followed by the
`*` catch-all, which must come last — everything not whitelisted stays remote.

## Options

```
--api-key KEY         Syncthing REST API key
--syncthing-url URL   default http://127.0.0.1:8384
--port PORT           default 8080
--bind ADDR           default 127.0.0.1 (non-loopback is unsupported)
--allow-host HOST     extra Host header to accept (reverse-proxy setups)
--no-open             don't open the browser
```

