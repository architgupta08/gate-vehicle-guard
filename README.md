# GateGuard – College Vehicle Monitoring System

A real-time **Automatic Number Plate Recognition (ANPR)** system for monitoring vehicle entry/exit at college gates. Built with Flask, OpenCV, and EasyOCR.

## 🎯 Features

### Student Dashboard
- 📋 Register personal vehicles (car, bike, etc.)
- 🔍 View vehicle entry/exit logs
- 👤 Account management (name, email, phone, student ID)

### Admin Dashboard  
- 🎥 Real-time live camera feed with license plate detection
- 📊 Dashboard with statistics (entries, exits, vehicles currently inside)
- 📈 Hourly and weekly traffic trends
- 🚗 Complete vehicle & entry/exit logs with search/filter
- 👥 User & vehicle management
- 📸 Manual entry/exit logging
- 🖼️ Image upload for offline detection

### Core System
- ✅ Real-time ANPR using OpenCV + EasyOCR
- ✅ Indian number plate validation & formatting
- ✅ SQLite database with comprehensive logging
- ✅ WebSocket live updates (Socket.IO)
- ✅ Automatic entry/exit detection with cooldown
- ✅ Confidence scoring for detections
- ✅ Registered vs unregistered vehicle tracking

---

## 📋 Prerequisites

- **Python 3.8+**
- **Webcam** (for live detection, optional for image uploads)
- **ffmpeg** (for OpenCV video codec support)

### Install ffmpeg:
```bash
# Ubuntu/Debian
sudo apt-get install ffmpeg

# macOS
brew install ffmpeg

# Windows
# Download from https://ffmpeg.org/download.html
```

---

## 🚀 Installation & Setup

### 1. Clone Repository
```bash
git clone https://github.com/architgupta08/gate-vehicle-guard.git
cd gate-vehicle-guard
```

### 2. Create Virtual Environment
```bash
python -m venv venv
source venv/bin/activate      # Linux/Mac
venv\Scripts\activate          # Windows
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Run Application
```bash
python app.py
```

The server starts on **http://localhost:5000**

---

## 🔐 Default Credentials

| Role  | Email | Password |
|-------|-------|----------|
| Admin | `admin@college.edu` | `admin123` |

⚠️ **Change admin password in production!**

---

## 📖 Usage Guide

### Admin Workflow
1. Login with admin credentials
2. Start camera from dashboard
3. View real-time detections and logs
4. Check statistics and trends
5. Manage users and vehicles

### Student Workflow
1. Register account with student ID
2. Add vehicle(s) with license plate
3. View entry/exit logs for personal vehicles
4. Update account details

### System Operation
- **Entry Detection**: Camera detects new plate → logs entry → broadcasts to all connected clients
- **Exit Detection**: Same plate detected again → logs exit (automatic state tracking)
- **Cooldown**: Same plate won't trigger multiple times within 8 seconds
- **Registration**: Registered vehicles show owner info; unregistered marked as "Unknown"

---

## 📊 Database Schema

### users
- id, name, email, password_hash, role (admin/student), student_id, phone, created_at

### vehicles  
- id, user_id, plate_number (unique), vehicle_type, make, model_name, color, description, registered_at

### logs
- id, plate_number, vehicle_id, log_type (entry/exit), timestamp, confidence, notes

**Indices**: plate_number, timestamp for fast queries

---

## 🎥 Camera & Detection

### Supported Camera Indices
- `0` = Default system camera
- `1`, `2`, etc. = Additional cameras if available

### Plate Detection Process
1. Capture frame (1280×720)
2. EasyOCR reads text
3. Validate against Indian plate patterns
4. Format: `XX 00 XXX 0000` (e.g., DL 01 ABC 1234)
5. Check confidence threshold (25%+)
6. Log to database & broadcast via WebSocket

### OCR Fallback
- Primary: EasyOCR (GPU-capable)
- Fallback: Tesseract (if installed)
- Manual: Image upload or manual entry

---

## 🛠️ API Endpoints

### Authentication
- `POST /api/auth/login` – Login with email & password
- `POST /api/auth/register` – Create student account
- `POST /api/auth/logout` – Logout
- `GET /api/auth/me` – Get current user info

### Vehicles
- `GET /api/vehicles` – List user/all vehicles
- `POST /api/vehicles` – Add vehicle
- `DELETE /api/vehicles/<id>` – Remove vehicle

### Logs
- `GET /api/logs` – Paginated logs with filters
- `GET /api/logs/live` – Last 25 logs (live view)
- `GET /api/logs/inside` – Vehicles currently inside
- `POST /api/logs/manual` – Manual entry/exit (admin)

### Camera
- `POST /api/camera/start` – Start camera detection
- `POST /api/camera/stop` – Stop camera
- `GET /api/camera/status` – Check camera status
- `GET /api/camera/feed` – MJPEG stream for live view

### Detection
- `POST /api/detect/image` – Detect plates from uploaded image

### Admin Only
- `GET /api/stats` – Dashboard statistics
- `GET /api/admin/users` – All users

---

## 🔌 WebSocket Events

### Client emits:
- `ping_status` – Check system status

### Server broadcasts:
- `plate_detected` – New plate detected (auto-entry/exit)
- `status` – Camera & OCR readiness

**Event format:**
```json
{
  "plate": "DL 01 ABC 1234",
  "type": "entry|exit",
  "registered": true,
  "owner": "Rahul Sharma",
  "timestamp": "2024-11-20T14:30:45.123456",
  "confidence": 98.5,
  "manual": false
}
```

---

## 🎨 UI Components

### Login Page
- Beautiful sci-fi theme with grid background
- Dual-tab system (Login/Register)
- Role selector (Student/Admin)
- Real-time clock & status bar

### Admin Dashboard
- **Live Feed**: Real-time camera view with detected plates overlay
- **Stats Panel**: Entry/exit counts, registered vehicles, unregistered today
- **Charts**: Hourly bar chart, 7-day trend
- **Vehicles Inside**: Real-time list of vehicles currently in campus
- **Logs Table**: Paginated, searchable, filterable by date/type
- **Camera Controls**: Start/Stop with status indicator
- **Manual Logging**: Quick entry/exit input

### Student Panel
- **My Vehicles**: Register, view, delete vehicles
- **My Logs**: Searchable entry/exit history for own vehicles
- **Profile**: View & update account info

---

## 🐛 Troubleshooting

### Camera not opening
```bash
# Check camera permissions (Linux)
ls -la /dev/video*

# Test with OpenCV
python -c "import cv2; cap = cv2.VideoCapture(0); print('OK' if cap.isOpened() else 'FAIL')"
```

### EasyOCR model download fails
```bash
# Download manually
python -c "import easyocr; easyocr.Reader(['en'])"
```

### Port 5000 already in use
```bash
# Change port in app.py line 402
socketio.run(app, host='0.0.0.0', port=5001, debug=True)
```

### Database locked
```bash
# Remove old database
rm college_gate.db
# Will reinitialize on next run
```

---

## 📝 Configuration

Edit these variables in source files:

**app.py:**
- `app.secret_key` – Change session secret
- Host/port in `socketio.run()`

**database.py:**
- `db_path` – SQLite file location

**plate_detector.py:**
- `_cooldown` – Seconds before same plate triggers again
- `PLATE_PATTERNS` – Regex for different Indian plate formats

---

## 🔒 Security Notes

1. **Change default admin password** before production
2. **Use HTTPS** in production (configure Flask properly)
3. **Environment variables** for sensitive data
4. **Rate limiting** on API endpoints recommended
5. **Input validation** on all user inputs
6. **Database backups** for operational continuity

---

## 🚀 Deployment

### Gunicorn + Nginx (Production)
```bash
pip install gunicorn
gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:8000 app:app
```

Then configure Nginx as reverse proxy.

### Docker
Create `Dockerfile`:
```dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN apt-get update && apt-get install -y ffmpeg
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "app.py"]
```

Build & run:
```bash
docker build -t gateguard .
docker run -p 5000:5000 gateguard
```

---

## 📞 Support & Issues

- Check logs in console for errors
- Verify camera permissions
- Ensure dependencies installed: `pip list`
- Test with sample image upload first

---

## 📄 License

This project is provided as-is for educational purposes.

---

**Last Updated:** November 2024  
**Version:** 2.0
