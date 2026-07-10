"""
Zaraa Robot API - Images Only (No Fake AI)
"""
import os, uuid, base64
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime

app   = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# حفظ آخر صورة يمين وآخر صورة يسار في الذاكرة
latest = {"RIGHT": None, "LEFT": None}

# ════════════════════════════════════════
@app.route('/')
def home():
    return jsonify({
        "status":  "ok",
        "project": "Zaraa Robot - Images API",
        "version": "3.0.0",
        "endpoints": {
            "POST /upload":        "الروبوت يرفع صورة",
            "GET  /latest":        "آخر صورة يمين + يسار",
            "GET  /latest/right":  "آخر صورة يمين بس",
            "GET  /latest/left":   "آخر صورة يسار بس",
            "GET  /health":        "السيرفر شغّال؟",
        }
    }), 200

# ════════════════════════════════════════
@app.route('/health')
def health():
    has_right = latest["RIGHT"] is not None
    has_left  = latest["LEFT"]  is not None
    return jsonify({
        "status":    "ok",
        "has_right": has_right,
        "has_left":  has_left,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }), 200

# ════════════════════════════════════════
#  الروبوت يرفع صورة
#  POST /upload
#  Header: X-Direction: RIGHT أو LEFT
#  Body: صورة JPEG
# ════════════════════════════════════════
@app.route('/upload', methods=['POST'])
def upload():
    data = request.data
    if not data or len(data) < 100:
        return jsonify({"status": "error", "msg": "مفيش صورة"}), 400

    direction = request.headers.get('X-Direction', 'UNKNOWN').upper()
    if direction not in ['RIGHT', 'LEFT']:
        direction = 'RIGHT'

    # تحويل الصورة لـ base64 عشان تتبعت في الـ JSON
    img_b64 = base64.b64encode(data).decode('utf-8')

    entry = {
        "direction":    direction,
        "direction_ar": "يمين" if direction == "RIGHT" else "يسار",
        "size_bytes":   len(data),
        "captured_at":  datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "captured_time": datetime.now().strftime("%H:%M:%S"),
        "image_base64": img_b64,
        "image_data_url": f"data:image/jpeg;base64,{img_b64}",
    }

    latest[direction] = entry
    print(f"[UPLOAD] {direction} | {len(data):,} bytes | {entry['captured_time']}")

    return jsonify({"status": "ok", "direction": direction, "size": len(data)}), 200

# ════════════════════════════════════════
#  جلب آخر صورتين (يمين + يسار)
#  GET /latest
# ════════════════════════════════════════
@app.route('/latest')
def get_latest():
    return jsonify({
        "status":     "ok",
        "right":      latest["RIGHT"],
        "left":       latest["LEFT"],
        "updated_at": datetime.now().strftime("%H:%M:%S")
    }), 200

# ════════════════════════════════════════
#  جلب آخر صورة يمين بس
#  GET /latest/right
# ════════════════════════════════════════
@app.route('/latest/right')
def get_right():
    if not latest["RIGHT"]:
        return jsonify({"status": "empty", "msg": "مفيش صورة يمين لسه"}), 404
    return jsonify({"status": "ok", "scan": latest["RIGHT"]}), 200

# ════════════════════════════════════════
#  جلب آخر صورة يسار بس
#  GET /latest/left
# ════════════════════════════════════════
@app.route('/latest/left')
def get_left():
    if not latest["LEFT"]:
        return jsonify({"status": "empty", "msg": "مفيش صورة يسار لسه"}), 404
    return jsonify({"status": "ok", "scan": latest["LEFT"]}), 200

# ════════════════════════════════════════
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"[SYS] Zaraa API v3 — port {port}")
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
