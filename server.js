const express = require('express');
const cors = require('cors');
const path = require('path');
const bcrypt = require('bcrypt');
const jwt = require('jsonwebtoken');
const mongoose = require('mongoose');
const { google } = require('googleapis');
require('dotenv').config();

const app = express();
const PORT = process.env.PORT || 3000;
const JWT_SECRET = process.env.JWT_SECRET || 'your-secret-key-change-in-production';

// Middleware
app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

// MongoDB Connection
let isMongoConnected = false;

async function connectDB() {
    if (!process.env.MONGODB_URI) {
        console.error('✗ MONGODB_URI not set in environment variables');
        return;
    }

    try {
        console.log('Attempting to connect to MongoDB...');
        await mongoose.connect(process.env.MONGODB_URI);
        isMongoConnected = true;
        console.log('✓ Connected to MongoDB successfully');
    } catch (err) {
        console.error('✗ MongoDB Connection Error:', err.message);
        isMongoConnected = false;
    }
}

// MongoDB Schemas
const StudentSchema = new mongoose.Schema({
    rollNumber: { type: String, required: true, unique: true },
    name: String,
    email: { type: String, required: true },
    password: { type: String, required: true },
    createdAt: { type: Date, default: Date.now }
});

const AdminSchema = new mongoose.Schema({
    name: { type: String, required: true },
    email: { type: String, required: true, unique: true },
    password: { type: String, required: true },
    createdAt: { type: Date, default: Date.now }
});

const SourceSchema = new mongoose.Schema({
    sheetId: { type: String, required: true },
    range: { type: String, default: 'Sheet1!A2:Z' },
    addedAt: { type: Date, default: Date.now }
});

const Student = mongoose.model('Student', StudentSchema);
const Admin = mongoose.model('Admin', AdminSchema);
const Source = mongoose.model('Source', SourceSchema);

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

async function fetchStudentsFromSheets() {
    if (!sheetsClient) {
        console.log('Google Sheets not initialized');
        return [];
    }

    try {
        const sources = await Source.find();
        const allStudents = [];

        for (const source of sources) {
            try {
                const response = await sheetsClient.spreadsheets.values.get({
                    spreadsheetId: source.sheetId,
                    range: source.range,
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
        dbConnected: isMongoConnected,
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

        if (!isMongoConnected) {
            return res.status(500).json({ success: false, error: 'Database not connected' });
        }

        // Check if roll number exists in cache
        const studentExists = studentCache.find(s => s.rollNumber === rollNumber);
        if (!studentExists) {
            return res.status(400).json({ success: false, error: 'Invalid roll number. Please check your roll number and try again.' });
        }

        // Check if already registered
        const existing = await Student.findOne({ rollNumber });
        if (existing) {
            return res.status(400).json({ success: false, error: 'Student already registered' });
        }

        // Hash password and save
        const hashedPassword = await bcrypt.hash(password, 10);
        const student = new Student({
            rollNumber,
            name: name || studentExists.name,
            email,
            password: hashedPassword
        });

        await student.save();

        res.json({ success: true, message: 'Registration successful! You can now login.' });
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

        if (!isMongoConnected) {
            return res.status(500).json({ success: false, error: 'Database not connected' });
        }

        const student = await Student.findOne({ rollNumber, email });

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

        if (!isMongoConnected) {
            return res.status(500).json({ success: false, error: 'Database not connected' });
        }

        const existing = await Admin.findOne({ email });
        if (existing) {
            return res.status(400).json({ success: false, error: 'Admin already exists' });
        }

        const hashedPassword = await bcrypt.hash(password, 10);
        const admin = new Admin({
            name,
            email,
            password: hashedPassword
        });

        await admin.save();

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

        if (!isMongoConnected) {
            return res.status(500).json({ success: false, error: 'Database not connected' });
        }

        const admin = await Admin.findOne({ email });

        if (!admin) {
            return res.status(401).json({ success: false, error: 'Invalid credentials' });
        }

        const passwordMatch = await bcrypt.compare(password, admin.password);
        if (!passwordMatch) {
            return res.status(401).json({ success: false, error: 'Invalid credentials' });
        }

        const token = jwt.sign({ id: admin._id, email: admin.email }, JWT_SECRET, { expiresIn: '24h' });

        res.json({
            success: true,
            token,
            admin: {
                id: admin._id,
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

        if (!isMongoConnected) {
            return res.status(500).json({ success: false, error: 'Database not connected' });
        }

        const source = new Source({
            sheetId,
            range: range || 'Sheet1!A2:Z'
        });

        await source.save();

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
    await connectDB();
    await initializeGoogleSheets();

    if (isMongoConnected) {
        await fetchStudentsFromSheets();
    }

    app.listen(PORT, () => {
        console.log('='.repeat(60));
        console.log(`🚀 Student Marks Portal`);
        console.log(`📡 Server running on http://localhost:${PORT}`);
        console.log(`💾 Database: ${isMongoConnected ? 'MongoDB Connected' : 'MongoDB DISCONNECTED'}`);
        console.log(`📊 Cached Students: ${studentCache.length}`);
        console.log('='.repeat(60));
    });
}

// Initialize for Vercel serverless
connectDB();
initializeGoogleSheets().then(success => {
    if (success && isMongoConnected) {
        fetchStudentsFromSheets();
    }
});

if (require.main === module) {
    startServer();
}

module.exports = app;
