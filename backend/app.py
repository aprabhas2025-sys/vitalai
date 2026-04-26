from dotenv import load_dotenv
load_dotenv()
from flask import Flask, render_template, request, jsonify, redirect, session
from flask_cors import CORS
import requests
import os
import json
from datetime import datetime, timedelta
import urllib.parse

import os as _os
_base = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
app = Flask(__name__,
            template_folder=_os.path.join(_base, "frontend"),
            static_folder=_os.path.join(_base, "static"))
import os
app.secret_key = os.environ.get("SECRET_KEY", "vitalai-secret-2026-xK9mP") # fixed key so sessions survive restarts
CORS(app, supports_credentials=True)

# ── Import & register Medication module ──
from medication import medication_bp, init_med_db
app.register_blueprint(medication_bp)

# ─────────────────────────────────────────
# Google OAuth Config
# ─────────────────────────────────────────
CLIENT_ID     = os.environ.get("GOOGLE_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
REDIRECT_URI = os.environ.get("REDIRECT_URI", "http://localhost:5000/callback")

SCOPES = [
    "https://www.googleapis.com/auth/fitness.activity.read",
    "https://www.googleapis.com/auth/fitness.body.read",
    "https://www.googleapis.com/auth/fitness.sleep.read",
    "https://www.googleapis.com/auth/fitness.heart_rate.read",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/userinfo.email",
]

# ─────────────────────────────────────────
# Google Fit Helpers
# ─────────────────────────────────────────
def get_fit_data(access_token, data_type, start_ms, end_ms):
    url     = "https://www.googleapis.com/fitness/v1/users/me/dataset:aggregate"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    body    = {
        "aggregateBy": [{"dataTypeName": data_type}],
        "bucketByTime": {"durationMillis": 86400000},
        "startTimeMillis": start_ms,
        "endTimeMillis": end_ms,
    }
    try:
        resp = requests.post(url, headers=headers, json=body, timeout=10)
        return resp.json()
    except Exception as e:
        return {"error": str(e)}

def ms_range_today():
    now   = datetime.utcnow()
    start = datetime(now.year, now.month, now.day)
    end   = start + timedelta(days=1)
    return int(start.timestamp() * 1000), int(end.timestamp() * 1000)

def ms_range_week():
    now   = datetime.utcnow()
    start = now - timedelta(days=7)
    return int(start.timestamp() * 1000), int(now.timestamp() * 1000)

def extract_steps(fit_data):
    total = 0
    for bucket in fit_data.get("bucket", []):
        for ds in bucket.get("dataset", []):
            for point in ds.get("point", []):
                for val in point.get("value", []):
                    total += val.get("intVal", 0)
    return total

def extract_calories(fit_data):
    total = 0.0
    for bucket in fit_data.get("bucket", []):
        for ds in bucket.get("dataset", []):
            for point in ds.get("point", []):
                for val in point.get("value", []):
                    total += val.get("fpVal", 0.0)
    return round(total, 1)

def extract_heart_rate(fit_data):
    values = []
    for bucket in fit_data.get("bucket", []):
        for ds in bucket.get("dataset", []):
            for point in ds.get("point", []):
                for val in point.get("value", []):
                    v = val.get("fpVal", 0)
                    if v > 0:
                        values.append(v)
    return round(sum(values) / len(values), 1) if values else None

def extract_weight(fit_data):
    latest = None
    for bucket in fit_data.get("bucket", []):
        for ds in bucket.get("dataset", []):
            for point in ds.get("point", []):
                for val in point.get("value", []):
                    v = val.get("fpVal", 0)
                    if v > 0:
                        latest = round(v, 1)
    return latest

# ─────────────────────────────────────────
# AI Health Chat
# ─────────────────────────────────────────
def ai_health_reply(message, health_data=None):
    msg   = message.lower().strip()
    steps = health_data.get("steps", 0) if health_data else 0
    hr    = health_data.get("heart_rate") if health_data else None

    if not msg:
        return "Please ask me a health question!"

    if "steps" in msg:
        if steps:
            s = "Great job! 🎉" if steps >= 8000 else "Keep going! 💪"
            return f"You've walked **{steps:,} steps** today. {s} Goal: 8,000–10,000 steps/day."
        return "Walking 8,000–10,000 steps daily supports cardiovascular health and mental wellbeing."

    if any(x in msg for x in ["heart","bpm","pulse"]):
        if hr:
            s = "Normal ✅" if 60 <= hr <= 100 else "Please consult a doctor ⚠️"
            return f"Your average heart rate is **{hr} BPM**. Status: {s}. Normal range: 60–100 BPM."
        return "A healthy resting heart rate is 60–100 BPM. Athletes may have rates as low as 40 BPM."

    if any(x in msg for x in ["calorie","burn"]):
        return "Calorie burn depends on weight, age, and activity. Moderate exercise burns 300–600 kcal/hour."

    if "sleep" in msg:
        return "Adults need 7–9 hours of sleep. Consistent sleep/wake times improve sleep quality. Avoid screens 1 hour before bed."

    if any(x in msg for x in ["water","hydrat"]):
        return "Drink 2–3 litres of water daily. In India's climate, you may need more in summer."

    if "bmi" in msg:
        return "BMI = weight(kg) / height(m)². Healthy: 18.5–24.9. For Indians, BMI ≥23 may indicate health risks."

    if any(x in msg for x in ["fever","temperature"]):
        return "Normal body temperature: 36.1–37.2°C. Fever (>38°C) usually indicates infection. Seek help if >39.5°C or lasting 3+ days."

    if any(x in msg for x in ["diet","food","eat","nutrition"]):
        return "A balanced Indian diet: whole grains, dal, vegetables, dairy, fruits. Limit processed food and refined sugar."

    if any(x in msg for x in ["exercise","workout","fitness"]):
        return "WHO recommends 150 min of moderate aerobic activity per week. Even 30 min daily makes a big difference."

    if any(x in msg for x in ["stress","anxiet","mental"]):
        return "Mental health matters. Practice deep breathing, yoga, or meditation. Don't hesitate to seek professional help."

    if any(x in msg for x in ["bp","blood pressure"]):
        return "Normal BP: below 120/80 mmHg. High BP (>130/80) raises heart disease risk. Reduce salt and exercise regularly."

    if any(x in msg for x in ["diabetes","sugar","glucose"]):
        return "Normal fasting blood sugar: 70–100 mg/dL. Manage with low-GI diet, regular exercise, and prescribed medication."

    if any(x in msg for x in ["medicine","medication","drug","tablet","capsule"]):
        return "I can help with medication info! Go to the 💊 Medications page to search medicines, check interactions, and track your doses."

    if any(x in msg for x in ["hello","hi","hey"]):
        return "Hello! 👋 I'm your AI Health Assistant. Ask me about fitness, symptoms, diet, sleep, or medications!"

    if "thank" in msg:
        return "You're welcome! Stay healthy! 💚"

    return "I can help with steps, heart rate, sleep, diet, exercise, BP, diabetes, and medications. Please ask a specific question!"


# ─────────────────────────────────────────
# Routes
# ─────────────────────────────────────────

@app.route("/")
def home():
    return render_template("index.html", user=session.get("user"))

@app.route("/login")
def login():
    scope    = " ".join(SCOPES)
    params   = {
        "client_id": CLIENT_ID, "redirect_uri": REDIRECT_URI,
        "response_type": "code", "scope": scope,
        "access_type": "offline", "prompt": "consent",
    }
    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)
    return redirect(auth_url)

@app.route("/callback")
def callback():
    code = request.args.get("code")
    if not code:
        return redirect("/?error=auth_failed")
    try:
        token_resp = requests.post("https://oauth2.googleapis.com/token", data={
            "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
            "code": code, "grant_type": "authorization_code", "redirect_uri": REDIRECT_URI,
        }, timeout=10)
        tokens = token_resp.json()
        if "access_token" not in tokens:
            return redirect("/?error=token_failed")
        session["access_token"]  = tokens["access_token"]
        session["refresh_token"] = tokens.get("refresh_token")
        profile = requests.get("https://www.googleapis.com/oauth2/v2/userinfo",
                               headers={"Authorization": f"Bearer {tokens['access_token']}"}, timeout=10).json()
        session["user"] = {
            "name":    profile.get("name", "User"),
            "email":   profile.get("email", ""),
            "picture": profile.get("picture", ""),
        }
        return redirect("/dashboard")
    except Exception as e:
        return redirect(f"/?error={e}")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/dashboard")
def dashboard():
    if "access_token" not in session:
        return redirect("/")
    return render_template("dashboard.html", user=session.get("user", {}))

@app.route("/medications")
def medications_page():
    return render_template("medications.html", user=session.get("user", {}))

@app.route("/api/health-data")
def health_data():
    token = session.get("access_token")
    if not token:
        return jsonify({"error": "Not authenticated"}), 401

    start_ms, end_ms   = ms_range_today()
    week_start, week_end = ms_range_week()

    steps_data    = get_fit_data(token, "com.google.step_count.delta", start_ms, end_ms)
    calories_data = get_fit_data(token, "com.google.calories.expended", start_ms, end_ms)
    hr_data       = get_fit_data(token, "com.google.heart_rate.bpm", start_ms, end_ms)
    weight_data   = get_fit_data(token, "com.google.weight", week_start, week_end)
    week_steps    = get_fit_data(token, "com.google.step_count.delta", week_start, week_end)

    weekly_steps = []
    for bucket in week_steps.get("bucket", []):
        ts   = int(bucket.get("startTimeMillis", 0)) // 1000
        date_label = datetime.utcfromtimestamp(ts).strftime("%a")
        day_steps  = sum(
            val.get("intVal", 0)
            for ds in bucket.get("dataset", [])
            for point in ds.get("point", [])
            for val in point.get("value", [])
        )
        weekly_steps.append({"day": date_label, "steps": day_steps})

    result = {
        "steps":        extract_steps(steps_data),
        "calories":     extract_calories(calories_data),
        "heart_rate":   extract_heart_rate(hr_data),
        "weight":       extract_weight(weight_data),
        "weekly_steps": weekly_steps,
        "last_updated": datetime.utcnow().strftime("%H:%M UTC"),
    }
    session["health_data"] = result
    return jsonify(result)

@app.route("/api/chat", methods=["POST"])
def chat():
    d       = request.get_json()
    message = d.get("message", "")
    reply   = ai_health_reply(message, session.get("health_data"))
    return jsonify({"reply": reply, "timestamp": datetime.utcnow().strftime("%H:%M")})

@app.route("/api/status")
def status():
    return jsonify({"authenticated": "access_token" in session, "user": session.get("user")})


# ─────────────────────────────────────────
# Run
# ─────────────────────────────────────────
init_med_db()
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
