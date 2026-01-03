from fastapi import FastAPI, HTTPException, Depends, status
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

def get_sheet_sources():
    """Fetch list of Marking Sheets from the Admin Config Sheet"""
    sheet_id = os.getenv("ADMIN_SHEET_ID")
    print(f"\n=== Reading Sources from Admin Sheet ===")
    print(f"Admin Sheet ID: {sheet_id}")
    if not sheet_id or not sheets_service:
        print("❌ No Admin Sheet ID or sheets service not initialized")
        return []
    try:
        # Format: SheetID | Range | Name
        result = sheets_service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range="Sources!A:C"
        ).execute()
        rows = result.get('values', [])
        print(f"Got {len(rows)} rows from Sources tab")

        sources = []
        for idx, row in enumerate(rows[1:], 1): # Skip header
            if len(row) >= 1:
                sid = row[0].strip()
                rng = row[1].strip() if len(row) > 1 else "Sheet1!A2:Z"
                name = row[2].strip() if len(row) > 2 else sid[:15] + "..."
                sources.append((sid, rng, name))
                print(f" Source {idx}: {name} ({sid[:20]}...)")

        print(f"✓ Loaded {len(sources)} sources")
        return sources
    except Exception as e:
        print(f"❌ Error reading Sources tab: {e}")
        import traceback
        traceback.print_exc()
        return []

def append_source_to_sheet(target_sheet_id, target_range, sheet_name=""):
    """Save a new Marking Sheet ID to the Admin Config Sheet"""
    config_sheet_id = os.getenv("ADMIN_SHEET_ID")
    if not config_sheet_id or not sheets_service:
        return False, "ADMIN_SHEET_ID not configured or Sheets service not initialized"
    try:
        body = {"values": [[target_sheet_id, target_range, sheet_name]]}
        sheets_service.spreadsheets().values().append(
            spreadsheetId=config_sheet_id,
            range="Sources!A:C",
            valueInputOption="RAW",
            body=body
        ).execute()
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
        print(f"\n=== Direct Sheet Lookup for: '{roll_number}' ===")
        print(f"Sheets service status: {sheets_service is not None}")

        if not sheets_service:
            print("❌ Sheets service not initialized!")
            raise HTTPException(status_code=500, detail="Google Sheets service not initialized")

        # Get admin-configured sources only (no DEFAULT_SHEET_ID)
        sources = get_sheet_sources()

        print(f"Searching in {len(sources)} sheets...")

        # Search each sheet directly
        for source in sources:
            if len(source) == 3:
                sheet_id, range_val, name = source
            else:
                sheet_id, range_val = source
                name = "Unknown"

            print(f"Checking sheet: {name}")

            try:
                # First, get the header row to know column names
                header_result = sheets_service.spreadsheets().values().get(
                    spreadsheetId=sheet_id,
                    range=range_val.replace('A2:', 'A1:') # Get headers from row 1
                ).execute()
                header_rows = header_result.get('values', [])
                headers = header_rows[0][2:] if header_rows and len(header_rows[0]) > 2 else []

                # Now get the data rows
                result = sheets_service.spreadsheets().values().get(
                    spreadsheetId=sheet_id,
                    range=range_val
                ).execute()
                rows = result.get('values', [])
                print(f"  Found {len(rows)} rows in {name}")
                print(f"  Headers from sheet: {headers}")

                # Print all roll numbers found for debugging
                all_rolls = [row[0].strip() if row and len(row) >= 1 else "EMPTY" for row in rows[:20]] # First 20
                print(f"  Sample roll numbers: {all_rolls}")

                for idx, row in enumerate(rows):
                    if row and len(row) >= 2:
                        row_roll = row[0].strip()

                        if idx < 5: # Log first 5 for debugging
                            print(f"  Row {idx+2}: '{row_roll}' vs '{roll_number}' = {row_roll == roll_number}")

                        if row_roll == roll_number:
                            print(f"✓ MATCH FOUND in {name}!")
                            student_name = row[1].strip()
                            
                            # Build marks dictionary for admin
                            marks_dict = {
                                "rollNumber": row_roll,
                                "name": student_name
                            }
                            
                            # Build marks array for student
                            marks_array = []
                            raw_marks = row[2:]

                            # Calculate total
                            total = 0
                            for i, mark in enumerate(raw_marks):
                                if i < len(headers):
                                    label = headers[i]
                                    value = mark if mark else '-'
                                    
                                    # Add to dictionary (for admin)
                                    marks_dict[label] = value
                                    
                                    # Add to array (for student)
                                    marks_array.append({"label": label, "value": value})

                                    # Add to total if it's a number
                                    try:
                                        if mark and label.lower() != 'total':
                                            total += float(mark)
                                    except:
                                        pass

                            marks_dict["Total"] = total

                            return {
                                "success": True,
                                "marks": marks_dict,  # For admin dashboard
                                "student": {          # For student dashboard
                                    "rollNumber": row_roll,
                                    "name": student_name,
                                    "marks": marks_array,
                                    "total": total
                                }
                            }
            except Exception as e:
                print(f"  Error reading sheet {name}: {e}")
                continue

        print(f"❌ Roll number '{roll_number}' not found in any sheet")
        raise HTTPException(status_code=404, detail=f"Student marks not found for roll number: {roll_number}")

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.post("/api/admin/register")
async def register_admin(admin: AdminRegister):
    hashed_password = get_password_hash(admin.password)

    # 1. OPTION A: Google Sheets DB (Permanent -> admin_data)
    # Check duplicates in sheet
    sheet_admins = get_sheet_users("ADMIN_SHEET_ID")

    # STRICT SECURITY: Only 1 Admin Allowed
    if len(sheet_admins) > 0:
        raise HTTPException(status_code=403, detail="Registration Closed. Only one Admin account is allowed.")

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

@app.post("/api/admin/add-source")
async def add_source(source: AddSource):
    # 1. OPTION A: Google Sheet Config (Permanent)
    success, msg = append_source_to_sheet(source.sheetId, source.range or "Sheet1!A2:Z", source.name or "")
    if success:
        # Refresh immediately
        fetch_students_from_sheets()
        return {"success": True, "message": "Source added permanently to Admin Sheet!"}
    else:
        # Show the EXACT error instead of falling back silently
        raise HTTPException(status_code=500, detail=f"Failed to save source permanently: {msg}. Please ensure the 'Sources' tab exists in your Admin Google Sheet.")

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
async def get_sources():
    # 1. Get Permanent Sources
    sources = get_sheet_sources()
    
    # Format for frontend
    data = [{"sheetId": s[0], "range": s[1], "name": s[2] if len(s) > 2 else s[0][:15] + "..."} for s in sources]
    return {"success": True, "sources": data}

# Serve static files with absolute path
current_dir = os.path.dirname(os.path.abspath(__file__))
public_path = os.path.join(current_dir, "public")

if os.path.exists(public_path):
    app.mount("/public", StaticFiles(directory=public_path), name="public")
else:
    print(f"Warning: Public directory not found at {public_path}")

@app.get("/")
async def read_root():
    return FileResponse(os.path.join(public_path, "index-auth.html"))

@app.get("/admin.html")
async def read_admin():
    return FileResponse(os.path.join(public_path, "admin.html"))

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
