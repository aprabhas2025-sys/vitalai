"""
extras.py — Additional modules:
- Indian Dietary Recommendations & Nutrition Tracking
- Indian Health Insurance & Medical History
- Regional Doctor Networks & Local Health Preferences
- Family Health Monitoring & Caregiver Notifications
- 1mg / Practo Integration (smart redirects + local data)
"""

import sqlite3
import os
import json
from datetime import datetime, date, timedelta
from flask import Blueprint, request, jsonify, session

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, "extras.db")

extras_bp = Blueprint("extras", __name__)

# ─────────────────────────────────────────
# DB Connection
# ─────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def rows_to_list(rows): return [dict(r) for r in rows]
def row_to_dict(row):   return dict(row) if row else None

# ─────────────────────────────────────────
# Init DB
# ─────────────────────────────────────────
def init_extras_db():
    conn = get_db()
    c = conn.cursor()

    # ── Nutrition Log ──
    c.execute("""CREATE TABLE IF NOT EXISTS nutrition_log (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        log_date    TEXT NOT NULL,
        meal_type   TEXT CHECK(meal_type IN ('breakfast','lunch','dinner','snack','other')),
        food_name   TEXT NOT NULL,
        quantity    REAL DEFAULT 1,
        unit        TEXT DEFAULT 'serving',
        calories    REAL DEFAULT 0,
        protein_g   REAL DEFAULT 0,
        carbs_g     REAL DEFAULT 0,
        fat_g       REAL DEFAULT 0,
        fiber_g     REAL DEFAULT 0,
        notes       TEXT,
        created_at  TEXT DEFAULT (datetime('now'))
    )""")

    # ── Wellness Goals ──
    c.execute("""CREATE TABLE IF NOT EXISTS wellness_goals (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        goal_type   TEXT NOT NULL,
        goal_name   TEXT NOT NULL,
        target      REAL NOT NULL,
        current     REAL DEFAULT 0,
        unit        TEXT,
        deadline    TEXT,
        status      TEXT DEFAULT 'active',
        created_at  TEXT DEFAULT (datetime('now'))
    )""")

    # ── Medical History ──
    c.execute("""CREATE TABLE IF NOT EXISTS medical_history (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        record_type     TEXT CHECK(record_type IN ('condition','surgery','allergy','vaccination','test','hospitalization','other')),
        title           TEXT NOT NULL,
        description     TEXT,
        date_occurred   TEXT,
        doctor_name     TEXT,
        hospital        TEXT,
        severity        TEXT CHECK(severity IN ('mild','moderate','severe','resolved')),
        is_ongoing      INTEGER DEFAULT 0,
        created_at      TEXT DEFAULT (datetime('now'))
    )""")

    # ── Insurance Records ──
    c.execute("""CREATE TABLE IF NOT EXISTS insurance_records (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        provider_name   TEXT NOT NULL,
        policy_number   TEXT,
        policy_type     TEXT,
        sum_insured     REAL,
        premium_amount  REAL,
        premium_freq    TEXT,
        start_date      TEXT,
        expiry_date     TEXT,
        nominee_name    TEXT,
        contact_number  TEXT,
        cashless_hospitals TEXT,
        notes           TEXT,
        created_at      TEXT DEFAULT (datetime('now'))
    )""")

    # ── Family Members ──
    c.execute("""CREATE TABLE IF NOT EXISTS family_members (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT NOT NULL,
        relation    TEXT NOT NULL,
        age         INTEGER,
        blood_group TEXT,
        phone       TEXT,
        conditions  TEXT,
        medicines   TEXT,
        notes       TEXT,
        created_at  TEXT DEFAULT (datetime('now'))
    )""")

    # ── Family Health Logs ──
    c.execute("""CREATE TABLE IF NOT EXISTS family_health_logs (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        member_id   INTEGER REFERENCES family_members(id),
        log_date    TEXT NOT NULL,
        log_type    TEXT,
        value       TEXT,
        notes       TEXT,
        created_at  TEXT DEFAULT (datetime('now'))
    )""")

    # ── Doctor Network ──
    c.execute("""CREATE TABLE IF NOT EXISTS my_doctors (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT NOT NULL,
        specialty   TEXT,
        hospital    TEXT,
        city        TEXT,
        phone       TEXT,
        email       TEXT,
        address     TEXT,
        rating      REAL,
        notes       TEXT,
        is_primary  INTEGER DEFAULT 0,
        created_at  TEXT DEFAULT (datetime('now'))
    )""")

    # ── Health Preferences ──
    c.execute("""CREATE TABLE IF NOT EXISTS health_preferences (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        pref_key    TEXT UNIQUE NOT NULL,
        pref_value  TEXT NOT NULL,
        updated_at  TEXT DEFAULT (datetime('now'))
    )""")

    conn.commit()

    # Seed default preferences
    c.execute("SELECT COUNT(*) FROM health_preferences")
    if c.fetchone()[0] == 0:
        _seed_preferences(c)
        conn.commit()

    conn.close()
    print("[ExtrasDB] Database initialised at", DB_PATH)


def _seed_preferences(c):
    defaults = [
        ("diet_type", "vegetarian"),
        ("state", "Karnataka"),
        ("city", "Bengaluru"),
        ("language", "English"),
        ("religion_diet", "none"),
        ("calorie_goal", "2000"),
        ("water_goal", "3"),
        ("weight_goal", "75"),
        ("blood_group", ""),
        ("allergies", ""),
    ]
    c.executemany("INSERT OR IGNORE INTO health_preferences (pref_key, pref_value) VALUES (?,?)", defaults)


# ════════════════════════════════════════════
# ── NUTRITION ROUTES ──
# ════════════════════════════════════════════

# Indian food database — 60 common Indian foods with nutrition
INDIAN_FOODS = [
    {"name":"Idli (1 piece)","calories":39,"protein":1.8,"carbs":8,"fat":0.2,"fiber":0.5,"category":"South Indian","meal_type":"breakfast"},
    {"name":"Dosa (plain, 1 medium)","calories":120,"protein":3,"carbs":20,"fat":3,"fiber":1,"category":"South Indian","meal_type":"breakfast"},
    {"name":"Masala Dosa","calories":210,"protein":5,"carbs":30,"fat":7,"fiber":2,"category":"South Indian","meal_type":"breakfast"},
    {"name":"Upma (1 cup)","calories":177,"protein":4.5,"carbs":28,"fat":5,"fiber":2,"category":"South Indian","meal_type":"breakfast"},
    {"name":"Poha (1 cup)","calories":158,"protein":3,"carbs":30,"fat":3,"fiber":2,"category":"Maharashtra","meal_type":"breakfast"},
    {"name":"Paratha (1 plain)","calories":200,"protein":4,"carbs":28,"fat":8,"fiber":2,"category":"North Indian","meal_type":"breakfast"},
    {"name":"Aloo Paratha","calories":280,"protein":6,"carbs":35,"fat":12,"fiber":3,"category":"North Indian","meal_type":"breakfast"},
    {"name":"Roti / Chapati (1)","calories":71,"protein":2.7,"carbs":15,"fat":0.4,"fiber":2.7,"category":"North Indian","meal_type":"lunch"},
    {"name":"Dal Tadka (1 cup)","calories":170,"protein":10,"carbs":25,"fat":4,"fiber":6,"category":"North Indian","meal_type":"lunch"},
    {"name":"Dal Makhani (1 cup)","calories":220,"protein":11,"carbs":28,"fat":7,"fiber":7,"category":"North Indian","meal_type":"lunch"},
    {"name":"Paneer Butter Masala (1 cup)","calories":340,"protein":14,"carbs":15,"fat":25,"fiber":2,"category":"North Indian","meal_type":"lunch"},
    {"name":"Chole (1 cup)","calories":210,"protein":12,"carbs":32,"fat":4,"fiber":10,"category":"North Indian","meal_type":"lunch"},
    {"name":"Rajma (1 cup)","calories":220,"protein":13,"carbs":35,"fat":1,"fiber":11,"category":"North Indian","meal_type":"lunch"},
    {"name":"Palak Paneer (1 cup)","calories":250,"protein":12,"carbs":10,"fat":18,"fiber":3,"category":"North Indian","meal_type":"lunch"},
    {"name":"Rice (1 cup cooked)","calories":206,"protein":4.3,"carbs":45,"fat":0.4,"fiber":0.6,"category":"Staple","meal_type":"lunch"},
    {"name":"Brown Rice (1 cup cooked)","calories":216,"protein":5,"carbs":45,"fat":1.8,"fiber":3.5,"category":"Staple","meal_type":"lunch"},
    {"name":"Biryani Veg (1 plate)","calories":380,"protein":9,"carbs":60,"fat":11,"fiber":4,"category":"Hyderabadi","meal_type":"lunch"},
    {"name":"Chicken Biryani (1 plate)","calories":480,"protein":28,"carbs":55,"fat":14,"fiber":3,"category":"Hyderabadi","meal_type":"lunch"},
    {"name":"Sambar (1 cup)","calories":97,"protein":4.5,"carbs":16,"fat":2,"fiber":5,"category":"South Indian","meal_type":"lunch"},
    {"name":"Rasam (1 cup)","calories":45,"protein":1.5,"carbs":8,"fat":1,"fiber":1.5,"category":"South Indian","meal_type":"lunch"},
    {"name":"Curd Rice (1 cup)","calories":180,"protein":6,"carbs":30,"fat":4,"fiber":0.5,"category":"South Indian","meal_type":"lunch"},
    {"name":"Pav Bhaji (1 plate)","calories":350,"protein":8,"carbs":50,"fat":12,"fiber":6,"category":"Mumbai Street Food","meal_type":"lunch"},
    {"name":"Vada Pav","calories":290,"protein":6,"carbs":42,"fat":10,"fiber":3,"category":"Mumbai Street Food","meal_type":"snack"},
    {"name":"Samosa (1 piece)","calories":130,"protein":3,"carbs":17,"fat":6,"fiber":2,"category":"Snack","meal_type":"snack"},
    {"name":"Dhokla (2 pieces)","calories":160,"protein":6,"carbs":26,"fat":3,"fiber":1.5,"category":"Gujarat","meal_type":"snack"},
    {"name":"Khichdi (1 cup)","calories":210,"protein":8,"carbs":38,"fat":3,"fiber":4,"category":"Comfort Food","meal_type":"dinner"},
    {"name":"Egg Bhurji (2 eggs)","calories":200,"protein":14,"carbs":4,"fat":14,"fiber":0.5,"category":"Egg","meal_type":"breakfast"},
    {"name":"Boiled Egg (1)","calories":78,"protein":6,"carbs":0.6,"fat":5,"fiber":0,"category":"Egg","meal_type":"breakfast"},
    {"name":"Chicken Curry (1 cup)","calories":300,"protein":25,"carbs":8,"fat":18,"fiber":2,"category":"Non-Veg","meal_type":"dinner"},
    {"name":"Fish Curry (1 cup)","calories":250,"protein":28,"carbs":6,"fat":12,"fiber":1,"category":"Non-Veg","meal_type":"dinner"},
    {"name":"Dahi / Curd (1 cup)","calories":61,"protein":3.5,"carbs":4.7,"fat":3.3,"fiber":0,"category":"Dairy","meal_type":"snack"},
    {"name":"Lassi (1 glass sweet)","calories":180,"protein":6,"carbs":28,"fat":5,"fiber":0,"category":"Dairy","meal_type":"snack"},
    {"name":"Chai with milk (1 cup)","calories":50,"protein":2,"carbs":6,"fat":2,"fiber":0,"category":"Beverage","meal_type":"snack"},
    {"name":"Banana (1 medium)","calories":89,"protein":1.1,"carbs":23,"fat":0.3,"fiber":2.6,"category":"Fruit","meal_type":"snack"},
    {"name":"Mango (1 cup)","calories":99,"protein":1.4,"carbs":25,"fat":0.6,"fiber":2.6,"category":"Fruit","meal_type":"snack"},
    {"name":"Papaya (1 cup)","calories":55,"protein":0.9,"carbs":14,"fat":0.3,"fiber":2.5,"category":"Fruit","meal_type":"snack"},
    {"name":"Guava (1 medium)","calories":68,"protein":2.6,"carbs":14,"fat":1,"fiber":5.4,"category":"Fruit","meal_type":"snack"},
    {"name":"Moong Dal Soup (1 cup)","calories":104,"protein":7,"carbs":18,"fat":0.5,"fiber":4,"category":"Healthy","meal_type":"dinner"},
    {"name":"Vegetable Pulao (1 cup)","calories":220,"protein":5,"carbs":40,"fat":5,"fiber":3,"category":"Rice","meal_type":"lunch"},
    {"name":"Aloo Sabzi (1 cup)","calories":150,"protein":3,"carbs":25,"fat":4,"fiber":3,"category":"Vegetable","meal_type":"lunch"},
    {"name":"Bhindi Masala (1 cup)","calories":110,"protein":3,"carbs":12,"fat":5,"fiber":4,"category":"Vegetable","meal_type":"lunch"},
    {"name":"Mixed Veg Curry (1 cup)","calories":130,"protein":4,"carbs":18,"fat":5,"fiber":4,"category":"Vegetable","meal_type":"dinner"},
    {"name":"Sprouts Salad (1 cup)","calories":80,"protein":6,"carbs":12,"fat":0.5,"fiber":4,"category":"Healthy","meal_type":"breakfast"},
    {"name":"Peanuts (30g)","calories":170,"protein":7.5,"carbs":5,"fat":14,"fiber":2.5,"category":"Snack","meal_type":"snack"},
    {"name":"Roasted Chana (30g)","calories":110,"protein":7,"carbs":16,"fat":2,"fiber":4,"category":"Snack","meal_type":"snack"},
    {"name":"Chicken (raw, 100g)","calories":165,"protein":31,"carbs":0,"fat":3.6,"fiber":0,"category":"Non-Veg","meal_type":"other"},
    {"name":"Chicken (boiled, 100g)","calories":165,"protein":31,"carbs":0,"fat":3.6,"fiber":0,"category":"Non-Veg","meal_type":"other"},
    {"name":"Chicken (grilled, 100g)","calories":195,"protein":29,"carbs":0,"fat":8,"fiber":0,"category":"Non-Veg","meal_type":"other"},
    {"name":"Chicken Tandoori (1 piece)","calories":165,"protein":25,"carbs":4,"fat":5,"fiber":0.5,"category":"Non-Veg","meal_type":"dinner"},
    {"name":"Chicken Tikka (6 pieces)","calories":220,"protein":28,"carbs":5,"fat":10,"fiber":0.5,"category":"Non-Veg","meal_type":"dinner"},
    {"name":"Mutton Curry (1 cup)","calories":350,"protein":26,"carbs":6,"fat":24,"fiber":1,"category":"Non-Veg","meal_type":"dinner"},
    {"name":"Egg White (1)","calories":17,"protein":3.6,"carbs":0.2,"fat":0.1,"fiber":0,"category":"Egg","meal_type":"breakfast"},
    {"name":"Omelette (2 eggs)","calories":190,"protein":13,"carbs":1,"fat":15,"fiber":0,"category":"Egg","meal_type":"breakfast"},
    {"name":"Paneer (100g)","calories":265,"protein":18,"carbs":1.2,"fat":20,"fiber":0,"category":"Dairy","meal_type":"other"},
    {"name":"Milk (1 glass, full fat)","calories":149,"protein":8,"carbs":12,"fat":8,"fiber":0,"category":"Dairy","meal_type":"breakfast"},
    {"name":"Almonds (30g)","calories":173,"protein":6,"carbs":6,"fat":15,"fiber":3.5,"category":"Dry Fruits","meal_type":"snack"},
    {"name":"Walnuts (30g)","calories":196,"protein":5,"carbs":4,"fat":20,"fiber":2,"category":"Dry Fruits","meal_type":"snack"},
    {"name":"Cashews (30g)","calories":163,"protein":5,"carbs":9,"fat":13,"fiber":1,"category":"Dry Fruits","meal_type":"snack"},
    {"name":"Dates (2 pieces)","calories":56,"protein":0.4,"carbs":15,"fat":0.1,"fiber":1.6,"category":"Dry Fruits","meal_type":"snack"},
    {"name":"Ragi Mudde (1 ball)","calories":180,"protein":3.5,"carbs":38,"fat":1,"fiber":3.6,"category":"South Indian","meal_type":"dinner"},
    {"name":"Pesarattu (2 pieces)","calories":170,"protein":9,"carbs":26,"fat":3,"fiber":3,"category":"South Indian","meal_type":"breakfast"},
    {"name":"Uttapam (1 medium)","calories":175,"protein":5,"carbs":28,"fat":4,"fiber":2,"category":"South Indian","meal_type":"breakfast"},
    {"name":"Medu Vada (1 piece)","calories":130,"protein":4,"carbs":14,"fat":7,"fiber":2,"category":"South Indian","meal_type":"breakfast"},
    {"name":"Mysore Pak (1 piece)","calories":180,"protein":3,"carbs":20,"fat":10,"fiber":0.5,"category":"Dessert","meal_type":"snack"},
    {"name":"Gajar Halwa (1 cup)","calories":310,"protein":6,"carbs":42,"fat":13,"fiber":3,"category":"Dessert","meal_type":"snack"},
    {"name":"Bread (white, 2 slices)","calories":160,"protein":5,"carbs":30,"fat":2,"fiber":1.4,"category":"Bakery","meal_type":"breakfast"},
    {"name":"Bread (brown, 2 slices)","calories":140,"protein":6,"carbs":26,"fat":2,"fiber":4,"category":"Bakery","meal_type":"breakfast"},
    {"name":"Corn (1 cup boiled)","calories":132,"protein":5,"carbs":29,"fat":2,"fiber":3.6,"category":"Vegetable","meal_type":"snack"},
    {"name":"Sweet Potato (1 medium)","calories":103,"protein":2.3,"carbs":24,"fat":0.1,"fiber":3.8,"category":"Vegetable","meal_type":"other"},
    {"name":"Green Peas (1 cup)","calories":118,"protein":8,"carbs":21,"fat":0.6,"fiber":7.4,"category":"Vegetable","meal_type":"other"},
    {"name":"Spinach Dal (1 cup)","calories":150,"protein":9,"carbs":22,"fat":3,"fiber":6,"category":"Healthy","meal_type":"lunch"},
    {"name":"Tofu Bhurji (1 cup)","calories":160,"protein":14,"carbs":5,"fat":9,"fiber":2,"category":"Healthy","meal_type":"breakfast"},
    {"name":"Quinoa (1 cup cooked)","calories":222,"protein":8,"carbs":39,"fat":4,"fiber":5,"category":"Healthy","meal_type":"lunch"},
    {"name":"Greek Yogurt (1 cup)","calories":100,"protein":17,"carbs":6,"fat":0.7,"fiber":0,"category":"Dairy","meal_type":"snack"},
    {"name":"Nimbu Pani (1 glass)","calories":29,"protein":0.4,"carbs":7,"fat":0,"fiber":0.4,"category":"Beverage","meal_type":"other"},
    {"name":"Coconut Water (1 glass)","calories":46,"protein":1.7,"carbs":9,"fat":0.5,"fiber":2.6,"category":"Beverage","meal_type":"other"},
    {"name":"Amla Juice (1 glass)","calories":30,"protein":0.5,"carbs":7,"fat":0,"fiber":1,"category":"Beverage","meal_type":"other"},
    {"name":"Coconut Chutney (2 tbsp)","calories":60,"protein":1,"carbs":3,"fat":5,"fiber":1.5,"category":"Condiment","meal_type":"snack"},
    {"name":"Pickle (1 tsp)","calories":15,"protein":0.2,"carbs":2,"fat":1,"fiber":0.5,"category":"Condiment","meal_type":"snack"},
    {"name":"Halwa (1 cup)","calories":380,"protein":5,"carbs":50,"fat":18,"fiber":1,"category":"Dessert","meal_type":"snack"},
    {"name":"Kheer (1 cup)","calories":230,"protein":6,"carbs":38,"fat":7,"fiber":0.5,"category":"Dessert","meal_type":"snack"},
]

@extras_bp.route("/api/nutrition/foods/search")
def search_foods():
    q = request.args.get("q","").lower().strip()
    category = request.args.get("category","")
    
    if not q:
        # Return all foods if no query
        results = INDIAN_FOODS if not category else [f for f in INDIAN_FOODS if f.get("meal_type","")==category]
        return jsonify(results[:30])
    
    # Split query into words for smarter matching
    query_words = q.split()
    scored = []
    for f in INDIAN_FOODS:
        search_text = (f["name"] + " " + f["category"] + " " + f.get("meal_type","")).lower()
        # Score: how many query words match
        score = sum(1 for word in query_words if word in search_text)
        if score > 0:
            # Bonus score for exact match at start
            if q in search_text:
                score += 2
            scored.append((score, f))
    
    # Sort by score descending
    scored.sort(key=lambda x: x[0], reverse=True)
    results = [f for _, f in scored]
    
    if category:
        results = [f for f in results if f.get("meal_type","") == category]
    
    return jsonify(results[:30])

@extras_bp.route("/api/nutrition/log", methods=["POST"])
def add_nutrition_log():
    d = request.get_json()
    conn = get_db()
    conn.execute("""INSERT INTO nutrition_log
        (log_date,meal_type,food_name,quantity,unit,calories,protein_g,carbs_g,fat_g,fiber_g,notes)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (d.get("log_date", date.today().isoformat()),
         d.get("meal_type","other"), d["food_name"],
         d.get("quantity",1), d.get("unit","serving"),
         d.get("calories",0), d.get("protein_g",0),
         d.get("carbs_g",0), d.get("fat_g",0),
         d.get("fiber_g",0), d.get("notes","")))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@extras_bp.route("/api/nutrition/log")
def get_nutrition_log():
    log_date = request.args.get("date", date.today().isoformat())
    conn = get_db()
    rows = conn.execute("SELECT * FROM nutrition_log WHERE log_date=? ORDER BY meal_type", (log_date,)).fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))

@extras_bp.route("/api/nutrition/log/<int:lid>", methods=["DELETE"])
def delete_nutrition_log(lid):
    conn = get_db()
    conn.execute("DELETE FROM nutrition_log WHERE id=?", (lid,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@extras_bp.route("/api/nutrition/summary")
def nutrition_summary():
    log_date = request.args.get("date", date.today().isoformat())
    conn = get_db()
    rows = conn.execute("""SELECT meal_type,
        SUM(calories) as cal, SUM(protein_g) as protein,
        SUM(carbs_g) as carbs, SUM(fat_g) as fat, SUM(fiber_g) as fiber
        FROM nutrition_log WHERE log_date=? GROUP BY meal_type""", (log_date,)).fetchall()
    totals = conn.execute("""SELECT
        SUM(calories) as cal, SUM(protein_g) as protein,
        SUM(carbs_g) as carbs, SUM(fat_g) as fat, SUM(fiber_g) as fiber
        FROM nutrition_log WHERE log_date=?""", (log_date,)).fetchone()
    conn.close()
    return jsonify({"by_meal": rows_to_list(rows), "totals": row_to_dict(totals)})


# ════════════════════════════════════════════
# ── WELLNESS GOALS ──
# ════════════════════════════════════════════

@extras_bp.route("/api/goals")
def get_goals():
    conn = get_db()
    rows = conn.execute("SELECT * FROM wellness_goals WHERE status='active' ORDER BY created_at DESC").fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))

@extras_bp.route("/api/goals", methods=["POST"])
def add_goal():
    d = request.get_json()
    conn = get_db()
    conn.execute("INSERT INTO wellness_goals (goal_type,goal_name,target,current,unit,deadline) VALUES (?,?,?,?,?,?)",
        (d["goal_type"], d["goal_name"], d["target"], d.get("current",0), d.get("unit",""), d.get("deadline","")))
    conn.commit(); conn.close()
    return jsonify({"success": True})

@extras_bp.route("/api/goals/<int:gid>", methods=["PUT"])
def update_goal(gid):
    d = request.get_json()
    conn = get_db()
    conn.execute("UPDATE wellness_goals SET current=?, status=? WHERE id=?",
        (d.get("current",0), d.get("status","active"), gid))
    conn.commit(); conn.close()
    return jsonify({"success": True})

@extras_bp.route("/api/goals/<int:gid>", methods=["DELETE"])
def delete_goal(gid):
    conn = get_db()
    conn.execute("UPDATE wellness_goals SET status='completed' WHERE id=?", (gid,))
    conn.commit(); conn.close()
    return jsonify({"success": True})


# ════════════════════════════════════════════
# ── MEDICAL HISTORY ──
# ════════════════════════════════════════════

@extras_bp.route("/api/medical-history")
def get_medical_history():
    rtype = request.args.get("type","")
    conn = get_db()
    sql = "SELECT * FROM medical_history"
    if rtype: sql += f" WHERE record_type='{rtype}'"
    sql += " ORDER BY date_occurred DESC"
    rows = conn.execute(sql).fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))

@extras_bp.route("/api/medical-history", methods=["POST"])
def add_medical_history():
    d = request.get_json()
    conn = get_db()
    conn.execute("""INSERT INTO medical_history
        (record_type,title,description,date_occurred,doctor_name,hospital,severity,is_ongoing)
        VALUES (?,?,?,?,?,?,?,?)""",
        (d.get("record_type","other"), d["title"], d.get("description",""),
         d.get("date_occurred",""), d.get("doctor_name",""), d.get("hospital",""),
         d.get("severity","mild"), 1 if d.get("is_ongoing") else 0))
    conn.commit(); conn.close()
    return jsonify({"success": True})

@extras_bp.route("/api/medical-history/<int:hid>", methods=["DELETE"])
def delete_medical_history(hid):
    conn = get_db()
    conn.execute("DELETE FROM medical_history WHERE id=?", (hid,))
    conn.commit(); conn.close()
    return jsonify({"success": True})


# ════════════════════════════════════════════
# ── INSURANCE ──
# ════════════════════════════════════════════

# Indian insurance providers
INDIAN_INSURERS = [
    "Star Health Insurance","Niva Bupa Health Insurance","Care Health Insurance",
    "HDFC ERGO Health Insurance","Bajaj Allianz Health Insurance",
    "New India Assurance","United India Insurance","Oriental Insurance",
    "National Insurance","Aditya Birla Health Insurance","ICICI Lombard Health Insurance",
    "Max Bupa Health Insurance","Manipal Cigna Health Insurance","Religare Health Insurance",
    "Tata AIG Health Insurance","Digit Insurance","Acko Health Insurance",
]

@extras_bp.route("/api/insurance/providers")
def get_providers():
    return jsonify(INDIAN_INSURERS)

@extras_bp.route("/api/insurance")
def get_insurance():
    conn = get_db()
    rows = conn.execute("SELECT * FROM insurance_records ORDER BY created_at DESC").fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))

@extras_bp.route("/api/insurance", methods=["POST"])
def add_insurance():
    d = request.get_json()
    conn = get_db()
    conn.execute("""INSERT INTO insurance_records
        (provider_name,policy_number,policy_type,sum_insured,premium_amount,
         premium_freq,start_date,expiry_date,nominee_name,contact_number,
         cashless_hospitals,notes)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (d["provider_name"], d.get("policy_number",""), d.get("policy_type",""),
         d.get("sum_insured",0), d.get("premium_amount",0), d.get("premium_freq","yearly"),
         d.get("start_date",""), d.get("expiry_date",""), d.get("nominee_name",""),
         d.get("contact_number",""), d.get("cashless_hospitals",""), d.get("notes","")))
    conn.commit(); conn.close()
    return jsonify({"success": True})

@extras_bp.route("/api/insurance/<int:iid>", methods=["DELETE"])
def delete_insurance(iid):
    conn = get_db()
    conn.execute("DELETE FROM insurance_records WHERE id=?", (iid,))
    conn.commit(); conn.close()
    return jsonify({"success": True})


# ════════════════════════════════════════════
# ── FAMILY HEALTH ──
# ════════════════════════════════════════════

@extras_bp.route("/api/family")
def get_family():
    conn = get_db()
    members = rows_to_list(conn.execute("SELECT * FROM family_members ORDER BY relation").fetchall())
    for m in members:
        logs = conn.execute("SELECT * FROM family_health_logs WHERE member_id=? ORDER BY log_date DESC LIMIT 5",(m["id"],)).fetchall()
        m["recent_logs"] = rows_to_list(logs)
    conn.close()
    return jsonify(members)

@extras_bp.route("/api/family", methods=["POST"])
def add_family_member():
    d = request.get_json()
    conn = get_db()
    conn.execute("INSERT INTO family_members (name,relation,age,blood_group,phone,conditions,medicines,notes) VALUES (?,?,?,?,?,?,?,?)",
        (d["name"], d["relation"], d.get("age"), d.get("blood_group",""),
         d.get("phone",""), d.get("conditions",""), d.get("medicines",""), d.get("notes","")))
    conn.commit(); conn.close()
    return jsonify({"success": True})

@extras_bp.route("/api/family/<int:fid>", methods=["DELETE"])
def delete_family_member(fid):
    conn = get_db()
    conn.execute("DELETE FROM family_members WHERE id=?", (fid,))
    conn.commit(); conn.close()
    return jsonify({"success": True})

@extras_bp.route("/api/family/<int:fid>/log", methods=["POST"])
def add_family_log(fid):
    d = request.get_json()
    conn = get_db()
    conn.execute("INSERT INTO family_health_logs (member_id,log_date,log_type,value,notes) VALUES (?,?,?,?,?)",
        (fid, d.get("log_date", date.today().isoformat()), d.get("log_type",""), d.get("value",""), d.get("notes","")))
    conn.commit(); conn.close()
    return jsonify({"success": True})


# ════════════════════════════════════════════
# ── DOCTORS ──
# ════════════════════════════════════════════

# Indian cities for doctor search
INDIAN_CITIES = ["Bengaluru","Mumbai","Delhi","Chennai","Hyderabad","Pune","Kolkata",
                 "Ahmedabad","Jaipur","Lucknow","Chandigarh","Kochi","Coimbatore","Nagpur","Surat"]

SPECIALTIES = ["General Physician","Cardiologist","Dermatologist","Orthopedic","Neurologist",
               "Gynecologist","Pediatrician","Psychiatrist","Ophthalmologist","ENT Specialist",
               "Diabetologist","Nephrologist","Gastroenterologist","Pulmonologist","Urologist",
               "Oncologist","Endocrinologist","Ayurvedic Doctor","Homeopathic Doctor","Dentist"]

@extras_bp.route("/api/doctors")
def get_doctors():
    conn = get_db()
    rows = conn.execute("SELECT * FROM my_doctors ORDER BY is_primary DESC, name").fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))

@extras_bp.route("/api/doctors", methods=["POST"])
def add_doctor():
    d = request.get_json()
    conn = get_db()
    conn.execute("""INSERT INTO my_doctors
        (name,specialty,hospital,city,phone,email,address,rating,notes,is_primary)
        VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (d["name"], d.get("specialty",""), d.get("hospital",""), d.get("city",""),
         d.get("phone",""), d.get("email",""), d.get("address",""),
         d.get("rating",0), d.get("notes",""), 1 if d.get("is_primary") else 0))
    conn.commit(); conn.close()
    return jsonify({"success": True})

@extras_bp.route("/api/doctors/<int:did>", methods=["DELETE"])
def delete_doctor(did):
    conn = get_db()
    conn.execute("DELETE FROM my_doctors WHERE id=?", (did,))
    conn.commit(); conn.close()
    return jsonify({"success": True})

@extras_bp.route("/api/doctors/meta")
def doctors_meta():
    return jsonify({"cities": INDIAN_CITIES, "specialties": SPECIALTIES})


# ════════════════════════════════════════════
# ── PREFERENCES ──
# ════════════════════════════════════════════

@extras_bp.route("/api/preferences")
def get_preferences():
    conn = get_db()
    rows = conn.execute("SELECT * FROM health_preferences").fetchall()
    conn.close()
    prefs = {r["pref_key"]: r["pref_value"] for r in rows}
    return jsonify(prefs)

@extras_bp.route("/api/preferences", methods=["POST"])
def save_preferences():
    d = request.get_json()
    conn = get_db()
    for key, value in d.items():
        conn.execute("""INSERT INTO health_preferences (pref_key, pref_value, updated_at)
            VALUES (?,?,datetime('now'))
            ON CONFLICT(pref_key) DO UPDATE SET pref_value=?, updated_at=datetime('now')""",
            (key, str(value), str(value)))
    conn.commit(); conn.close()
    return jsonify({"success": True})


# ════════════════════════════════════════════
# ── 1MG / PRACTO INTEGRATION ──
# ════════════════════════════════════════════

@extras_bp.route("/api/platform/search")
def platform_search():
    q = request.args.get("q","")
    city = request.args.get("city","Bengaluru")
    return jsonify({
        "practo_url":  f"https://www.practo.com/search/doctors?results_type=doctor&q={q.replace(' ','%20')}&city={city}",
        "onemg_url":   f"https://www.1mg.com/search/all?name={q.replace(' ','+')}",
        "apollo_url":  f"https://www.apollopharmacy.in/search-medicines/{q.replace(' ','%20')}",
        "netmeds_url": f"https://www.netmeds.com/catalogsearch/result?q={q.replace(' ','+')}",
        "query": q,
        "city": city,
    })

@extras_bp.route("/api/platform/lab-tests")
def lab_tests():
    city = request.args.get("city","Bengaluru")
    return jsonify({
        "thyrocare_url": f"https://www.thyrocare.com/",
        "lal_path_url":  f"https://www.lalpathlabs.com/",
        "practo_tests":  f"https://www.practo.com/{city.lower()}/lab-tests",
        "onemg_tests":   f"https://www.1mg.com/lab-tests",
    })


# ════════════════════════════════════════════
# ── COMPREHENSIVE HEALTH REPORT ──
# ════════════════════════════════════════════

@extras_bp.route("/api/full-report")
def full_report():
    conn = get_db()
    today = date.today().isoformat()
    since_30 = (date.today() - timedelta(days=30)).isoformat()

    # Nutrition summary last 7 days
    nutrition = conn.execute("""SELECT log_date,
        SUM(calories) as cal, SUM(protein_g) as protein
        FROM nutrition_log WHERE log_date >= ?
        GROUP BY log_date ORDER BY log_date DESC""",
        ((date.today()-timedelta(days=7)).isoformat(),)).fetchall()

    # Active goals
    goals = conn.execute("SELECT * FROM wellness_goals WHERE status='active'").fetchall()

    # Medical conditions ongoing
    conditions = conn.execute("SELECT * FROM medical_history WHERE is_ongoing=1").fetchall()

    # Insurance expiring in 60 days
    exp_soon = conn.execute("""SELECT * FROM insurance_records
        WHERE expiry_date IS NOT NULL AND expiry_date != ''
        AND julianday(expiry_date) - julianday('now') <= 60""").fetchall()

    # Family members
    family = conn.execute("SELECT COUNT(*) as c FROM family_members").fetchone()

    conn.close()
    return jsonify({
        "generated_at": datetime.now().strftime("%d %b %Y, %I:%M %p"),
        "nutrition_7day": rows_to_list(nutrition),
        "active_goals": rows_to_list(goals),
        "ongoing_conditions": rows_to_list(conditions),
        "insurance_expiring": rows_to_list(exp_soon),
        "family_members_count": family["c"] if family else 0,
    })
