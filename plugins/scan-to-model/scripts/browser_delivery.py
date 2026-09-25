"""Exercise a copied delivery using normal file-origin rules and disabled networking."""

import base64
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from urllib.request import urlopen

import websocket

from delivery_contract import digest, require


class Browser:
    def __init__(self, socket):
        self.socket = socket
        self.sequence = 0
        self.errors, self.requests = [], []

    def call(self, method, params=None):
        self.sequence += 1
        ident = self.sequence
        self.socket.send(json.dumps({"id": ident, "method": method, "params": params or {}}))
        while True:
            reply = json.loads(self.socket.recv())
            if reply.get("method") == "Runtime.exceptionThrown":
                self.errors.append(reply["params"])
            if reply.get("method") == "Log.entryAdded" and reply["params"]["entry"]["level"] == "error":
                self.errors.append(reply["params"]["entry"])
            if reply.get("method") == "Network.requestWillBeSent":
                self.requests.append(reply["params"]["request"]["url"])
            if reply.get("id") == ident:
                if "error" in reply:
                    raise RuntimeError(reply["error"])
                return reply.get("result", {})

    def evaluate(self, expression):
        result = self.call("Runtime.evaluate", {"expression": expression, "returnByValue": True, "awaitPromise": True})
        if "exceptionDetails" in result:
            raise RuntimeError(result["exceptionDetails"])
        return result["result"].get("value")

    def wait_for(self, expression):
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            try:
                if self.evaluate(expression):
                    return
            except RuntimeError:
                # Navigation destroys the preceding execution context.
                pass
            require(not self.errors, "browser errors: " + json.dumps(self.errors))
            time.sleep(.1)
        raise ValueError("browser did not satisfy readiness check: " + expression)

    def select(self, selector, value):
        self.evaluate(f"document.querySelector({json.dumps(selector)}).value={json.dumps(value)};document.querySelector({json.dumps(selector)}).dispatchEvent(new Event('change'))")

    def capture(self, path):
        Path(path).write_bytes(base64.b64decode(self.call("Page.captureScreenshot", {"format": "png"})["data"]))

    def metrics(self, mobile):
        self.call("Emulation.setDeviceMetricsOverride", {"width": 390 if mobile else 1280,
                  "height": 844 if mobile else 900, "deviceScaleFactor": 1, "mobile": mobile})
        self.call("Emulation.setTouchEmulationEnabled", {"enabled": mobile})


def exercise(browser, copied, captures):
    metadata = json.loads((copied / "model.json").read_text())
    objects = {row["id"]: row for row in metadata["objects"]}
    for domain in ["Page", "Runtime", "Log", "Network"]:
        browser.call(domain + ".enable")
    browser.call("Network.emulateNetworkConditions", {"offline": True, "latency": 0, "downloadThroughput": -1, "uploadThroughput": -1})
    browser.metrics(False)
    url = (copied / "index.html").as_uri()
    browser.call("Page.navigate", {"url": url})
    browser.wait_for("window.modelViewState?.().ready && modelViewState().calls>0")
    require(set(browser.evaluate("modelViewState().objectIds")) == objects.keys(), "browser model scope differs")
    browser.capture(captures / "desktop.png")
    views = [row["id"] for row in metadata["viewpoints"]]
    for ident in views:
        browser.select("#room", ident)
        state = browser.evaluate("modelViewState()")
        require(state["room"] == ident and state["floor"] == "all", "room jump failed")
        require(state["mode"] == ("orbit" if ident == "exterior" else "fly"), "wrong navigation mode")
    interior = views[1]
    browser.select("#room", interior)
    browser.evaluate("document.activeElement?.blur()")
    before = browser.evaluate("modelViewState().position")
    browser.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "w", "code": "KeyW", "windowsVirtualKeyCode": 87})
    time.sleep(.8)
    browser.call("Input.dispatchKeyEvent", {"type": "keyUp", "key": "w", "code": "KeyW", "windowsVirtualKeyCode": 87})
    after = browser.evaluate("modelViewState().position")
    flight = sum((a-b)**2 for a, b in zip(after, before))**.5
    require(.01 < flight < 3, "keyboard flight did not move the camera correctly")
    browser.select("#room", interior)
    browser.capture(captures / "room.png")
    for level in metadata["levels"]:
        browser.select("#floor", level)
        visible = browser.evaluate("modelViewState().visibleObjectIds")
        wanted = {ident for ident, row in objects.items() if row["level"] == level and row["role"] not in {"roof", "ceiling"}}
        require(set(visible) == wanted, "floor visibility differs from declared object membership")
    browser.evaluate("document.querySelector('#home').click();document.querySelector('#roof').click()")
    wanted = {ident for ident, row in objects.items() if row["role"] not in {"roof", "ceiling"}}
    require(set(browser.evaluate("modelViewState().visibleObjectIds")) == wanted, "roof visibility failed")
    browser.evaluate("document.querySelector('#diagnostic').click()")
    require(browser.evaluate("modelViewState().diagnostic"), "diagnostic materials did not activate")
    browser.evaluate("document.querySelector('#diagnostic').click();document.querySelector('#home').click()")
    require(set(browser.evaluate("modelViewState().visibleObjectIds")) == objects.keys(), "reset did not restore the model")
    browser.metrics(True)
    browser.call("Page.navigate", {"url": url + "?input=touch"})
    browser.wait_for("location.search==='?input=touch' && window.modelViewState?.().ready && modelViewState().calls>0")
    require(not browser.evaluate("document.documentElement.scrollWidth>innerWidth"), "mobile viewer overflows horizontally")
    browser.capture(captures / "mobile.png")
    browser.select("#room", interior)
    require(browser.evaluate("!document.querySelector('#touch-controls').hidden"), "touch controls are unavailable")
    point = browser.evaluate("(()=>{const r=document.querySelector('[data-key=KeyW]').getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()")
    before = browser.evaluate("modelViewState().position")
    browser.call("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [point]})
    time.sleep(.8)
    browser.call("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    after = browser.evaluate("modelViewState().position")
    touch = sum((a-b)**2 for a, b in zip(after, before))**.5
    require(.01 < touch < 3, "touch movement did not move the camera correctly")
    browser.select("#room", interior)
    browser.capture(captures / "mobile-room.png")
    slides = []
    if metadata["stills_available"]:
        browser.metrics(False)
        browser.call("Page.navigate", {"url": (copied / "tour.html").as_uri()})
        browser.wait_for("window.MODEL_TOUR && document.querySelector('#contents')?.options.length===MODEL_TOUR.slides.length")
        slides = browser.evaluate("MODEL_TOUR.slides")
        for slide in slides:
            browser.select("#contents", slide["id"])
            browser.wait_for("document.querySelector('#shot').getAttribute('src')===" + json.dumps(slide["image"]) +
                             " && document.querySelector('#shot').complete && document.querySelector('#shot').naturalWidth>0")
            require(browser.evaluate("document.querySelector('#title').textContent") == slide["title"], "tour caption differs")
        browser.select("#contents", slides[0]["id"])
        browser.wait_for("document.querySelector('#shot').complete")
        browser.capture(captures / "tour.png")
        if len(slides) > 1:
            browser.evaluate("document.activeElement?.blur()")
            browser.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "ArrowRight", "code": "ArrowRight", "windowsVirtualKeyCode": 39})
            browser.call("Input.dispatchKeyEvent", {"type": "keyUp", "key": "ArrowRight", "code": "ArrowRight", "windowsVirtualKeyCode": 39})
            browser.wait_for("location.hash===" + json.dumps("#" + slides[1]["id"]))
        browser.metrics(True)
        require(not browser.evaluate("document.documentElement.scrollWidth>innerWidth"), "mobile tour overflows horizontally")
        browser.capture(captures / "mobile-tour.png")
    browser.evaluate("void 0")
    require(not browser.errors, "browser errors: " + json.dumps(browser.errors))
    external = [url for url in browser.requests if url.startswith(("http:", "https:"))]
    require(not external, "viewer attempted external requests: " + json.dumps(external))
    return {"file_url_load_passed": True, "network_disabled": True, "browser_errors": [], "external_requests": [],
            "room_jumps": views, "object_count": len(objects), "flight_distance_m": flight, "touch_distance_m": touch,
            "floor_roof_diagnostic_reset_passed": True, "tour_images_loaded": [row["id"] for row in slides],
            "mobile_horizontal_overflow": False, "copied_delivery_tested": True}


def check_browser(output, executable=None):
    executable = executable or next((shutil.which(name) for name in ["google-chrome", "chromium", "chromium-browser"] if shutil.which(name)), None)
    require(executable is not None, "Chrome/Chromium is required for offline browser verification")
    executable = shutil.which(str(executable))
    require(executable is not None, "browser executable not found")
    captures = Path(output) / "browser-check"
    attempt = 1
    while captures.exists():
        attempt += 1
        captures = Path(output) / ("browser-check-" + str(attempt))
    captures.mkdir(exist_ok=False)
    with tempfile.TemporaryDirectory(prefix="scan-to-model-browser-") as temporary:
        root = Path(temporary)
        copied = root / "delivery"
        shutil.copytree(output, copied, ignore=shutil.ignore_patterns("browser-check*", "node_modules"))
        profile = root / "profile"
        command = [str(executable), "--headless=new", "--no-sandbox", "--disable-dev-shm-usage", "--use-angle=swiftshader",
                   "--enable-unsafe-swiftshader", "--remote-debugging-port=0", "--user-data-dir=" + str(profile), "about:blank"]
        with (captures / "browser.log").open("w") as log:
            process = subprocess.Popen(command, stdout=log, stderr=log)
            socket = None
            try:
                active = profile / "DevToolsActivePort"
                deadline = time.monotonic() + 20
                while not active.exists() and time.monotonic() < deadline and process.poll() is None:
                    time.sleep(.1)
                require(active.exists(), "browser debugging endpoint did not start")
                port = int(active.read_text().splitlines()[0])
                with urlopen(f"http://127.0.0.1:{port}/json", timeout=5) as response:
                    pages = json.load(response)
                page = next(row for row in pages if row.get("type") == "page")
                socket = websocket.create_connection(page["webSocketDebuggerUrl"], suppress_origin=True, timeout=60)
                result = exercise(Browser(socket), copied, captures)
                result.update(bundle_sha256=digest(Path(output) / "viewer.bundle.js"),
                              browser_executable=str(executable), browser_sha256=digest(executable),
                              browser_version=subprocess.check_output([executable, "--version"], text=True).strip(),
                              screenshots={file.relative_to(output).as_posix(): digest(file) for file in captures.glob("*.png")})
                return result
            finally:
                if socket:
                    socket.close()
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
