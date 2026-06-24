# 🩺 Queue Cure '26 — Real-time Clinic Queue System

> Built for [Queue Cure '26](https://wooble.org/hackathon/queue-cure-26) by Wooble · Django + Channels + MongoDB + WebSocket

**The problem:** 76% of India's 1.5M clinics still run on paper tokens and shouting. Patients wait 2–3 hours with zero visibility. Doctors have no dashboard. Receptionists juggle from memory.

**Our fix:** A WebSocket-powered real-time queue system with 3 portals — Patient, Receptionist, Doctor — all syncing instantly. Plus a public live board on the home page so anyone can see the queue status.

---

## ✨ Features

### Core
- 🏠 **Home page** — clinic description, live queue board, doctor list with room/fees/timings
- 📱 **Patient check-in** — no login, select doctor, auto-fill fees, pay (Cash/UPI/Online), get token
- 🎟️ **Smart tokens** — letter-based: Doctor A → `A-01`, `A-02`; Doctor B → `B-01`, `B-02`
- 📍 **Live position tracking** — WebSocket updates, no refresh needed
- 💼 **Receptionist dashboard** — walk-in entry, manage all doctors' queues, cancel tokens, emergency call next
- 🩺 **Doctor dashboard** — current consult, notes, up next queue, call next
- 🔐 **Auth** — receptionist has one login; each doctor has separate login (no cross-access)

### Winning Extras
- 📺 **Public live queue board** — Token | Doctor | Room | Wait Time | Status (on home page)
- 📊 **EMA wait time** — Exponential Moving Average (α=0.3) updates after every patient, per doctor
- ⏱️ **Live countdown** — wait time counts down second by second on patient screen
- 🔔 **Browser notifications** — pings patient when 2 away
- 📱 **QR code** — doctor-specific, auto-uses live URL after deployment
- 🎯 **Demo page** — one-click populate, reset, step-by-step judge guide
- 🔄 **Auto-reconnecting WebSocket** — exponential backoff, polling fallback

---

## 🛠️ Tech Stack

| Layer | Choice |
|---|---|
| Backend | Django 4.2 + Django REST Framework |
| Real-time | Django Channels (ASGI + WebSocket) |
| Database | MongoDB via pymongo |
| Wait Estimation | EMA Algorithm (α=0.3) |
| Static Files | WhiteNoise (production) |
| Frontend | Vanilla JS + Custom CSS |
| Deployment | Railway + MongoDB Atlas |

---

## 🚀 Quick Start (Local)

```bash
# 1. Extract and enter
unzip queue_cure.zip
cd queue_cure

# 2. Create virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Mac/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run migrations
python manage.py migrate

# 5. Start server
daphne -b 127.0.0.1 -p 8000 queue_cure.asgi:application
```

Open **http://localhost:8000** 🎉

> No MongoDB? No problem — app auto-falls back to in-memory store for local dev.

---

## 🎬 Demo Flow (for judges)

1. Open **http://localhost:8000/demo/**
2. Click **⚡ Populate Demo Data** — 7 patients added across 4 doctors
3. Open patient link on phone — see live position
4. Click **Call Next** — watch phone update instantly
5. Click **🔄 Reset** to start fresh

---

## 🔐 Credentials

### Receptionist
| Username | Password |
|---|---|
| `reception` | `clinic@123` |

### Doctors (separate logins)
| Doctor | Username | Password | Room |
|---|---|---|---|
| A) Dr. Rohit Mehta | `doctorA` | `docA@123` | 114 |
| B) Dr. Anjali Sharma | `doctorB` | `docB@123` | 128 |
| C) Dr. Priya Kapoor | `doctorC` | `docC@123` | 111 |
| D) Dr. Karan Patel | `doctorD` | `docD@123` | 105 |

---

## 🎟️ Token Format

Tokens are based on **doctor letter + sequential number** (daily reset):

```
Doctor A → A-01, A-02, A-03...
Doctor B → B-01, B-02, B-03...
Doctor C → C-01, C-02...
Doctor D → D-01, D-02...
```

Patient can instantly identify their doctor and room from the token letter.

---

## ⚡ EMA Wait Time Algorithm

```
new_avg = α × last_consult_time + (1 - α) × old_avg
α = 0.3 (recent patient weighs 30%, history weighs 70%)
```

- Starts at **10 min** default per doctor
- Updates after every patient marked done
- **Separate per doctor** — never shared
- Reflected live on home page board and patient status page

**Example:**
```
Default avg = 10 min
Patient 1 takes 30 min → new avg = 0.3×30 + 0.7×10 = 16 min
Patient 2 takes 60 min → new avg = 0.3×60 + 0.7×16 = 29.2 min
```

---

## 🗂️ Project Structure

```
queue_cure/
├── manage.py
├── requirements.txt
├── Procfile                    ← Railway deployment
├── runtime.txt                 ← Python version
├── README.md
├── .env.example
├── queue_cure/
│   ├── settings.py             ← Django + Channels + MongoDB config
│   ├── asgi.py                 ← Routes HTTP + WebSocket
│   ├── urls.py
│   └── wsgi.py
├── clinic/
│   ├── db.py                   ← MongoDB layer + EMA + in-memory fallback
│   ├── views.py                ← All pages + REST API + auth + demo
│   ├── consumers.py            ← WebSocket consumers (queue + live board)
│   ├── routing.py              ← WebSocket URL routing
│   └── urls.py                 ← API routes
├── templates/
│   ├── base.html               ← Shared navbar + toast + JS utils
│   ├── home.html               ← Landing + live board + doctor list
│   ├── patient_checkin.html    ← Check-in form with auto-fees
│   ├── patient_status.html     ← Live position + countdown
│   ├── receptionist.html       ← Queue management dashboard
│   ├── doctor.html             ← Doctor dashboard + EMA stats
│   ├── login.html              ← Auth page (receptionist + per-doctor)
│   └── demo.html               ← Judge demo page
└── static/css/
    └── style.css               ← Full design system
```

---

## 🔌 API Reference

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/checkin/` | Create patient token |
| `GET` | `/api/queue/<clinic>/<doctor>/` | Current queue state |
| `GET` | `/api/token/<token_id>/` | Token status + position + ETA |
| `POST` | `/api/next/<clinic>/<doctor>/` | Call next patient |
| `POST` | `/api/done/<clinic>/<doctor>/` | Mark current done (updates EMA) |
| `POST` | `/api/status/<token_id>/` | Update token status |
| `GET` | `/api/stats/<clinic>/<doctor>/` | Doctor analytics |
| `GET` | `/api/liveboard/<clinic>/` | Public live board data |
| `POST` | `/api/demo/populate/` | Populate demo data |
| `POST` | `/api/reset/<clinic>/` | Clear all queues |
| `WS` | `/ws/queue/<clinic>/<doctor>/` | Live queue updates |
| `WS` | `/ws/liveboard/<clinic>/` | Live board updates |

---

## 🚀 Deploy on Railway + MongoDB Atlas

### 1. MongoDB Atlas (free)
```
1. cloud.mongodb.com → free M0 cluster
2. Database Access → add user
3. Network Access → 0.0.0.0/0
4. Connect → Drivers → copy connection string
```

### 2. Push to GitHub
```bash
git init
git add .
git commit -m "Queue Cure 26"
git remote add origin https://github.com/YOUR_USERNAME/queue-cure.git
git push -u origin main
```

### 3. Railway
```
1. railway.app → New Project → Deploy from GitHub
2. Add environment variables:
   MONGODB_URI       = mongodb+srv://user:pass@cluster0.xxxxx.mongodb.net/queue_cure
   MONGODB_DB_NAME   = queue_cure
   DJANGO_SECRET_KEY = your-secret-key
   DEBUG             = False
3. Start command: daphne -b 0.0.0.0 -p $PORT queue_cure.asgi:application
4. Generate domain → live URL!
```

---

## 🌐 Pages

| URL | Page | Auth |
|---|---|---|
| `/` | Home + Live Board | Public |
| `/checkin/` | Patient Check-in | Public |
| `/status/<token>/` | Patient Live Status | Public |
| `/demo/` | Judge Demo Page | Public |
| `/receptionist/` | Reception Dashboard | Login required |
| `/doctor/` | Doctor Dashboard | Login required |
| `/qr/<clinic>/` | QR Code PNG | Public |

---

## 🎤 30-second Pitch

> "We didn't just digitize the token slip. We gave every stakeholder real-time visibility. Patients see their live position and get a browser ping when they're 2 away — so they can wait outside. Receptionists stop firefighting. Doctors call next without stepping out. The wait time is calculated using EMA so it adapts to each doctor's actual pace throughout the day. Built on Django Channels with WebSocket — open it on 3 devices and watch everything sync in under 50ms."

---

## 📜 License
MIT — Built for Queue Cure '26 by Wooble.
