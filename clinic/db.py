"""
MongoDB data layer for Queue Cure.

Collections:
  clinics  — clinic metadata
  doctors  — doctor profiles (letter, room, fees, timings, ema_avg, credentials)
  tokens   — patient tokens / queue

EMA (Exponential Moving Average) for wait time:
  new_avg = alpha * last_consult_time + (1 - alpha) * old_avg
  alpha = 0.3, default start = 10 min
"""
from datetime import datetime, timezone
from django.conf import settings
from pymongo import MongoClient, ASCENDING
from pymongo.errors import ServerSelectionTimeoutError

EMA_ALPHA = 0.3
DEFAULT_AVG = 10  # minutes

_client = None
_db = None


_bootstrapped = False

def get_db():
    global _client, _db, _bootstrapped
    if _db is not None:
        return _db
    try:
        _client = MongoClient(settings.MONGODB_URI, serverSelectionTimeoutMS=5000)
        _client.admin.command('ping')
        _db = _client[settings.MONGODB_DB_NAME]
        _db.tokens.create_index([('clinic_id', ASCENDING), ('status', ASCENDING)])
        _db.tokens.create_index([('token_id', ASCENDING)], unique=True)
        _db.doctors.create_index([('clinic_id', ASCENDING)])
        print(f"[clinic] MongoDB connected -> {settings.MONGODB_DB_NAME}")
        if not _bootstrapped:
            _bootstrapped = True
            bootstrap_defaults()
        return _db
    except (ServerSelectionTimeoutError, Exception) as e:
        print(f"[clinic] MongoDB unavailable ({e}). Using in-memory fallback.")
        _db = _InMemoryDB()
        if not _bootstrapped:
            _bootstrapped = True
            bootstrap_defaults()
        return _db


# ─── In-Memory Fallback ─────────────────────────────────────────────────

class _InMemoryCollection:
    def __init__(self):
        self._data = []

    def insert_one(self, doc):
        self._data.append(dict(doc))
        return type('R', (), {'inserted_id': doc.get('_id', len(self._data))})()

    def find_one(self, query=None, sort=None):
        results = self._filter(query or {})
        if sort:
            for field, direction in reversed(sort):
                results.sort(key=lambda d: d.get(field) or 0, reverse=(direction == -1))
        return results[0] if results else None

    def find(self, query=None, sort=None):
        results = self._filter(query or {})
        if sort:
            for field, direction in reversed(sort):
                results.sort(key=lambda d: d.get(field) or 0, reverse=(direction == -1))
        return _Cursor(results)

    def update_one(self, query, update):
        for doc in self._filter(query):
            if '$set' in update:
                doc.update(update['$set'])
            if '$inc' in update:
                for k, v in update['$inc'].items():
                    doc[k] = doc.get(k, 0) + v
            return type('R', (), {'modified_count': 1})()
        return type('R', (), {'modified_count': 0})()

    def count_documents(self, query):
        return len(self._filter(query))

    def delete_many(self, query):
        before = len(self._data)
        self._data = [d for d in self._data if not self._matches(d, query)]
        return type('R', (), {'deleted_count': before - len(self._data)})()

    def create_index(self, *args, **kwargs):
        pass

    def _matches(self, doc, query):
        for k, v in query.items():
            if isinstance(v, dict):
                if '$in' in v and doc.get(k) not in v['$in']:
                    return False
                if '$ne' in v and doc.get(k) == v['$ne']:
                    return False
                if '$gte' in v and (doc.get(k) is None or doc.get(k) < v['$gte']):
                    return False
            elif doc.get(k) != v:
                return False
        return True

    def _filter(self, query):
        return [d for d in self._data if self._matches(d, query)]


class _Cursor:
    def __init__(self, data):
        self._data = data
    def __iter__(self):
        return iter(self._data)
    def sort(self, field, direction=1):
        self._data.sort(key=lambda d: d.get(field) or 0, reverse=(direction == -1))
        return self
    def limit(self, n):
        self._data = self._data[:n]
        return self


class _InMemoryDB:
    def __init__(self):
        self.clinics = _InMemoryCollection()
        self.doctors = _InMemoryCollection()
        self.tokens = _InMemoryCollection()


# ─── Bootstrap ───────────────────────────────────────────────────────────

def bootstrap_defaults():
    db = get_db()
    if db.clinics.count_documents({}) == 0:
        db.clinics.insert_one({
            'clinic_id': 'C001',
            'name': 'Demo Clinic',
            'address': 'Delhi',
            'description': 'A modern multi-speciality clinic providing quality healthcare with minimal wait times. Walk in or check in online — track your queue in real time.',
            'created_at': datetime.now(timezone.utc),
        })
    if db.doctors.count_documents({}) == 0:
        doctors = [
            {
                'doctor_id': 'D001', 'letter': 'A',
                'name': 'Dr. Rohit Mehta',
                'specialty': 'General Physician',
                'clinic_id': 'C001',
                'room': '114', 'fees': 500,
                'timings': '9:00 AM - 1:00 PM',
                'ema_avg': DEFAULT_AVG,
                'username': 'doctorA', 'password': 'docA@123',
            },
            {
                'doctor_id': 'D002', 'letter': 'B',
                'name': 'Dr. Anjali Sharma',
                'specialty': 'Pediatrician',
                'clinic_id': 'C001',
                'room': '128', 'fees': 700,
                'timings': '10:00 AM - 3:00 PM',
                'ema_avg': DEFAULT_AVG,
                'username': 'doctorB', 'password': 'docB@123',
            },
            {
                'doctor_id': 'D003', 'letter': 'C',
                'name': 'Dr. Priya Kapoor',
                'specialty': 'Dermatologist',
                'clinic_id': 'C001',
                'room': '111', 'fees': 800,
                'timings': '11:00 AM - 4:00 PM',
                'ema_avg': DEFAULT_AVG,
                'username': 'doctorC', 'password': 'docC@123',
            },
            {
                'doctor_id': 'D004', 'letter': 'D',
                'name': 'Dr. Karan Patel',
                'specialty': 'Orthopedic',
                'clinic_id': 'C001',
                'room': '105', 'fees': 600,
                'timings': '2:00 PM - 6:00 PM',
                'ema_avg': DEFAULT_AVG,
                'username': 'doctorD', 'password': 'docD@123',
            },
        ]
        for d in doctors:
            db.doctors.insert_one(d)


# ─── Token operations ────────────────────────────────────────────────────

def generate_token_id(clinic_id, doctor_id):
    """Token format: <DoctorLetter>-<seq>  e.g. A-01, B-05"""
    db = get_db()
    doctor = get_doctor(doctor_id)
    letter = (doctor or {}).get('letter', 'X')
    if isinstance(db, _InMemoryDB):
        count = db.tokens.count_documents({'clinic_id': clinic_id, 'doctor_id': doctor_id})
    else:
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        count = db.tokens.count_documents({
            'clinic_id': clinic_id, 'doctor_id': doctor_id,
            'check_in_time': {'$gte': today_start},
        })
    return f"{letter}-{count + 1:02d}"


def create_token(clinic_id, doctor_id, patient_name, phone, payment_method=''):
    db = get_db()
    token_id = generate_token_id(clinic_id, doctor_id)
    doctor = get_doctor(doctor_id) or {}
    doc = {
        'token_id': token_id,
        'clinic_id': clinic_id,
        'doctor_id': doctor_id,
        'patient_name': patient_name,
        'phone': phone,
        'payment_method': payment_method,  # cash / upi / online
        'fees': doctor.get('fees', 0),
        'status': 'waiting',
        'check_in_time': datetime.now(timezone.utc),
        'called_at': None,
        'completed_at': None,
        'notes': '',
    }
    db.tokens.insert_one(doc)
    return doc


def get_token(token_id):
    return get_db().tokens.find_one({'token_id': token_id})


def get_queue(clinic_id, doctor_id):
    return list(get_db().tokens.find({
        'clinic_id': clinic_id, 'doctor_id': doctor_id, 'status': 'waiting',
    }).sort('check_in_time', 1))


def get_all_queues(clinic_id):
    """All waiting + called tokens across all doctors (for live board)."""
    db = get_db()
    waiting = list(db.tokens.find({
        'clinic_id': clinic_id,
        'status': {'$in': ['waiting', 'called']},
    }).sort('check_in_time', 1))
    return waiting


def get_current_called(clinic_id, doctor_id):
    return get_db().tokens.find_one({
        'clinic_id': clinic_id, 'doctor_id': doctor_id, 'status': 'called',
    })


def call_next(clinic_id, doctor_id):
    """Complete current patient (update EMA), then call next waiting."""
    db = get_db()
    current = get_current_called(clinic_id, doctor_id)
    if current:
        now = datetime.now(timezone.utc)
        db.tokens.update_one(
            {'token_id': current['token_id']},
            {'$set': {'status': 'seen', 'completed_at': now}}
        )
        # Update EMA if we have called_at time
        if current.get('called_at'):
            consult_mins = (now - current['called_at']).total_seconds() / 60
            update_ema(doctor_id, consult_mins)

    queue = get_queue(clinic_id, doctor_id)
    if not queue:
        return None
    next_token = queue[0]
    db.tokens.update_one(
        {'token_id': next_token['token_id']},
        {'$set': {'status': 'called', 'called_at': datetime.now(timezone.utc)}}
    )
    next_token['status'] = 'called'
    return next_token


def mark_done_current(clinic_id, doctor_id, notes=''):
    """Mark current patient as done without calling next. Updates EMA."""
    db = get_db()
    current = get_current_called(clinic_id, doctor_id)
    if not current:
        return None
    now = datetime.now(timezone.utc)
    db.tokens.update_one(
        {'token_id': current['token_id']},
        {'$set': {'status': 'seen', 'completed_at': now, 'notes': notes}}
    )
    if current.get('called_at'):
        consult_mins = (now - current['called_at']).total_seconds() / 60
        update_ema(doctor_id, consult_mins)
    return current


def update_token_status(token_id, status, notes=None):
    db = get_db()
    update = {'status': status}
    if status in ('seen', 'no_show', 'skipped'):
        update['completed_at'] = datetime.now(timezone.utc)
    if notes is not None:
        update['notes'] = notes
    db.tokens.update_one({'token_id': token_id}, {'$set': update})
    return get_token(token_id)


# ─── EMA ─────────────────────────────────────────────────────────────────

def update_ema(doctor_id, consult_minutes):
    """Update the doctor's EMA average consultation time."""
    db = get_db()
    doctor = get_doctor(doctor_id)
    if not doctor:
        return
    old_avg = doctor.get('ema_avg', DEFAULT_AVG)
    new_avg = round(EMA_ALPHA * consult_minutes + (1 - EMA_ALPHA) * old_avg, 1)
    # Clamp to reasonable range
    new_avg = max(2, min(new_avg, 120))
    db.doctors.update_one({'doctor_id': doctor_id}, {'$set': {'ema_avg': new_avg}})


def get_wait_estimate(clinic_id, doctor_id, position):
    """Wait = position * doctor's current EMA avg."""
    doctor = get_doctor(doctor_id)
    avg = (doctor or {}).get('ema_avg', DEFAULT_AVG)
    return round(position * avg, 1)


# ─── Doctor / Clinic ops ─────────────────────────────────────────────────

def get_doctors(clinic_id):
    return list(get_db().doctors.find({'clinic_id': clinic_id}))


def get_doctor(doctor_id):
    return get_db().doctors.find_one({'doctor_id': doctor_id})


def get_doctor_by_letter(clinic_id, letter):
    return get_db().doctors.find_one({'clinic_id': clinic_id, 'letter': letter})


def get_doctor_by_username(username):
    return get_db().doctors.find_one({'username': username})


def get_clinic(clinic_id):
    return get_db().clinics.find_one({'clinic_id': clinic_id})


def get_position(token_id):
    token = get_token(token_id)
    if not token or token['status'] != 'waiting':
        return 0
    queue = get_queue(token['clinic_id'], token['doctor_id'])
    for i, t in enumerate(queue):
        if t['token_id'] == token_id:
            return i + 1
    return 0


def get_stats(clinic_id, doctor_id):
    db = get_db()
    base = {'clinic_id': clinic_id, 'doctor_id': doctor_id}
    if isinstance(db, _InMemoryDB):
        all_today = list(db.tokens.find(base))
    else:
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        all_today = list(db.tokens.find({**base, 'check_in_time': {'$gte': today_start}}))

    seen = [t for t in all_today if t['status'] == 'seen']
    no_shows = [t for t in all_today if t['status'] == 'no_show']
    waiting = [t for t in all_today if t['status'] == 'waiting']
    doctor = get_doctor(doctor_id)
    ema = (doctor or {}).get('ema_avg', DEFAULT_AVG)

    return {
        'total_today': len(all_today),
        'seen': len(seen),
        'no_shows': len(no_shows),
        'waiting': len(waiting),
        'ema_avg': ema,
    }


def reset_clinic_day(clinic_id):
    db = get_db()
    db.tokens.delete_many({'clinic_id': clinic_id})
    # Reset EMA to default
    for d in get_doctors(clinic_id):
        db.doctors.update_one({'doctor_id': d['doctor_id']}, {'$set': {'ema_avg': DEFAULT_AVG}})
