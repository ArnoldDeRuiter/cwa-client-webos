#!/usr/bin/env python3
"""Background daemon: autofills the CWA login form, never submits it.

Same architecture as family7-webos's loginfill.py: polls the on-device
Chrome DevTools Protocol endpoint (127.0.0.1:9998) for this app's WAM tab
and injects a fill script into every new document. Credentials come from
the root-only /var/lib/webosbrew/tv-credentials.json ("cwa" key).

Only fills input[name="username"] / input[name="password"] of CWA's plain
server-rendered Flask login form on /login. Never clicks sign-in.
"""

import json
import os
import socket
import time
import urllib.request

CDP_HOST = "127.0.0.1"
CDP_PORT = 9998
APP_DESCRIPTION = "nl.arnolderuiter.cwa"
POLL_INTERVAL_SECONDS = 3
CREDENTIALS_PATH = "/var/lib/webosbrew/tv-credentials.json"


def _handshake(sock, host, port, path):
    import base64

    key = base64.b64encode(os.urandom(16)).decode("ascii")
    lines = [
        "GET %s HTTP/1.1" % path,
        "Host: %s:%d" % (host, port),
        "Upgrade: websocket",
        "Connection: Upgrade",
        "Sec-WebSocket-Key: %s" % key,
        "Sec-WebSocket-Version: 13",
        "",
        "",
    ]
    sock.sendall("\r\n".join(lines).encode("ascii"))
    buf = b""
    while b"\r\n\r\n" not in buf:
        chunk = sock.recv(4096)
        if not chunk:
            raise OSError("connection closed during handshake")
        buf += chunk
    header = buf.split(b"\r\n\r\n", 1)[0].decode("latin-1")
    status_line = header.split("\r\n", 1)[0]
    if " 101 " not in (" " + status_line + " "):
        raise OSError("unexpected handshake response: %s" % status_line)


def _send_frame(sock, payload):
    data = payload.encode("utf-8")
    header = bytearray([0x80 | 0x1])
    length = len(data)
    mask = os.urandom(4)
    if length <= 125:
        header.append(0x80 | length)
    elif length <= 0xFFFF:
        header.append(0x80 | 126)
        header += length.to_bytes(2, "big")
    else:
        header.append(0x80 | 127)
        header += length.to_bytes(8, "big")
    header += mask
    masked = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
    sock.sendall(bytes(header) + masked)


def _recv_frame(sock):
    def recv_exact(n):
        buf = b""
        while len(buf) < n:
            chunk = sock.recv(n - len(buf))
            if not chunk:
                raise OSError("connection closed")
            buf += chunk
        return buf

    first2 = recv_exact(2)
    opcode = first2[0] & 0x0F
    length = first2[1] & 0x7F
    if length == 126:
        length = int.from_bytes(recv_exact(2), "big")
    elif length == 127:
        length = int.from_bytes(recv_exact(8), "big")
    payload = recv_exact(length) if length else b""
    return opcode, payload


def load_credentials():
    with open(CREDENTIALS_PATH) as f:
        data = json.load(f)
    creds = data["cwa"]
    return creds["username"], creds["password"]


def build_fill_js(username, password):
    # JSON-encode so any password characters are safely quoted.
    username_js = json.dumps(username)
    password_js = json.dumps(password)
    return """
(function(){
  if (window.__loginFillInstalled) return;
  window.__loginFillInstalled = true;

  function setInputValue(el, value) {
    var setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
    setter.call(el, value);
    el.dispatchEvent(new Event('input', {bubbles: true}));
  }

  var username = %s;
  var password = %s;
  var filled = false;

  function tryFill() {
    if (filled) return;
    var userField = document.querySelector('form.cwa-login-form input[name="username"]');
    var passField = document.querySelector('form.cwa-login-form input[name="password"]');
    if (!userField || !passField) return;
    if (userField.value || passField.value) return;
    setInputValue(userField, username);
    setInputValue(passField, password);
    filled = true;
    console.log('__loginFillComplete__');
  }

  // Polling re-queries the live DOM, same as the f1tv/family7 loginfill.
  var pollInterval = setInterval(function(){
    tryFill();
    if (filled) clearInterval(pollInterval);
  }, 500);
})();
""" % (username_js, password_js)


def _find_target():
    while True:
        try:
            with urllib.request.urlopen(
                "http://%s:%d/json" % (CDP_HOST, CDP_PORT), timeout=5
            ) as resp:
                targets = json.loads(resp.read().decode("utf-8"))
        except OSError:
            targets = []
        for target in targets:
            if target.get("description") == APP_DESCRIPTION:
                return target
        time.sleep(POLL_INTERVAL_SECONDS)


AUTH_COOKIE_DOMAIN_SUFFIX = "cwa.1701.nl"
AUTH_COOKIE_NAME_PREFIX = "remember_token"  # Flask-Login; set because remember_me is checked by default


def _call(sock, msg_id, method, params=None):
    """Request/response helper: sends one CDP command and blocks for the
    matching reply, discarding any events that arrive first."""
    _send_frame(sock, json.dumps({"id": msg_id, "method": method, "params": params or {}}))
    while True:
        opcode, payload = _recv_frame(sock)
        if opcode != 0x1:
            continue
        try:
            msg = json.loads(payload.decode("utf-8"))
        except ValueError:
            continue
        if msg.get("id") == msg_id:
            return msg


def _has_valid_session(sock):
    """True if a cookie proving an already-logged-in session exists. Checked
    before injecting anything -- no point watching for a login form that
    won't even show up because the site will just load straight into the
    logged-in view."""
    result = _call(sock, 100, "Network.getAllCookies")
    cookies = result.get("result", {}).get("cookies", [])
    for cookie in cookies:
        domain = cookie.get("domain", "")
        name = cookie.get("name", "")
        if domain.endswith(AUTH_COOKIE_DOMAIN_SUFFIX) and name.startswith(AUTH_COOKIE_NAME_PREFIX):
            return True
    return False


FILL_COMPLETE_MARKER = "__loginFillComplete__"


def _is_fill_complete_message(payload):
    try:
        msg = json.loads(payload.decode("utf-8"))
    except ValueError:
        return False
    if msg.get("method") != "Runtime.consoleAPICalled":
        return False
    args = msg.get("params", {}).get("args", [])
    return bool(args) and args[0].get("value") == FILL_COMPLETE_MARKER


def _watch_target(target, fill_js):
    """Blocks until the fields are filled, or the target closes (app closed) --
    whichever comes first. Once autofill succeeds there's nothing further for
    this connection to do, so it closes itself immediately rather than
    holding a root process + CDP connection open for the rest of the app's
    lifetime just to watch a login page that's no longer showing."""
    target_id = target["id"]
    ws_url = target["webSocketDebuggerUrl"]
    path = ws_url.split(CDP_HOST + ":" + str(CDP_PORT), 1)[1]
    sock = socket.create_connection((CDP_HOST, CDP_PORT), timeout=10)
    try:
        _handshake(sock, CDP_HOST, CDP_PORT, path)
        _call(sock, 99, "Network.enable")
        if _has_valid_session(sock):
            print("loginfill: already logged in, nothing to fill", flush=True)
            return "already-logged-in"
        _send_frame(sock, json.dumps({"id": 1, "method": "Page.enable"}))
        _send_frame(sock, json.dumps({"id": 2, "method": "Runtime.enable"}))
        _send_frame(
            sock,
            json.dumps(
                {
                    "id": 3,
                    "method": "Page.addScriptToEvaluateOnNewDocument",
                    "params": {"source": fill_js},
                }
            ),
        )
        _send_frame(
            sock, json.dumps({"id": 4, "method": "Runtime.evaluate", "params": {"expression": fill_js}})
        )
        print("loginfill: injected into target %s" % target_id, flush=True)
        sock.settimeout(60)
        while True:
            try:
                opcode, payload = _recv_frame(sock)
            except socket.timeout:
                continue
            if opcode == 0x8:
                return "closed"
            if opcode == 0x1 and _is_fill_complete_message(payload):
                return "filled"
    except OSError as exc:
        print("loginfill: target %s connection ended: %s" % (target_id, exc), flush=True)
        return "error"
    finally:
        try:
            sock.close()
        except OSError:
            pass


def main():
    print("loginfill: watching for %s" % APP_DESCRIPTION, flush=True)
    try:
        username, password = load_credentials()
    except (OSError, KeyError, ValueError) as exc:
        print("loginfill: no usable credentials at %s (%s), exiting" % (CREDENTIALS_PATH, exc), flush=True)
        return
    fill_js = build_fill_js(username, password)
    target = _find_target()
    reason = _watch_target(target, fill_js)
    print("loginfill: exiting (%s)" % reason, flush=True)


if __name__ == "__main__":
    main()
