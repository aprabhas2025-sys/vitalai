# 🏥 VitalAI — Indian Personal Health Assistant

A full-stack personal health monitoring web application built for the Indian healthcare context. Tracks medications, fitness, nutrition, wellness goals, family health, medical history, insurance, and your local doctor network — all in one place.

---

## ✨ Features

### 🏃 Fitness Tracking (Google Fit)
- Live steps, calories, heart rate, weight from Google Fit API
- 7-day weekly steps breakdown chart
- Sleep and activity monitoring

### 💊 Medication Management
- 30+ pre-seeded Indian medicines (allopathic + Ayurvedic)
- Personal medicine list with dosage scheduling
- Daily dose tracker — mark doses taken / missed / skipped
- Adherence reports with per-medicine breakdown
- Medicine interaction checker
- Refill and expiry alerts
- Full dose history log

### 🥗 Indian Diet & Nutrition Tracker
- 60+ Indian foods database with nutrition values
- Daily food log by meal type (breakfast / lunch / dinner / snack)
- Calorie, protein, carbs, fat, fiber tracking
- Daily calorie goal progress bar

### 🎯 Wellness Goals
- Create and track personal health goals with deadlines
- Progress update and goal completion tracking

### 🏥 Medical History
- Record conditions, surgeries, allergies, vaccinations, hospitalizations, tests
- Severity tracking and ongoing condition flags

### 🛡️ Health Insurance
- Store Indian insurance policies (Star, HDFC Ergo, LIC, etc.)
- Premium tracking, expiry alerts (60 days ahead), nominee details

### 👨‍👩‍👧 Family Health
- Add family members with blood group, conditions, current medicines
- Log health events per member (BP readings, glucose, etc.)

### 🩺 My Doctors Network
- Save your personal doctors with specialty, hospital, city, contact
- Integrated Practo, 1mg, Apollo, Netmeds search redirects
- Lab test links (Thyrocare, Lal PathLabs, Practo)

### 🤖 AI Health Assistant
- Covers 50+ health topics: symptoms, diseases, nutrition, medications, mental health, first aid
- Live Google Fit data integration in chat responses
- Indian health context (Ayurveda, Indian diet, regional diseases)

### 📤 Export Functionality
| Export | Format | Route |
|---|---|---|
| Active Medications | CSV | `/api/export/medications/csv` |
| Dose History (30 days) | CSV | `/api/export/dose-history/csv` |
| Nutrition Log (30 days) | CSV | `/api/export/nutrition/csv` |
| Full Health Report | JSON | `/api/export/health-report/json` |
| Full Health Report | XML | `/api/export/health-report/xml` |

### 📥 Import
- Import nutrition logs from CSV (`/api/import/nutrition/csv`)

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.10+, Flask |
| Database | SQLite (medications.db, extras.db) |
| Auth | Google OAuth 2.0 |
| Fitness API | Google Fit REST API |
| Frontend | Vanilla HTML/CSS/JS |
| Deployment | Render / Railway / any Python host |

---

## ⚙️ Setup Instructions

### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/vitalai.git
cd vitalai
```

### 2. Create a Virtual Environment
```bash
python -m venv venv
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate           # Windows
```

### 3. Install Dependencies
```bash
pip install flask flask-cors python-dotenv requests
```

### 4. Set Up Google OAuth & Fitness API

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project
3. Enable these APIs:
   - **Google Fitness API**
   - **Google OAuth 2.0**
4. Go to **Credentials → Create OAuth 2.0 Client ID**
   - Application type: Web application
   - Authorized redirect URIs: `http://localhost:5000/callback`
5. Download credentials

### 5. Create `.env` File
```env
GOOGLE_CLIENT_ID=your_client_id_here
GOOGLE_CLIENT_SECRET=your_client_secret_here
REDIRECT_URI=http://localhost:5000/callback
SECRET_KEY=your_random_secret_key_here
```

### 6. Project Structure
```
vitalai/
├── backend/
│   ├── app.py              # Main Flask app + export routes
│   ├── medication.py       # Medication module + DB
│   ├── extras.py           # Nutrition, goals, insurance, family, doctors
│   ├── medications.db      # Auto-created on first run
│   └── extras.db           # Auto-created on first run
├── frontend/
│   ├── index.html          # Login page
│   ├── dashboard.html      # Main dashboard
│   ├── medications.html    # Medication tracker
│   └── health_extras.html  # Health manager (diet, goals, etc.)
├── .env                    # Environment variables (not committed)
├── .gitignore
└── README.md
```

### 7. Run the Application
```bash
cd backend
python app.py
```
Visit `http://localhost:5000`

---

## 🚀 Deployment (Render)

1. Push to GitHub
2. Create a new **Web Service** on [Render](https://render.com)
3. Set build command: `pip install flask flask-cors python-dotenv requests`
4. Set start command: `python backend/app.py`
5. Add environment variables from your `.env` file
6. Update `REDIRECT_URI` to your Render domain

---

## 🔌 API Reference

### Health Data
| Method | Route | Description |
|---|---|---|
| GET | `/api/health-data` | Fetch Google Fit metrics |
| POST | `/api/chat` | AI health chatbot |

### Medications
| Method | Route | Description |
|---|---|---|
| GET | `/api/med/catalogue/search` | Search medicine catalogue |
| GET | `/api/med/my-medicines` | List personal medicines |
| POST | `/api/med/my-medicines` | Add medicine |
| PUT | `/api/med/my-medicines/<id>` | Edit medicine |
| DELETE | `/api/med/my-medicines/<id>` | Remove medicine |
| GET | `/api/med/today` | Today's dose schedule |
| POST | `/api/med/log` | Log a dose taken/missed |
| GET | `/api/med/adherence` | Adherence stats |
| POST | `/api/med/interactions` | Check drug interactions |
| GET | `/api/med/report` | Medication report |
| GET | `/api/med/alerts` | Refill & expiry alerts |

### Nutrition
| Method | Route | Description |
|---|---|---|
| GET | `/api/nutrition/foods/search` | Search Indian foods |
| GET | `/api/nutrition/log` | Get day's food log |
| POST | `/api/nutrition/log` | Add food entry |
| DELETE | `/api/nutrition/log/<id>` | Delete food entry |
| GET | `/api/nutrition/summary` | Day's nutrition summary |

### Goals, Medical History, Insurance, Family, Doctors
| Method | Route | Description |
|---|---|---|
| GET/POST | `/api/goals` | Wellness goals |
| GET/POST | `/api/medical-history` | Medical records |
| GET/POST | `/api/insurance` | Insurance policies |
| GET/POST | `/api/family` | Family members |
| GET/POST | `/api/doctors` | Doctor network |
| GET | `/api/platform/search?q=...` | 1mg/Practo search links |

### Export / Import
| Method | Route | Description |
|---|---|---|
| GET | `/api/export/medications/csv` | Download medications CSV |
| GET | `/api/export/dose-history/csv` | Download dose history CSV |
| GET | `/api/export/nutrition/csv` | Download nutrition log CSV |
| GET | `/api/export/health-report/json` | Download health report JSON |
| GET | `/api/export/health-report/xml` | Download health report XML |
| POST | `/api/import/nutrition/csv` | Upload nutrition CSV |

---

## 🗺️ Roadmap

- [ ] Streamlit version for portfolio
- [ ] Push notification reminders (Firebase)
- [ ] Voice-controlled health queries
- [ ] PDF health report generation
- [ ] LangChain integration for smarter AI responses
- [ ] PostgreSQL migration for production scale
- [ ] HIPAA-compliant data handling

---

## 📄 License
MIT License — free to use and modify.
