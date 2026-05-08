# GateGuard – Quick Start Guide

## ⚡ 5-Minute Setup

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Run the Application
```bash
python app.py
```

You'll see:
```
============================================================
  College Gate Monitor  –  Starting on http://0.0.0.0:5000
  Admin login: admin@college.edu / admin123
============================================================
```

### Step 3: Open in Browser
Navigate to **http://localhost:5000**

---

## 🔑 First Login

### Admin Access
- **Email:** `admin@college.edu`
- **Password:** `admin123`

### Create Student Account
1. Click **REGISTER** tab
2. Fill in details (name, student ID, email, phone, password)
3. Click **CREATE ACCOUNT**
4. Use new credentials to login as student

---

## 🎥 Testing the System

### Option A: With Webcam (Live Detection)
1. Login as Admin
2. Go to **Live Camera** page
3. Click **▶ START** button
4. System starts real-time plate detection

### Option B: Without Webcam (Test with Images)
1. Login as Admin
2. Go to **Live Camera** page
3. Upload an image with a license plate in it
4. System detects and logs the plate
5. Check the detection in **DETECTION LOG**

### Option C: Manual Logging
1. Login as Admin
2. Go to **Live Camera** page
3. Scroll to **MANUAL PLATE ENTRY**
4. Enter plate number (e.g., `DL 01 AB 1234`)
5. Select ENTRY or EXIT
6. Click **LOG**

---

## 📋 Example Workflows

### Workflow 1: Student Registers Vehicle
1. Student login with email & password
2. Go to **Register Vehicle**
3. Enter license plate: `DL 01 AB 1234`
4. Select type: **Car**
5. Fill optional fields (make, model, color)
6. Click **REGISTER VEHICLE**
7. Vehicle appears in **My Vehicles**

### Workflow 2: Track Vehicle Movement
1. Admin detects student's vehicle plate at gate (via camera or image upload)
2. System automatically logs as **ENTRY** (first time)
3. Student sees entry in their **My Logs**
4. Admin logs same plate as **EXIT** (manual or auto-detection)
5. Both entry & exit appear in logs with timestamps

### Workflow 3: Check Dashboard Stats
1. Login as Admin
2. **Dashboard** shows:
   - Total registered vehicles
   - Entries today
   - Exits today
   - Currently inside campus
   - Registered students
3. Scroll down for **Recent Activity** table

---

## 🚗 Supported Plate Formats

### Indian Plate Patterns (Automatically Detected)
- **Standard:** `DL 01 AB 1234` (State + District + Series + Number)
- **Variants:** `DL 01 ABC 123`, `MH 02 D 1234`
- **Auto-Format:** Raw OCR text cleaned and formatted

### Manual Entry
Type plates as:
- `DL01AB1234` (spaces removed, auto-formatted)
- `dl 01 ab 1234` (case-insensitive)
- `DL-01-AB-1234` (dashes removed)

---

## 📊 Dashboard Pages

### Admin Dashboard
| Page | Purpose |
|------|---------|
| **Dashboard** | Stats, trends, recent activity |
| **Live Camera** | Real-time feed, image upload, manual entry |
| **Currently Inside** | Vehicles in campus now |
| **Vehicle Logs** | Search, filter, export all logs |
| **Registered Vehicles** | All vehicles with owner info |
| **Students** | All registered student accounts |

### Student Panel
| Page | Purpose |
|------|---------|
| **My Vehicles** | Register, view, delete own vehicles |
| **Register Vehicle** | Add new vehicle to account |
| **My Logs** | Entry/exit history for own vehicles |
| **Profile** | View & update account info |

---

## 🔍 How Detection Works

```
Camera Feed
    ↓
OpenCV Captures Frame (1280×720)
    ↓
EasyOCR Reads Text
    ↓
Validate Against Indian Plate Pattern
    ↓
Format Plate (DL 01 AB 1234)
    ↓
Check Confidence (>25%)
    ↓
Log to Database
    ↓
Broadcast via WebSocket
    ↓
Dashboard & Admin Alerts Update in Real-Time
```

### Key Points:
- **Automatic Entry/Exit:** First detection = ENTRY, second = EXIT
- **Cooldown:** Same plate won't trigger again for 8 seconds
- **Confidence:** Shows detection accuracy (98.5%, etc.)
- **Registered:** Shows owner name if vehicle registered, else "Unknown"

---

## 🔐 Default Credentials

| Role | Email | Password | Notes |
|------|-------|----------|-------|
| Admin | `admin@college.edu` | `admin123` | ⚠️ Change immediately in production |

---

## 📁 Project Structure

```
gate-vehicle-guard/
├── app.py                 # Flask application & routes
├── database.py            # SQLite database layer
├── plate_detector.py      # ANPR engine (OpenCV + EasyOCR)
├── requirements.txt       # Python dependencies
├── README.md             # Full documentation
├── QUICKSTART.md         # This file
├── .gitignore            # Git ignore rules
├── login.html            # Login/Register UI
├── admin.html            # Admin dashboard
├── student.html          # Student portal
└── college_gate.db       # SQLite database (auto-created)
```

---

## 🐛 Common Issues & Fixes

### Issue: "Camera not found"
**Solution:**
```bash
# Check camera index (0, 1, 2...)
python -c "import cv2; cap = cv2.VideoCapture(0); print('OK' if cap.isOpened() else 'FAIL')"
```

### Issue: "EasyOCR taking too long to load"
**Solution:**
- First run downloads ~200MB OCR model
- Runs in background; wait for "EasyOCR ready" in logs
- Subsequent runs are instant

### Issue: "Port 5000 already in use"
**Solution:**
Edit `app.py` line 402:
```python
socketio.run(app, host='0.0.0.0', port=5001, debug=True)  # Use 5001 instead
```

### Issue: "Database locked"
**Solution:**
```bash
rm college_gate.db
python app.py  # Recreates clean database
```

### Issue: "WebSocket connection failed"
**Solution:**
- Ensure `python-socketio` and `python-engineio` installed
- Check browser console for errors
- Try refreshing page

---

## 🚀 Next Steps

1. **Customize Admin Password:** Update default credentials in `database.py`
2. **Configure Camera:** Test with different camera indices if multiple cameras
3. **Adjust Plate Patterns:** Edit `PLATE_PATTERNS` in `plate_detector.py` for other countries
4. **Set Cooldown:** Change `_cooldown` value in `plate_detector.py` (default: 8 seconds)
5. **Deploy:** Use Gunicorn + Nginx for production

---

## 📞 Support

**File Structure Issues?**
```bash
# Verify all files exist
ls -la *.py *.html *.txt *.md
```

**Import Errors?**
```bash
pip list  # Check all packages installed
pip install --upgrade -r requirements.txt
```

**Database Issues?**
```bash
# Start fresh
rm college_gate.db
python app.py
```

---

## ✅ Checklist Before Production

- [ ] Change default admin password
- [ ] Enable HTTPS/SSL
- [ ] Set up database backups
- [ ] Configure proper logging
- [ ] Test with multiple users
- [ ] Optimize OCR for your plate format
- [ ] Deploy with Gunicorn/uWSGI
- [ ] Set up monitoring/alerts

---

**Ready to go! 🎉**

Start with the admin dashboard to explore the system and understand the workflow.

For detailed documentation, see **README.md**
