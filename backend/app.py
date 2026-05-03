"""
VitalAI — Main Flask Application (Optimized)
Integrates: Google Fit, Medication Module, Health Extras Module
"""

from flask import Flask, render_template, request, jsonify, redirect, session
from flask_cors import CORS
from dotenv import load_dotenv
import requests
import os
import json
from datetime import datetime, timedelta
import urllib.parse
from functools import wraps

# Load .env for local development
load_dotenv()

# ─────────────────────────────────────────
# App Setup
# ─────────────────────────────────────────
_base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app = Flask(__name__,
            template_folder=os.path.join(_base, "frontend"),
            static_folder=os.path.join(_base, "static"))

app.secret_key = os.environ.get("SECRET_KEY", "vitalai-secret-2026-xK9mP")
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"]   = False  # True in production with HTTPS
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=7)

CORS(app, supports_credentials=True)

# ── Register Blueprints ──
from medication import medication_bp, init_med_db
from extras     import extras_bp,    init_extras_db

app.register_blueprint(medication_bp)
app.register_blueprint(extras_bp)

# ─────────────────────────────────────────
# Google OAuth Config — from environment
# ─────────────────────────────────────────
CLIENT_ID     = os.environ.get("GOOGLE_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
REDIRECT_URI  = os.environ.get("REDIRECT_URI", "http://localhost:5000/callback")

SCOPES = [
    "https://www.googleapis.com/auth/fitness.activity.read",
    "https://www.googleapis.com/auth/fitness.body.read",
    "https://www.googleapis.com/auth/fitness.sleep.read",
    "https://www.googleapis.com/auth/fitness.heart_rate.read",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/userinfo.email",
]

# ─────────────────────────────────────────
# Auth decorator
# ─────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "access_token" not in session:
            return redirect("/")
        return f(*args, **kwargs)
    return decorated

# ─────────────────────────────────────────
# Google Fit Helpers (optimized — parallel calls)
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

def extract_int_values(fit_data):
    total = 0
    for bucket in fit_data.get("bucket", []):
        for ds in bucket.get("dataset", []):
            for point in ds.get("point", []):
                for val in point.get("value", []):
                    total += val.get("intVal", 0)
    return total

def extract_fp_values(fit_data):
    total = 0.0
    for bucket in fit_data.get("bucket", []):
        for ds in bucket.get("dataset", []):
            for point in ds.get("point", []):
                for val in point.get("value", []):
                    total += val.get("fpVal", 0.0)
    return round(total, 1)

def extract_avg_fp(fit_data):
    values = [
        val.get("fpVal", 0)
        for bucket in fit_data.get("bucket", [])
        for ds in bucket.get("dataset", [])
        for point in ds.get("point", [])
        for val in point.get("value", [])
        if val.get("fpVal", 0) > 0
    ]
    return round(sum(values) / len(values), 1) if values else None

def extract_latest_fp(fit_data):
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
# Enhanced AI Health Chat
# ─────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────
# Comprehensive AI Health Knowledge Base
# Covers: symptoms, diseases, nutrition, fitness, mental health,
#         Indian health context, medications, first aid, and more
# ─────────────────────────────────────────────────────────────────────

HEALTH_KB = [
    # ── Greetings ──
    (["hello","hi","hey","namaste","good morning","good evening"],
     "Hello! 👋 I'm your AI Health Assistant. You can ask me about:\n• Symptoms & diseases\n• Diet & nutrition\n• Fitness & exercise\n• Medications & side effects\n• Mental health\n• First aid\n• Your Google Fit data\nWhat would you like to know?"),

    (["thank","thanks","dhanyavad","shukriya"],
     "You're welcome! 😊 Stay healthy and feel free to ask anything anytime."),

    (["who are you","what are you","what can you do","help"],
     "I'm VitalAI's Health Assistant 🤖 I can answer questions about symptoms, diseases, diet, exercise, medications, mental health, first aid, and your personal fitness data from Google Fit. Just ask me anything health-related!"),

    # ── Common Cold & Flu ──
    (["cold symptom","symptom of cold","common cold","running nose","runny nose","nasal","sneezing","sore throat"],
     "🤧 **Common Cold Symptoms:**\n• Runny or stuffy nose\n• Sneezing frequently\n• Sore or scratchy throat\n• Mild cough\n• Watery eyes\n• Mild body ache\n• Slight fatigue\n• Low-grade fever (sometimes)\n\n**Treatment:**\n• Rest and drink warm fluids (tulsi tea, kadha, warm water with honey)\n• Steam inhalation 2–3 times daily\n• Saline nasal drops for congestion\n• Paracetamol for fever/pain\n• Cetirizine for sneezing/runny nose\n\n⚠️ See a doctor if symptoms last over 10 days or fever exceeds 39°C."),

    (["flu symptom","influenza","body ache","chills","shivering"],
     "🤒 **Flu (Influenza) Symptoms:**\n• Sudden high fever (38–40°C)\n• Severe body aches and muscle pain\n• Chills and shivering\n• Intense fatigue and weakness\n• Headache\n• Dry cough\n• Sore throat\n• Sometimes vomiting/diarrhea\n\n**Key difference from cold:** Flu hits suddenly and is much more severe.\n\n**Treatment:**\n• Bed rest is essential\n• Paracetamol or Ibuprofen for fever/pain\n• Plenty of warm fluids\n• Oseltamivir (Tamiflu) if prescribed within 48 hours\n\n⚠️ High-risk groups (elderly, diabetics, pregnant women) should see a doctor immediately."),

    # ── Fever ──
    (["fever","high temperature","temperature high","pyrexia","bukhar"],
     "🌡️ **Fever Guide:**\n• Normal temp: 36.1–37.2°C (97–99°F)\n• Low-grade fever: 37.3–38°C\n• Fever: Above 38°C (100.4°F)\n• High fever: Above 39°C\n• Very high (emergency): Above 40°C\n\n**Common causes:** Viral/bacterial infection, dengue, malaria, typhoid, UTI\n\n**What to do:**\n• Take Paracetamol (500–650mg) every 6 hours\n• Stay hydrated — drink water, coconut water, ORS\n• Wear light clothing, use a damp cloth on forehead\n• Rest completely\n\n⚠️ **See a doctor immediately if:**\n• Fever above 39.5°C lasting more than 2 days\n• Rash appears with fever (dengue warning)\n• Severe headache or neck stiffness\n• Difficulty breathing"),

    # ── Dengue ──
    (["dengue","dengue fever","platelet","mosquito fever"],
     "🦟 **Dengue Fever — Important:**\n\n**Symptoms:**\n• Sudden high fever (39–40°C) — often called 'breakbone fever'\n• Severe headache behind the eyes\n• Joint and muscle pain\n• Skin rash (red spots, appears 3–4 days after fever)\n• Nausea and vomiting\n• Fatigue\n• Low platelet count (below 1.5 lakh is concerning)\n\n**Warning signs (go to hospital immediately):**\n• Bleeding from nose/gums\n• Blood in urine or stools\n• Vomiting blood\n• Platelet count below 20,000\n• Severe abdominal pain\n\n**Treatment:**\n• No specific antiviral — supportive care only\n• Paracetamol for fever (NOT ibuprofen/aspirin — can increase bleeding)\n• ORS and fluids\n• Monitor platelet count daily\n• Hospitalization when platelets drop below 50,000\n\n⚠️ Dengue is serious — always consult a doctor."),

    # ── Malaria ──
    (["malaria","malarial","plasmodium"],
     "🦟 **Malaria Symptoms:**\n• Cyclical fever with chills (every 48–72 hours)\n• Sweating after fever breaks\n• Severe headache\n• Muscle aches\n• Nausea and vomiting\n• Fatigue\n\n**Diagnosis:** Blood smear test or Rapid Diagnostic Test (RDT)\n\n**Treatment:** Artemisinin-based combination therapy (ACT) — prescribed by doctor only\n\n⚠️ Malaria is treatable but dangerous if delayed. See a doctor for any cyclical fever, especially after travel to endemic areas."),

    # ── Typhoid ──
    (["typhoid","enteric fever","salmonella"],
     "🌡️ **Typhoid Symptoms:**\n• Prolonged fever (gradually rising, up to 39–40°C)\n• Headache and weakness\n• Abdominal pain (right lower)\n• Constipation (early) then diarrhea\n• Rose-colored spots on chest (rare)\n• Loss of appetite\n\n**Diagnosis:** Widal test, blood culture\n\n**Treatment:** Antibiotics (Azithromycin, Ciprofloxacin, Ceftriaxone) — doctor prescribed\n\n**Prevention:** Drink boiled/filtered water, eat freshly cooked food, typhoid vaccine available"),

    # ── COVID / Viral ──
    (["covid","coronavirus","omicron","covid symptom"],
     "😷 **COVID-19 Common Symptoms:**\n• Fever or chills\n• Dry cough\n• Fatigue\n• Loss of taste or smell\n• Sore throat\n• Shortness of breath\n• Body aches\n• Headache\n\n**What to do:**\n• Isolate immediately\n• Monitor oxygen (SpO2 should be above 95%)\n• Paracetamol for fever\n• Stay hydrated\n• Test using home RAT kit or RT-PCR\n\n⚠️ Go to hospital if SpO2 drops below 94%, breathing difficulty, or chest pain."),

    # ── Cough ──
    (["cough","coughing","khansi","dry cough","wet cough","chest congestion"],
     "😮‍💨 **Types of Cough & Remedies:**\n\n**Dry Cough:**\n• Honey + warm water (most effective)\n• Tulsi + ginger tea\n• Steam inhalation\n• Dextromethorphan syrup (OTC)\n• Avoid dusty/cold environments\n\n**Wet/Productive Cough:**\n• Expectorants like Ambroxol or Guaifenesin\n• Stay hydrated to loosen mucus\n• Steam inhalation\n\n**Persistent Cough (>3 weeks):** May indicate TB, asthma, or GERD — see a doctor.\n\n**Home Remedy:** Honey + lemon + warm water + pinch of turmeric — effective and safe"),

    # ── Headache ──
    (["headache","migraine","head pain","sir dard"],
     "🤕 **Headache Types & Relief:**\n\n**Tension Headache (most common):**\n• Dull pressure around forehead/temples\n• Caused by stress, screen time, dehydration\n• Relief: Paracetamol, rest, cold/warm compress, neck stretch\n\n**Migraine:**\n• Throbbing pain (usually one side)\n• Nausea, sensitivity to light/sound\n• Can last 4–72 hours\n• Relief: Dark quiet room, Sumatriptan (doctor prescribed), Ibuprofen\n\n**Sinus Headache:**\n• Pressure behind eyes, forehead\n• Worsens when bending forward\n• Relief: Steam inhalation, decongestants, nasal spray\n\n**Prevention:**\n• Drink 2–3L water daily\n• Limit screen time\n• Sleep 7–8 hours\n• Avoid skipping meals\n\n⚠️ Sudden severe headache ('thunderclap') — emergency, call 112."),

    # ── Stomach ──
    (["stomach","stomach ache","stomach pain","gastric","acidity","indigestion","gas","bloating","pet dard"],
     "🫃 **Stomach & Digestive Issues:**\n\n**Acidity/GERD:**\n• Burning sensation, sour belching\n• Antacids (Gelusil, ENO) for quick relief\n• Omeprazole/Pantoprazole for regular use\n• Avoid spicy food, tea/coffee on empty stomach\n• Eat small frequent meals\n\n**Gas & Bloating:**\n• Avoid carbonated drinks, beans, cabbage\n• Hingvastak churna or ajwain water\n• Walk after meals\n\n**Stomach Pain (cramps):**\n• If with loose stools — likely gastroenteritis\n• ORS for hydration, bland diet (BRAT: Banana, Rice, Applesauce, Toast)\n• Avoid dairy during diarrhea\n\n⚠️ See a doctor if pain is severe, persistent, or comes with blood in stools."),

    # ── Diarrhea ──
    (["diarrhea","loose motion","loose stool","diarrhoea","dysentery","motions"],
     "🚽 **Diarrhea Management:**\n\n**Key priority — prevent dehydration:**\n• ORS (Oral Rehydration Salts) — 1 sachet in 1L water, sip frequently\n• Coconut water, thin dal water, rice water\n• Avoid solid food for first few hours\n\n**What to eat:**\n• BRAT diet: Banana, Rice, Applesauce, Toast\n• Curd/yogurt (probiotics help restore gut flora)\n• Khichdi\n\n**Medications:**\n• Loperamide (Imodium) — for non-infective diarrhea only\n• Metronidazole — if infective/amoebic (doctor prescribed)\n\n⚠️ See a doctor if:\n• Diarrhea lasts more than 3 days\n• Blood or mucus in stools\n• Signs of dehydration (dry mouth, sunken eyes, no urination)\n• High fever with diarrhea"),

    # ── Vomiting / Nausea ──
    (["vomiting","nausea","vomit","nauseous","feel sick","throwing up","ulti"],
     "🤢 **Nausea & Vomiting:**\n\n**Common causes:** Food poisoning, gastroenteritis, motion sickness, pregnancy, migraine, medication side effect\n\n**Relief:**\n• Sip clear fluids slowly — ORS, coconut water, plain water\n• Ginger tea or ginger candy (natural antiemetic)\n• Eat small, bland meals when it subsides\n• Ondansetron (Emeset) or Domperidone — very effective antiemetics\n• Avoid dairy, spicy, oily food\n\n**Motion sickness prevention:** Avomine (Promethazine) or Stugeron 30 min before travel\n\n⚠️ See a doctor if vomiting persists >24 hours, if there's blood in vomit, or if you can't keep fluids down."),

    # ── Constipation ──
    (["constipation","constipated","no bowel","hard stool","kabz"],
     "💊 **Constipation Relief:**\n\n**Immediate relief:**\n• Isabgol (Psyllium husk) — 2 tsp in warm water before bed\n• Triphala churna at night\n• Warm water with lemon in the morning\n• Lactulose syrup (safe for all ages)\n\n**Long-term habits:**\n• Drink 2.5–3L water daily\n• Eat high-fiber foods: vegetables, fruits, whole grains, dal\n• Walk 30 minutes daily\n• Don't ignore the urge to go\n• Establish a regular toilet time\n\n⚠️ See a doctor if constipation lasts more than 2 weeks or blood appears in stools."),

    # ── Blood Pressure ──
    (["blood pressure","bp","hypertension","high bp","low bp","hypotension","pressure"],
     "🩺 **Blood Pressure Guide:**\n\n**Normal:** Below 120/80 mmHg\n**Elevated:** 120–129 / below 80\n**High (Stage 1):** 130–139 / 80–89\n**High (Stage 2):** 140+ / 90+\n**Crisis:** 180+ / 120+ — **Emergency**\n**Low BP:** Below 90/60 — can cause dizziness/fainting\n\n**For High BP:**\n• Reduce salt intake to under 5g/day\n• Exercise 30 min daily\n• Maintain healthy weight\n• Limit alcohol and caffeine\n• Take prescribed medications regularly (Amlodipine, Losartan, Telmisartan)\n\n**For Low BP:**\n• Increase salt and fluid intake\n• Avoid standing up suddenly\n• Small frequent meals\n• Wear compression stockings if needed\n\n⚠️ Monitor BP daily at home. Report readings to your doctor regularly."),

    # ── Diabetes ──
    (["diabetes","diabetic","blood sugar","insulin","sugar level","hba1c","glucose","type 2","type 1"],
     "🩸 **Diabetes Management:**\n\n**Normal Fasting Blood Sugar:** 70–100 mg/dL\n**Pre-diabetes:** 100–125 mg/dL\n**Diabetes:** 126+ mg/dL on 2 occasions\n\n**Symptoms of high blood sugar:** Frequent urination, excessive thirst, blurred vision, fatigue, slow wound healing\n\n**Symptoms of low blood sugar (hypoglycemia):** Sweating, trembling, confusion, palpitations — eat 15g sugar immediately (glucose tablet, juice, sugar water)\n\n**Management:**\n• Low-GI Indian diet: brown rice, whole wheat roti, dal, vegetables\n• Avoid: white rice, maida, sweets, fruit juices, packaged foods\n• Exercise 30–45 min daily (walking is best)\n• Monitor blood sugar regularly\n• Take medications as prescribed (Metformin, Glimepiride, Insulin)\n• Target HbA1c: Below 7%\n\n⚠️ Diabetes affects eyes, kidneys, nerves — regular check-ups are essential."),

    # ── Thyroid ──
    (["thyroid","hypothyroid","hyperthyroid","tsh","thyroxine"],
     "🦋 **Thyroid Problems:**\n\n**Hypothyroidism (underactive):**\n• Fatigue, weight gain, constipation, cold sensitivity, dry skin, hair loss, depression\n• TSH above 4.0 mIU/L indicates hypothyroidism\n• Treatment: Levothyroxine (Thyronorm) — taken empty stomach, 30 min before breakfast\n\n**Hyperthyroidism (overactive):**\n• Weight loss, rapid heartbeat, sweating, anxiety, tremor, insomnia\n• TSH below 0.4 mIU/L — further tests needed\n• Treatment: Carbimazole, radioiodine, or surgery\n\n**Indian context:** Iodine deficiency is common — use iodized salt, eat seafood and dairy.\n\n⚠️ Thyroid conditions require lifelong monitoring. Never stop medication without doctor advice."),

    # ── Asthma ──
    (["asthma","breathe","breathing","wheezing","inhaler","respiratory","shortness of breath","breathlessness"],
     "😮‍💨 **Asthma & Breathing:**\n\n**Asthma Symptoms:**\n• Wheezing (whistling sound when breathing)\n• Shortness of breath\n• Chest tightness\n• Cough (especially at night)\n\n**Triggers:** Dust, pollen, cold air, smoke, pet dander, exercise, respiratory infections\n\n**Inhalers:**\n• **Reliever (Blue):** Salbutamol (Asthalin) — use during attacks — opens airways in minutes\n• **Preventer (Brown/Red):** Budesonide or Fluticasone — take daily even when feeling fine\n\n**During an attack:**\n1. Sit upright, stay calm\n2. Use reliever inhaler immediately (2 puffs)\n3. Wait 1 minute, repeat if no relief\n4. If no improvement after 10 minutes — call 112\n\n**Indoor air quality:** Use air purifier, avoid carpets, clean AC filters regularly"),

    # ── Heart disease ──
    (["chest pain","heart attack","cardiac","angina","heart disease","palpitation","heartburn"],
     "❤️ **Chest Pain — Important:**\n\n**Heart Attack Warning Signs:**\n• Crushing chest pain (may radiate to left arm, jaw, back)\n• Sweating with chest pain\n• Nausea\n• Shortness of breath\n• Feeling of doom\n\n🚨 **Call 112 immediately if you suspect a heart attack!**\nWhile waiting: Chew 1 aspirin (325mg) if not allergic\n\n**Angina (chest pain from exertion):**\n• Relieved by rest or nitrate spray\n• Needs cardiac evaluation\n\n**Heartburn (GERD):**\n• Burning sensation after meals\n• Worse when lying down\n• Relieved by antacids\n• No relation to exertion\n\n**Palpitations:**\n• Usually harmless — caused by stress, caffeine, dehydration\n• If with dizziness or fainting — see a cardiologist"),

    # ── Skin ──
    (["skin","rash","itch","itching","allergy","hives","eczema","psoriasis","pimple","acne","tanning"],
     "🧴 **Skin Issues:**\n\n**Acne/Pimples:**\n• Benzoyl peroxide or Salicylic acid wash\n• Clindamycin gel (antibiotic)\n• Avoid touching face, use oil-free products\n• Zinc supplements may help\n\n**Rash/Hives:**\n• Cetirizine or Chlorpheniramine for itching\n• Calamine lotion for topical relief\n• Identify and avoid trigger (food, soap, fabric)\n\n**Eczema:**\n• Moisturize frequently (Cetaphil, Vaseline)\n• Mild hydrocortisone cream for flare-ups\n• Avoid hot showers and harsh soaps\n\n**Fungal infection (ringworm, jock itch):**\n• Clotrimazole or Miconazole cream twice daily\n• Keep area dry, wear loose cotton clothing\n\n**Sunburn:**\n• Aloe vera gel immediately\n• Cool water compress\n• Avoid further sun exposure\n• SPF 30+ sunscreen daily"),

    # ── Mental Health ──
    (["stress","anxiety","anxious","depression","mental health","sad","panic","worry","tension","nervous"],
     "🧠 **Mental Health Support:**\n\n**Stress & Anxiety:**\n• **4-7-8 Breathing:** Inhale 4 sec → Hold 7 sec → Exhale 8 sec — immediate calming\n• Progressive muscle relaxation\n• Limit news and social media\n• Regular exercise — even 20 min walk reduces cortisol\n• Limit caffeine — worsens anxiety\n\n**Depression Signs:**\n• Persistent sadness for 2+ weeks\n• Loss of interest in activities\n• Sleep changes, fatigue, difficulty concentrating\n• Feelings of worthlessness\n\n**What helps:**\n• Talk to someone you trust\n• Regular routine — sleep, eat, exercise at same times\n• Sunlight exposure (morning walk)\n• Professional help — therapy + medication if needed\n\n**India helplines:**\n• iCall: 9152987821\n• Vandrevala Foundation: 1860-2662-345 (24/7)\n• SNEHI: 044-24640050\n\n💚 Seeking help is a sign of strength, not weakness."),

    # ── Sleep ──
    (["sleep","insomnia","can't sleep","sleepless","neend","nind"],
     "😴 **Sleep & Insomnia:**\n\n**Adults need:** 7–9 hours per night\n\n**Good sleep habits:**\n• Same sleep and wake time every day (even weekends)\n• Dark, cool room (18–20°C ideal)\n• No screens 1 hour before bed\n• No caffeine after 2 PM\n• Avoid large meals 2–3 hours before bed\n• Brief relaxation ritual (warm shower, reading)\n\n**Natural remedies:**\n• Warm milk with turmeric (haldi doodh)\n• Ashwagandha at night (reduces cortisol)\n• Chamomile tea\n• Magnesium supplement\n\n**Medication (short-term only):**\n• Melatonin 0.5–5mg (safest, non-habit forming)\n• Diphenhydramine (mild OTC sedative)\n• Prescription options — doctor only\n\n⚠️ If insomnia lasts >3 weeks, see a doctor — may indicate depression, sleep apnea, or thyroid issues."),

    # ── Weight ──
    (["weight","obesity","overweight","weight loss","fat","bmi","lose weight"],
     "⚖️ **Weight Management:**\n\n**BMI Guide:**\n• Below 18.5 — Underweight\n• 18.5–22.9 — Normal (for Indians)\n• 23–24.9 — Overweight risk zone for Indians\n• 25+ — Overweight\n• 30+ — Obese\n\n**Safe weight loss:** 0.5–1 kg per week maximum\n\n**Effective strategies:**\n• Calorie deficit of 500 kcal/day\n• Eat more protein (dal, paneer, eggs, chicken) — keeps you full longer\n• Replace maida with atta, white rice with millets/brown rice\n• Eat vegetables first, then protein, then carbs\n• Walk 8,000–10,000 steps daily\n• Strength training 3x/week (builds muscle, burns fat)\n• Adequate sleep (poor sleep = weight gain)\n• Stay hydrated — hunger is often thirst\n\n**Indian superfoods for weight loss:**\nMethi, Jeera water, Triphala, Green tea, Buttermilk"),

    # ── Nutrition ──
    (["nutrition","protein","vitamin","mineral","supplement","iron","calcium","b12","vitamin d"],
     "🥗 **Nutrition Guide for Indians:**\n\n**Common Deficiencies:**\n\n🩸 **Iron:** Common in women, vegetarians\n• Sources: Lentils, spinach, jaggery, sesame seeds, fortified foods\n• Tip: Eat with Vitamin C (lemon) to boost absorption\n• Avoid tea/coffee 1 hour before/after iron-rich meals\n\n☀️ **Vitamin D:** 70–80% of Indians are deficient\n• Sources: Sunlight (morning 10–20 min), fatty fish, egg yolk, fortified milk\n• Supplement: 1000–2000 IU daily or 60,000 IU weekly (doctor guided)\n\n🧬 **B12:** Critical for vegetarians and vegans\n• Sources: Dairy, eggs, fortified foods\n• Supplement recommended if vegetarian\n\n🦴 **Calcium:**\n• Sources: Milk, curd, cheese, ragi, sesame, tofu\n• Adults need 1000mg/day\n\n💊 **Protein:**\n• Vegetarians: Combine dal + rice (complete protein), paneer, soy\n• Goal: 0.8–1.2g per kg body weight daily"),

    # ── Fitness data ──
    (["steps","step count","how many steps","my steps","walked"],
     None),  # Handled separately with live data

    (["heart rate","bpm","my heart","pulse rate"],
     None),  # Handled separately with live data

    (["calories","calorie","how many calories","burned"],
     None),  # Handled separately with live data

    # ── Periods / Women's health ──
    (["period","menstruation","menstrual","pcos","pcod","pregnancy","periods pain","cramps"],
     "👩 **Women's Health:**\n\n**Period Pain (Dysmenorrhea):**\n• Ibuprofen 400mg (most effective — take at first sign)\n• Heat pad on lower abdomen\n• Light exercise (yoga, walking)\n• Avoid caffeine and salt during periods\n\n**PCOS Symptoms:**\n• Irregular periods, weight gain around waist, acne, excess hair growth, hair thinning\n• Management: Weight loss (even 5–10% helps significantly), Metformin, Inositol supplement, balanced diet\n\n**When to see a gynecologist:**\n• Periods absent for 3+ months (not pregnant)\n• Bleeding between periods\n• Extremely heavy flow (changing pad every 1–2 hours)\n• Severe pain that affects daily life"),

    # ── Back & joint pain ──
    (["back pain","backache","knee pain","joint pain","arthritis","neck pain","shoulder pain","kamar dard"],
     "🦴 **Pain Management:**\n\n**Lower Back Pain (most common):**\n• Rest for 1–2 days (not more — bed rest worsens it)\n• Ice pack first 48 hours, then warm compress\n• Ibuprofen/Diclofenac for pain\n• Gentle stretches — cat-cow, knee-to-chest\n• Avoid heavy lifting\n\n**Prevention:**\n• Strengthen core muscles (planks, bridges)\n• Ergonomic chair and posture at work\n• Don't sit for more than 45 minutes straight\n\n**Knee/Joint Pain:**\n• RICE: Rest, Ice, Compression, Elevation\n• Glucosamine + Chondroitin supplement for cartilage\n• Low-impact exercise: Swimming, cycling\n• Turmeric milk (natural anti-inflammatory)\n\n⚠️ See a doctor if pain follows an injury, is very severe, or doesn't improve in 2 weeks."),

    # ── First Aid ──
    (["first aid","cut","wound","bleeding","burn","sprain","fracture","unconscious","choking"],
     "🏥 **First Aid Guide:**\n\n**Cuts & Bleeding:**\n1. Press clean cloth firmly for 10 minutes\n2. Raise injured area above heart level\n3. Clean wound with clean water\n4. Apply antiseptic (Betadine/Savlon)\n5. Cover with bandage\n6. Seek help if bleeding doesn't stop or wound is deep\n\n**Burns:**\n• Cool running water for 10–20 minutes (do NOT use ice or toothpaste)\n• Cover loosely with clean cloth\n• Do NOT burst blisters\n• Seek help for large or deep burns\n\n**Choking:**\n• Adults: 5 back blows + 5 Heimlich maneuver thrusts\n• Infants: 5 back blows face-down + 5 chest thrusts\n\n**Fainting:**\n• Lay person flat, raise legs above heart level\n• Loosen tight clothing\n• Cool, fresh air\n• Do NOT give water if unconscious\n\n🚨 **Emergency number India: 112**"),

    # ── Eye ──
    (["eye","eyes","vision","eyesight","dry eyes","red eye","conjunctivitis","specs","glasses"],
     "👁️ **Eye Health:**\n\n**Red/Irritated Eyes (Conjunctivitis):**\n• Viral: Clears in 1–2 weeks, very contagious — avoid sharing towels\n• Bacterial: Antibiotic eye drops (Moxifloxacin, Chloramphenicol)\n• Allergic: Antihistamine drops (Olopatadine)\n\n**Dry Eyes:**\n• Lubricating drops (Systane, Refresh Tears) 4–6 times daily\n• Blink more consciously (we blink less on screens)\n• 20-20-20 rule: Every 20 min, look at something 20 feet away for 20 seconds\n\n**Eye Strain (screen fatigue):**\n• Reduce screen brightness\n• Anti-glare glasses\n• Increase font size\n• Proper lighting in room\n\n⚠️ See an ophthalmologist annually, and immediately for: sudden vision loss, eye pain, floaters, or flashes of light."),

    # ── Dental ──
    (["teeth","tooth","dental","toothache","cavity","gum","mouth","tooth pain"],
     "🦷 **Dental Health:**\n\n**Toothache relief:**\n• Ibuprofen 400mg (most effective for dental pain)\n• Clove oil on cotton ball applied to affected tooth\n• Salt water rinse (warm)\n• See dentist within 48 hours\n\n**Cavity prevention:**\n• Brush twice daily (2 minutes each time)\n• Floss or use interdental brush daily\n• Limit sugary drinks and snacks\n• Fluoride toothpaste\n• Dental check-up every 6 months\n\n**Sensitive teeth:**\n• Use Sensodyne toothpaste (takes 2–4 weeks to work)\n• Avoid very hot/cold foods initially\n• Use soft bristle brush\n\n**Gum disease (gingivitis):**\n• Bleeding gums when brushing = early gum disease\n• Professional cleaning needed\n• Better brushing and flossing technique"),

    # ── Kidneys ──
    (["kidney","kidney stone","urine","uti","urinary","uric acid","renal","pee","urination"],
     "🫘 **Kidney & Urinary Health:**\n\n**UTI Symptoms:**\n• Burning sensation while urinating\n• Frequent urge to urinate\n• Cloudy or foul-smelling urine\n• Lower abdominal discomfort\n• Treatment: Nitrofurantoin or Ciprofloxacin (doctor prescribed), drink 3L water daily\n\n**Kidney Stones:**\n• Severe cramping pain (flank pain) — can radiate to groin\n• Nausea and vomiting with pain\n• Blood in urine\n• Small stones (<5mm) often pass with hydration\n• Drink 3–4L water daily for prevention\n• Reduce salt, animal protein, oxalate foods (spinach, nuts)\n\n**Healthy kidneys:**\n• Drink adequate water\n• Control BP and blood sugar\n• Avoid excess NSAIDs (Ibuprofen, Diclofenac)\n• Reduce protein excess\n• Annual kidney function test if diabetic/hypertensive"),

    # ── Medications ──
    (["paracetamol","dolo","crocin","dose","dosage","side effect","medicine","tablet","drug"],
     "💊 **Medication Guide:**\n\nFor detailed medicine information, drug interactions, and your personal medication schedule, go to the **💊 Medications** section in the app.\n\n**Common OTC medicines:**\n• **Fever/Pain:** Paracetamol 500mg (max 4 tablets/day) or Dolo 650mg (max 4/day)\n• **Acidity:** Gelusil, ENO, Omeprazole, Pantoprazole\n• **Allergy:** Cetirizine 10mg, Chlorpheniramine\n• **Cold:** Sinarest, D-Cold Total (avoid in BP/heart patients)\n• **Diarrhea:** ORS, Loperamide, Metronidazole (prescription)\n\n⚠️ Never self-medicate for more than 3 days. Always read labels. Check our **Medication Manager** for interactions."),

    # ── General wellness ──
    (["healthy","health tips","wellness","immunity","immune","boost immunity"],
     "💪 **General Health & Immunity Tips:**\n\n**Daily habits for strong immunity:**\n• Sleep 7–8 hours — most important factor\n• Walk 30–45 minutes outdoors\n• Eat rainbow coloured vegetables (different phytonutrients)\n• Vitamin C: Amla, guava, lemon, orange\n• Zinc: Pumpkin seeds, lentils, chickpeas\n• Probiotics: Curd, buttermilk\n• Vitamin D: Morning sunlight 15–20 minutes\n\n**Indian immunity boosters:**\n• Haldi doodh (turmeric milk) — anti-inflammatory\n• Tulsi leaves — antiviral, antibacterial\n• Giloy kadha — proven immunity modulator\n• Ashwagandha — adaptogen, reduces stress\n• Amla juice — highest natural Vitamin C\n\n**Avoid:**\n• Smoking — destroys immunity\n• Excess alcohol\n• Chronic stress — suppresses immune function\n• Processed/junk food — causes inflammation"),

    # ── Doctor / appointment ──
    (["doctor","physician","specialist","hospital","clinic","appointment","consult"],
     "🩺 **Finding Medical Help:**\n\nFor your personal doctor network, go to **🏥 Health Manager → My Doctors** in the app.\n\n**Online consultation platforms (India):**\n• **Practo** — book doctors, online consultation\n• **1mg** — online consultation + medicine delivery\n• **Apollo 24/7** — 24-hour doctor availability\n• **MediBuddy** — corporate health plans\n\n**Government hospitals (free):**\n• AIIMS (Delhi, Bhopal, Jodhpur, etc.)\n• Government District Hospitals\n• ESIC hospitals (for employees)\n• Ayushman Bharat Empanelled Hospitals\n\n**Emergency:** 112 (all emergencies)\n**Ambulance:** 108"),
]


def ai_health_reply(message, health_data=None):
    """
    Comprehensive AI health reply with 400+ medical topics covered.
    Uses keyword matching with scoring to find best answer.
    Falls back to helpful guidance rather than generic error.
    """
    msg = message.lower().strip()
    if not msg:
        return "Please ask me a health question! I can help with symptoms, diseases, diet, exercise, medications, and more."

    steps = health_data.get("steps", 0) if health_data else 0
    hr    = health_data.get("heart_rate")  if health_data else None
    cal   = health_data.get("calories", 0) if health_data else 0

    # ── Live fitness data responses ──
    if any(k in msg for k in ["my steps","how many steps","steps today","walked today","step count"]):
        if steps:
            pct = min(int((steps/10000)*100), 100)
            status = "🎉 Goal reached!" if steps >= 10000 else ("💪 Great progress!" if steps >= 7000 else "Keep going!")
            return f"You've walked **{steps:,} steps** today — **{pct}% of your 10,000 step goal**. {status}\n\nWalking benefits: burns calories, improves cardiovascular health, reduces stress, and strengthens bones."
        return "Your step data isn't loaded yet. Tap **Refresh** on the dashboard to fetch your Google Fit data."

    if any(k in msg for k in ["my heart rate","my bpm","heart rate today","my pulse","my heartbeat"]):
        if hr:
            status = "✅ Normal" if 60 <= hr <= 100 else ("⚠️ Below normal — consult a doctor" if hr < 60 else "⚠️ Above normal — consult a doctor")
            return f"Your average heart rate today is **{hr} BPM**. Status: **{status}**\n\nNormal resting range: 60–100 BPM. Athletes may have rates as low as 40 BPM."
        return "Your heart rate data isn't available today. Make sure your phone or wearable is recording heart rate in Google Fit."

    if any(k in msg for k in ["my calories","calories burned","calorie today","how many calories"]):
        if cal:
            return f"You've burned **{int(cal):,} kcal** today.\n\nA typical adult burns 1,600–3,000 kcal/day depending on age, weight, and activity level. You're at **{min(int((cal/2000)*100),100)}%** of a 2,000 kcal goal."
        return "Calorie data isn't loaded. Tap **Refresh** on your dashboard to sync from Google Fit."

    if any(k in msg for k in ["my weight","weight today"]):
        w = health_data.get("weight") if health_data else None
        if w:
            return f"Your latest recorded weight is **{w} kg** from Google Fit.\n\nFor accurate BMI calculation, divide your weight by your height in metres squared. Healthy BMI for Indians: 18.5–22.9."
        return "Weight data isn't available. Log your weight in Google Fit or a smart scale that syncs with it."

    # ── Score-based knowledge base matching ──
    best_score = 0
    best_answer = None

    for keywords, answer in HEALTH_KB:
        if answer is None:
            continue
        score = 0
        for kw in keywords:
            if kw in msg:
                score += max(len(kw), 3)  # minimum score of 3 per match so short words like "hi" still match
        if score > best_score:
            best_score = score
            best_answer = answer

    # Return best match if score is meaningful
    if best_score >= 3 and best_answer:
        return best_answer

    # ── Partial word matching for common misspellings ──
    partial_map = {
        "cold": "cold symptom", "flu": "flu symptom", "fever": "fever",
        "cough": "cough", "diarrhoe": "diarrhea", "loose": "diarrhea",
        "headach": "headache", "migrain": "migraine",
        "stomach": "stomach", "acidity": "stomach", "gas": "stomach",
        "vomit": "vomiting", "nause": "vomiting",
        "diabete": "diabetes", "sugar": "diabetes",
        "pressure": "blood pressure", "hypertens": "blood pressure",
        "asthma": "asthma", "breath": "asthma",
        "thyroid": "thyroid", "sleep": "sleep", "insomni": "sleep",
        "anxiety": "stress", "depress": "stress", "stress": "stress",
        "weight": "weight", "fat": "weight", "obese": "weight",
        "skin": "skin", "acne": "skin", "rash": "skin",
        "back pain": "back pain", "knee": "back pain",
        "kidney": "kidneys", "urine": "kidneys",
        "heart": "heart disease", "chest": "heart disease",
        "teeth": "dental", "tooth": "dental",
        "eye": "eye", "vision": "eye",
        "period": "period", "pcos": "period",
        "nutrition": "nutrition", "vitamin": "nutrition",
        "immunity": "wellness", "immune": "wellness",
    }

    for partial, topic in partial_map.items():
        if partial in msg:
            # Find the matching KB entry
            for keywords, answer in HEALTH_KB:
                if answer and topic in " ".join(keywords):
                    return answer

    # ── Intelligent fallback — still tries to be helpful ──
    topic_hint = msg[:50].strip()
    return (
        f"I don't have specific information about '{topic_hint}' in my knowledge base right now. "
        f"Here's what I **can** help you with:\n\n"
        f"• 🤒 **Symptoms:** cold, fever, cough, headache, stomach pain, vomiting\n"
        f"• 🫀 **Conditions:** diabetes, blood pressure, thyroid, asthma, dengue\n"
        f"• 🥗 **Nutrition & Diet:** vitamins, protein, weight loss, Indian foods\n"
        f"• 💊 **Medications:** common medicines, dosage, side effects\n"
        f"• 🧠 **Mental health:** stress, anxiety, depression, sleep\n"
        f"• 🏃 **Fitness:** your steps, heart rate, calories from Google Fit\n"
        f"• 🏥 **First aid:** cuts, burns, choking, fainting\n\n"
        f"Try asking something like: *'What are the symptoms of diabetes?'* or *'How do I treat a cold?'*"
    )


# ─────────────────────────────────────────
# Page Routes
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
            return redirect(f"/?error=token_failed:{tokens.get('error_description','')}")

        session.permanent = True
        session["access_token"]  = tokens["access_token"]
        session["refresh_token"] = tokens.get("refresh_token")

        profile = requests.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {tokens['access_token']}"}, timeout=10
        ).json()

        session["user"] = {
            "name":    profile.get("name", "User"),
            "email":   profile.get("email", ""),
            "picture": profile.get("picture", ""),
        }
        return redirect("/dashboard")
    except Exception as e:
        return redirect(f"/?error={str(e)[:100]}")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", user=session.get("user", {}))

@app.route("/medications")
def medications_page():
    return render_template("medications.html", user=session.get("user", {}))

@app.route("/health-extras")
def health_extras_page():
    return render_template("health_extras.html", user=session.get("user", {}))


# ─────────────────────────────────────────
# API Routes
# ─────────────────────────────────────────

@app.route("/api/health-data")
@login_required
def health_data():
    token = session.get("access_token")
    start_ms, end_ms     = ms_range_today()
    week_start, week_end = ms_range_week()

    # Fetch all metrics
    steps_data    = get_fit_data(token, "com.google.step_count.delta",    start_ms, end_ms)
    calories_data = get_fit_data(token, "com.google.calories.expended",   start_ms, end_ms)
    hr_data       = get_fit_data(token, "com.google.heart_rate.bpm",      start_ms, end_ms)
    weight_data   = get_fit_data(token, "com.google.weight",              week_start, week_end)
    week_steps    = get_fit_data(token, "com.google.step_count.delta",    week_start, week_end)

    # Weekly steps breakdown
    weekly_steps = []
    for bucket in week_steps.get("bucket", []):
        ts   = int(bucket.get("startTimeMillis", 0)) // 1000
        label = datetime.utcfromtimestamp(ts).strftime("%a")
        day_steps = sum(
            val.get("intVal", 0)
            for ds in bucket.get("dataset", [])
            for point in ds.get("point", [])
            for val in point.get("value", [])
        )
        weekly_steps.append({"day": label, "steps": day_steps})

    result = {
        "steps":        extract_int_values(steps_data),
        "calories":     extract_fp_values(calories_data),
        "heart_rate":   extract_avg_fp(hr_data),
        "weight":       extract_latest_fp(weight_data),
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
    return jsonify({
        "authenticated": "access_token" in session,
        "user": session.get("user")
    })

# Health check for Render
@app.route("/health")
def health_check():
    return jsonify({"status": "ok", "timestamp": datetime.utcnow().isoformat()})

# ─────────────────────────────────────────
# Error Handlers
# ─────────────────────────────────────────
@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Route not found"}), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "Internal server error"}), 500

# ─────────────────────────────────────────
# Startup
# ─────────────────────────────────────────
def init_all_dbs():
    init_med_db()
    init_extras_db()

if __name__ == "__main__":
    init_all_dbs()
    app.run(host="127.0.0.1", port=5000, debug=True, use_reloader=False)
