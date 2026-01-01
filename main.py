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
        
        conn.commit()
        conn.close()
        print("✓ Database initialized")
    except Exception as e:
        print(f"DB Init Error: {e}")

def initialize_google_sheets():
    global sheets_service
    try:
        credentials_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
        if not credentials_json:
            print("⚠ Google Sheets credentials not configured")
            return False
        
        credentials_dict = json.loads(credentials_json)
        credentials = service_account.Credentials.from_service_account_info(
            credentials_dict,
            scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
        )
        
        sheets_service = build('sheets', 'v4', credentials=credentials)
        print("✓ Google Sheets initialized")
        return True
    except Exception as e:
        print(f"✗ Google Sheets initialization failed: {e}")
        return False

def fetch_students_from_sheets():
    global student_cache
    if not sheets_service:
        return []
    
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT sheet_id, range FROM sources")
        sources = cursor.fetchall()
        conn.close()
        
        all_students = []
        
        # Standard headers based on user request
        headers = ["Quiz 1", "Assigment 1", "Mid", "Quiz 2", "Assigment 2", "CCP", "CP", "Final", "Total"]
        
        for sheet_id, range_val in sources:
            try:
                # Use default range if not specified or invalid (Sheet1!A2:Z skipping header)
                # Ideally we want A1:Z to see headers, but let's assume standard structure
                result = sheets_service.spreadsheets().values().get(
                    spreadsheetId=sheet_id,
                    range=range_val
                ).execute()
                
                rows = result.get('values', [])
                for row in rows:
                    if row and len(row) >= 2:
                        roll_no = row[0].strip()
                        name = row[1].strip()
                        
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
            except Exception as e:
                print(f"Error fetching from sheet {sheet_id}: {e}")
        
        student_cache = all_students
        print(f"✓ Cached {len(all_students)} students from Google Sheets")
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
    email: EmailStr
    password: str

class StudentLogin(BaseModel):
    rollNumber: str
    email: EmailStr
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

# Helper functions
def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

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
        "cachedStudents": len(student_cache)
    }

@app.post("/api/register")
async def register_student(student: StudentRegister):
    ensure_cache()
    
    # Check if roll number exists in cache
    student_exists = any(s['rollNumber'] == student.rollNumber for s in student_cache)
    if not student_exists:
        # Try fetching fresh data once just in case
        fetch_students_from_sheets()
        student_exists = any(s['rollNumber'] == student.rollNumber for s in student_cache)
        
        if not student_exists:
            raise HTTPException(
                status_code=400,
                detail="Invalid roll number. Make sure your data is in the Google Sheet."
            )
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Check if already registered
    cursor.execute("SELECT * FROM students WHERE roll_number = ?", (student.rollNumber,))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="Student already registered")
    
    # Hash password and save
    hashed_password = get_password_hash(student.password)
    try:
        cursor.execute(
            "INSERT INTO students (roll_number, name, email, password) VALUES (?, ?, ?, ?)",
            (student.rollNumber, student.name, student.email, hashed_password)
        )
        conn.commit()
        conn.close()
        return {"success": True, "message": "Registration successful! You can now login."}
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")

@app.post("/api/login")
async def login_student(credentials: StudentLogin):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT * FROM students WHERE roll_number = ? AND email = ?",
        (credentials.rollNumber, credentials.email)
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

@app.get("/api/marks/{roll_number}")
async def get_marks(roll_number: str):
    ensure_cache()
    
    student = next((s for s in student_cache if s['rollNumber'] == roll_number), None)
    
    if not student:
        # Try fresh fetch
        fetch_students_from_sheets()
        student = next((s for s in student_cache if s['rollNumber'] == roll_number), None)
    
    if not student:
        raise HTTPException(status_code=404, detail="Student marks not found")
    
    return {
        "success": True,
        "student": student
    }

@app.post("/api/admin/register")
async def register_admin(admin: AdminRegister):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM admins WHERE email = ?", (admin.email,))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="Admin already exists")
    
    hashed_password = get_password_hash(admin.password)
    try:
        cursor.execute(
            "INSERT INTO admins (name, email, password) VALUES (?, ?, ?)",
            (admin.name, admin.email, hashed_password)
        )
        conn.commit()
        conn.close()
        return {"success": True, "message": "Admin registered successfully"}
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")

@app.post("/api/admin/login")
async def login_admin(credentials: AdminLogin):
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
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            "INSERT INTO sources (sheet_id, range) VALUES (?, ?)",
            (source.sheetId, source.range)
        )
        conn.commit()
        conn.close()
        
        # Refresh student cache immediatley when admin adds source
        fetch_students_from_sheets()
        
        return {"success": True, "message": "Source added successfully"}
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=f"Failed to add source: {str(e)}")

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
