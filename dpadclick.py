#!/usr/bin/env python3
"""Background daemon: D-pad left/right click the page's left/right edge.

Turns a remote's D-pad into page-turn taps for CWA's web reader: ArrowLeft
clicks at (50px, mid-height) and ArrowRight at (width - 50px, mid-height),
descending into same-origin iframes (the epub reader renders inside one).
Injected over the on-device Chrome DevTools Protocol, same architecture as
family7-webos's scrollfix.py, since index.html's own JS context is gone
after the top-level redirect.
"""

import base64
import json
import os
import socket
import time
import urllib.request

CDP_HOST = "127.0.0.1"
CDP_PORT = 9998
APP_DESCRIPTION = "nl.arnolderuiter.cwa"
POLL_INTERVAL_SECONDS = 3
PIDFILE = "/tmp/cwa-dpadclick.pid"

FIX_JS = """
(function(){
  if (window.__dpadClickInstalled) return;
  window.__dpadClickInstalled = true;
  var EDGE_OFFSET = 50;
  var POINTER_DOWN = {pointerdown: 1, mousedown: 1};

  function topWindow() {
    try { return window.top.document ? window.top : window; } catch (e) { return window; }
  }

  // Walks into same-origin iframes so the click lands on the real element.
  function resolveTarget(doc, x, y) {
    var el = doc.elementFromPoint(x, y);
    while (el && el.tagName === 'IFRAME') {
      var inner;
      try { inner = el.contentDocument; } catch (e) { inner = null; }
      if (!inner) break;
      var rect = el.getBoundingClientRect();
      var innerX = x - rect.left - el.clientLeft;
      var innerY = y - rect.top - el.clientTop;
      var next = inner.elementFromPoint(innerX, innerY);
      if (!next) break;
      el = next; doc = inner; x = innerX; y = innerY;
    }
    return {el: el, view: doc.defaultView, x: x, y: y};
  }

  function fire(t, type) {
    var isPointer = type.indexOf('pointer') === 0 && t.view.PointerEvent;
    var Ctor = isPointer ? t.view.PointerEvent : t.view.MouseEvent;
    t.el.dispatchEvent(new Ctor(type, {
      bubbles: true, cancelable: true, composed: true, view: t.view,
      clientX: t.x, clientY: t.y, button: 0, buttons: POINTER_DOWN[type] ? 1 : 0,
      pointerType: 'mouse', isPrimary: true
    }));
  }

  function clickSide(right) {
    var w = topWindow();
    var x = right ? w.innerWidth - EDGE_OFFSET : EDGE_OFFSET;
    var t = resolveTarget(w.document, x, Math.round(w.innerHeight / 2));
    if (!t.el) return;
    ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click'].forEach(function(type){ fire(t, type); });
  }

  function onKeyDown(e) {
    var right = e.key === 'ArrowRight' || e.keyCode === 39;
    var left = e.key === 'ArrowLeft' || e.keyCode === 37;
    if (!left && !right) return;
    var a = e.target;
    if (a && (a.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName))) return;
    e.preventDefault();
    e.stopImmediatePropagation();
    clickSide(right);
  }

  function hook(win) {
    try {
      if (win.__dpadClickHooked) return;
      win.__dpadClickHooked = true;
      win.addEventListener('keydown', onKeyDown, true);
    } catch (e) {}
  }

  hook(window);
  // Reader iframes (about:blank/srcdoc) may skip new-document injection, so hook them too.
  setInterval(function(){
    var frames = document.getElementsByTagName('iframe');
    for (var i = 0; i < frames.length; i++) {
      try { hook(frames[i].contentWindow); } catch (e) {}
    }
  }, 1000);
})();
"""


def _handshake(sock, host, port, path):
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


def _watch_target(target):
    """Blocks until the target's debugger connection closes (app closed)."""
    target_id = target["id"]
    ws_url = target["webSocketDebuggerUrl"]
    path = ws_url.split(CDP_HOST + ":" + str(CDP_PORT), 1)[1]
    sock = socket.create_connection((CDP_HOST, CDP_PORT), timeout=10)
    try:
        _handshake(sock, CDP_HOST, CDP_PORT, path)
        _send_frame(sock, json.dumps({"id": 1, "method": "Page.enable"}))
        _send_frame(
            sock,
            json.dumps(
                {
                    "id": 2,
                    "method": "Page.addScriptToEvaluateOnNewDocument",
                    "params": {"source": FIX_JS},
                }
            ),
        )
        _send_frame(
            sock, json.dumps({"id": 3, "method": "Runtime.evaluate", "params": {"expression": FIX_JS}})
        )
        print("dpadclick: injected into target %s" % target_id, flush=True)
        sock.settimeout(60)
        while True:
            try:
                opcode, _payload = _recv_frame(sock)
            except socket.timeout:
                continue
            if opcode == 0x8:
                break
    except OSError as exc:
        print("dpadclick: target %s connection ended: %s" % (target_id, exc), flush=True)
    finally:
        try:
            sock.close()
        except OSError:
            pass


def main():
    print("dpadclick: watching for %s" % APP_DESCRIPTION, flush=True)
    target = _find_target()
    _watch_target(target)
    print("dpadclick: CWA closed, exiting", flush=True)
    try:
        if str(os.getpid()) == open(PIDFILE).read().strip():
            os.remove(PIDFILE)
    except OSError:
        pass


if __name__ == "__main__":
    main()
