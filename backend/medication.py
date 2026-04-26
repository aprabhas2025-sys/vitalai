"""
medication.py — Complete Medication Management Module
Plug this into your existing app.py using:
    from medication import medication_bp, init_med_db
    app.register_blueprint(medication_bp)
    init_med_db()
"""

import sqlite3
import os
from datetime import datetime, date, timedelta
from flask import Blueprint, request, jsonify, session

# ─────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, "medications.db")

medication_bp = Blueprint("medication", __name__)


# ─────────────────────────────────────────────────
# DB Connection
# ─────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ─────────────────────────────────────────────────
# Init DB — creates all tables + seeds Indian medicines
# ─────────────────────────────────────────────────
def init_med_db():
    conn = get_db()
    c = conn.cursor()

    # ── Master Medicine Catalogue ──
    c.execute("""
    CREATE TABLE IF NOT EXISTS medicine_catalogue (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        medicine_name       TEXT NOT NULL,
        generic_name        TEXT NOT NULL,
        brand_name          TEXT,
        dosage              TEXT,
        medicine_type       TEXT CHECK(medicine_type IN
                            ('tablet','capsule','syrup','injection','cream',
                             'drops','inhaler','powder','suspension','patch','other')),
        category            TEXT,
        usage_purpose       TEXT,
        side_effects        TEXT,
        precautions         TEXT,
        prescription_req    INTEGER DEFAULT 0,
        manufacturer        TEXT,
        ayurvedic_allopathic TEXT CHECK(ayurvedic_allopathic IN ('allopathic','ayurvedic','homeopathic','other')),
        interaction_warnings TEXT,
        storage_instructions TEXT,
        created_at          TEXT DEFAULT (datetime('now')),
        is_active           INTEGER DEFAULT 1
    )""")

    # ── User's Personal Medicine List ──
    c.execute("""
    CREATE TABLE IF NOT EXISTS user_medicines (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        catalogue_id    INTEGER REFERENCES medicine_catalogue(id),
        custom_name     TEXT,
        dosage_amount   TEXT NOT NULL,
        frequency       TEXT NOT NULL,
        times_per_day   INTEGER DEFAULT 1,
        meal_timing     TEXT CHECK(meal_timing IN ('before_meal','after_meal','with_meal','any','empty_stomach')),
        start_date      TEXT NOT NULL,
        end_date        TEXT,
        prescribed_by   TEXT,
        notes           TEXT,
        total_quantity  INTEGER,
        remaining_qty   INTEGER,
        refill_alert_at INTEGER DEFAULT 5,
        expiry_date     TEXT,
        is_active       INTEGER DEFAULT 1,
        created_at      TEXT DEFAULT (datetime('now'))
    )""")

    # ── Daily Dose Schedule ──
    c.execute("""
    CREATE TABLE IF NOT EXISTS dose_schedule (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        user_med_id     INTEGER NOT NULL REFERENCES user_medicines(id),
        scheduled_time  TEXT NOT NULL,
        dose_label      TEXT
    )""")

    # ── Dose Tracker (taken / missed) ──
    c.execute("""
    CREATE TABLE IF NOT EXISTS dose_log (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        user_med_id     INTEGER NOT NULL REFERENCES user_medicines(id),
        schedule_id     INTEGER REFERENCES dose_schedule(id),
        scheduled_date  TEXT NOT NULL,
        scheduled_time  TEXT NOT NULL,
        status          TEXT CHECK(status IN ('taken','missed','skipped')) DEFAULT 'missed',
        taken_at        TEXT,
        notes           TEXT
    )""")

    # ── Interaction pairs ──
    c.execute("""
    CREATE TABLE IF NOT EXISTS interactions (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        med_a_id    INTEGER REFERENCES medicine_catalogue(id),
        med_b_id    INTEGER REFERENCES medicine_catalogue(id),
        severity    TEXT CHECK(severity IN ('mild','moderate','severe')),
        description TEXT,
        advice      TEXT
    )""")

    # ── Prescriptions ──
    c.execute("""
    CREATE TABLE IF NOT EXISTS prescriptions (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        doctor_name     TEXT,
        hospital        TEXT,
        date_issued     TEXT,
        valid_till      TEXT,
        notes           TEXT,
        filename        TEXT,
        created_at      TEXT DEFAULT (datetime('now'))
    )""")

    conn.commit()

    # Seed if empty
    c.execute("SELECT COUNT(*) FROM medicine_catalogue")
    if c.fetchone()[0] == 0:
        _seed_medicines(c)
        _seed_interactions(c)
        conn.commit()

    conn.close()
    print("[MedDB] Database initialised at", DB_PATH)


# ─────────────────────────────────────────────────
# Seed — 30 Common Indian Medicines
# ─────────────────────────────────────────────────
def _seed_medicines(c):
    medicines = [
        # (name, generic, brand, dosage, type, category, usage, side_effects, precautions, rx_req, manufacturer, system, interactions, storage)
        ("Paracetamol 500mg","Paracetamol","Crocin / Dolo / Calpol","500mg","tablet","Analgesic / Antipyretic",
         "Fever, headache, mild to moderate pain, cold","Nausea, skin rash, liver damage (overdose)",
         "Do not exceed 4g/day. Avoid alcohol. Caution in liver disease.","No","Sun Pharma / GSK","allopathic",
         "Avoid with other paracetamol-containing medicines","Store below 30°C, away from moisture"),

        ("Dolo 650","Paracetamol","Dolo 650","650mg","tablet","Analgesic / Antipyretic",
         "High fever, body pain, post-COVID fever management","Nausea, liver toxicity in overdose",
         "Max 4 tablets/day. Avoid in severe liver disease.","No","Micro Labs","allopathic",
         "Do not combine with other paracetamol drugs","Store in cool dry place"),

        ("Azithromycin 500mg","Azithromycin","Azithral / Zithromax","500mg","tablet","Antibiotic",
         "Bacterial infections: respiratory tract, skin, ear infections","Diarrhoea, nausea, abdominal pain, QT prolongation",
         "Complete full course. Avoid antacids 2 hours before/after. Not for viral infections.","Yes","Alembic / Pfizer","allopathic",
         "Avoid with antacids, warfarin, digoxin","Store at room temperature"),

        ("Cetirizine 10mg","Cetirizine","Cetzine / Alerid","10mg","tablet","Antihistamine",
         "Allergic rhinitis, urticaria, hay fever, skin allergies","Drowsiness, dry mouth, fatigue",
         "Avoid driving. Caution in kidney disease. Avoid alcohol.","No","UCB / Dr Reddy's","allopathic",
         "Additive effect with alcohol, CNS depressants","Store below 30°C"),

        ("Pantoprazole 40mg","Pantoprazole","Pan-40 / Pantop","40mg","tablet","Proton Pump Inhibitor",
         "Acid reflux, GERD, peptic ulcer, gastritis","Headache, diarrhoea, nausea, low magnesium (long-term)",
         "Take 30 min before meals. Long-term use may affect B12 absorption.","No","Wyeth / Alkem","allopathic",
         "Reduces absorption of ketoconazole, iron, atazanavir","Store at room temperature"),

        ("ORS Sachet","Oral Rehydration Salts","Electral / ORS","1 sachet in 1L water","powder","Rehydration",
         "Diarrhoea, vomiting, dehydration, heat exhaustion","Hypernatraemia if taken in excess",
         "Prepare fresh solution each time. Use within 1 hour. Do not boil.","No","FDC / Wockhardt","allopathic",
         "None significant","Store in cool dry place"),

        ("Metformin 500mg","Metformin","Glycomet / Glucophage","500mg","tablet","Antidiabetic",
         "Type 2 diabetes, insulin resistance, PCOS","Nausea, diarrhoea, lactic acidosis (rare)",
         "Take with meals. Avoid alcohol. Stop before contrast dye procedures.","Yes","USV / Merck","allopathic",
         "Avoid with contrast agents, alcohol","Store at room temperature"),

        ("Amlodipine 5mg","Amlodipine","Amlopress / Norvasc","5mg","tablet","Calcium Channel Blocker",
         "Hypertension, angina, coronary artery disease","Ankle swelling, flushing, headache, palpitations",
         "Do not stop suddenly. Monitor BP regularly. Avoid grapefruit juice.","Yes","Pfizer / Sun Pharma","allopathic",
         "Avoid with grapefruit juice, simvastatin (high dose)","Store below 30°C"),

        ("Atorvastatin 10mg","Atorvastatin","Lipitor / Atorva","10mg","tablet","Statin / Lipid-lowering",
         "High cholesterol, cardiovascular disease prevention","Muscle pain, liver enzyme elevation, headache",
         "Avoid grapefruit juice. Report unexplained muscle pain immediately.","Yes","Pfizer / Cadila","allopathic",
         "Avoid with grapefruit, antifungals, some antibiotics","Store below 25°C"),

        ("Omeprazole 20mg","Omeprazole","Omez / Prilosec","20mg","capsule","Proton Pump Inhibitor",
         "Peptic ulcer, GERD, Zollinger-Ellison syndrome","Headache, diarrhoea, abdominal pain",
         "Take before meals. Do not crush capsule.","No","Dr Reddy's / AstraZeneca","allopathic",
         "Reduces clopidogrel effect, methotrexate levels rise","Store at room temperature"),

        ("Amoxicillin 500mg","Amoxicillin","Mox / Amoxil","500mg","capsule","Antibiotic (Penicillin)",
         "Ear, nose, throat, urinary tract, skin infections","Diarrhoea, rash, nausea, allergic reactions",
         "Check for penicillin allergy before use. Complete full course.","Yes","Ranbaxy / GSK","allopathic",
         "Avoid with methotrexate, warfarin","Store below 25°C"),

        ("Ibuprofen 400mg","Ibuprofen","Brufen / Combiflam","400mg","tablet","NSAID / Analgesic",
         "Pain, fever, inflammation, arthritis, dental pain","Stomach irritation, GI bleed, kidney damage (long-term)",
         "Take after food. Avoid in kidney disease, peptic ulcer, heart failure. Avoid in pregnancy (3rd trimester).","No","Abbott / Wockhardt","allopathic",
         "Avoid with aspirin, blood thinners, ACE inhibitors","Store below 30°C"),

        ("Aspirin 75mg","Aspirin","Ecosprin / Disprin","75mg","tablet","Antiplatelet / Analgesic",
         "Heart attack prevention, blood clot prevention, fever, pain","GI bleeding, tinnitus, Reye's syndrome in children",
         "Avoid in children under 16. Take with food. Avoid in peptic ulcer.","No","USV / Bayer","allopathic",
         "Avoid with warfarin, ibuprofen, clopidogrel (increased bleeding risk)","Store in dry place"),

        ("Montelukast 10mg","Montelukast","Montair / Singulair","10mg","tablet","Leukotriene Antagonist",
         "Asthma prevention, allergic rhinitis, exercise-induced asthma","Headache, dizziness, mood changes, abdominal pain",
         "Take in evening. Not for acute asthma attacks. Monitor for mood changes.","Yes","Sun Pharma / Merck","allopathic",
         "Phenobarbital may reduce effectiveness","Store at room temperature"),

        ("Levothyroxine 50mcg","Levothyroxine","Thyronorm / Eltroxin","50mcg","tablet","Thyroid Hormone",
         "Hypothyroidism, goitre, thyroid cancer (post-surgery)","Palpitations, insomnia, weight loss if overdosed",
         "Take on empty stomach 30 min before breakfast. Consistent timing essential.","Yes","Abbott / GSK","allopathic",
         "Avoid with calcium, iron, antacids (take 4 hrs apart)","Store away from heat and light"),

        ("Vitamin D3 60000 IU","Cholecalciferol","Calcirol / Uprise D3","60000 IU","capsule","Vitamin Supplement",
         "Vitamin D deficiency, bone health, immunity support","Hypercalcaemia if overdosed — nausea, weakness, confusion",
         "Usually taken once weekly. Take with fatty meal for best absorption.","No","Cadila / Abbott","allopathic",
         "High doses with thiazide diuretics may cause hypercalcaemia","Store below 30°C"),

        ("Iron + Folic Acid","Ferrous Sulphate + Folic Acid","Autrin / Feronia-XT","Varies","tablet","Haematinic",
         "Iron deficiency anaemia, pregnancy, weakness, fatigue","Constipation, dark stools, nausea, stomach cramps",
         "Take with Vitamin C for better absorption. Avoid tea/coffee 1 hr before/after.","No","Emcure / Cipla","allopathic",
         "Reduces absorption of levothyroxine, quinolone antibiotics","Store in dry cool place"),

        ("Ciprofloxacin 500mg","Ciprofloxacin","Cifran / Ciplox","500mg","tablet","Fluoroquinolone Antibiotic",
         "UTI, typhoid, respiratory infections, traveller's diarrhoea","Tendon rupture, QT prolongation, nausea, photosensitivity",
         "Avoid dairy products 2 hrs around dose. Use sunscreen. Complete full course.","Yes","Cipla / Bayer","allopathic",
         "Avoid with antacids, iron, dairy. Increases theophylline levels","Store at room temperature"),

        ("Ranitidine 150mg","Ranitidine","Zinetac / Rantac","150mg","tablet","H2 Blocker",
         "Acid peptic disease, GERD, gastric ulcer, heartburn","Headache, dizziness, constipation",
         "Avoid in porphyria. Antacid use may reduce absorption.","No","GSK / Zydus","allopathic",
         "May affect absorption of ketoconazole, itraconazole","Store below 25°C"),

        ("Loperamide 2mg","Loperamide","Imodium / Eldoper","2mg","capsule","Antidiarrhoeal",
         "Acute non-specific diarrhoea, traveller's diarrhoea","Constipation, abdominal cramps, nausea",
         "Do not use in bloody diarrhoea or bacterial infection. Not for children under 2.","No","Janssen / Elder Pharma","allopathic",
         "Avoid with opioids, QT-prolonging drugs","Store below 25°C"),

        ("Ashwagandha 300mg","Withania somnifera","Himalaya Ashwagandha / KSM-66","300mg","capsule","Adaptogen",
         "Stress, anxiety, fatigue, immunity boost, male fertility","Drowsiness, GI upset, thyroid changes (high doses)",
         "Avoid in pregnancy, thyroid disorders (without doctor advice), autoimmune conditions.","No","Himalaya / Dabur","ayurvedic",
         "Possible interaction with thyroid medications, sedatives","Store in cool dry place"),

        ("Triphala","Amalaki + Bibhitaki + Haritaki","Triphala Churna / Patanjali","1-2 tsp","powder","Digestive Tonic",
         "Constipation, digestive health, detoxification, eye health","Diarrhoea in high doses, abdominal cramps",
         "Take at night with warm water. Avoid in pregnancy.","No","Patanjali / Himalaya / Dabur","ayurvedic",
         "May interact with blood thinners","Store in airtight container"),

        ("Tulsi Drops","Ocimum sanctum","Himalaya Tulsi / Patanjali","10 drops in water","drops","Immunity / Respiratory",
         "Cold, cough, immunity, stress, respiratory health","Rarely — nausea in high doses",
         "Avoid with blood thinners. Not for prolonged use during pregnancy.","No","Himalaya / Patanjali","ayurvedic",
         "May potentiate anticoagulants","Store at room temperature"),

        ("Clonazepam 0.5mg","Clonazepam","Rivotril / Zapiz","0.5mg","tablet","Benzodiazepine / Anticonvulsant",
         "Epilepsy, panic disorder, anxiety disorders","Drowsiness, confusion, memory problems, dependence",
         "Do not stop abruptly. Avoid alcohol and driving. High dependency risk.","Yes","Roche / Sun Pharma","allopathic",
         "Dangerous with alcohol, opioids, other CNS depressants","Store below 25°C, away from children"),

        ("Metronidazole 400mg","Metronidazole","Flagyl / Metrogyl","400mg","tablet","Antibiotic / Antiprotozoal",
         "Amoebic dysentery, giardiasis, bacterial vaginosis, dental infections","Metallic taste, nausea, dark urine, peripheral neuropathy",
         "Absolutely avoid alcohol during and 48hrs after use. Complete full course.","Yes","Pfizer / J.B. Chemicals","allopathic",
         "Severe reaction with alcohol (disulfiram-like), potentiates warfarin","Store below 25°C"),

        ("Insulin Glargine","Insulin Glargine","Basaglar / Lantus","As prescribed","injection","Insulin / Antidiabetic",
         "Type 1 and Type 2 diabetes requiring insulin","Hypoglycaemia, injection site reactions, weight gain",
         "Monitor blood glucose. Rotate injection sites. Refrigerate. Never freeze.","Yes","Eli Lilly / Sanofi","allopathic",
         "Hypoglycaemia risk increases with alcohol, other antidiabetics, beta-blockers","Refrigerate 2-8°C, do not freeze"),

        ("Salbutamol Inhaler","Salbutamol","Asthalin / Ventolin","100mcg/puff","inhaler","Bronchodilator",
         "Asthma, COPD, bronchospasm, exercise-induced asthma","Tremors, tachycardia, headache, hypokalaemia",
         "Shake before use. Rinse mouth after use. Not a substitute for preventer inhalers.","Yes","Cipla / GSK","allopathic",
         "Avoid with beta-blockers, MAO inhibitors","Store below 30°C, protect from frost"),

        ("Losartan 50mg","Losartan","Losar / Cozaar","50mg","tablet","ARB / Antihypertensive",
         "Hypertension, diabetic nephropathy, heart failure","Dizziness, hyperkalaemia, cough (less than ACE inhibitors)",
         "Monitor potassium. Avoid in pregnancy (causes fetal harm). Avoid potassium supplements.","Yes","Merck / Cipla","allopathic",
         "Avoid with potassium supplements, NSAIDs, lithium","Store at room temperature"),

        ("Glimepiride 1mg","Glimepiride","Amaryl / Glimpid","1mg","tablet","Sulfonylurea / Antidiabetic",
         "Type 2 diabetes (with diet and exercise)","Hypoglycaemia, weight gain, nausea, dizziness",
         "Take with breakfast. Monitor blood glucose. Avoid fasting doses.","Yes","Sanofi / USV","allopathic",
         "Risk of hypoglycaemia with alcohol, other antidiabetics, NSAIDs","Store below 25°C"),

        ("Digoxin 0.25mg","Digoxin","Lanoxin","0.25mg","tablet","Cardiac Glycoside",
         "Heart failure, atrial fibrillation","Nausea, bradycardia, visual disturbances, digoxin toxicity",
         "Narrow therapeutic index. Regular blood level monitoring needed. Many interactions.","Yes","GSK / Cadila","allopathic",
         "MANY interactions: amiodarone, quinidine, verapamil, erythromycin, antacids","Store below 25°C"),
    ]

    c.executemany("""
        INSERT INTO medicine_catalogue
        (medicine_name, generic_name, brand_name, dosage, medicine_type, category,
         usage_purpose, side_effects, precautions, prescription_req, manufacturer,
         ayurvedic_allopathic, interaction_warnings, storage_instructions)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, medicines)


def _seed_interactions(c):
    # Get IDs of key medicines
    def mid(name):
        c.execute("SELECT id FROM medicine_catalogue WHERE medicine_name LIKE ?", (f"%{name}%",))
        r = c.fetchone()
        return r[0] if r else None

    paracetamol = mid("Paracetamol 500")
    dolo        = mid("Dolo 650")
    aspirin     = mid("Aspirin")
    ibuprofen   = mid("Ibuprofen")
    metformin   = mid("Metformin")
    glimepiride = mid("Glimepiride")
    losartan    = mid("Losartan")
    amlodipine  = mid("Amlodipine")
    atorvastatin= mid("Atorvastatin")
    clonazepam  = mid("Clonazepam")
    metronidazole=mid("Metronidazole")
    ciprofloxacin=mid("Ciprofloxacin")
    digoxin     = mid("Digoxin")
    insulin     = mid("Insulin")

    pairs = []
    def add(a, b, sev, desc, advice):
        if a and b:
            pairs.append((a, b, sev, desc, advice))

    add(paracetamol, dolo, "severe",
        "Both contain Paracetamol — taking together can cause liver toxicity and overdose.",
        "Never take Dolo 650 and Paracetamol 500mg together. Choose one only. Max 4g Paracetamol per day.")

    add(aspirin, ibuprofen, "moderate",
        "Both NSAIDs — increased risk of GI bleeding and stomach ulcers when combined.",
        "Avoid combination. If both needed, take ibuprofen 8 hours after aspirin. Consult doctor.")

    add(metformin, glimepiride, "moderate",
        "Combined antidiabetic effect may cause hypoglycaemia (low blood sugar).",
        "Monitor blood glucose regularly. Adjust doses under medical supervision.")

    add(clonazepam, metronidazole, "moderate",
        "Metronidazole may increase clonazepam levels, increasing sedation risk.",
        "Monitor for excessive sedation. Consult doctor before combining.")

    add(losartan, metformin, "mild",
        "Both may affect kidney function; monitor renal parameters.",
        "Regular kidney function tests recommended when used together.")

    add(atorvastatin, ciprofloxacin, "moderate",
        "Ciprofloxacin can increase atorvastatin blood levels, raising risk of muscle damage.",
        "Monitor for muscle pain/weakness. Consider temporary statin dose reduction.")

    add(digoxin, ciprofloxacin, "severe",
        "Ciprofloxacin significantly increases digoxin levels, risk of digoxin toxicity.",
        "Avoid combination if possible. If essential, closely monitor digoxin levels and heart rate.")

    add(insulin, metformin, "mild",
        "Enhanced glucose-lowering effect — risk of hypoglycaemia.",
        "This combination is intentional in diabetes management but requires careful monitoring.")

    add(aspirin, losartan, "moderate",
        "NSAIDs like aspirin can reduce the blood pressure lowering effect of losartan.",
        "Use minimum effective aspirin dose. Monitor blood pressure closely.")

    c.executemany("""
        INSERT INTO interactions (med_a_id, med_b_id, severity, description, advice)
        VALUES (?,?,?,?,?)
    """, pairs)


# ─────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────
def row_to_dict(row):
    return dict(row) if row else None

def rows_to_list(rows):
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────────
# ── CATALOGUE ROUTES ──
# ─────────────────────────────────────────────────

@medication_bp.route("/api/med/catalogue/search")
def catalogue_search():
    q = request.args.get("q", "").strip()
    med_type = request.args.get("type", "")
    system = request.args.get("system", "")

    sql = """SELECT id, medicine_name, generic_name, brand_name, dosage,
                    medicine_type, category, usage_purpose, prescription_req,
                    ayurvedic_allopathic, manufacturer
             FROM medicine_catalogue WHERE is_active=1"""
    params = []

    if q:
        sql += " AND (medicine_name LIKE ? OR generic_name LIKE ? OR brand_name LIKE ? OR usage_purpose LIKE ?)"
        like = f"%{q}%"
        params += [like, like, like, like]
    if med_type:
        sql += " AND medicine_type=?"
        params.append(med_type)
    if system:
        sql += " AND ayurvedic_allopathic=?"
        params.append(system)

    sql += " ORDER BY medicine_name LIMIT 50"

    conn = get_db()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))


@medication_bp.route("/api/med/catalogue/<int:mid>")
def catalogue_detail(mid):
    conn = get_db()
    row = conn.execute("SELECT * FROM medicine_catalogue WHERE id=?", (mid,)).fetchone()
    conn.close()
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify(row_to_dict(row))


@medication_bp.route("/api/med/catalogue", methods=["POST"])
def catalogue_add():
    d = request.get_json()
    required = ["medicine_name","generic_name","medicine_type"]
    for f in required:
        if not d.get(f):
            return jsonify({"error": f"{f} is required"}), 400

    conn = get_db()
    conn.execute("""
        INSERT INTO medicine_catalogue
        (medicine_name,generic_name,brand_name,dosage,medicine_type,category,
         usage_purpose,side_effects,precautions,prescription_req,manufacturer,
         ayurvedic_allopathic,interaction_warnings,storage_instructions)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (d.get("medicine_name"), d.get("generic_name"), d.get("brand_name"),
          d.get("dosage"), d.get("medicine_type"), d.get("category"),
          d.get("usage_purpose"), d.get("side_effects"), d.get("precautions"),
          1 if d.get("prescription_req") else 0, d.get("manufacturer"),
          d.get("ayurvedic_allopathic","allopathic"),
          d.get("interaction_warnings"), d.get("storage_instructions")))
    new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()
    conn.close()
    return jsonify({"success": True, "id": new_id})


@medication_bp.route("/api/med/catalogue/<int:mid>", methods=["PUT"])
def catalogue_edit(mid):
    d = request.get_json()
    conn = get_db()
    conn.execute("""
        UPDATE medicine_catalogue SET
        medicine_name=?,generic_name=?,brand_name=?,dosage=?,medicine_type=?,
        category=?,usage_purpose=?,side_effects=?,precautions=?,prescription_req=?,
        manufacturer=?,ayurvedic_allopathic=?,interaction_warnings=?,storage_instructions=?
        WHERE id=?
    """, (d.get("medicine_name"), d.get("generic_name"), d.get("brand_name"),
          d.get("dosage"), d.get("medicine_type"), d.get("category"),
          d.get("usage_purpose"), d.get("side_effects"), d.get("precautions"),
          1 if d.get("prescription_req") else 0, d.get("manufacturer"),
          d.get("ayurvedic_allopathic","allopathic"),
          d.get("interaction_warnings"), d.get("storage_instructions"), mid))
    conn.commit()
    conn.close()
    return jsonify({"success": True})


@medication_bp.route("/api/med/catalogue/<int:mid>", methods=["DELETE"])
def catalogue_delete(mid):
    conn = get_db()
    conn.execute("UPDATE medicine_catalogue SET is_active=0 WHERE id=?", (mid,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})


# ─────────────────────────────────────────────────
# ── USER MEDICINES ──
# ─────────────────────────────────────────────────

@medication_bp.route("/api/med/my-medicines")
def my_medicines():
    conn = get_db()
    rows = conn.execute("""
        SELECT um.*, mc.medicine_name as cat_name, mc.generic_name, mc.medicine_type,
               mc.category, mc.side_effects, mc.precautions, mc.storage_instructions
        FROM user_medicines um
        LEFT JOIN medicine_catalogue mc ON um.catalogue_id=mc.id
        WHERE um.is_active=1
        ORDER BY um.created_at DESC
    """).fetchall()
    meds = rows_to_list(rows)

    # Attach schedules
    for m in meds:
        scheds = conn.execute(
            "SELECT * FROM dose_schedule WHERE user_med_id=? ORDER BY scheduled_time",
            (m["id"],)
        ).fetchall()
        m["schedules"] = rows_to_list(scheds)

        # Refill alert
        if m.get("remaining_qty") and m.get("refill_alert_at"):
            m["refill_needed"] = m["remaining_qty"] <= m["refill_alert_at"]

        # Expiry alert
        if m.get("expiry_date"):
            try:
                exp = datetime.strptime(m["expiry_date"], "%Y-%m-%d").date()
                days_left = (exp - date.today()).days
                m["expiry_days_left"] = days_left
                m["expiry_alert"] = days_left <= 30
            except:
                pass

    conn.close()
    return jsonify(meds)


@medication_bp.route("/api/med/my-medicines", methods=["POST"])
def add_my_medicine():
    d = request.get_json()
    if not d.get("dosage_amount") or not d.get("frequency") or not d.get("start_date"):
        return jsonify({"error": "dosage_amount, frequency, start_date are required"}), 400

    conn = get_db()
    conn.execute("""
        INSERT INTO user_medicines
        (catalogue_id,custom_name,dosage_amount,frequency,times_per_day,
         meal_timing,start_date,end_date,prescribed_by,notes,
         total_quantity,remaining_qty,refill_alert_at,expiry_date)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (d.get("catalogue_id"), d.get("custom_name"), d["dosage_amount"],
          d["frequency"], d.get("times_per_day", 1), d.get("meal_timing","any"),
          d["start_date"], d.get("end_date"), d.get("prescribed_by"),
          d.get("notes"), d.get("total_quantity"), d.get("total_quantity"),
          d.get("refill_alert_at", 5), d.get("expiry_date")))

    user_med_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    # Insert schedule slots
    times = d.get("schedule_times", [])
    for i, t in enumerate(times):
        label = ["Morning","Afternoon","Evening","Night","Before Bed"][i] if i < 5 else f"Dose {i+1}"
        conn.execute(
            "INSERT INTO dose_schedule (user_med_id, scheduled_time, dose_label) VALUES (?,?,?)",
            (user_med_id, t, label)
        )

    conn.commit()
    conn.close()
    return jsonify({"success": True, "id": user_med_id})


@medication_bp.route("/api/med/my-medicines/<int:mid>", methods=["PUT"])
def edit_my_medicine(mid):
    d = request.get_json()
    conn = get_db()
    conn.execute("""
        UPDATE user_medicines SET
        custom_name=?,dosage_amount=?,frequency=?,times_per_day=?,meal_timing=?,
        start_date=?,end_date=?,prescribed_by=?,notes=?,
        total_quantity=?,remaining_qty=?,refill_alert_at=?,expiry_date=?
        WHERE id=?
    """, (d.get("custom_name"), d.get("dosage_amount"), d.get("frequency"),
          d.get("times_per_day",1), d.get("meal_timing","any"),
          d.get("start_date"), d.get("end_date"), d.get("prescribed_by"),
          d.get("notes"), d.get("total_quantity"), d.get("remaining_qty"),
          d.get("refill_alert_at",5), d.get("expiry_date"), mid))
    conn.commit()
    conn.close()
    return jsonify({"success": True})


@medication_bp.route("/api/med/my-medicines/<int:mid>", methods=["DELETE"])
def delete_my_medicine(mid):
    conn = get_db()
    conn.execute("UPDATE user_medicines SET is_active=0 WHERE id=?", (mid,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})


# ─────────────────────────────────────────────────
# ── DOSE TRACKER ──
# ─────────────────────────────────────────────────

@medication_bp.route("/api/med/today")
def today_doses():
    today = date.today().isoformat()
    conn = get_db()

    # Get all active medicines with schedules
    meds = conn.execute("""
        SELECT um.id as user_med_id,
               COALESCE(um.custom_name, mc.medicine_name) as medicine_name,
               um.dosage_amount, um.meal_timing, mc.medicine_type,
               ds.id as schedule_id, ds.scheduled_time, ds.dose_label
        FROM user_medicines um
        LEFT JOIN medicine_catalogue mc ON um.catalogue_id=mc.id
        JOIN dose_schedule ds ON ds.user_med_id=um.id
        WHERE um.is_active=1
          AND (um.end_date IS NULL OR um.end_date >= ?)
          AND um.start_date <= ?
        ORDER BY ds.scheduled_time
    """, (today, today)).fetchall()

    result = []
    for m in meds:
        m_dict = dict(m)
        # Check if logged for today
        log = conn.execute("""
            SELECT * FROM dose_log
            WHERE user_med_id=? AND schedule_id=? AND scheduled_date=?
        """, (m["user_med_id"], m["schedule_id"], today)).fetchone()
        m_dict["log"] = row_to_dict(log)
        m_dict["status"] = log["status"] if log else "pending"
        result.append(m_dict)

    conn.close()
    return jsonify(result)


@medication_bp.route("/api/med/log", methods=["POST"])
def log_dose():
    d = request.get_json()
    required = ["user_med_id","schedule_id","scheduled_date","scheduled_time","status"]
    for f in required:
        if not d.get(f):
            return jsonify({"error": f"{f} required"}), 400

    conn = get_db()
    # Upsert
    existing = conn.execute("""
        SELECT id FROM dose_log
        WHERE user_med_id=? AND schedule_id=? AND scheduled_date=?
    """, (d["user_med_id"], d["schedule_id"], d["scheduled_date"])).fetchone()

    taken_at = datetime.now().isoformat() if d["status"] == "taken" else None

    if existing:
        conn.execute("""
            UPDATE dose_log SET status=?, taken_at=?, notes=? WHERE id=?
        """, (d["status"], taken_at, d.get("notes"), existing["id"]))
    else:
        conn.execute("""
            INSERT INTO dose_log (user_med_id,schedule_id,scheduled_date,scheduled_time,status,taken_at,notes)
            VALUES (?,?,?,?,?,?,?)
        """, (d["user_med_id"], d["schedule_id"], d["scheduled_date"],
              d["scheduled_time"], d["status"], taken_at, d.get("notes")))

    # Decrease quantity if taken
    if d["status"] == "taken":
        conn.execute("""
            UPDATE user_medicines SET remaining_qty = MAX(0, remaining_qty-1)
            WHERE id=? AND remaining_qty IS NOT NULL
        """, (d["user_med_id"],))

    conn.commit()
    conn.close()
    return jsonify({"success": True})


@medication_bp.route("/api/med/history")
def dose_history():
    days = int(request.args.get("days", 7))
    since = (date.today() - timedelta(days=days)).isoformat()

    conn = get_db()
    rows = conn.execute("""
        SELECT dl.*, COALESCE(um.custom_name, mc.medicine_name) as medicine_name,
               ds.dose_label
        FROM dose_log dl
        JOIN user_medicines um ON dl.user_med_id=um.id
        LEFT JOIN medicine_catalogue mc ON um.catalogue_id=mc.id
        LEFT JOIN dose_schedule ds ON dl.schedule_id=ds.id
        WHERE dl.scheduled_date >= ?
        ORDER BY dl.scheduled_date DESC, dl.scheduled_time
    """, (since,)).fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))


@medication_bp.route("/api/med/adherence")
def adherence():
    days = int(request.args.get("days", 30))
    since = (date.today() - timedelta(days=days)).isoformat()

    conn = get_db()
    rows = conn.execute("""
        SELECT status, COUNT(*) as count FROM dose_log
        WHERE scheduled_date >= ? GROUP BY status
    """, (since,)).fetchall()

    stats = {"taken": 0, "missed": 0, "skipped": 0, "total": 0, "percentage": 0}
    for r in rows:
        stats[r["status"]] = r["count"]

    stats["total"] = stats["taken"] + stats["missed"] + stats["skipped"]
    if stats["total"] > 0:
        stats["percentage"] = round((stats["taken"] / stats["total"]) * 100, 1)

    # Per-medicine breakdown
    med_rows = conn.execute("""
        SELECT COALESCE(um.custom_name, mc.medicine_name) as name,
               SUM(CASE WHEN dl.status='taken' THEN 1 ELSE 0 END) as taken,
               SUM(CASE WHEN dl.status='missed' THEN 1 ELSE 0 END) as missed,
               COUNT(*) as total
        FROM dose_log dl
        JOIN user_medicines um ON dl.user_med_id=um.id
        LEFT JOIN medicine_catalogue mc ON um.catalogue_id=mc.id
        WHERE dl.scheduled_date >= ?
        GROUP BY dl.user_med_id
    """, (since,)).fetchall()

    stats["by_medicine"] = rows_to_list(med_rows)
    conn.close()
    return jsonify(stats)


# ─────────────────────────────────────────────────
# ── INTERACTION CHECKER ──
# ─────────────────────────────────────────────────

@medication_bp.route("/api/med/interactions", methods=["POST"])
def check_interactions():
    d = request.get_json()
    ids = d.get("medicine_ids", [])

    if len(ids) < 2:
        return jsonify({"interactions": [], "message": "Select at least 2 medicines to check."})

    conn = get_db()
    results = []
    for i in range(len(ids)):
        for j in range(i+1, len(ids)):
            a, b = ids[i], ids[j]
            row = conn.execute("""
                SELECT i.*, ma.medicine_name as med_a_name, mb.medicine_name as med_b_name
                FROM interactions i
                JOIN medicine_catalogue ma ON i.med_a_id=ma.id
                JOIN medicine_catalogue mb ON i.med_b_id=mb.id
                WHERE (i.med_a_id=? AND i.med_b_id=?) OR (i.med_a_id=? AND i.med_b_id=?)
            """, (a, b, b, a)).fetchone()
            if row:
                results.append(row_to_dict(row))

    conn.close()
    return jsonify({
        "interactions": results,
        "count": len(results),
        "has_severe": any(r["severity"] == "severe" for r in results)
    })


# ─────────────────────────────────────────────────
# ── HEALTH REPORT ──
# ─────────────────────────────────────────────────

@medication_bp.route("/api/med/report")
def medication_report():
    conn = get_db()

    # Active medicines
    meds = conn.execute("""
        SELECT COALESCE(um.custom_name, mc.medicine_name) as name,
               um.dosage_amount, um.frequency, um.meal_timing,
               um.start_date, um.end_date, um.prescribed_by,
               um.expiry_date, um.remaining_qty,
               mc.medicine_type, mc.category
        FROM user_medicines um
        LEFT JOIN medicine_catalogue mc ON um.catalogue_id=mc.id
        WHERE um.is_active=1
    """).fetchall()

    # 30-day adherence
    since = (date.today() - timedelta(days=30)).isoformat()
    logs = conn.execute("""
        SELECT status, COUNT(*) as c FROM dose_log
        WHERE scheduled_date >= ? GROUP BY status
    """, (since,)).fetchall()

    taken = sum(r["c"] for r in logs if r["status"]=="taken")
    total = sum(r["c"] for r in logs)
    pct = round((taken/total)*100, 1) if total > 0 else 0

    # Alerts
    refill_alerts = conn.execute("""
        SELECT COALESCE(um.custom_name, mc.medicine_name) as name, um.remaining_qty
        FROM user_medicines um
        LEFT JOIN medicine_catalogue mc ON um.catalogue_id=mc.id
        WHERE um.is_active=1 AND um.remaining_qty IS NOT NULL
          AND um.remaining_qty <= um.refill_alert_at
    """).fetchall()

    expiry_alerts = conn.execute("""
        SELECT COALESCE(um.custom_name, mc.medicine_name) as name, um.expiry_date
        FROM user_medicines um
        LEFT JOIN medicine_catalogue mc ON um.catalogue_id=mc.id
        WHERE um.is_active=1 AND um.expiry_date IS NOT NULL
          AND julianday(um.expiry_date) - julianday('now') <= 30
    """).fetchall()

    conn.close()
    return jsonify({
        "generated_at": datetime.now().strftime("%d %b %Y, %I:%M %p"),
        "active_medicines": rows_to_list(meds),
        "adherence": {"taken": taken, "total": total, "percentage": pct},
        "refill_alerts": rows_to_list(refill_alerts),
        "expiry_alerts": rows_to_list(expiry_alerts),
    })


# ─────────────────────────────────────────────────
# ── ALERTS ──
# ─────────────────────────────────────────────────

@medication_bp.route("/api/med/alerts")
def alerts():
    conn = get_db()
    result = {"refill": [], "expiry": [], "missed_today": []}

    # Refill
    rows = conn.execute("""
        SELECT COALESCE(um.custom_name, mc.medicine_name) as name,
               um.remaining_qty, um.refill_alert_at
        FROM user_medicines um
        LEFT JOIN medicine_catalogue mc ON um.catalogue_id=mc.id
        WHERE um.is_active=1 AND um.remaining_qty IS NOT NULL
          AND um.remaining_qty <= um.refill_alert_at
    """).fetchall()
    result["refill"] = rows_to_list(rows)

    # Expiry
    rows = conn.execute("""
        SELECT COALESCE(um.custom_name, mc.medicine_name) as name,
               um.expiry_date,
               CAST(julianday(um.expiry_date) - julianday('now') AS INTEGER) as days_left
        FROM user_medicines um
        LEFT JOIN medicine_catalogue mc ON um.catalogue_id=mc.id
        WHERE um.is_active=1 AND um.expiry_date IS NOT NULL
          AND julianday(um.expiry_date) - julianday('now') <= 30
    """).fetchall()
    result["expiry"] = rows_to_list(rows)

    # Missed today
    today = date.today().isoformat()
    rows = conn.execute("""
        SELECT COALESCE(um.custom_name, mc.medicine_name) as name,
               ds.scheduled_time, ds.dose_label
        FROM user_medicines um
        LEFT JOIN medicine_catalogue mc ON um.catalogue_id=mc.id
        JOIN dose_schedule ds ON ds.user_med_id=um.id
        WHERE um.is_active=1
          AND NOT EXISTS (
              SELECT 1 FROM dose_log dl
              WHERE dl.user_med_id=um.id AND dl.schedule_id=ds.id
                AND dl.scheduled_date=? AND dl.status='taken'
          )
          AND ds.scheduled_time < time('now','+5:30')
          AND (um.end_date IS NULL OR um.end_date >= ?)
    """, (today, today)).fetchall()
    result["missed_today"] = rows_to_list(rows)

    conn.close()
    return jsonify(result)
