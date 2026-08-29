# Threat model

`speek` is a small web UI for managing Syncthing `.stignore` whitelists. It is
meant to run **on the same machine as Syncthing, bound to loopback, for a single
trusted local user**. This document states what that implies for security, what
`speek` defends against, and what it deliberately does not.

## What speek can do

`speek` is not a passive viewer. It holds the Syncthing REST API key and it acts
directly on the filesystem:

- reads and rewrites each folder's `.stignore` whitelist,
- **deletes** local copies when you stop syncing a path (`shutil.rmtree`),
- **renames** local directories (`os.rename`),
- **accepts pending folder shares**: creates a local directory at a
  user-chosen path, writes a skeleton `.stignore`, and adds the folder to
  Syncthing's config (POST, CSRF-guarded; refuses non-empty directories, and
  only folder ids with an actual pending offer can be accepted).

Mutations are additionally refused for any folder whose `.stignore` does not
conform to the speek-managed layout — unmanaged folders are browse-only.

So `speek` is a *confused-deputy* risk: it already has the authority: anything
that can make `speek` perform a request can delete or rename real files without
ever knowing the API key. `speek` itself is the trust boundary, not the key.

## Assumptions (the framing)

1. **Loopback only.** The server binds `127.0.0.1` by default. The intended
   deployment never exposes it to other hosts.
2. **The local user is trusted.** Other local users / processes on the machine
   are out of scope (they can already reach Syncthing's own API and the files).
3. **The browser is not trusted to be visiting only friendly pages.** While
   `speek` is running, the user may have *any* website open in the same browser.

Assumption 3 is the crux. "Loopback only" does **not** mean "no attacker." The
relevant attacker under this model is a **web page the browser loads from the
internet**, which can then send requests to `http://127.0.0.1:<port>`. Defending
the loopback service against that page is the entire job here.

## In scope (defended)

Two browser-driven attacks reach a loopback service and are defended against:

- **Cross-site request forgery (CSRF).** A malicious page tries to POST to
  `speek`'s `/api/*` endpoints to delete or rename files. Defense: state-changing
  POSTs require `Content-Type: application/json` (which forces a CORS preflight
  that this server never answers, so a cross-origin request never fires), and
  the `Origin` / `Sec-Fetch-Site` headers are validated when present. A form or
  `text/plain` "simple request" is rejected outright.
- **DNS rebinding.** A malicious page rebinds its domain to `127.0.0.1` to become
  same-origin with `speek`. Defense: every request's `Host` header must be a
  loopback literal (`127.0.0.1`, `localhost`, `::1`); anything else is `403`.

Both guards run at a single dispatch point (`parse_request`), before any `do_*`
handler, so every HTTP verb — including ones added later, and `OPTIONS`
preflights — is covered by default rather than opting in per handler. GET
requests are additionally read-only by construction: merely viewing a folder
never writes `.stignore` (initialization happens only on a whitelist mutation,
and grafts onto existing content instead of replacing it), and the
delete/rename sinks refuse the folder root outright as a backstop.

Output is HTML-escaped throughout (`html.escape`), so reflected/stored XSS from
file and folder names is not a live vector.

## Parity with passwordless Syncthing

A reasonable question: Syncthing's own GUI can run without a password on
loopback — is `speek` any worse? Passwordless Syncthing is **not** an unprotected
server: it still defends its API with CSRF tokens and a `Host`-header check, so a
random web page cannot drive it. The `Host` + CSRF guards exist to bring `speek`
to parity with that passwordless baseline.

## Out of scope

- **Non-loopback exposure.** `--bind 0.0.0.0` (or any non-loopback address) puts
  an unauthenticated file-mutation API on the network. This is not defended and
  not supported (`speek` prints a warning and accepts the bind address as a valid
  `Host`). Do not do it. If you need remote access, put `speek` behind an
  authenticating reverse proxy and keep it bound to loopback; if the proxy
  forwards the original `Host` header (Caddy and Traefik do), pass it with
  `--allow-host speek.example.com`.
- **Malicious local users/processes** on the same machine.
- **Protecting the Syncthing API key** from a user who already has it.
- **Multi-user use.** There are no accounts, sessions, or authorization.

