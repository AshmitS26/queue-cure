"""
Views — pages + REST API + auth.

Auth:
  Receptionist: single account (reception / clinic@123)
  Doctors: separate per doctor (doctorA / docA@123, etc.)
"""
import io
import json
import qrcode
from datetime import datetime
from functools import wraps

from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from clinic import db

RECEPTIONIST_CREDS = {'username': 'reception', 'password': 'clinic@123'}


# ─── Auth decorators ─────────────────────────────────────────────────────

def receptionist_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.session.get('receptionist_logged_in'):
            return redirect(f'/login/receptionist/?next={request.path}')
        return view_func(request, *args, **kwargs)
    return wrapper


def doctor_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.session.get('doctor_id'):
            return redirect(f'/login/doctor/?next={request.path}')
        return view_func(request, *args, **kwargs)
    return wrapper


# ─── Serialization ───────────────────────────────────────────────────────

def _serialize_token(token):
    if not token:
        return None
    return {
        'token_id': token['token_id'],
        'patient_name': token['patient_name'],
        'phone': token.get('phone', ''),
        'status': token['status'],
        'clinic_id': token['clinic_id'],
        'doctor_id': token['doctor_id'],
        'fees': token.get('fees', 0),
        'payment_method': token.get('payment_method', ''),
        'check_in_time': token['check_in_time'].isoformat() if token.get('check_in_time') else None,
        'called_at': token['called_at'].isoformat() if token.get('called_at') else None,
        'notes': token.get('notes', ''),
    }


def _serialize_doctor(d):
    if not d:
        return None
    return {
        'doctor_id': d['doctor_id'],
        'letter': d.get('letter', '?'),
        'name': d['name'],
        'specialty': d.get('specialty', ''),
        'room': d.get('room', ''),
        'fees': d.get('fees', 0),
        'timings': d.get('timings', ''),
        'ema_avg': d.get('ema_avg', 10),
    }


def _broadcast(clinic_id, doctor_id):
    """Push queue update to all WS subscribers of this clinic+doctor."""
    channel_layer = get_channel_layer()
    if not channel_layer:
        return
    queue = db.get_queue(clinic_id, doctor_id)
    current = db.get_current_called(clinic_id, doctor_id)
    doctor = db.get_doctor(doctor_id) or {}
    payload = {
        'type': 'queue_update',
        'doctor_id': doctor_id,
        'current_called': _serialize_token(current),
        'queue': [_serialize_token(t) for t in queue],
        'queue_length': len(queue),
        'ema_avg': doctor.get('ema_avg', 10),
        'timestamp': datetime.utcnow().isoformat(),
    }
    async_to_sync(channel_layer.group_send)(f'clinic_{clinic_id}_{doctor_id}', payload)
    # Also broadcast to the global live-board group
    _broadcast_live_board(clinic_id)


def _broadcast_live_board(clinic_id):
    """Push live board data (all doctors' queues) to home page subscribers."""
    channel_layer = get_channel_layer()
    if not channel_layer:
        return
    board = _build_live_board(clinic_id)
    async_to_sync(channel_layer.group_send)(f'liveboard_{clinic_id}', {
        'type': 'liveboard_update',
        'board': board,
    })


def _build_live_board(clinic_id):
    """Build the public live queue board data."""
    doctors = db.get_doctors(clinic_id)
    entries = []
    for d in doctors:
        current = db.get_current_called(clinic_id, d['doctor_id'])
        queue = db.get_queue(clinic_id, d['doctor_id'])
        ema = d.get('ema_avg', 10)

        if current:
            entries.append({
                'token_id': current['token_id'],
                'room': d.get('room', ''),
                'doctor_name': d['name'],
                'doctor_letter': d.get('letter', '?'),
                'status': 'called',
                'wait_minutes': 0,
            })
        for i, t in enumerate(queue):
            wait = round((i + 1) * ema, 1)
            entries.append({
                'token_id': t['token_id'],
                'room': d.get('room', ''),
                'doctor_name': d['name'],
                'doctor_letter': d.get('letter', '?'),
                'status': 'waiting',
                'wait_minutes': wait,
            })
    return entries


# ─── Login / Logout ──────────────────────────────────────────────────────

def login_view(request, role):
    if role not in ('receptionist', 'doctor'):
        raise Http404()

    next_url = request.GET.get('next') or request.POST.get('next', '')
    error = None

    if role == 'receptionist':
        if request.session.get('receptionist_logged_in'):
            return redirect(next_url or '/receptionist/')
        if request.method == 'POST':
            u = request.POST.get('username', '').strip()
            p = request.POST.get('password', '').strip()
            if u == RECEPTIONIST_CREDS['username'] and p == RECEPTIONIST_CREDS['password']:
                request.session['receptionist_logged_in'] = True
                request.session.set_expiry(28800)
                return redirect(next_url or '/receptionist/')
            error = 'Incorrect username or password.'
        return render(request, 'login.html', {
            'role': 'receptionist', 'role_label': 'Receptionist',
            'role_icon': '💼', 'error': error, 'next': next_url,
            'demo_user': 'reception', 'demo_pass': 'clinic@123',
        })

    else:  # doctor
        if request.session.get('doctor_id'):
            return redirect(next_url or '/doctor/')
        if request.method == 'POST':
            u = request.POST.get('username', '').strip()
            p = request.POST.get('password', '').strip()
            doc = db.get_doctor_by_username(u)
            if doc and doc.get('password') == p:
                request.session['doctor_id'] = doc['doctor_id']
                request.session['doctor_name'] = doc['name']
                request.session.set_expiry(28800)
                return redirect(next_url or '/doctor/')
            error = 'Incorrect username or password.'
        # Build credentials hint for all doctors
        doctors = db.get_doctors('C001')
        return render(request, 'login.html', {
            'role': 'doctor', 'role_label': 'Doctor',
            'role_icon': '🩺', 'error': error, 'next': next_url,
            'doctors': doctors,
        })


def logout_view(request, role):
    if role == 'receptionist':
        request.session.pop('receptionist_logged_in', None)
    elif role == 'doctor':
        request.session.pop('doctor_id', None)
        request.session.pop('doctor_name', None)
    return redirect('/')


# ─── Page renderers ──────────────────────────────────────────────────────

def home(request):
    clinic = db.get_clinic('C001')
    doctors = db.get_doctors('C001')
    board = _build_live_board('C001')
    return render(request, 'home.html', {
        'clinic': clinic,
        'doctors': [_serialize_doctor(d) for d in doctors],
        'board': json.dumps(board),
    })


def patient_checkin_page(request):
    clinic_id = request.GET.get('clinic', 'C001')
    doctor_id = request.GET.get('doctor', '')
    clinic = db.get_clinic(clinic_id)
    doctors = db.get_doctors(clinic_id)
    return render(request, 'patient_checkin.html', {
        'clinic': clinic,
        'doctors': [_serialize_doctor(d) for d in doctors],
        'doctors_json': json.dumps([_serialize_doctor(d) for d in doctors]),
        'preselected_doctor': doctor_id,
    })


def patient_status_page(request, token_id):
    token = db.get_token(token_id)
    if not token:
        raise Http404("Token not found")
    doctor = db.get_doctor(token['doctor_id'])
    clinic = db.get_clinic(token['clinic_id'])
    return render(request, 'patient_status.html', {
        'token': token,
        'doctor': doctor,
        'clinic': clinic,
    })


@receptionist_required
def receptionist_page(request):
    clinic_id = 'C001'
    clinic = db.get_clinic(clinic_id)
    doctors = db.get_doctors(clinic_id)
    return render(request, 'receptionist.html', {
        'clinic': clinic,
        'doctors': [_serialize_doctor(d) for d in doctors],
        'doctors_json': json.dumps([_serialize_doctor(d) for d in doctors]),
    })


@doctor_required
def doctor_page(request):
    doctor_id = request.session.get('doctor_id')
    doctor = db.get_doctor(doctor_id)
    if not doctor:
        return redirect('/logout/doctor/')
    clinic = db.get_clinic(doctor['clinic_id'])
    return render(request, 'doctor.html', {
        'doctor': doctor,
        'clinic': clinic,
    })


def clinic_qr(request, clinic_id):
    doctor_id = request.GET.get('doctor', '')
    url = request.build_absolute_uri(f'/checkin/?clinic={clinic_id}')
    if doctor_id:
        url += f'&doctor={doctor_id}'
    img = qrcode.make(url)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return HttpResponse(buf.getvalue(), content_type='image/png')


# ─── REST API ────────────────────────────────────────────────────────────

@csrf_exempt
@require_http_methods(['POST'])
def api_checkin(request):
    try:
        data = json.loads(request.body)
        clinic_id = data['clinic_id']
        doctor_id = data['doctor_id']
        patient_name = data['patient_name'].strip()
        phone = data.get('phone', '').strip()
        payment = data.get('payment_method', '')
        if not patient_name:
            return JsonResponse({'error': 'Name required'}, status=400)
        token = db.create_token(clinic_id, doctor_id, patient_name, phone, payment)
        _broadcast(clinic_id, doctor_id)
        return JsonResponse({
            'success': True,
            'token': _serialize_token(token),
            'redirect_url': f'/status/{token["token_id"]}/',
        })
    except (KeyError, json.JSONDecodeError) as e:
        return JsonResponse({'error': f'Bad request: {e}'}, status=400)


@require_http_methods(['GET'])
def api_queue(request, clinic_id, doctor_id):
    queue = db.get_queue(clinic_id, doctor_id)
    current = db.get_current_called(clinic_id, doctor_id)
    doctor = db.get_doctor(doctor_id) or {}
    return JsonResponse({
        'queue': [_serialize_token(t) for t in queue],
        'current_called': _serialize_token(current),
        'queue_length': len(queue),
        'ema_avg': doctor.get('ema_avg', 10),
    })


@require_http_methods(['GET'])
def api_token_status(request, token_id):
    token = db.get_token(token_id)
    if not token:
        return JsonResponse({'error': 'Not found'}, status=404)
    position = db.get_position(token_id)
    doctor = db.get_doctor(token['doctor_id']) or {}
    ema = doctor.get('ema_avg', 10)
    return JsonResponse({
        'token': _serialize_token(token),
        'position': position,
        'estimated_wait_minutes': round(position * ema, 1),
        'room': doctor.get('room', ''),
    })


@csrf_exempt
@require_http_methods(['POST'])
def api_call_next(request, clinic_id, doctor_id):
    next_token = db.call_next(clinic_id, doctor_id)
    _broadcast(clinic_id, doctor_id)
    return JsonResponse({'success': True, 'called': _serialize_token(next_token)})


@csrf_exempt
@require_http_methods(['POST'])
def api_mark_done(request, clinic_id, doctor_id):
    try:
        data = json.loads(request.body) if request.body else {}
        notes = data.get('notes', '')
        token = db.mark_done_current(clinic_id, doctor_id, notes)
        _broadcast(clinic_id, doctor_id)
        return JsonResponse({'success': True, 'token': _serialize_token(token)})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@csrf_exempt
@require_http_methods(['POST'])
def api_update_status(request, token_id):
    try:
        data = json.loads(request.body)
        status = data['status']
        notes = data.get('notes')
        if status not in ('waiting', 'called', 'seen', 'no_show', 'skipped'):
            return JsonResponse({'error': 'Invalid status'}, status=400)
        token = db.update_token_status(token_id, status, notes)
        if token:
            _broadcast(token['clinic_id'], token['doctor_id'])
        return JsonResponse({'success': True, 'token': _serialize_token(token)})
    except (KeyError, json.JSONDecodeError) as e:
        return JsonResponse({'error': f'Bad request: {e}'}, status=400)


@require_http_methods(['GET'])
def api_stats(request, clinic_id, doctor_id):
    return JsonResponse(db.get_stats(clinic_id, doctor_id))


@require_http_methods(['GET'])
def api_doctors(request, clinic_id):
    doctors = db.get_doctors(clinic_id)
    return JsonResponse({'doctors': [_serialize_doctor(d) for d in doctors]})


@require_http_methods(['GET'])
def api_live_board(request, clinic_id):
    return JsonResponse({'board': _build_live_board(clinic_id)})


@csrf_exempt
@require_http_methods(['POST'])
def api_reset(request, clinic_id):
    db.reset_clinic_day(clinic_id)
    for d in db.get_doctors(clinic_id):
        _broadcast(clinic_id, d['doctor_id'])
    return JsonResponse({'success': True})


# ─── Demo page ───────────────────────────────────────────────────────────

DEMO_PATIENTS = [
    {'name': 'Aarav Sharma',   'phone': '9810012345', 'doctor': 'D001', 'pay': 'upi'},
    {'name': 'Priya Mehta',    'phone': '9820023456', 'doctor': 'D001', 'pay': 'cash'},
    {'name': 'Rahul Verma',    'phone': '9830034567', 'doctor': 'D001', 'pay': 'upi'},
    {'name': 'Sneha Iyer',     'phone': '9840045678', 'doctor': 'D002', 'pay': 'cash'},
    {'name': 'Karan Patel',    'phone': '9850056789', 'doctor': 'D002', 'pay': 'upi'},
    {'name': 'Anjali Singh',   'phone': '9860067890', 'doctor': 'D003', 'pay': 'cash'},
    {'name': 'Vikram Nair',    'phone': '9870078901', 'doctor': 'D004', 'pay': 'upi'},
]


def demo_page(request):
    clinic = db.get_clinic('C001')
    doctors = db.get_doctors('C001')
    tech = [
        {'icon': '🐍', 'name': 'Django 4.2', 'role': 'Backend framework'},
        {'icon': '🔌', 'name': 'Channels', 'role': 'WebSocket / ASGI'},
        {'icon': '🍃', 'name': 'MongoDB', 'role': 'Database'},
        {'icon': '🎨', 'name': 'Vanilla JS', 'role': 'Frontend'},
        {'icon': '📡', 'name': 'WebSocket', 'role': 'Real-time sync'},
        {'icon': '📊', 'name': 'EMA Algorithm', 'role': 'Wait estimation'},
        {'icon': '🚂', 'name': 'Railway', 'role': 'Deployment'},
        {'icon': '☁️', 'name': 'Atlas', 'role': 'Cloud database'},
    ]
    return render(request, 'demo.html', {
        'clinic': clinic,
        'doctors': json.dumps([_serialize_doctor(d) for d in doctors]),
        'doctors_list': [_serialize_doctor(d) for d in doctors],
        'tech': tech,
    })


@csrf_exempt
@require_http_methods(['POST'])
def api_demo_populate(request):
    """Populate demo data — reset queue then add sample patients and call first."""
    clinic_id = 'C001'
    # Reset
    db.reset_clinic_day(clinic_id)
    tokens = []
    for p in DEMO_PATIENTS:
        token = db.create_token(clinic_id, p['doctor'], p['name'], p['phone'], p['pay'])
        tokens.append(_serialize_token(token))

    # Call first patient for Doctor A and Doctor B
    db.call_next(clinic_id, 'D001')
    db.call_next(clinic_id, 'D002')

    # Broadcast all
    doctors = db.get_doctors(clinic_id)
    for d in doctors:
        _broadcast(clinic_id, d['doctor_id'])

    return JsonResponse({'success': True, 'tokens': tokens})
