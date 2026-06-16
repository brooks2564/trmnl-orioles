import io
import threading
import time

from flask import Flask, jsonify, request, send_file

from mlb import get_game_data
from renderer import render_image

app = Flask(__name__)

_cache = {"data": None, "png": None}
_lock = threading.Lock()


def _refresh():
    while True:
        try:
            data = get_game_data()
            img = render_image(data)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            with _lock:
                _cache["data"] = data
                _cache["png"] = buf.getvalue()
        except Exception as e:
            print(f"[refresh] {e}")

        status = (_cache.get("data") or {}).get("status", "")
        time.sleep(15 if status == "Live" else 60)


_thread = threading.Thread(target=_refresh, daemon=True)
_thread.start()


@app.route("/api/display")
@app.route("/api/display/")
def display():
    with _lock:
        data = _cache.get("data") or {}
    status = data.get("status", "")
    refresh_rate = 15 if status == "Live" else 60

    base = f"{request.scheme}://{request.host}"
    return jsonify(
        {
            "status": 0,
            "image_url": f"{base}/image.png",
            "filename": "orioles.png",
            "refresh_rate": refresh_rate,
            "reset_firmware": False,
            "update_firmware": False,
            "firmware_url": None,
            "special_function": "sleep",
        }
    )


@app.route("/image.png")
def image():
    with _lock:
        png = _cache.get("png")

    if not png:
        data = get_game_data()
        img = render_image(data)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        png = buf.getvalue()

    return send_file(io.BytesIO(png), mimetype="image/png")


@app.route("/preview")
def preview():
    """Browser-viewable preview of the current image."""
    with _lock:
        png = _cache.get("png")
    if not png:
        data = get_game_data()
        img = render_image(data)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        png = buf.getvalue()
    return send_file(io.BytesIO(png), mimetype="image/png")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
