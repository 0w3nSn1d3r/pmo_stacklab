from pmo_stacklab.app.lifecycle import run
import threading
import time
import urllib.error
import urllib.request
import webview

URL = "http://127.0.0.1:5000/"

if __name__ == "__main__":
    threading.Thread(target=run, daemon=True).start()

    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(URL, timeout=1)
            break
        except (urllib.error.URLError, TimeoutError):
            time.sleep(0.25)
    else:
        raise RuntimeError(
            f"Flask did not become reachable at {URL}. "
            "Check the server startup logs and configured host/port."
        )

    webview.create_window("PMO StackLab", URL)
    webview.start()
