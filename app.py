"""
College Gate Monitor – Flask Backend
Real-time ANPR vehicle tracking system for college gates.
"""

import time
import base64
from datetime import datetime
from functools import wraps

from flask import (Flask, render_template, request, jsonify,
                   session, redirect, url_for, Response)
from flask_socketio import SocketIO, emit
from werkzeug.security import generate_password_hash, check_password_hash

from database import Database
from plate_detector import PlateDetector, fuzzy_match_plate
from plate_detector import PlateDetector

# ─────────────────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = 'cgm-super-secret-key-change-in-prod-2024'
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

db       = Database()
detector = PlateDetector()


# ─────────────────────────────────────────────────────────────────────────────
#  Decorators
# ─────────────────────────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            if request.is_json:
                return jsonify({'error': 'Unauthorized'}), 401
            return redirect('/')
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Unauthorized'}), 401
        if session.get('role') != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated


# ─────────────────────────────────────────────────────────────────────────────
#  Page routes
# ─────────────────────────────────────────────────────────────────────────────
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect('/admin' if session['role'] == 'admin' else '/student')
    return render_template('login.html')


@app.route('/admin')
def admin_page():
    if session.get('role') != 'admin':
        return redirect('/')
    return render_template('admin.html',
                           user_name=session.get('name', 'Admin'))


@app.route('/student')
def student_page():
    if session.get('role') not in ('student', 'admin'):
        return redirect('/')
    return render_template('student.html',
                           user_name=session.get('name', 'Student'))


# ─────────────────────────────────────────────────────────────────────────────
#  Auth API
# ─────────────────────────────────────────────────────────────────────────────
@app.route('/api/auth/login', methods=['POST'])
def api_login():
    data = request.get_json(force=True)
    user = db.get_user_by_email(data.get('email', '').strip())
    if user and check_password_hash(user['password'], data.get('password', '')):
        session.permanent = True
        session['user_id'] = user['id']
        session['role']    = user['role']
        session['name']    = user['name']
        return jsonify({'success': True,
                        'role': user['role'],
                        'name': user['name']})
    return jsonify({'error': 'Invalid email or password'}), 401


@app.route('/api/auth/logout', methods=['POST'])
def api_logout():
    session.clear()
    return jsonify({'success': True})


@app.route('/api/auth/register', methods=['POST'])
def api_register():
    data = request.get_json(force=True)
    required = ['name', 'email', 'password']
    if not all(data.get(k) for k in required):
        return jsonify({'error': 'Name, email and password are required'}), 400

    if db.get_user_by_email(data['email']):
        return jsonify({'error': 'Email already registered'}), 409

    user_id = db.create_user(
        name       = data['name'].strip(),
        email      = data['email'].strip().lower(),
        password   = generate_password_hash(data['password']),
        role       = 'student',
        student_id = data.get('student_id', '').strip(),
        phone      = data.get('phone', '').strip(),
    )
    return jsonify({'success': True, 'user_id': user_id}), 201


@app.route('/api/auth/me')
@login_required
def api_me():
    user = db.get_user_by_id(session['user_id'])
    return jsonify({k: user[k] for k in
                    ('id', 'name', 'email', 'role', 'student_id', 'phone')})


# ─────────────────────────────────────────────────────────────────────────────
#  Vehicles API
# ─────────────────────────────────────────────────────────────────────────────
@app.route('/api/vehicles', methods=['GET'])
@login_required
def api_get_vehicles():
    if session['role'] == 'admin':
        return jsonify(db.get_all_vehicles())
    return jsonify(db.get_user_vehicles(session['user_id']))


@app.route('/api/vehicles', methods=['POST'])
@login_required
def api_add_vehicle():
    data = request.get_json(force=True)
    plate = data.get('plate_number', '').upper().strip()
    if not plate:
        return jsonify({'error': 'Plate number required'}), 400

    # Normalize: remove spaces
    plate_norm = plate.replace(' ', '')

    try:
        vid = db.add_vehicle(
            user_id      = session['user_id'],
            plate_number = plate,
            vehicle_type = data.get('vehicle_type', 'car'),
            make         = data.get('make', ''),
            model_name   = data.get('model_name', ''),
            color        = data.get('color', ''),
            description  = data.get('description', ''),
        )
        return jsonify({'success': True, 'vehicle_id': vid}), 201
    except Exception as e:
        if 'UNIQUE' in str(e):
            return jsonify({'error': 'Plate number already registered'}), 409
        return jsonify({'error': str(e)}), 500


@app.route('/api/vehicles/<int:vid>', methods=['DELETE'])
@login_required
def api_delete_vehicle(vid):
    uid = None if session['role'] == 'admin' else session['user_id']
    db.delete_vehicle(vid, uid)
    return jsonify({'success': True})


# ─────────────────────────────────────────────────────────────────────────────
#  Logs API
# ─────────────────────────────────────────────────────────────────────────────
@app.route('/api/logs', methods=['GET'])
@login_required
def api_get_logs():
    page       = int(request.args.get('page', 1))
    per_page   = int(request.args.get('per_page', 20))
    search     = request.args.get('search', '')
    date_f     = request.args.get('date', '')
    log_type   = request.args.get('type', '')

    if session['role'] == 'admin':
        logs, total = db.get_all_logs(page, per_page, search, date_f, log_type)
    else:
        logs, total = db.get_user_logs(session['user_id'], page, per_page)

    return jsonify({'logs': logs, 'total': total,
                    'page': page, 'per_page': per_page})


@app.route('/api/logs/live')
@login_required
def api_live_logs():
    return jsonify(db.get_recent_logs(25))


@app.route('/api/logs/inside')
@login_required
def api_inside():
    return jsonify(db.get_vehicles_inside())


@app.route('/api/logs/manual', methods=['POST'])
@admin_required
def api_manual_log():
    data  = request.get_json(force=True)
    plate = data.get('plate', '').upper().strip()
    ltype = data.get('type', 'entry')

    if not plate:
        return jsonify({'error': 'Plate required'}), 400

    # Try exact match
    vehicle = db.get_vehicle_by_plate(plate)
    
    # If no match, try fuzzy matching
    if not vehicle:
        from difflib import SequenceMatcher
        all_vehicles = db.get_all_vehicles()
        registered_plates = [v['plate_number'] for v in all_vehicles]
        
        best_plate, score = fuzzy_match_plate(plate, registered_plates, threshold=0.80)
        if best_plate:
            vehicle = db.get_vehicle_by_plate(best_plate)
            plate = best_plate

    if ltype == 'entry':
        db.log_entry(plate, vehicle['id'] if vehicle else None)
    else:
        db.log_exit(plate)

    event = {
        'plate':      plate,
        'type':       ltype,
        'registered': vehicle is not None,
        'owner':      vehicle['owner_name'] if vehicle else 'Unknown',
        'timestamp':  datetime.now().isoformat(),
        'confidence': 100,
        'manual':     True,
    }
    socketio.emit('plate_detected', event)
    return jsonify({'success': True, 'event': event})

# ─────────────────────────────────────────────────────────────────────────────
#  Stats API
# ─────────────────────────────────────────────────────────────────────────────
@app.route('/api/stats')
@admin_required
def api_stats():
    return jsonify(db.get_stats())


# ─────────────────────────────────────────────────────────────────────────────
#  Camera API
# ─────────────────────────────────────────────────────────────────────────────
def _on_plate_detected(plate_info: dict):
    """Callback from background camera thread → DB + SocketIO broadcast."""
    plate = plate_info['plate']
    
    # Try exact match first
    vehicle = db.get_vehicle_by_plate(plate)
    
    # If no exact match, try fuzzy matching
    if not vehicle:
        from difflib import SequenceMatcher
        all_vehicles = db.get_all_vehicles()
        registered_plates = [v['plate_number'] for v in all_vehicles]
        
        best_plate, score = fuzzy_match_plate(plate, registered_plates, threshold=0.80)
        if best_plate:
            vehicle = db.get_vehicle_by_plate(best_plate)
            plate = best_plate  # Use the matched plate
    
    inside = db.is_vehicle_inside(plate)

    if inside:
        db.log_exit(plate, confidence=plate_info['confidence'])
        ltype = 'exit'
    else:
        db.log_entry(plate,
                     vehicle['id'] if vehicle else None,
                     confidence=plate_info['confidence'])
        ltype = 'entry'

    socketio.emit('plate_detected', {
        'plate':      plate,
        'type':       ltype,
        'registered': vehicle is not None,
        'owner':      vehicle['owner_name'] if vehicle else 'Unknown',
        'timestamp':  plate_info['timestamp'],
        'confidence': plate_info['confidence'],
    })


@app.route('/api/camera/start', methods=['POST'])
@admin_required
def api_camera_start():
    data  = request.get_json(force=True) or {}
    index = int(data.get('camera_index', 0))
    ok    = detector.start_camera(callback=_on_plate_detected,
                                   camera_index=index)
    return jsonify({'success': ok,
                    'message': 'Camera started' if ok else 'Could not open camera'})


@app.route('/api/camera/stop', methods=['POST'])
@admin_required
def api_camera_stop():
    detector.stop_camera()
    return jsonify({'success': True})


@app.route('/api/camera/status')
@login_required
def api_camera_status():
    return jsonify({'running': detector.is_running,
                    'ocr_ready': detector.ocr_ready})


@app.route('/api/camera/feed')
def camera_feed():
    """MJPEG stream for live view."""
    def generate():
        while True:
            if detector.is_running:
                frame = detector.get_frame_jpeg()
            else:
                frame = detector.generate_demo_frame()

            if frame:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            time.sleep(0.05)

    return Response(generate(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


# ─────────────────────────────────────────────────────────────────────────────
#  Image upload detection
# ─────────────────────────────────────────────────────────────────────────────
@app.route('/api/detect/image', methods=['POST'])
@admin_required
def api_detect_image():
    plates = []

    if request.content_type and 'multipart' in request.content_type:
        f = request.files.get('image')
        if f:
            plates = detector.detect_from_bytes(f.read())
    else:
        data = request.get_json(force=True) or {}
        b64  = data.get('image_base64', '')
        if b64:
            plates = detector.detect_from_base64(b64)

    enriched = []
    for p in plates:
        plate   = p['plate']
        vehicle = db.get_vehicle_by_plate(plate)
        inside  = db.is_vehicle_inside(plate)
        ltype   = 'exit' if inside else 'entry'

        if inside:
            db.log_exit(plate, confidence=p['confidence'])
        else:
            db.log_entry(plate,
                         vehicle['id'] if vehicle else None,
                         confidence=p['confidence'])

        event = {**p,
                 'type':       ltype,
                 'registered': vehicle is not None,
                 'owner':      vehicle['owner_name'] if vehicle else 'Unknown'}
        socketio.emit('plate_detected', event)
        enriched.append(event)

    return jsonify({'success': True, 'plates': enriched,
                    'count': len(enriched)})


# ─────────────────────────────────────────────────────────────────────────────
#  Admin: Users management
# ─────────────────────────────────────────────────────────────────────────────
@app.route('/api/admin/users')
@admin_required
def api_all_users():
    return jsonify(db.get_all_users())


# ─────────────────────────────────────────────────────────────────────────────
#  WebSocket events
# ─────────────────────────────────────────────────────────────────────────────
@socketio.on('connect')
def on_connect():
    if 'user_id' not in session:
        return False          # reject unauthenticated socket connections
    emit('status', {'connected': True,
                    'camera': detector.is_running,
                    'ocr': detector.ocr_ready})


@socketio.on('ping_status')
def on_ping():
    emit('status', {'connected': True,
                    'camera': detector.is_running,
                    'ocr': detector.ocr_ready})


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print("=" * 60)
    print("  College Gate Monitor  –  Starting on http://0.0.0.0:5000")
    print("  Admin login: admin@college.edu / admin123")
    print("=" * 60)
    socketio.run(app, host='0.0.0.0', port=5000, debug=True,
                 allow_unsafe_werkzeug=True)
