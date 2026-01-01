from fastapi import FastAPI
import os
import sqlite3

app = FastAPI()

@app.get("/api/health")
def health():
    # Debug info
    db_status = "Not checked"
    try:
        # Check if we can write to /tmp
        with open("/tmp/test_write.txt", "w") as f:
            f.write("test")
        tmp_writable = True
    except Exception as e:
        tmp_writable = False
    
    return {
        "status": "Minimal server is running",
        "env": dict(os.environ),
        "tmp_writable": tmp_writable
    }

@app.get("/")
def read_root():
    return {"message": "Hello from Vercel Python!"}
