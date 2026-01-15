from fastapi import FastAPI, HTTPException, Depends, status, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
import sqlite3
import os
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build
from dotenv import load_dotenv
from contextlib import asynccontextmanager

load_dotenv()

# Configuration
SECRET_KEY = os.getenv("JWT_SECRET", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

# Database path configuration for Vercel (read-only filesystem)
if os.path.exists("/tmp"):
    DATABASE_PATH = "/tmp/portal.db"
    print(f"Using temporary database at {DATABASE_PATH}")
else:
    DATABASE_PATH = "portal.db"
    print(f"Using local database at {DATABASE_PATH}")

# Global variables
sheets_service = None
student_cache = []

# Database initialization
def init_db():
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        # Students table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                roll_number TEXT UNIQUE NOT NULL,
                name TEXT,
                email TEXT NOT NULL,
                password TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Admins table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Sources table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sheet_id TEXT NOT NULL,
                range TEXT DEFAULT 'Sheet1!A2:Z',
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Manual Grades table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS manual_grades (
                sheet_id TEXT NOT NULL,
                roll_number TEXT NOT NULL,
                grade TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (sheet_id, roll_number)
            )
        ''')

        # Initialize Default Admin if Env Vars set (Persistence for Vercel)
        admin_email = os.getenv("ADMIN_EMAIL")
        admin_pass = os.getenv("ADMIN_PASSWORD")
        if admin_email and admin_pass:
            cursor.execute("SELECT * FROM admins WHERE email = ?", (admin_email,))
            if not cursor.fetchone():
                try:
                    # Late binding call to get_password_hash (defined below) is passing here because
                    # init_db is called in lifespan, after module load.
                    hashed = get_password_hash(admin_pass)
                    cursor.execute("INSERT INTO admins (name, email, password) VALUES (?, ?, ?)", ("Admin", admin_email, hashed))
                    print("✓ Default Admin initialized from Env")
                except Exception as e:
                    print(f"Auth Init skipped: {e}")

        # Initialize Default Sheet if Env Vars set
        default_sheet = os.getenv("DEFAULT_SHEET_ID")
        if default_sheet:
            cursor.execute("SELECT * FROM sources WHERE sheet_id = ?", (default_sheet,))
            if not cursor.fetchone():
                cursor.execute("INSERT INTO sources (sheet_id, range) VALUES (?, ?)", (default_sheet, "Sheet1!A2:Z"))
                print("✓ Default Sheet initialized from Env")

        conn.commit()
        conn.close()
        print("✓ Database initialized with defaults")
    except Exception as e:
        print(f"DB Init Error: {e}")

sheet_init_error = None

def initialize_google_sheets():
    global sheets_service, sheet_init_error
    try:
        credentials_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
        if not credentials_json:
            sheet_init_error = "GOOGLE_CREDENTIALS_JSON not found in env"
            print("⚠ Google Sheets credentials not configured")
            return False

        credentials_dict = json.loads(credentials_json)
        credentials = service_account.Credentials.from_service_account_info(
            credentials_dict,
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        sheets_service = build('sheets', 'v4', credentials=credentials)
        print("✓ Google Sheets initialized")
        return True
    except Exception as e:
        sheet_init_error = str(e)
        print(f"✗ Google Sheets initialization failed: {e}")
        return False

def fetch_students_from_sheets():
    global student_cache
    if not sheets_service:
        return []

    try:
        # Load sources from Permanent Google Sheet Config
        sources = get_sheet_sources()

       

        # Fallback to SQLite (Ephemeral) if no sheets configured
        if not sources:
            try:
                conn = sqlite3.connect(DATABASE_PATH)
                cursor = conn.cursor()
                cursor.execute("SELECT sheet_id, range FROM sources")
                db_sources = cursor.fetchall()
                conn.close()
                for s in db_sources:
                    sources.append((s[0], s[1]))
            except:
                pass

        all_students = []
        # Standard headers based on user request
        headers = ["Quiz 1", "Assigment 1", "Mid", "Quiz 2", "Assigment 2", "CCP", "CP", "Final", "Total"]

        for source in sources:
            # Handle both old 2-item and new 3-item tuple formats
            if len(source) == 3:
                sheet_id, range_val, name = source
            else:
                sheet_id, range_val = source
                name = "Unknown"

            print(f"\n=== Fetching from sheet: {name} ===")
            print(f"Sheet ID: {sheet_id}")
            print(f"Range: {range_val}")

            try:
                # Use default range if not specified or invalid (Sheet1!A2:Z skipping header)
                # Ideally we want A1:Z to see headers, but let's assume standard structure
                result = sheets_service.spreadsheets().values().get(
                    spreadsheetId=sheet_id,
                    range=range_val
                ).execute()
                rows = result.get('values', [])
                print(f"Got {len(rows)} rows from sheet")

                if len(rows) > 0:
                    print(f"First row sample: {rows[0][:3] if len(rows[0]) >= 3 else rows[0]}")
                    for idx, row in enumerate(rows):
                        if row and len(row) >= 2:
                            roll_no = row[0].strip()
                            name = row[1].strip()

                            if idx < 3: # Log first 3 students
                                print(f"  Student {idx+1}: Roll={roll_no}, Name={name}")

                            # Parse marks
                            marks_data = {}
                            raw_marks = row[2:]
                            for i, mark in enumerate(raw_marks):
                                if i < len(headers):
                                    label = headers[i]
                                    marks_data[label] = mark
                                else:
                                    marks_data[f"Extra {i}"] = mark

                            all_students.append({
                                'rollNumber': roll_no,
                                'name': name,
                                'marks': marks_data
                            })
                print(f"Added {len(rows)} students from this sheet")
            except Exception as e:
                print(f"❌ Error fetching from sheet {sheet_id}: {e}")
                import traceback
                traceback.print_exc()

        student_cache = all_students
        print(f"\n✓ Total cached: {len(all_students)} students")
        if all_students:
            print(f"Sample roll numbers: {[s['rollNumber'] for s in all_students[:5]]}")

        return all_students
    except Exception as e:
        print(f"Error fetching students: {e}")
        return []

def ensure_cache():
    # Helper to load cache lazily if empty
    if not student_cache:
        print("Cache empty or cold start. Fetching from sheets...")
        fetch_students_from_sheets()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize DB and Google Sheets connection (fast)
    # Defer heavy fetch logic to first request
    init_db()
    initialize_google_sheets()
    # Fetch student data on startup
    print("\n🚀 Server starting - fetching student data...")
    fetch_students_from_sheets()
    yield

# Initialize FastAPI
app = FastAPI(title="Student Marks Portal", lifespan=lifespan)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Pydantic models
class StudentRegister(BaseModel):
    rollNumber: str
    name: str
    password: str

class StudentLogin(BaseModel):
    rollNumber: str
    password: str

class AdminRegister(BaseModel):
    name: str
    email: EmailStr
    password: str

class AdminLogin(BaseModel):
    email: EmailStr
    password: str

class AddSource(BaseModel):
    sheetId: str
    range: Optional[str] = "Sheet1!A2:Z" # Default to skipping header row
    name: Optional[str] = "" # Friendly name for the sheet

class GradingConfig(BaseModel):
    sheetId: str
    method: str = "automatic"
    ranges: Optional[Dict[str, float]] = None
    limits: Optional[Dict[str, int]] = None

class ManualGradeEntry(BaseModel):
    rollNumber: str
    grade: str

class ManualGradesPayload(BaseModel):
    sheetId: str
    grades: List[ManualGradeEntry]


# Helper functions
def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# Google Sheets User DB Helpers
def get_sheet_users(env_var_name="STUDENT_SHEET_ID"):
    sheet_id = os.getenv(env_var_name)
    if not sheet_id or not sheets_service:
        return []
    try:
        # Default to Sheet1 since these are dedicated files
        result = sheets_service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range="Sheet1!A:E"
        ).execute()
        rows = result.get('values', [])

        users = []
        for row in rows[1:]: # Skip header
            if len(row) >= 5:
                users.append({
                    "role": row[0],
                    "rollNumber": row[1],
                    "name": row[2],
                    "email": row[3],
                    "password": row[4]
                })
        return users
    except Exception as e:
        print(f"Sheet Auth Error ({env_var_name}): {e}")
        return []

def append_user_to_sheet(env_var_name, role, roll, name, email, hashed_password):
    sheet_id = os.getenv(env_var_name)
    if not sheet_id or not sheets_service:
        return False, f"Missing Sheet ID ({env_var_name}) or Service not initialized"
    try:
        body = {"values": [[role, roll, name, email, hashed_password]]}
        sheets_service.spreadsheets().values().append(
            spreadsheetId=sheet_id,
            range="Sheet1!A:E",
            valueInputOption="RAW",
            body=body
        ).execute()
        return True, "Success"
    except Exception as e:
        error_msg = str(e)
        print(f"Sheet Append Error ({env_var_name}): {error_msg}")
        return False, f"Google Sheet Error: {error_msg}"

def get_sheet_sources(owner_email=None):
    """Fetch list of Marking Sheets from the Admin Config Sheet"""
    sheet_id = os.getenv("ADMIN_SHEET_ID")
    print(f"\n=== Reading Sources from Admin Sheet (Filter: {owner_email}) ===")
    print(f"Admin Sheet ID: {sheet_id}")
    if not sheet_id or not sheets_service:
        print("❌ No Admin Sheet ID or sheets service not initialized")
        return []
    try:
        # Format: SheetID | Range | Name | OwnerEmail
        result = sheets_service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range="Sources!A:D"
        ).execute()
        rows = result.get('values', [])
        print(f"Got {len(rows)} rows from Sources tab")

        sources = []
        for idx, row in enumerate(rows[1:], 1): # Skip header
            if len(row) >= 1:
                # Get owner email from Column D (index 3)
                row_owner = row[3].strip().lower() if len(row) > 3 and row[3].strip() else None
                
                if owner_email:
                    # STRICT ADMIN FILTERING: Only show sources that explicitly belong to this admin
                    # Legacy sources (no owner) are NOT shown to admins
                    if not row_owner or row_owner != owner_email.lower():
                        print(f" Skipping {row[2] if len(row) > 2 else 'Unknown'}: Owner={row_owner}, Looking for={owner_email.lower()}")
                        continue
                else:
                    # Student Context (owner_email=None): Show all sheets for public search
                    pass
                
                sid = row[0].strip()
                rng = row[1].strip() if len(row) > 1 else "Sheet1!A2:Z"
                name = row[2].strip() if len(row) > 2 else sid[:15] + "..."
                sources.append((sid, rng, name))
                print(f" ✓ Source {idx}: {name} ({sid[:20]}...) Owner={row_owner}")

        print(f"✓ Loaded {len(sources)} sources for {owner_email or 'public'}")
        return sources
    except Exception as e:
        print(f"❌ Error reading Sources tab: {e}")
    except Exception as e:
        print(f"❌ Error reading Sources tab: {e}")
        import traceback
        traceback.print_exc()
        return []

def append_source_to_sheet(target_sheet_id, target_range, sheet_name="", owner_email=""):
    """Save a new Marking Sheet ID to the Admin Config Sheet"""
    config_sheet_id = os.getenv("ADMIN_SHEET_ID")
    if not config_sheet_id or not sheets_service:
        return False, "ADMIN_SHEET_ID not configured or Sheets service not initialized"
    try:
        # Append with Owner Email in Column D
        body = {"values": [[target_sheet_id, target_range, sheet_name, owner_email]]}
        sheets_service.spreadsheets().values().append(
            spreadsheetId=config_sheet_id,
            range="Sources!A:D",
            valueInputOption="RAW",
            body=body
        ).execute()
        return True, "Success"
    except Exception as e:
        error_msg = str(e)
        print(f"Source Config Write Error: {error_msg}")
        return False, f"Failed to write to Sources tab: {error_msg}"
        return True, "Success"
    except Exception as e:
        error_msg = str(e)
        print(f"Source Config Write Error: {error_msg}")
        return False, f"Failed to write to Sources tab: {error_msg}"

import bcrypt

def verify_password(plain_password, hashed_password):
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except:
        return False

def get_password_hash(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# API Routes

@app.get("/api/debug/config")
async def debug_config():
    """Diagnostic tool to verify detailed connection status"""
    creds_found = bool(os.getenv("GOOGLE_CREDENTIALS_JSON"))
    sheet_id_found = bool(os.getenv("STUDENT_SHEET_ID"))
    admin_id_found = bool(os.getenv("ADMIN_SHEET_ID"))
    
    error_log = []
    
    if not creds_found: error_log.append("Missing GOOGLE_CREDENTIALS_JSON")
    if not sheet_id_found: error_log.append("Missing STUDENT_SHEET_ID")
    
    service_status = "Not Initialized"
    sheet_access = "Unknown"
    
    if sheets_service:
        service_status = "Initialized"
        try:
            # Try to read properties of Student Sheet
            sid = os.getenv("STUDENT_SHEET_ID")
            if sid:
                c = sheets_service.spreadsheets().get(spreadsheetId=sid).execute()
                title = c.get('properties', {}).get('title', 'Unknown')
                sheet_access = f"Success (Found Sheet: '{title}')"
        except Exception as e:
            sheet_access = f"Failed (Error: {str(e)})"
            error_log.append(f"Cannot access Sheet: {str(e)}")
            
    return {
        "env_vars": {
            "credentials": "Present" if creds_found else "Missing",
            "student_sheet_id": "Present" if sheet_id_found else "Missing",
             "admin_sheet_id": "Present" if admin_id_found else "Missing"
        },
        "service_status": service_status,
        "sheet_connection": sheet_access,
        "instructions": "If Sheet Connection Failed, share your sheet with: student-marks-portal@ml-student-mark-sheet.iam.gserviceaccount.com",
        "errors": error_log
    }

@app.get("/api/health")
async def health_check():
    return {
        "success": True,
        "status": "Server is running",
        "database": "SQLite3",
        "sheetsConnected": sheets_service is not None,
        "initError": sheet_init_error,
        "cachedStudents": len(student_cache)
    }



@app.post("/api/register")
async def register_student(student: StudentRegister):
    # Normalize inputs (Clean data before saving)
    student.rollNumber = student.rollNumber.strip()
    student.name = student.name.strip()

    # Removed validation - students can register even if marks aren't in sheet yet
    # They'll see marks if data exists, or "not found" message if it doesn't

    hashed_password = get_password_hash(student.password)

    # 1. OPTION A: Google Sheets DB (Permanent & Editable)
    # Check duplicates in sheet
    sheet_users = get_sheet_users("STUDENT_SHEET_ID")
    if any(u['rollNumber'] == student.rollNumber for u in sheet_users):
        raise HTTPException(status_code=400, detail="Student already registered (in Sheet)")

    success, msg = append_user_to_sheet("STUDENT_SHEET_ID", 'student', student.rollNumber, student.name, "", hashed_password)
    if success:
        return {"success": True, "message": "Registration successful! Account saved to Google Sheet."}
    else:
        raise HTTPException(status_code=500, detail=f"Failed to save to Student Sheet: {msg}")

    # 2. OPTION B: SQLite (Fallback / Ephemeral)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM students WHERE roll_number = ?", (student.rollNumber,))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="Student already registered")

    try:
        cursor.execute(
            "INSERT INTO students (roll_number, name, email, password) VALUES (?, ?, ?, ?)",
            (student.rollNumber, student.name, "", hashed_password)
        )
        conn.commit()
        conn.close()
        return {"success": True, "message": "Result Account Created (Note: Configure Sheets for permanent storage)"}
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")

@app.post("/api/login")
async def login_student(credentials: StudentLogin):
    # 1. OPTION A: Google Sheet DB
    sheet_users = get_sheet_users("STUDENT_SHEET_ID")
    
    # Robust matching (Case insensitive, ignore whitespace - Fix for Mobile)
    input_roll = credentials.rollNumber.strip().lower()

    user = next((u for u in sheet_users if u['rollNumber'].strip().lower() == input_roll), None)

    if user:
        if verify_password(credentials.password, user['password']):
            access_token = create_access_token(
                data={"rollNumber": user['rollNumber'], "email": ""}
            )
            return {
                "success": True,
                "token": access_token,
                "student": {"rollNumber": user['rollNumber'], "name": user['name'], "email": user['email']}
            }
        else:
            raise HTTPException(status_code=401, detail="Invalid credentials")

    # 2. OPTION B: SQLite Fallback
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM students WHERE roll_number = ?",
        (credentials.rollNumber,)
    )
    student = cursor.fetchone()
    conn.close()

    if not student or not verify_password(credentials.password, student['password']):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token = create_access_token(
        data={"rollNumber": student['roll_number'], "email": student['email']}
    )
    return {
        "success": True,
        "token": access_token,
        "student": {
            "rollNumber": student['roll_number'],
            "name": student['name'],
            "email": student['email']
        }
    }

@app.get("/api/test")
async def test_endpoint():
    """Test endpoint to verify deployment"""
    return {
        "status": "OK",
        "message": "New deployment is live!",
        "sheets_service": "initialized" if sheets_service else "not initialized"
    }

@app.get("/api/marks/{roll_number:path}")
async def get_marks(roll_number: str):
    try:
        if not sheets_service:
             raise HTTPException(status_code=500, detail="Google Sheets service not initialized")

        # Get admin-configured sources only
        sources = get_sheet_sources()
        sheet_errors = []

        # Search each sheet directly
        for source in sources:
            if len(source) == 3:
                sheet_id, range_val, name = source
            else:
                sheet_id, range_val = source
                name = "Unknown"

            try:
                # First, get the header row to know column names
                # Determine Header Row dynamically based on Data Range
                # Logic: If data starts at A3, Header is at Row 2.
                header_row = 1
                sheet_part = "Sheet1"
                
                if "!" in range_val:
                    parts = range_val.split("!")
                    sheet_part = parts[0]
                    range_part = parts[1]
                else:
                    range_part = range_val

                # Find start row number in range (e.g. A3:Z -> 3)
                import re
                match = re.search(r'([0-9]+)', range_part)
                if match:
                    data_start_row = int(match.group(1))
                    if data_start_row > 1:
                        header_row = data_start_row - 1
                
                header_range = f"{sheet_part}!{header_row}:{header_row}"
                
                header_result = sheets_service.spreadsheets().values().get(
                    spreadsheetId=sheet_id,
                    range=header_range
                ).execute()
                header_rows = header_result.get('values', [])
                headers = header_rows[0][2:] if header_rows and len(header_rows[0]) > 2 else []

                # Now get the data rows
                result = sheets_service.spreadsheets().values().get(
                    spreadsheetId=sheet_id,
                    range=range_val
                ).execute()
                rows = result.get('values', [])
                
                # Loop through all rows to calculate class stats AND find student
                sheet_totals = []
                found_student_payload = None
                
                for row in rows:
                    if row and len(row) >= 2:
                        # 1. Calculate Total for this row (for Class Average)
                        current_row_total = 0
                        current_raw_marks = row[2:]
                        for i, m in enumerate(current_raw_marks):
                            if i < len(headers):
                                label = headers[i]
                                if label.lower() != 'total':
                                    try:
                                        if m:
                                            current_row_total += float(m.replace('%','').strip())
                                    except: pass
                        
                        sheet_totals.append(current_row_total)

                        # 2. Check if this is the student
                        row_roll = row[0].strip()
                        if row_roll.lower() == roll_number.lower():
                            student_name = row[1].strip()
                            
                            # Build marks objects
                            marks_dict = {"rollNumber": row_roll, "name": student_name, "Total": current_row_total}
                            marks_array = []
                            
                            for i, mark in enumerate(current_raw_marks):
                                if i < len(headers):
                                    label = headers[i]
                                    value = mark if mark else '-'
                                    marks_dict[label] = value
                                    marks_array.append({"label": label, "value": value})
                            
                            found_student_payload = {
                                "success": True,
                                "marks": marks_dict,
                                "student": {
                                    "rollNumber": row_roll,
                                    "name": student_name,
                                    "sheetName": name,
                                    "marks": marks_array,
                                    "total": current_row_total
                                }
                            }
                
                if found_student_payload:
                    # Calculate Class Average
                    class_avg = sum(sheet_totals) / len(sheet_totals) if sheet_totals else 0
                    found_student_payload["classAverage"] = round(class_avg, 2)
                    found_student_payload["student"]["classAverage"] = round(class_avg, 2)
                    return found_student_payload
            except Exception as e:
                print(f"Error reading sheet {name}: {e}")
                # Store friendly error
                err_str = str(e)
                if "403" in err_str: sheet_errors.append(f"{name}: Permission Denied (Share sheet with service email)")
                elif "404" in err_str: sheet_errors.append(f"{name}: Sheet Not Found")
                elif "Unable to parsing" in err_str: sheet_errors.append(f"{name}: Tab/Range Error")
                else: sheet_errors.append(f"{name}: {err_str}")
                continue

        # If we get here, student not found
        error_detail = f"Student marks not found for: {roll_number}"
        if sheet_errors:
            error_detail += f". WARNING: Failed to read sheets: {'; '.join(sheet_errors)}"
            
        raise HTTPException(status_code=404, detail=error_detail)

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

@app.post("/api/admin/register")
async def register_admin(admin: AdminRegister):
    hashed_password = get_password_hash(admin.password)

    # 1. OPTION A: Google Sheets DB (Permanent -> admin_data)
    # Check duplicates in sheet
    sheet_admins = get_sheet_users("ADMIN_SHEET_ID")

    # MULTI-ADMIN SUPPORT: Removed single-admin restriction
    # if len(sheet_admins) > 0:
    #     raise HTTPException(status_code=403, detail="Registration Closed. Only one Admin account is allowed.")

    if any(u['email'].lower() == admin.email.lower() for u in sheet_admins):
        raise HTTPException(status_code=400, detail="Admin already registered (in Sheet)")

    success, msg = append_user_to_sheet("ADMIN_SHEET_ID", 'admin', 'Admin', admin.name, admin.email, hashed_password)
    if success:
        return {"success": True, "message": "Admin Registration successful! Account saved to Google Sheet."}
    else:
        # If sheet write fails, we MUST tell the user why (Permissions? Tab Name?)
        # Do not fallback silently, as user expects permanence.
        raise HTTPException(status_code=500, detail=f"Failed to save to Admin Sheet: {msg}")

    # 2. OPTION B: SQLite (Ephemeral)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM admins WHERE email = ?", (admin.email,))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="Admin already exists")

    try:
        cursor.execute(
            "INSERT INTO admins (name, email, password) VALUES (?, ?, ?)",
            (admin.name, admin.email, hashed_password)
        )
        conn.commit()
        conn.close()
        return {"success": True, "message": "Admin registered (Ephemeral). Use Sheets for permanence."}
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")

@app.post("/api/admin/login")
async def login_admin(credentials: AdminLogin):
    # 1. OPTION A: Google Sheet DB
    sheet_admins = get_sheet_users("ADMIN_SHEET_ID")

    # Robust matching (Fix for Mobile users adding spaces)
    input_email = credentials.email.strip().lower()

    admin_user = next((u for u in sheet_admins if u['email'].strip().lower() == input_email), None)

    if admin_user:
        if verify_password(credentials.password, admin_user['password']):
            access_token = create_access_token(
                data={"id": "sheet_admin", "email": admin_user['email']}
            )
            return {"success": True, "token": access_token}
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # 2. OPTION B: SQLite Fallback
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM admins WHERE email = ?", (credentials.email,))
    admin = cursor.fetchone()
    conn.close()

    if not admin or not verify_password(credentials.password, admin['password']):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token = create_access_token(
        data={"id": admin['id'], "email": admin['email']}
    )
    return {
        "success": True,
        "token": access_token,
        "admin": {
            "id": admin['id'],
            "name": admin['name'],
            "email": admin['email']
        }
    }

class UpdateSource(BaseModel):
    oldSheetId: str
    sheetId: str
    range: str
    name: str

@app.post("/api/admin/add-source")
async def add_source(source: AddSource, token: str = Header(..., alias="Authorization")):
    # 1. Verify User
    try:
        scheme, _, param = token.partition(" ")
        payload = jwt.decode(param, SECRET_KEY, algorithms=[ALGORITHM])
        admin_email = payload.get("email")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    # 1. OPTION A: Google Sheet Config (Permanent)
    success, msg = append_source_to_sheet(source.sheetId, source.range or "Sheet1!A2:Z", source.name or "", admin_email)
    if success:
        # Refresh immediately
        fetch_students_from_sheets()
        return {"success": True, "message": "Source added permanently to Admin Sheet!"}
    else:
        # Show the EXACT error instead of falling back silently
        raise HTTPException(status_code=500, detail=f"Failed to save source permanently: {msg}. Please ensure the 'Sources' tab exists in your Admin Google Sheet.")

@app.post("/api/admin/update-source")
async def update_source(data: UpdateSource):
    # 1. Get current config sheet range
    config_sheet_id = os.getenv("ADMIN_SHEET_ID")
    if not config_sheet_id or not sheets_service:
        raise HTTPException(status_code=500, detail="Services not configured")

    try:
        # Read all sources to find index
        result = sheets_service.spreadsheets().values().get(
            spreadsheetId=config_sheet_id,
            range="Sources!A:C"
        ).execute()
        rows = result.get('values', [])
        
        row_index = -1
        # Skip header row (index 0), data starts at row 2 (index 1) in Python list, but sheet row is index+1
        for idx, row in enumerate(rows):
            if idx == 0: continue # Skip Header
            if len(row) > 0 and row[0].strip() == data.oldSheetId:
                row_index = idx + 1 # 1-based index for API
                break
        
        if row_index == -1:
            raise HTTPException(status_code=404, detail="Source sheet not found to update")
            
        # Update specific row
        body = {"values": [[data.sheetId, data.range, data.name]]}
        sheets_service.spreadsheets().values().update(
            spreadsheetId=config_sheet_id,
            range=f"Sources!A{row_index}:C{row_index}",
            valueInputOption="RAW",
            body=body
        ).execute()
        
        # Trigger refresh
        fetch_students_from_sheets()
        return {"success": True, "message": "Source updated successfully"}
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Update failed: {str(e)}")

@app.post("/api/admin/refresh")
async def refresh_data():
    # Allow refreshing without auth for ease of use if token is lost,
    # or better: require auth. Let's keep it open for the admin panel context.
    # In a strict app we would add: current_user: dict = Depends(get_current_admin)
    global student_cache
    student_cache = []
    # Trigger fetch immediately
    fetch_students_from_sheets()
    return {"success": True, "message": "Data refreshed from Google Sheets"}

@app.get("/api/admin/sources")
async def get_sources(authorization: str = Header(None)):
    admin_email = None
    
    # Extract email from token if provided
    if authorization:
        try:
            scheme, _, param = authorization.partition(" ")
            payload = jwt.decode(param, SECRET_KEY, algorithms=[ALGORITHM])
            admin_email = payload.get("email")
        except:
            pass  # If token invalid, return all sources (or none for security)
    
    # 1. Get Sources (Filtered by owner if admin_email exists)
    sources = get_sheet_sources(admin_email)
    
    # Format for frontend
    data = [{"sheetId": s[0], "range": s[1], "name": s[2] if len(s) > 2 else s[0][:15] + "..."} for s in sources]
    return {"success": True, "sources": data}

def calculate_relative_grade(score, all_scores, student_index=None):
    """
    Calculate relative grade based on university marking system
    Uses refined grading scale: A+, A, A-, B+, B, B-, C+, C, C-, D+, D, D-, F
    
    Special Rule for A+:
    - Maximum 2 students can get A+
    - Only if top 2 students' marks are within 1-3 marks difference
    - Otherwise, only rank 1 gets A+
    
    University Standard Grading (More Realistic Distribution):
    - Top performers get A grades
    - Good performers get B grades  
    - Average performers get C grades
    - Below average get D grades
    - Failing students get F
    """
    if not all_scores or score is None:
        return "N/A"
    
    # Sort all scores to find rank (highest first)
    sorted_scores = sorted([s for s in all_scores if s is not None], reverse=True)
    
    if not sorted_scores:
        return "N/A"
    
    # Find rank (1-based)
    try:
        rank = sorted_scores.index(score) + 1
    except ValueError:
        rank = len(sorted_scores)
    
    total_students = len(sorted_scores)
    
    # Calculate percentile (what percentage of students this student beat)
    percentile = ((total_students - rank) / total_students) * 100
    
    # Special handling for A+ grade
    # Maximum 2 students, only if top 2 are within 1-3 marks
    if rank == 1:
        # Rank 1 always gets A+ (if they're the top)
        return "A+"
    elif rank == 2:
        # Rank 2 gets A+ only if within 1-3 marks of rank 1
        top_score = sorted_scores[0]
        second_score = sorted_scores[1]
        difference = top_score - second_score
        
        if 1 <= difference <= 3:
            return "A+"
        else:
            return "A"  # If difference > 3, rank 2 gets A instead
    
    # For all other students, use percentile-based grading
    # UPDATED: More realistic university-standard distribution
    # Allows more students to get good grades based on performance
    
    if percentile >= 85:  # Top 15% (after A+)
        return "A"
    elif percentile >= 75:  # Next 10%
        return "A-"
    elif percentile >= 65:  # Next 10%
        return "B+"
    elif percentile >= 55:  # Next 10%
        return "B"
    elif percentile >= 45:  # Next 10%
        return "B-"
    elif percentile >= 35:  # Next 10%
        return "C+"
    elif percentile >= 28:  # Next 7%
        return "C"
    elif percentile >= 21:  # Next 7%
        return "C-"
    elif percentile >= 14:  # Next 7%
        return "D+"
    elif percentile >= 9:   # Next 5%
        return "D"
    elif percentile >= 5:   # Next 4%
        return "D-"
    else:  # Bottom 5%
        return "F"

@app.post("/api/admin/save-manual-grades")
async def save_manual_grades(payload: ManualGradesPayload):
    conn = get_db()
    cursor = conn.cursor()
    try:
        # Use transaction
        for entry in payload.grades:
            cursor.execute('''
                INSERT INTO manual_grades (sheet_id, roll_number, grade) 
                VALUES (?, ?, ?)
                ON CONFLICT(sheet_id, roll_number) 
                DO UPDATE SET grade=excluded.grade, updated_at=CURRENT_TIMESTAMP
            ''', (payload.sheetId, entry.rollNumber, entry.grade))
        conn.commit()
        return {"success": True, "message": "Manual grades saved successfully"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to save grades: {str(e)}")
    finally:
        conn.close()

def get_manual_overrides(sheet_id: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT roll_number, grade FROM manual_grades WHERE sheet_id = ?", (sheet_id,))
    rows = cursor.fetchall()
    conn.close()
    return {row['roll_number']: row['grade'] for row in rows}

def calculate_custom_grade(score, all_scores, config: GradingConfig, roll_number=None, manual_overrides=None):
    if not all_scores or score is None:
        return "N/A"
    
    # 1. Manual
    if config.method == 'manual':
        if manual_overrides and roll_number and roll_number in manual_overrides:
            return manual_overrides[roll_number]
        # Fallback to current relative grade if no manual override exists yet
        return calculate_relative_grade(score, all_scores)

    # 2. Percentage Based
    if config.method == 'percentage-based' and config.ranges:
        # Check against ranges (e.g., {'A': 80}) meaning >= 80
        sorted_ranges = sorted(config.ranges.items(), key=lambda x: x[1], reverse=True)
        
        # Calculate Percentage (of 55? or 100?)
        # User implies percentage of course. Current marks max is 55.
        current_max = 55
        percentage = (score / current_max) * 100 if current_max > 0 else 0
        
        for grade, min_percent in sorted_ranges:
            if percentage >= min_percent:
                return grade
        return "F" # Default if below all ranges
        
    # 3. Class Limits
    elif config.method == 'class-limits' and config.limits:
        # Need rank
        sorted_scores = sorted([s for s in all_scores if s is not None], reverse=True)
        try:
            rank = sorted_scores.index(score) + 1 # 1-based
        except ValueError:
            rank = len(sorted_scores)
            
        count = 0
        ordered_grades = ['A+', 'A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D+', 'D', 'D-', 'F']
        
        for grade in ordered_grades:
            limit = config.limits.get(grade, 0)
            if limit > 0:
                if rank <= count + limit:
                    return grade
                count += limit
        
        # If limits exceeded (overflow), assign F or lowest?
        return "F"
        
    # 4. Automatic (Default)
    else:
        return calculate_relative_grade(score, all_scores)


def _fetch_sheet_statistics_internal(sheet_id: str, range_val: str, sheet_name: str):
    """
    Internal helper to fetch sheet stats without re-fetching source config.
    """
    try:
        if not sheets_service:
            raise Exception("Google Sheets service not initialized")
            
        # Get header row
        header_row = 1
        sheet_part = "Sheet1"
        
        if "!" in range_val:
            parts = range_val.split("!")
            sheet_part = parts[0]
            range_part = parts[1]
        else:
            range_part = range_val
        
        # Find start row number in range
        import re
        match = re.search(r'([0-9]+)', range_part)
        if match:
            data_start_row = int(match.group(1))
            if data_start_row > 1:
                header_row = data_start_row - 1
        
        header_range = f"{sheet_part}!{header_row}:{header_row}"
        
        # Get headers
        header_result = sheets_service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=header_range
        ).execute()
        header_rows = header_result.get('values', [])
        headers = header_rows[0][2:] if header_rows and len(header_rows[0]) > 2 else []
        
        # Get all student data
        result = sheets_service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=range_val
        ).execute()
        rows = result.get('values', [])
        
        students = []
        all_totals = []
        subject_totals = {header: [] for header in headers if header.lower() != 'total'}
        
        # First pass: collect all data
        for row in rows:
            if row and len(row) >= 2:
                roll_no = row[0].strip()
                name = row[1].strip()
                raw_marks = row[2:]
                
                marks_dict = {}
                total = 0
                
                for i, mark in enumerate(raw_marks):
                    if i < len(headers):
                        label = headers[i]
                        try:
                            # Try to parse as number
                            mark_value = float(mark.replace('%', '').strip()) if mark else 0
                            marks_dict[label] = mark_value
                            
                            # Add to subject totals for average calculation
                            if label.lower() != 'total':
                                subject_totals[label].append(mark_value)
                                total += mark_value
                        except:
                            marks_dict[label] = mark if mark else '-'
                
                # Store total for relative grading
                all_totals.append(total)
                
                students.append({
                    'rollNumber': roll_no,
                    'name': name,
                    'marks': marks_dict,
                    'total': total
                })
        
        # Calculate class averages
        class_average = sum(all_totals) / len(all_totals) if all_totals else 0
        subject_averages = {}
        
        for subject, values in subject_totals.items():
            if values:
                subject_averages[subject] = sum(values) / len(values)
        
        # Second pass: assign relative grades
        for student in students:
            student['grade'] = calculate_relative_grade(student['total'], all_totals)
            # Calculate percentage based on actual current marks (55)
            # Total course marks = 100 (current 55 + future final 45)
            # Percentage = (student's current marks / 55) * 100
            current_marks_maximum = 55  # Actual maximum marks for current assessments
            student['percentage'] = round((student['total'] / current_marks_maximum) * 100, 2) if current_marks_maximum > 0 else 0
        
        # Capture sequential totals (Sheet Order) before sorting for Graph
        sequential_totals = [s['total'] for s in students]

        # Sort students by total (highest first)
        students.sort(key=lambda x: x['total'], reverse=True)
        
        # Calculate grade distribution for bell curve
        grade_distribution = {}
        for student in students:
            grade = student['grade']
            grade_distribution[grade] = grade_distribution.get(grade, 0) + 1
        
        # Ensure all grades are in distribution (even if count is 0)
        all_grades = ['A+', 'A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D+', 'D', 'D-', 'F']
        for grade in all_grades:
            if grade not in grade_distribution:
                grade_distribution[grade] = 0
        
        return {
            "success": True,
            "sheetName": sheet_name,
            "students": students,
            "statistics": {
                "totalStudents": len(students),
                "classAverage": round(class_average, 2),
                "subjectAverages": {k: round(v, 2) for k, v in subject_averages.items()},
                "highestScore": max(all_totals) if all_totals else 0,
                "lowestScore": min(all_totals) if all_totals else 0,
                "headers": headers,
                "gradeDistribution": grade_distribution,
                "totalPossibleMarks": 100,
                "currentMarksTotal": 55,  # Fixed: actual maximum marks for current assessments
                "sequentialTotals": sequential_totals
            }
        }
    except Exception as e:
        # Propagate exception
        raise e

@app.get("/api/admin/sheet-statistics/{sheet_id}")
def get_sheet_statistics(sheet_id: str):
    """
    Get all students from a specific sheet with class statistics and relative grades
    """
    try:
        if not sheets_service:
            raise HTTPException(status_code=500, detail="Google Sheets service not initialized")
        
        # Find the source configuration
        sources = get_sheet_sources()
        source_config = None
        
        for source in sources:
            if source[0] == sheet_id:
                source_config = source
                break
        
        if not source_config:
            raise HTTPException(status_code=404, detail="Sheet not found in configured sources")
        
        sheet_id, range_val, sheet_name = source_config if len(source_config) == 3 else (*source_config, "Unknown")
        
        return _fetch_sheet_statistics_internal(sheet_id, range_val, sheet_name)
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error fetching sheet statistics: {str(e)}")

@app.post("/api/admin/calculate-grades")
async def calculate_grades_endpoint(config: GradingConfig):
    """
    Calculate grades based on custom configuration without modifying original GET endpoint.
    """
    try:
        # Reuse logic from get_sheet_statistics (Duplicated to ensure stability of original)
        if not sheets_service:
            raise HTTPException(status_code=500, detail="Google Sheets service not initialized")
        
        sources = get_sheet_sources()
        source_config = next((s for s in sources if s[0] == config.sheetId), None)
        
        if not source_config:
            raise HTTPException(status_code=404, detail="Sheet not found")
            
        # Unpack explicitly - safer
        if len(source_config) == 3:
            sheet_id, range_val, sheet_name = source_config
        else:
            sheet_id, range_val = source_config
            sheet_name = "Unknown"
        
        import re
        parts = range_val.split("!") if "!" in range_val else ["Sheet1", range_val]
        sheet_part = parts[0]
        range_part = parts[1] if len(parts) > 1 else range_val
        
        header_row = 1
        match = re.search(r'([0-9]+)', range_part)
        if match:
            data_start_row = int(match.group(1))
            if data_start_row > 1:
                header_row = data_start_row - 1
                
        header_result = sheets_service.spreadsheets().values().get(
            spreadsheetId=sheet_id, range=f"{sheet_part}!{header_row}:{header_row}"
        ).execute()
        header_rows = header_result.get('values', [])
        headers = header_rows[0][2:] if header_rows and len(header_rows[0]) > 2 else []
        
        result = sheets_service.spreadsheets().values().get(
            spreadsheetId=sheet_id, range=range_val
        ).execute()
        rows = result.get('values', [])
        
        students = []
        all_totals = []
        subject_totals = {header: [] for header in headers if header.lower() != 'total'}
        
        for row in rows:
            if row and len(row) >= 2:
                roll_no = row[0].strip()
                name = row[1].strip()
                raw_marks = row[2:]
                marks_dict = {}
                total = 0
                for i, mark in enumerate(raw_marks):
                    if i < len(headers):
                        label = headers[i]
                        try:
                            mark_value = float(mark.replace('%', '').strip()) if mark else 0
                            marks_dict[label] = mark_value
                            if label.lower() != 'total':
                                subject_totals[label].append(mark_value)
                                total += mark_value
                        except:
                            marks_dict[label] = mark if mark else '-'
                all_totals.append(total)
                students.append({'rollNumber': roll_no, 'name': name, 'marks': marks_dict, 'total': total})
        
        # Calculate Stats
        class_average = sum(all_totals) / len(all_totals) if all_totals else 0
        subject_averages = {k: sum(v)/len(v) for k, v in subject_totals.items() if v}
        
        # Determine overrides once
        manual_overrides = None
        if config.method == 'manual':
            manual_overrides = get_manual_overrides(config.sheetId)

        # Assign Custom Grades
        for student in students:
            student['grade'] = calculate_custom_grade(
                student['total'], 
                all_totals, 
                config, 
                roll_number=student['rollNumber'], 
                manual_overrides=manual_overrides
            )
            current_marks_maximum = 55
            student['percentage'] = round((student['total'] / current_marks_maximum) * 100, 2) if current_marks_maximum > 0 else 0
        
        # Capture sequential totals before sorting
        sequential_totals = [s['total'] for s in students]

        students.sort(key=lambda x: x['total'], reverse=True)
        
        grade_distribution = {}
        for student in students:
            grade = student['grade']
            grade_distribution[grade] = grade_distribution.get(grade, 0) + 1
            
        all_grades = ['A+', 'A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D+', 'D', 'D-', 'F']
        for grade in all_grades:
            if grade not in grade_distribution:
                grade_distribution[grade] = 0
                
        return {
            "success": True,
            "sheetName": sheet_name,
            "students": students,
            "statistics": {
                "totalStudents": len(students),
                "classAverage": round(class_average, 2),
                "subjectAverages": {k: round(v, 2) for k, v in subject_averages.items()},
                "highestScore": max(all_totals) if all_totals else 0,
                "lowestScore": min(all_totals) if all_totals else 0,
                "headers": headers,
                "gradeDistribution": grade_distribution,
                "totalPossibleMarks": 100,
                "currentMarksTotal": 55,
                "sequentialTotals": sequential_totals
            }
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error calculating grades: {str(e)}")


# Serve static files with absolute path
current_dir = os.path.dirname(os.path.abspath(__file__))
public_path = os.path.join(current_dir, "public")

if os.path.exists(public_path):
    app.mount("/public", StaticFiles(directory=public_path), name="public")
else:
    print(f"Warning: Public directory not found at {public_path}. Using current directory as fallback.")
    public_path = current_dir

@app.get("/")
async def read_root():
    return FileResponse(os.path.join(public_path, "index-auth.html"))

@app.get("/admin.html")
async def read_admin():
    return FileResponse(os.path.join(public_path, "admin.html"))

@app.get("/api/admin/dashboard")
async def get_dashboard(authorization: Optional[str] = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        token = authorization.split(" ")[1] if " " in authorization else authorization
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        admin_email = payload.get("sub") or payload.get("email")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    # 1. Fetch Sources (Filtered by Admin)
    # Re-using fetch logic but filtering sources first
    sources = get_sheet_sources(admin_email)
    
    if not sources:
        return {
            "totalStudents": 0,
            "overallAverage": 0,
            "highestMarks": 0,
            "lowestMarks": 0,
            "sections": []
        }

    # 2. Sequential Processing for Dashboard
    import asyncio
    loop = asyncio.get_event_loop()
    
    sections_data = []
    
    for source in sources:
        if len(source) == 2:
            sh_id, sh_range = source
            sh_name = "Unknown"
        else:
            sh_id, sh_range, sh_name = source
            
        try:
            # Run in thread but await result (Sequential)
            res = await loop.run_in_executor(None, _fetch_sheet_statistics_internal, sh_id, sh_range, sh_name)
            
            stats = res["statistics"]
            student_totals = stats.get("sequentialTotals", [])
            
            sections_data.append({
                "id": sh_id,
                "name": res["sheetName"],
                "totalStudents": stats["totalStudents"],
                "classAverage": stats["classAverage"],
                "highest": stats["highestScore"],
                "lowest": stats["lowestScore"],
                "performanceCurve": student_totals 
            })
        except Exception as e:
            print(f"Dashboard Error reading {sh_name}: {e}")
            continue

    # 3. Calculate Overall Aggregates
    total_students = sum(s["totalStudents"] for s in sections_data)
    
    # Weighted average for overall accuracy
    if total_students > 0:
        overall_avg = sum(s["classAverage"] * s["totalStudents"] for s in sections_data) / total_students
    else:
        overall_avg = 0
        
    highest = max((s["highest"] for s in sections_data), default=0)
    lowest = min((s["lowest"] for s in sections_data), default=0)

    return {
        "adminName": payload.get("sub", "Admin"), # 'sub' usually isn't set for name in my token, assume 'Admin' or fetch
        "adminEmail": admin_email,
        "totalStudents": total_students,
        "overallAverage": round(overall_avg, 2),
        "highestMarks": highest,
        "lowestMarks": lowest,
        "sections": sections_data
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
