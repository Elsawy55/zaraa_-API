"""
╔══════════════════════════════════════════════════════════════╗
║        🌾 روبوت زراعي ذكي — السيرفر الكامل (API)           ║
║                                                              ║
║  ده السيرفر الوسيط بين كل الأطراف:                          ║
║  • الروبوت بيبعت صور هنا                                    ║
║  • الـ AI Model بياخد الصور منه ويرجع النتيجة               ║
║  • الفرونت اند والموبايل بيشوفوا النتايج منه                ║
╚══════════════════════════════════════════════════════════════╝

تثبيت المكتبات:
    pip install flask flask-cors requests

تشغيل السيرفر:
    python server.py

بعدين افتح المتصفح على:
    http://localhost:5000/api/docs
"""

import os
import uuid
import threading
import time
import requests
import random
from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS
from datetime import datetime

# ════════════════════════════════════════════════════════════
#  إعداد التطبيق
# ════════════════════════════════════════════════════════════
app = Flask(__name__)

# CORS مهم جداً — يسمح للفرونت اند والموبايل يتصلوا بالـ API
# بدونه المتصفح والموبايل هيمنعوا الاتصال
CORS(app, resources={r"/api/*": {"origins": "*"}})

os.makedirs("uploads", exist_ok=True)

# ════════════════════════════════════════════════════════════
#  الإعدادات — غيّرها حسب شبكتك
# ════════════════════════════════════════════════════════════
NODEMCU_IP   = "10.101.47.182"   # ← IP الـ NodeMCU (من Serial Monitor)
AI_MODEL_URL = ""                # ← URL موديل الـ AI (لما يكون جاهز)
USE_FAKE_AI  = True              # ← True = تحليل وهمي للاختبار

# ════════════════════════════════════════════════════════════
#  تحليل وهمي للاختبار (يُستبدل بالموديل الحقيقي)
# ════════════════════════════════════════════════════════════
FAKE_RESULTS = [
    {"status": "healthy", "status_ar": "سليم",
     "disease": "None",            "disease_ar": "لا يوجد",
     "confidence": 97, "recommendation_ar": "النبتة بخير — استمر في الري"},
    {"status": "diseased", "status_ar": "مريض",
     "disease": "Early Blight",    "disease_ar": "اللفحة المبكرة",
     "confidence": 94, "recommendation_ar": "رش مبيد فطري فوراً"},
    {"status": "diseased", "status_ar": "مريض",
     "disease": "Leaf Mold",       "disease_ar": "عفن الأوراق",
     "confidence": 89, "recommendation_ar": "تهوية جيدة وعلاج فطري"},
    {"status": "healthy", "status_ar": "سليم",
     "disease": "None",            "disease_ar": "لا يوجد",
     "confidence": 99, "recommendation_ar": "ممتاز — لا تدخل مطلوب"},
    {"status": "diseased", "status_ar": "مريض",
     "disease": "Bacterial Spot",  "disease_ar": "التبقع البكتيري",
     "confidence": 91, "recommendation_ar": "أزل الأوراق المصابة"},
    {"status": "diseased", "status_ar": "مريض",
     "disease": "Powdery Mildew",  "disease_ar": "البياض الدقيقي",
     "confidence": 88, "recommendation_ar": "رش كبريت ميكروني"},
    {"status": "diseased", "status_ar": "مريض",
     "disease": "Late Blight",     "disease_ar": "اللفحة المتأخرة",
     "confidence": 93, "recommendation_ar": "عزل النبتة وعلاج فوري"},
    {"status": "healthy", "status_ar": "سليم",
     "disease": "None",            "disease_ar": "لا يوجد",
     "confidence": 98, "recommendation_ar": "النبتة في حالة ممتازة"},
]

# قاعدة البيانات في الذاكرة
scans_db = []       # كل الصور والنتايج
sessions_db = []    # جلسات الروبوت


# ════════════════════════════════════════════════════════════
#  ══ وظيفة التحليل (وهمي أو حقيقي) ══
# ════════════════════════════════════════════════════════════
def analyze_image(filepath, filename, direction, session_id):
    """
    دي الوظيفة اللي بتحلل الصورة
    دلوقتي: بتستخدم تحليل وهمي
    لما موديل الـ AI يكون جاهز: بتبعتله الصورة وتاخد النتيجة
    """
    time.sleep(1.5)  # محاكاة وقت التحليل

    if USE_FAKE_AI or not AI_MODEL_URL:
        # ── تحليل وهمي ──────────────────────────────
        result = random.choice(FAKE_RESULTS)
        ai_source = "fake_model_v1"
    else:
        # ── تحليل حقيقي (لما الموديل يكون جاهز) ──
        try:
            with open(filepath, 'rb') as img_file:
                resp = requests.post(
                    AI_MODEL_URL,
                    files={"image": (filename, img_file, "image/jpeg")},
                    timeout=30
                )
            if resp.status_code == 200:
                data = resp.json()
                result = {
                    "status":          data.get("status", "unknown"),
                    "status_ar":       data.get("status_ar", "غير محدد"),
                    "disease":         data.get("disease", "Unknown"),
                    "disease_ar":      data.get("disease_ar", "غير محدد"),
                    "confidence":      data.get("confidence", 0),
                    "recommendation_ar": data.get("recommendation_ar", "—"),
                }
                ai_source = "real_model"
            else:
                result = random.choice(FAKE_RESULTS)
                ai_source = "fake_fallback"
        except Exception as e:
            print(f"[AI] ✗ فشل الاتصال بالموديل: {e}")
            result = random.choice(FAKE_RESULTS)
            ai_source = "fake_fallback"

    # ── بناء النتيجة الكاملة ──────────────────────
    scan_entry = {
        "scan_id":         str(uuid.uuid4())[:8],
        "session_id":      session_id,
        "filename":        filename,
        "image_url":       f"/api/images/{filename}",
        "direction":       direction,
        "direction_ar":    "يمين" if direction == "RIGHT" else "يسار",
        "captured_at":     datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "captured_time":   datetime.now().strftime("%H:%M:%S"),
        "status":          result["status"],
        "status_ar":       result["status_ar"],
        "disease":         result["disease"],
        "disease_ar":      result["disease_ar"],
        "confidence":      result["confidence"],
        "recommendation":  result["recommendation_ar"],
        "ai_source":       ai_source,
        "is_new":          True,
    }

    scans_db.insert(0, scan_entry)
    if len(scans_db) > 100:
        scans_db.pop()

    emoji = "✅" if result["status"] == "healthy" else "🔴"
    print(f"[AI] {emoji} {direction} | {result['status_ar']} | "
          f"{result['disease']} | {result['confidence']}% | src:{ai_source}")

    return scan_entry


# ════════════════════════════════════════════════════════════
#  ══ الصفحات ══
# ════════════════════════════════════════════════════════════
@app.route('/')
def home():
    return send_file('dashboard.html')


# ════════════════════════════════════════════════════════════
#  ══ API: توثيق ══
#  GET /api/docs
# ════════════════════════════════════════════════════════════
@app.route('/api/docs')
def api_docs():
    """صفحة توثيق الـ API — مهمة للفريق"""
    base = request.host_url.rstrip('/')
    docs = {
        "project": "🌾 روبوت زراعي ذكي — API Documentation",
        "version": "1.0.0",
        "base_url": base,
        "endpoints": {

            "📸 الصور والتحليل": {
                "POST /api/upload": {
                    "description": "الروبوت يبعت صورة هنا",
                    "headers": {
                        "Content-Type": "image/jpeg",
                        "X-Direction": "RIGHT أو LEFT",
                        "X-Session-Id": "معرّف الجلسة (اختياري)"
                    },
                    "body": "binary image data",
                    "response": {"status": "ok", "scan_id": "abc123", "filename": "..."}
                },
                "GET /api/scans": {
                    "description": "جلب كل الصور والنتايج",
                    "params": "?limit=20&direction=RIGHT&status=diseased",
                    "response": {"scans": [...], "total": 50}
                },
                "GET /api/scans/latest": {
                    "description": "آخر صورة يمين + آخر صورة يسار",
                    "response": {"right": {...}, "left": {...}}
                },
                "GET /api/scans/<scan_id>": {
                    "description": "تفاصيل صورة معينة",
                    "response": {"scan_id": "...", "status": "...", "details": "..."}
                },
                "GET /api/images/<filename>": {
                    "description": "عرض صورة محفوظة",
                    "response": "image/jpeg file"
                },
            },

            "🔬 اختبار يدوي": {
                "POST /api/test/capture": {
                    "description": "السيرفر يطلب صورة من الكاميرا مباشرة",
                    "body": {"cam_ip": "192.168.x.x", "direction": "RIGHT"},
                    "response": {"status": "ok", "scan_id": "..."}
                },
                "POST /api/test/fake-scan": {
                    "description": "اختبار بدون كاميرا — ينشئ نتيجة وهمية",
                    "body": {"direction": "RIGHT"},
                    "response": {"status": "ok", "scan": {...}}
                },
            },

            "🤖 التحكم في الروبوت": {
                "POST /api/robot/start": {
                    "description": "تشغيل الروبوت",
                    "response": {"status": "ok", "msg": "..."}
                },
                "POST /api/robot/stop": {
                    "description": "إيقاف الروبوت",
                    "response": {"status": "ok", "msg": "..."}
                },
                "GET /api/robot/status": {
                    "description": "حالة الروبوت",
                    "response": {"state": "MOVING/IDLE/SCANNING", "running": True}
                },
            },

            "📊 الإحصائيات": {
                "GET /api/stats": {
                    "description": "إحصائيات عامة",
                    "response": {
                        "total_scans": 50,
                        "healthy": 35,
                        "diseased": 15,
                        "health_rate": "70%"
                    }
                },
            },

            "🔧 النظام": {
                "GET /api/health": {
                    "description": "التحقق إن السيرفر شغّال",
                    "response": {"status": "ok", "uptime": "..."}
                },
                "POST /api/ai/set-url": {
                    "description": "تعيين URL موديل الـ AI",
                    "body": {"url": "http://ai-server:8000/predict"},
                    "response": {"status": "ok"}
                },
            }
        }
    }
    return jsonify(docs), 200


# ════════════════════════════════════════════════════════════
#  ══ API: الروبوت يبعت صورة ══
#  POST /api/upload
#  Headers: X-Direction: RIGHT | LEFT
#           X-Session-Id: session_id (optional)
#  Body: raw JPEG bytes
# ════════════════════════════════════════════════════════════
@app.route('/api/upload', methods=['POST'])
def upload_image():
    data = request.data
    if not data or len(data) < 500:
        return jsonify({"status": "error",
                        "msg": "لا توجد بيانات صورة"}), 400

    direction  = request.headers.get('X-Direction', 'UNKNOWN').upper()
    session_id = request.headers.get('X-Session-Id', 'default')

    # تحقق من الاتجاه
    if direction not in ['RIGHT', 'LEFT', 'CENTER', 'UNKNOWN']:
        direction = 'UNKNOWN'

    # حفظ الصورة
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    uid       = uuid.uuid4().hex[:6]
    filename  = f"{timestamp}_{direction}_{uid}.jpg"
    filepath  = os.path.join("uploads", filename)

    with open(filepath, 'wb') as f:
        f.write(data)

    size = len(data)
    print(f"[UPLOAD] ✅ {filename} | {size:,} bytes | {direction}")

    # تحليل في background thread (عشان الروبوت ميستناش)
    t = threading.Thread(
        target=analyze_image,
        args=(filepath, filename, direction, session_id)
    )
    t.daemon = True
    t.start()

    return jsonify({
        "status":    "ok",
        "msg":       "تم استقبال الصورة وبدأ التحليل",
        "filename":  filename,
        "size":      size,
        "direction": direction,
    }), 200


# ════════════════════════════════════════════════════════════
#  ══ API: جلب كل الصور والنتايج ══
#  GET /api/scans?limit=20&direction=RIGHT&status=diseased
# ════════════════════════════════════════════════════════════
@app.route('/api/scans', methods=['GET'])
def get_scans():
    limit     = int(request.args.get('limit', 20))
    direction = request.args.get('direction', '').upper()
    status    = request.args.get('status', '')

    filtered = scans_db

    if direction:
        filtered = [s for s in filtered if s['direction'] == direction]
    if status:
        filtered = [s for s in filtered if s['status'] == status]

    # mark is_new = False
    for s in filtered[:limit]:
        s['is_new'] = False

    return jsonify({
        "status": "ok",
        "total":  len(filtered),
        "scans":  filtered[:limit]
    }), 200


# ════════════════════════════════════════════════════════════
#  ══ API: آخر صورة يمين + يسار ══
#  GET /api/scans/latest
# ════════════════════════════════════════════════════════════
@app.route('/api/scans/latest', methods=['GET'])
def get_latest():
    right = next((s for s in scans_db if s['direction'] == 'RIGHT'), None)
    left  = next((s for s in scans_db if s['direction'] == 'LEFT'),  None)

    return jsonify({
        "status": "ok",
        "right":  right,
        "left":   left,
        "updated_at": datetime.now().strftime("%H:%M:%S")
    }), 200


# ════════════════════════════════════════════════════════════
#  ══ API: تفاصيل صورة معينة ══
#  GET /api/scans/<scan_id>
# ════════════════════════════════════════════════════════════
@app.route('/api/scans/<scan_id>', methods=['GET'])
def get_scan(scan_id):
    scan = next((s for s in scans_db if s['scan_id'] == scan_id), None)
    if not scan:
        return jsonify({"status": "error", "msg": "الصورة مش موجودة"}), 404
    return jsonify({"status": "ok", "scan": scan}), 200


# ════════════════════════════════════════════════════════════
#  ══ API: عرض صورة ══
#  GET /api/images/<filename>
# ════════════════════════════════════════════════════════════
@app.route('/api/images/<filename>')
def serve_image(filename):
    return send_from_directory('uploads', filename)


# ════════════════════════════════════════════════════════════
#  ══ API: اختبار يدوي — طلب صورة من الكاميرا ══
#  POST /api/test/capture
#  Body: {"cam_ip": "192.168.x.x", "direction": "RIGHT"}
# ════════════════════════════════════════════════════════════
@app.route('/api/test/capture', methods=['POST'])
def test_capture():
    body      = request.json or {}
    cam_ip    = body.get('cam_ip', '')
    direction = body.get('direction', 'RIGHT').upper()

    if not cam_ip:
        return jsonify({"status": "error",
                        "msg": "محتاج cam_ip في الـ body"}), 400

    print(f"[TEST] طلب التقاط — IP: {cam_ip} | {direction}")

    try:
        resp = requests.get(f"http://{cam_ip}/capture", timeout=8)

        if resp.status_code != 200:
            return jsonify({"status": "error",
                            "msg": f"الكاميرا ردت بـ {resp.status_code}"}), 500

        image_data = resp.content
        if len(image_data) < 500:
            return jsonify({"status": "error",
                            "msg": "الصورة فارغة أو صغيرة جداً"}), 500

        # حفظ الصورة
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        uid       = uuid.uuid4().hex[:6]
        filename  = f"{timestamp}_{direction}_{uid}.jpg"
        filepath  = os.path.join("uploads", filename)

        with open(filepath, 'wb') as f:
            f.write(image_data)

        print(f"[TEST] ✅ {filename} ({len(image_data):,} bytes)")

        # تحليل في background
        t = threading.Thread(
            target=analyze_image,
            args=(filepath, filename, direction, "manual_test")
        )
        t.daemon = True
        t.start()

        return jsonify({
            "status":    "ok",
            "msg":       "تم الالتقاط — التحليل جاري...",
            "filename":  filename,
            "size":      len(image_data),
            "direction": direction,
        }), 200

    except requests.exceptions.ConnectionError:
        return jsonify({"status": "error",
                        "msg": f"مش قادر يتصل بالكاميرا — IP: {cam_ip}"}), 503
    except requests.exceptions.Timeout:
        return jsonify({"status": "error",
                        "msg": "الكاميرا مش بتستجيب — timeout"}), 504
    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)}), 500


# ════════════════════════════════════════════════════════════
#  ══ API: اختبار بدون كاميرا — نتيجة وهمية ══
#  POST /api/test/fake-scan
#  Body: {"direction": "RIGHT"}
# ════════════════════════════════════════════════════════════
@app.route('/api/test/fake-scan', methods=['POST'])
def fake_scan():
    """مفيد جداً للفرونت اند والموبايل — يختبروا العرض بدون روبوت"""
    body      = request.json or {}
    direction = body.get('direction', 'RIGHT').upper()

    # إنشاء صورة وهمية (صورة سوداء صغيرة)
    fake_jpeg = bytes([
        0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01,
        0x01, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00, 0xFF, 0xDB, 0x00, 0x43,
        0x00, 0x08, 0x06, 0x06, 0x07, 0x06, 0x05, 0x08, 0x07, 0x07, 0x07, 0x09,
        0x09, 0x08, 0x0A, 0x0C, 0x14, 0x0D, 0x0C, 0x0B, 0x0B, 0x0C, 0x19, 0x12,
        0x13, 0x0F, 0x14, 0x1D, 0x1A, 0x1F, 0x1E, 0x1D, 0x1A, 0x1C, 0x1C, 0x20,
        0x24, 0x2E, 0x27, 0x20, 0x22, 0x2C, 0x23, 0x1C, 0x1C, 0x28, 0x37, 0x29,
        0x2C, 0x30, 0x31, 0x34, 0x34, 0x34, 0x1F, 0x27, 0x39, 0x3D, 0x38, 0x32,
        0x3C, 0x2E, 0x33, 0x34, 0x32, 0xFF, 0xD9
    ])

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    uid       = uuid.uuid4().hex[:6]
    filename  = f"{timestamp}_{direction}_FAKE_{uid}.jpg"
    filepath  = os.path.join("uploads", filename)

    with open(filepath, 'wb') as f:
        f.write(fake_jpeg)

    # تحليل وهمي فوري
    result = random.choice(FAKE_RESULTS)
    scan_entry = {
        "scan_id":        str(uuid.uuid4())[:8],
        "session_id":     "fake_test",
        "filename":       filename,
        "image_url":      f"/api/images/{filename}",
        "direction":      direction,
        "direction_ar":   "يمين" if direction == "RIGHT" else "يسار",
        "captured_at":    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "captured_time":  datetime.now().strftime("%H:%M:%S"),
        "status":         result["status"],
        "status_ar":      result["status_ar"],
        "disease":        result["disease"],
        "disease_ar":     result["disease_ar"],
        "confidence":     result["confidence"],
        "recommendation": result["recommendation_ar"],
        "ai_source":      "fake_model_test",
        "is_new":         True,
        "is_fake":        True,
    }

    scans_db.insert(0, scan_entry)

    print(f"[FAKE] ✅ {direction} | {result['status_ar']} | {result['disease']}")

    return jsonify({
        "status": "ok",
        "msg":    "نتيجة وهمية للاختبار",
        "scan":   scan_entry
    }), 200


# ════════════════════════════════════════════════════════════
#  ══ API: التحكم في الروبوت ══
# ════════════════════════════════════════════════════════════
@app.route('/api/robot/start', methods=['POST'])
def start_robot():
    try:
        r = requests.get(f"http://{NODEMCU_IP}/start", timeout=4)
        print(f"[Robot] ▶ تشغيل")
        return jsonify({"status": "ok", "msg": "الروبوت شغّال ✅"}), 200
    except requests.exceptions.ConnectionError:
        return jsonify({"status": "error",
                        "msg": f"الروبوت مش متاح — IP: {NODEMCU_IP}"}), 503
    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)}), 500


@app.route('/api/robot/stop', methods=['POST'])
def stop_robot():
    try:
        r = requests.get(f"http://{NODEMCU_IP}/stop", timeout=4)
        print(f"[Robot] ⏹ إيقاف")
        return jsonify({"status": "ok", "msg": "الروبوت وقف ⏹"}), 200
    except requests.exceptions.ConnectionError:
        return jsonify({"status": "error",
                        "msg": f"الروبوت مش متاح — IP: {NODEMCU_IP}"}), 503
    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)}), 500


@app.route('/api/robot/status', methods=['GET'])
def robot_status():
    try:
        r = requests.get(f"http://{NODEMCU_IP}/status", timeout=3)
        return jsonify(r.json()), 200
    except:
        return jsonify({"state": "UNREACHABLE", "running": False}), 200


# ════════════════════════════════════════════════════════════
#  ══ API: الإحصائيات ══
#  GET /api/stats
# ════════════════════════════════════════════════════════════
@app.route('/api/stats', methods=['GET'])
def get_stats():
    total    = len(scans_db)
    healthy  = sum(1 for s in scans_db if s['status'] == 'healthy')
    diseased = sum(1 for s in scans_db if s['status'] == 'diseased')
    rate     = round((healthy / total * 100), 1) if total > 0 else 0

    diseases = {}
    for s in scans_db:
        if s['disease'] != 'None':
            diseases[s['disease']] = diseases.get(s['disease'], 0) + 1

    return jsonify({
        "status":       "ok",
        "total_scans":  total,
        "healthy":      healthy,
        "diseased":     diseased,
        "health_rate":  f"{rate}%",
        "top_diseases": sorted(diseases.items(),
                                key=lambda x: x[1], reverse=True)[:5]
    }), 200


# ════════════════════════════════════════════════════════════
#  ══ API: صحة السيرفر ══
#  GET /api/health
# ════════════════════════════════════════════════════════════
START_TIME = datetime.now()

@app.route('/api/health', methods=['GET'])
def health():
    uptime = str(datetime.now() - START_TIME).split('.')[0]
    return jsonify({
        "status":       "ok",
        "uptime":       uptime,
        "total_scans":  len(scans_db),
        "ai_mode":      "fake" if USE_FAKE_AI else "real",
        "ai_url":       AI_MODEL_URL or "not set",
        "nodemcu_ip":   NODEMCU_IP,
        "timestamp":    datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }), 200


# ════════════════════════════════════════════════════════════
#  ══ API: تعيين URL موديل الـ AI ══
#  POST /api/ai/set-url
#  Body: {"url": "http://ai-server:8000/predict"}
# ════════════════════════════════════════════════════════════
@app.route('/api/ai/set-url', methods=['POST'])
def set_ai_url():
    global AI_MODEL_URL, USE_FAKE_AI
    body = request.json or {}
    url  = body.get('url', '')

    if not url:
        return jsonify({"status": "error", "msg": "محتاج url"}), 400

    AI_MODEL_URL = url
    USE_FAKE_AI  = False
    print(f"[AI] ✅ تم تعيين URL الموديل: {url}")
    return jsonify({"status": "ok",
                    "msg": f"تم تعيين AI URL: {url}",
                    "use_fake": False}), 200


# ── endpoints قديمة للتوافق مع Dashboard القديم ────────────
@app.route('/upload', methods=['POST'])
def upload_old():
    return upload_image()

@app.route('/results', methods=['GET'])
def results_old():
    """توافق مع الـ Dashboard القديم"""
    results = []
    for s in scans_db[:20]:
        results.append({
            "filename":       s["filename"],
            "direction":      s["direction"],
            "status":         s["status_ar"],
            "disease":        s["disease_ar"],
            "confidence":     s["confidence"],
            "recommendation": s["recommendation"],
            "received_at":    s["captured_time"],
            "is_new":         s["is_new"],
        })
    return jsonify({"results": results}), 200

@app.route('/image/<filename>')
def image_old(filename):
    return serve_image(filename)

@app.route('/test/capture', methods=['POST'])
def test_capture_old():
    return test_capture()

@app.route('/control/start',  methods=['POST', 'GET'])
def control_start():  return start_robot()

@app.route('/control/stop',   methods=['POST', 'GET'])
def control_stop():   return stop_robot()

@app.route('/control/status', methods=['GET'])
def control_status(): return robot_status()


# ════════════════════════════════════════════════════════════
if __name__ == '__main__':
    print("=" * 55)
    print("  🌾 روبوت زراعي ذكي — السيرفر شغّال")
    print(f"  Dashboard:    http://localhost:5000")
    print(f"  API Docs:     http://localhost:5000/api/docs")
    print(f"  NodeMCU IP:   {NODEMCU_IP}")
    print(f"  AI Mode:      {'وهمي للاختبار' if USE_FAKE_AI else 'حقيقي'}")
    print("=" * 55)
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
