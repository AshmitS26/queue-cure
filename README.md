# 🩺 Queue Cure '26 — Real-time Clinic Queue System

> Built for [Queue Cure '26](https://wooble.org/hackathon/queue-cure-26) by Wooble · Django + Channels + MongoDB + WebSocket

**The problem:** 76% of India's 1.5M clinics still run on paper tokens and shouting. Patients wait 2–3 hours with zero visibility. Doctors have no dashboard. Receptionists juggle from memory.

**Our fix:** A WebSocket-powered real-time queue system with 3 portals — Patient, Receptionist, Doctor — all syncing instantly. Plus a public live board on the home page so anyone can see the queue status.

---

## 🌐 Live Deployment

| | Link |
|---|---|
| 🚀 **Live App** | [democlinic.up.railway.app](https://democlinic.up.railway.app) |
| 🎯 **Demo Page** | [democlinic.up.railway.app/demo](https://democlinic.up.railway.app/demo/) |
| 📱 **Patient Check-in** | [democlinic.up.railway.app/checkin](https://democlinic.up.railway.app/checkin/) |
| 💼 **Receptionist** | [democlinic.up.railway.app/receptionist](https://democlinic.up.railway.app/receptionist/) |
| 🩺 **Doctor** | [democlinic.up.railway.app/doctor](https://democlinic.up.railway.app/doctor/) |
| 💻 **GitHub Repo** | [github.com/AshmitS26/queue-cure](https://github.com/AshmitS26/queue-cure) |

**Hosted on:** Railway (ASGI/WebSocket) + MongoDB Atlas (M0 free tier) + WhiteNoise (static files)

---

## ✨ Features

### Core
- 🏠 **Home page** — clinic description, live queue board, doctor list with room/fees/timings
- 📱 **Patient check-in** — no login, select doctor, auto-fill fees, pay (Cash/UPI/Online), get token
- 🎟️ **Smart tokens** — letter-based: Doctor A → `A-01`, `A-02`; Doctor B → `B-01`, `B-02`
- 📍 **Live position tracking** — WebSocket updates, no refresh needed
- 💼 **Receptionist dashboard** — walk-in entry, manage all doctors' queues, cancel tokens, emergency call next
- 🩺 **Doctor dashboard** — current consult, notes, up next queue, call next
- 🔐 **Auth** — receptionist has one login; each doctor has a separate login (no cross-access)

### Winning Extras
- 📺 **Public live queue board** — Token | Doctor | Room | Wait Time | Status (on home page)
- 📊 **EMA wait time** — Exponential Moving Average (α=0.3) updates after every patient, per doctor
- ⏱️ **Live countdown** — wait time counts down second by second on patient screen
- 🔔 **Browser notifications** — pings patient when 2 away
- 📱 **QR code** — doctor-specific, auto-uses live deployed URL
- 🎯 **Demo page** — one-click populate, reset, step-by-step judge guide, live credentials
- 🔄 **Auto-reconnecting WebSocket** — exponential backoff, 15s polling fallback
- 📱 **Mobile responsive** — works on any phone screen size, no app install needed

---

## 🛠️ Tech Stack

| Layer | Choice | Why |
|---|---|---|
| Backend | Django 4.2 + DRF | Solid, clean MongoDB integration |
| Real-time | Django Channels + Daphne | Native ASGI WebSocket, no separate server |
| Database | MongoDB Atlas via pymongo | Flexible schema, free cloud hosting |
| Wait Estimation | EMA Algorithm (α=0.3) | Adapts to doctor's actual pace per day |
| Static Files | WhiteNoise | Serves compressed files without Nginx |
| Frontend | Vanilla JS + Custom CSS | Zero build step, instant load |
| Hosting | Railway | Auto-deploy from GitHub, WebSocket support |

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

> No MongoDB? No problem — app auto-falls back to in-memory store for local dev/demo.

---

## 🎬 Demo Flow (for judges)

1. Open **[democlinic.up.railway.app/demo](https://democlinic.up.railway.app/demo/)**
2. Click **⚡ Populate Demo Data** — 7 patients added across 4 doctors instantly
3. Open any patient tracking link on your phone — see live position
4. Click **Call Next** on screen — watch phone update in real-time (~50ms)
5. Open receptionist + doctor in separate tabs — all sync simultaneously
6. Click **🔄 Reset Everything** to start fresh

---

## 🔐 Credentials

### Receptionist
| Username | Password |
|---|---|
| `reception` | `clinic@123` |

### Doctors (each has a separate login — no cross-access)
| Doctor | Username | Password | Room | Specialty |
|---|---|---|---|---|
| A) Dr. Rohit Mehta | `doctorA` | `docA@123` | 114 | General Physician |
| B) Dr. Anjali Sharma | `doctorB` | `docB@123` | 128 | Pediatrician |
| C) Dr. Priya Kapoor | `doctorC` | `docC@123` | 111 | Dermatologist |
| D) Dr. Karan Patel | `doctorD` | `docD@123` | 105 | Orthopedic |

---

## 🎟️ Token Format

Tokens are based on **doctor letter + sequential number** (resets daily):

```
Doctor A → A-01, A-02, A-03...
Doctor B → B-01, B-02, B-03...
Doctor C → C-01, C-02...
Doctor D → D-01, D-02...
```

The letter instantly tells the patient which doctor and room they belong to — no lookup needed.

> We initially used patient name initials (AS-01 for Ashmit Singh) but switched to doctor letters for privacy and usability.

---

## ⚡ EMA Wait Time Algorithm

```
new_avg = α × last_consult_time + (1 - α) × old_avg
α = 0.3  →  recent patient weighs 30%, history weighs 70%
```

- Starts at **10 min** default per doctor
- Updates automatically after every patient marked as done
- **Completely separate per doctor** — Doctor A's slow morning doesn't affect Doctor B's estimates
- Reflected live on the home page board and patient status page
- Resets fresh every day

**Example:**
```
Default avg    = 10 min
Patient 1 → 30 min consult → new avg = 0.3×30 + 0.7×10 = 16.0 min
Patient 2 → 60 min consult → new avg = 0.3×60 + 0.7×16 = 29.2 min
Patient 3 → 8 min consult  → new avg = 0.3×8  + 0.7×29 = 22.7 min
```

---

## 🔌 WebSocket Architecture

```
Patient checks in / Doctor calls next / Receptionist cancels
                        ↓
              POST to Django REST API
                        ↓
            MongoDB write + EMA update
                        ↓
         Django Channels → group_send()
                        ↓
    ┌──────────────────────────────────┐
    │   clinic_C001_D001 group         │  ← Doctor queue subscribers
    │   clinic_C001_D002 group         │
    │   liveboard_C001 group           │  ← Home page live board
    └──────────────────────────────────┘
                        ↓
    ALL connected devices update in ~50ms
```

**Fallback:** Auto-reconnects with exponential backoff (1s → 10s max) + 15s REST polling safety net.

---

## 🗂️ Project Structure

```
queue_cure/
├── manage.py
├── requirements.txt
├── Procfile                    ← Railway: migrate + collectstatic + daphne
├── runtime.txt                 ← Python 3.11
├── README.md
├── .env.example
├── queue_cure/
│   ├── settings.py             ← Django + Channels + MongoDB + WhiteNoise
│   ├── asgi.py                 ← HTTP + WebSocket routing
│   ├── urls.py                 ← All URL patterns
│   └── wsgi.py
├── clinic/
│   ├── db.py                   ← MongoDB layer + EMA + in-memory fallback
│   ├── views.py                ← Pages + REST API + auth + demo
│   ├── consumers.py            ← QueueConsumer + LiveBoardConsumer
│   ├── routing.py              ← WebSocket URL routing
│   └── urls.py                 ← API routes
├── templates/
│   ├── base.html               ← Shared navbar + toast + JS utils
│   ├── home.html               ← Landing + live board + doctor table
│   ├── patient_checkin.html    ← Check-in form with auto-fees + payment
│   ├── patient_status.html     ← Live position + EMA countdown
│   ├── receptionist.html       ← All queues + walk-in + cancel
│   ├── doctor.html             ← Dashboard + EMA stats + notes
│   ├── login.html              ← Auth (receptionist + per-doctor)
│   └── demo.html               ← Judge demo with populate/reset
└── static/css/
    └── style.css               ← Full design system (light, indigo theme)
```

---

## 🔌 API Reference

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/checkin/` | Create patient token |
| `GET` | `/api/queue/<clinic>/<doctor>/` | Current queue state |
| `GET` | `/api/token/<token_id>/` | Token status + position + ETA |
| `POST` | `/api/next/<clinic>/<doctor>/` | Call next patient |
| `POST` | `/api/done/<clinic>/<doctor>/` | Mark done + update EMA |
| `POST` | `/api/status/<token_id>/` | Update token status |
| `GET` | `/api/stats/<clinic>/<doctor>/` | Doctor analytics |
| `GET` | `/api/liveboard/<clinic>/` | Public live board data |
| `POST` | `/api/demo/populate/` | Populate 7 demo patients |
| `POST` | `/api/reset/<clinic>/` | Clear all queues |
| `WS` | `/ws/queue/<clinic>/<doctor>/` | Live queue updates |
| `WS` | `/ws/liveboard/<clinic>/` | Home page live board |

---

## 🌐 All Pages

| URL | Page | Auth |
|---|---|---|
| `/` | Home + Live Board + Doctor List | Public |
| `/checkin/` | Patient Check-in | Public |
| `/status/<token>/` | Patient Live Status + Countdown | Public |
| `/demo/` | Judge Demo Page | Public |
| `/receptionist/` | Reception Dashboard | Login required |
| `/doctor/` | Doctor Dashboard | Login required |
| `/login/receptionist/` | Receptionist login | Public |
| `/login/doctor/` | Doctor login | Public |
| `/qr/<clinic>/` | QR Code PNG | Public |

---

## 🚀 Deploy on Railway + MongoDB Atlas

### 1. MongoDB Atlas (free)
```
1. cloud.mongodb.com → free M0 cluster (Mumbai region)
2. Database Access → Add user (Atlas Admin role)
3. Network Access → 0.0.0.0/0 (allow all IPs)
4. Connect → Drivers → copy connection string
```

### 2. Push to GitHub
```bash
git init
git add .
git commit -m "Queue Cure 26"
git remote add origin https://github.com/AshmitS26/queue-cure.git
git push -u origin master
```

### 3. Railway
```
1. railway.app → New Project → Deploy from GitHub repo
2. Settings → Start Command:
   python manage.py migrate && python manage.py collectstatic --noinput && daphne -b 0.0.0.0 -p $PORT queue_cure.asgi:application
3. Variables tab → add:
   MONGODB_URI       = mongodb+srv://user:pass@cluster0.xxxxx.mongodb.net/queue_cure
   MONGODB_DB_NAME   = queue_cure
   DJANGO_SECRET_KEY = your-long-random-secret-key
   DEBUG             = False
4. Settings → Networking → Generate Domain
5. Live in ~3 minutes!
```

### Important notes
- Do NOT set `PORT` as a variable — Railway handles it automatically via `$PORT`
- MongoDB timeout must be ≥ 5000ms for Atlas to connect on Railway
- WhiteNoise handles static files — no Nginx needed

---

## 🎤 30-second Pitch

> "We didn't just digitize the token slip. We gave every stakeholder real-time visibility. Patients see their live position and get a browser ping when they're 2 away — so they can wait outside. Receptionists stop firefighting. Doctors call next without stepping out. The wait time uses EMA so it adapts to each doctor's actual pace throughout the day. Built on Django Channels — open it on 3 devices and watch everything sync in under 50ms. Live at democlinic.up.railway.app."

---

## 📜 License
MIT — Built for Queue Cure '26 by Wooble · Ashmit Singh · IIT Delhi