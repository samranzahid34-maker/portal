const express = require('express');
const cors = require('cors');
const path = require('path');
const fs = require('fs').promises;
const bcrypt = require('bcrypt');
const jwt = require('jsonwebtoken');
const { google } = require('googleapis');
require('dotenv').config();

const app = express();
const PORT = process.env.PORT || 3000;
const JWT_SECRET = process.env.JWT_SECRET || 'your-secret-key-change-in-production';

// Data files
const DATA_DIR = path.join(__dirname, 'data');
const STUDENTS_FILE = path.join(DATA_DIR, 'students.json');
const ADMINS_FILE = path.join(DATA_DIR, 'admins.json');
const SOURCES_FILE = path.join(DATA_DIR, 'sources.json');

// Middleware
app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

// Initialize data directory and files
async function initializeDataFiles() {
    try {
        await fs.mkdir(DATA_DIR, { recursive: true });

        // Initialize students file
        try {
            await fs.access(STUDENTS_FILE);
        } catch {
            await fs.writeFile(STUDENTS_FILE, JSON.stringify([], null, 2));
        }

        // Initialize admins file
        try {
            await fs.access(ADMINS_FILE);
        } catch {
            await fs.writeFile(ADMINS_FILE, JSON.stringify([], null, 2));
        }

        // Initialize sources file
        try {
            await fs.access(SOURCES_FILE);
        } catch {
            await fs.writeFile(SOURCES_FILE, JSON.stringify([], null, 2));
        }

        console.log('✓ Data files initialized');
    } catch (error) {
        console.error('Error initializing data files:', error);
    }
}

// Helper functions to read/write JSON files
async function readJSON(filePath) {
    try {
        const data = await fs.readFile(filePath, 'utf8');
        return JSON.parse(data);
    } catch (error) {
        console.error(`Error reading ${filePath}:`, error);
        return [];
    }
}

async function writeJSON(filePath, data) {
    try {
        await fs.writeFile(filePath, JSON.stringify(data, null, 2));
        return true;
    } catch (error) {
        console.error(`Error writing ${filePath}:`, error);
        return false;
    }
}

// Google Sheets setup
let sheetsClient = null;
let studentCache = [];

async function initializeGoogleSheets() {
    try {
        if (!process.env.GOOGLE_CREDENTIALS_JSON) {
            console.log('⚠ Google Sheets credentials not configured');
            return false;
        }

        const credentials = JSON.parse(process.env.GOOGLE_CREDENTIALS_JSON);
        const auth = new google.auth.GoogleAuth({
            credentials,
            scopes: ['https://www.googleapis.com/auth/spreadsheets.readonly'],
        });

        sheetsClient = google.sheets({ version: 'v4', auth });
        console.log('✓ Google Sheets initialized');
        return true;
    } catch (error) {
        console.error('✗ Google Sheets initialization failed:', error.message);
        return false;
    }
}

// Fetch students from Google Sheets
async function fetchStudentsFromSheets() {
    if (!sheetsClient) {
        console.log('Google Sheets not initialized');
        return [];
    }

    try {
        const sources = await readJSON(SOURCES_FILE);
        const allStudents = [];

        for (const source of sources) {
            try {
                const response = await sheetsClient.spreadsheets.values.get({
                    spreadsheetId: source.sheetId,
                    range: source.range || 'Sheet1!A2:Z',
                });

                const rows = response.data.values || [];
                rows.forEach(row => {
                    if (row[0]) {
                        allStudents.push({
                            rollNumber: row[0],
                            name: row[1] || '',
                            marks: row.slice(2)
                        });
                    }
                });
            } catch (error) {
                console.error(`Error fetching from sheet ${source.sheetId}:`, error.message);
            }
        }

        studentCache = allStudents;
        console.log(`✓ Cached ${allStudents.length} students from Google Sheets`);
        return allStudents;
    } catch (error) {
        console.error('Error fetching students:', error);
        return [];
    }
}

// API Routes

// Health check
app.get('/api/health', (req, res) => {
    res.json({
        success: true,
        status: 'Server is running',
        sheetsConnected: sheetsClient !== null,
        cachedStudents: studentCache.length
    });
});

// Student registration
app.post('/api/register', async (req, res) => {
    try {
        const { rollNumber, name, email, password } = req.body;

        if (!rollNumber || !email || !password) {
            return res.status(400).json({ success: false, error: 'All fields are required' });
        }

        // Check if roll number exists in cache
        const studentExists = studentCache.find(s => s.rollNumber === rollNumber);
        if (!studentExists) {
            return res.status(400).json({ success: false, error: 'Invalid roll number' });
        }

        // Check if already registered
        const students = await readJSON(STUDENTS_FILE);
        if (students.find(s => s.rollNumber === rollNumber)) {
            return res.status(400).json({ success: false, error: 'Student already registered' });
        }

        // Hash password and save
        const hashedPassword = await bcrypt.hash(password, 10);
        students.push({
            rollNumber,
            name: name || studentExists.name,
            email,
            password: hashedPassword,
            createdAt: new Date().toISOString()
        });

        await writeJSON(STUDENTS_FILE, students);

        res.json({ success: true, message: 'Registration successful' });
    } catch (error) {
        console.error('Registration error:', error);
        res.status(500).json({ success: false, error: 'Registration failed' });
    }
});

// Student login
app.post('/api/login', async (req, res) => {
    try {
        const { rollNumber, email, password } = req.body;

        if (!rollNumber || !email || !password) {
            return res.status(400).json({ success: false, error: 'All fields are required' });
        }

        const students = await readJSON(STUDENTS_FILE);
        const student = students.find(s => s.rollNumber === rollNumber && s.email === email);

        if (!student) {
            return res.status(401).json({ success: false, error: 'Invalid credentials' });
        }

        const passwordMatch = await bcrypt.compare(password, student.password);
        if (!passwordMatch) {
            return res.status(401).json({ success: false, error: 'Invalid credentials' });
        }

        const token = jwt.sign({ rollNumber, email }, JWT_SECRET, { expiresIn: '24h' });

        res.json({
            success: true,
            token,
            student: {
                rollNumber: student.rollNumber,
                name: student.name,
                email: student.email
            }
        });
    } catch (error) {
        console.error('Login error:', error);
        res.status(500).json({ success: false, error: 'Login failed' });
    }
});

// Get student marks
app.get('/api/marks/:rollNumber', async (req, res) => {
    try {
        const { rollNumber } = req.params;
        const student = studentCache.find(s => s.rollNumber === rollNumber);

        if (!student) {
            return res.status(404).json({ success: false, error: 'Student not found' });
        }

        res.json({
            success: true,
            student: {
                rollNumber: student.rollNumber,
                name: student.name,
                marks: student.marks
            }
        });
    } catch (error) {
        console.error('Error fetching marks:', error);
        res.status(500).json({ success: false, error: 'Failed to fetch marks' });
    }
});

// Admin routes
app.post('/api/admin/register', async (req, res) => {
    try {
        const { name, email, password } = req.body;

        if (!name || !email || !password) {
            return res.status(400).json({ success: false, error: 'All fields are required' });
        }

        const admins = await readJSON(ADMINS_FILE);
        if (admins.find(a => a.email === email)) {
            return res.status(400).json({ success: false, error: 'Admin already exists' });
        }

        const hashedPassword = await bcrypt.hash(password, 10);
        admins.push({
            id: Date.now().toString(),
            name,
            email,
            password: hashedPassword,
            createdAt: new Date().toISOString()
        });

        await writeJSON(ADMINS_FILE, admins);

        res.json({ success: true, message: 'Admin registered successfully' });
    } catch (error) {
        console.error('Admin registration error:', error);
        res.status(500).json({ success: false, error: 'Registration failed' });
    }
});

app.post('/api/admin/login', async (req, res) => {
    try {
        const { email, password } = req.body;

        if (!email || !password) {
            return res.status(400).json({ success: false, error: 'Email and password required' });
        }

        const admins = await readJSON(ADMINS_FILE);
        const admin = admins.find(a => a.email === email);

        if (!admin) {
            return res.status(401).json({ success: false, error: 'Invalid credentials' });
        }

        const passwordMatch = await bcrypt.compare(password, admin.password);
        if (!passwordMatch) {
            return res.status(401).json({ success: false, error: 'Invalid credentials' });
        }

        const token = jwt.sign({ id: admin.id, email: admin.email }, JWT_SECRET, { expiresIn: '24h' });

        res.json({
            success: true,
            token,
            admin: {
                id: admin.id,
                name: admin.name,
                email: admin.email
            }
        });
    } catch (error) {
        console.error('Admin login error:', error);
        res.status(500).json({ success: false, error: 'Login failed' });
    }
});

// Add Google Sheet source
app.post('/api/admin/add-source', async (req, res) => {
    try {
        const { sheetId, range } = req.body;

        if (!sheetId) {
            return res.status(400).json({ success: false, error: 'Sheet ID required' });
        }

        const sources = await readJSON(SOURCES_FILE);
        sources.push({
            id: Date.now().toString(),
            sheetId,
            range: range || 'Sheet1!A2:Z',
            addedAt: new Date().toISOString()
        });

        await writeJSON(SOURCES_FILE, sources);

        // Refresh student cache
        await fetchStudentsFromSheets();

        res.json({ success: true, message: 'Source added successfully' });
    } catch (error) {
        console.error('Error adding source:', error);
        res.status(500).json({ success: false, error: 'Failed to add source' });
    }
});

// Serve frontend
app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'public', 'index-auth.html'));
});

app.get('/admin.html', (req, res) => {
    res.sendFile(path.join(__dirname, 'public', 'admin.html'));
});

// Start server
async function startServer() {
    await initializeDataFiles();
    await initializeGoogleSheets();
    await fetchStudentsFromSheets();

    app.listen(PORT, () => {
        console.log('='.repeat(60));
        console.log(`🚀 Student Marks Portal`);
        console.log(`📡 Server running on http://localhost:${PORT}`);
        console.log(`💾 Storage: JSON Files`);
        console.log(`📊 Cached Students: ${studentCache.length}`);
        console.log('='.repeat(60));
    });
}

if (require.main === module) {
    startServer();
}

module.exports = app;
