# VitalAI — Healthcare Monitoring Platform

AI-powered health dashboard with real Google Fit integration, live metrics, and an AI health assistant.

---

## Project Structure

```
healthai/
├── backend/
│   └── app.py              ← Flask server (main entry point)
├── frontend/
│   ├── index.html          ← Landing page
│   └── dashboard.html      ← Main dashboard (after login)
├── requirements.txt
└── README.md
```

---

## Setup Instructions

### Step 1 — Install Dependencies

```bash
cd healthai
pip install -r requirements.txt
```

### Step 2 — Google OAuth Setup (Already Done ✅)

Your credentials are already in `backend/app.py`:


**Important:** Add the redirect URI in Google Cloud Console:
1. Go to https://console.cloud.google.com
2. APIs & Services → Credentials → Your OAuth client
3. Add `http://localhost:5000/callback` under **Authorized redirect URIs**
4. Save

### Step 3 — Enable Google Fit API

1. In Google Cloud Console → APIs & Services → Library
2. Search "Fitness API" → Enable it

### Step 4 — Run the App

```bash
# Using full Python path (Windows):
C:\Users\prabh\AppData\Local\Python\pythoncore-3.14-64\python.exe backend/app.py

# Or standard:
python backend/app.py
```

### Step 5 — Open Browser

Visit: **http://127.0.0.1:5000**

---

## Features

| Feature | Status |
|---------|--------|
| Google OAuth 2.0 Login | ✅ |
| Live Steps from Google Fit | ✅ |
| Live Heart Rate | ✅ |
| Calories Burned | ✅ |
| Weight Tracking | ✅ |
| 7-Day Steps Chart | ✅ |
| AI Health Chat (context-aware) | ✅ |
| User Profile Display | ✅ |
| Secure Logout | ✅ |

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Landing page |
| `/login` | GET | Start Google OAuth flow |
| `/callback` | GET | OAuth callback |
| `/dashboard` | GET | Health dashboard |
| `/logout` | GET | Clear session |
| `/api/health-data` | GET | Fetch all Google Fit metrics |
| `/api/chat` | POST | AI health assistant |
| `/api/status` | GET | Auth status + user info |

---

## Troubleshooting

**"Python not found"** → Use full path:
```bash
C:\Users\prabh\AppData\Local\Python\pythoncore-3.14-64\python.exe backend/app.py
```

**"No health data"** → Make sure:
- You have Google Fit data recorded (walk with your phone)
- Fitness API is enabled in Google Cloud Console
- Authorized redirect URI is added

**OAuth error** → Ensure redirect URI `http://localhost:5000/callback` is added in Google Cloud Console
