// Enhanced Node.js Server with Registration + Login Authentication
const express = require('express');
const cors = require('cors');
const { google } = require('googleapis');
const path = require('path');
const fs = require('fs').promises;
const jwt = require('jsonwebtoken');
const bcrypt = require('bcrypt');
const mongoose = require('mongoose');
require('dotenv').config();

const app = express();
const PORT = process.env.PORT || 3000;

// Middleware
app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

// Configuration
const JWT_SECRET = process.env.JWT_SECRET || 'your-secret-key-change-this-in-production';

// --- MONGODB SETUP ---
let isMongoConnected = false;

const RegistrationSchema = new mongoose.Schema({
    normalizedRollNo: { type: String, required: true, unique: true },
    rollNo: String,
    name: String,
    email: String,
    registeredAt: Date
});

const AdminSchema = new mongoose.Schema({
    id: String,
    name: String,
    email: { type: String, unique: true },
    password: String,
    role: String,
    createdAt: Date
});

const SourceSchema = new mongoose.Schema({
    _id: String, // Unique internal ID
    id: String, // Google Sheet ID
    name: String, // Tab Name
    description: String,
    ownerId: String // Admin ID who owns this
});

const RegistrationModel = mongoose.model('Registration', RegistrationSchema);
const AdminModel = mongoose.model('Admin', AdminSchema);
const SourceModel = mongoose.model('Source', SourceSchema);

async function connectDB() {
    if (process.env.MONGODB_URI) {
        try {
            await mongoose.connect(process.env.MONGODB_URI);
            isMongoConnected = true;
            console.log('✓ Connected to MongoDB');
        } catch (err) {
            console.error('✗ MongoDB Connection Error:', err.message);
            // We do not fallback to file system anymore. Fatal error if DB essential.
        }
    } else {
        console.error('✗ MONGODB_URI is missing in environment variables.');
    }
}

// --- DATA ACCESS LAYER (MongoDB Only) ---

// Registrations
async function findRegistration(normalizedRollNo) {
    if (!isMongoConnected) return null;
    return await RegistrationModel.findOne({ normalizedRollNo });
}

async function saveRegistration(data) {
    if (!isMongoConnected) throw new Error('Database not connected');
    const exists = await RegistrationModel.findOne({ normalizedRollNo: data.normalizedRollNo });
    if (exists) {
        Object.assign(exists, data);
        await exists.save();
    } else {
        await RegistrationModel.create(data);
    }
}

// Admins
async function findAllAdmins() {
    if (!isMongoConnected) return [];
    return await AdminModel.find({});
}

async function saveAdmin(data) {
    if (!isMongoConnected) throw new Error('Database not connected');
    await AdminModel.create(data);
}

// Sources
async function loadMarksSources() {
    if (!isMongoConnected) return [];
    const sources = await SourceModel.find({});
    // Map _id (internal) if needed, but schema handles it.
    // Mongoose returns _doc usually, we can just return the array of docs.
    return sources;
}

async function saveMarksSources(sources) {
    // This helper was designed for full-file overwrite.
    // With Mongo, we should be careful. 
    // The current usage of this function in endpoints is: "modify array, save all".
    // Best way to adapt without rewriting all endpoints logic is:
    // Delete all and insert all (inefficient but safe for small data)
    // OR, better: The endpoints should be refactored to use create/update/delete individual items.
    // However, to keep this refactor focused, we will stick to the "sync" approach for `sources`.

    if (!isMongoConnected) throw new Error('Database not connected');

    // Check if we are adding or updating. 
    // Since this function receives the WHOLE array, we treat it as the source of truth.
    await SourceModel.deleteMany({});
    if (sources.length > 0) {
        // Ensure _id is present for all
        const validSources = sources.map(s => ({
            ...s,
            _id: s._id || Date.now().toString() + Math.random().toString(36).substr(2, 5)
        }));
        await SourceModel.insertMany(validSources);
    }
}

// Initialize Google Sheets API
let sheetsAPI = null;

async function initializeGoogleSheets() {
    try {
        let authConfig = {
            scopes: ['https://www.googleapis.com/auth/spreadsheets.readonly'],
        };

        if (process.env.GOOGLE_CREDENTIALS_JSON) {
            try {
                const credentials = JSON.parse(process.env.GOOGLE_CREDENTIALS_JSON);
                authConfig.credentials = credentials;
                console.log('ℹ Using credentials from Environment Variable');
            } catch (e) {
                console.error('✗ Failed to parse GOOGLE_CREDENTIALS_JSON');
            }
        } else {
            // Check if file exists before trying to use it
            try {
                await fs.access('credentials.json');
                authConfig.keyFile = 'credentials.json';
            } catch {
                console.warn('ℹ No credentials.json found and no GOOGLE_CREDENTIALS_JSON set.');
                return false;
            }
        }

        const auth = new google.auth.GoogleAuth(authConfig);
        const authClient = await auth.getClient();
        sheetsAPI = google.sheets({ version: 'v4', auth: authClient });

        console.log('✓ Google Sheets API initialized successfully');
        return true;
    } catch (error) {
        console.error('✗ Failed to initialize Google Sheets API:', error.message);
        return false;
    }
}

// Helper to normalize roll numbers
const normalizeCode = (str) => str ? str.toString().replace(/[^a-zA-Z0-9]/g, '').toUpperCase() : '';

// Parse student data from sheet rows
function parseStudentData(rows, sourceName) {
    if (!rows || rows.length < 2) return [];

    const headers = rows[0].map(h => h.toString().toLowerCase().trim());
    const students = [];

    // Dynamic Column Discovery
    let rollNoIndex = headers.findIndex(h => h.includes('roll') || h.includes('id') || h.includes('reg'));
    let nameIndex = headers.findIndex(h => h.includes('name') || h.includes('student'));
    let emailIndex = headers.findIndex(h => h.includes('email') || h.includes('mail') || h.includes('e-mail'));

    if (rollNoIndex === -1) rollNoIndex = 0;
    if (nameIndex === -1) nameIndex = 1;

    if (nameIndex === rollNoIndex) nameIndex = rollNoIndex + 1;

    for (let i = 1; i < rows.length; i++) {
        const row = rows[i];
        if (!row || row.length <= rollNoIndex) continue;

        const rollNoRaw = row[rollNoIndex];
        if (!rollNoRaw) continue;

        const student = {
            rollNo: rollNoRaw.toString().trim(),
            normalizedRollNo: normalizeCode(rollNoRaw),
            name: row[nameIndex] ? row[nameIndex].toString().trim() : 'Unknown',
            officialEmail: (emailIndex !== -1 && row[emailIndex]) ? row[emailIndex].toString().trim().toLowerCase() : null,
            source: sourceName,
            subjects: []
        };

        for (let j = 0; j < headers.length; j++) {
            if (j === rollNoIndex || j === nameIndex) continue;

            const subjectName = rows[0][j]?.toString().trim();
            const marks = row[j]?.toString().trim();

            if (subjectName && marks && marks.match(/\d/)) {
                student.subjects.push({
                    name: subjectName,
                    obtained: marks
                });
            }
        }

        if (student.rollNo) {
            students.push(student);
        }
    }

    return students;
}

let sourceStatuses = {};

// Fetch all students data from ALL Google Sheets
async function fetchAllStudentsData() {
    try {
        if (!sheetsAPI) {
            throw new Error('Google Sheets API not initialized');
        }

        const sources = await loadMarksSources(); // Fetched from DB
        let allStudents = [];
        console.log(`Fetching data from ${sources.length} sources...`);

        let newStatuses = {};

        for (const source of sources) {
            try {
                if (!source.id) continue;

                const response = await sheetsAPI.spreadsheets.values.get({
                    spreadsheetId: source.id,
                    range: `${source.name}!A:Z`,
                });

                const rows = response.data.values;
                const students = parseStudentData(rows, source.description || source.name);

                newStatuses[source._id] = { status: 'connected', count: students.length, timestamp: new Date() };
                allStudents = [...allStudents, ...students];

            } catch (err) {
                console.error(`  ✗ Error fetching source ${source.name}:`, err.message);
                newStatuses[source._id] = { status: 'error', error: err.message, timestamp: new Date() };
            }
        }

        sourceStatuses = newStatuses;
        return allStudents;
    } catch (error) {
        console.error('Error fetching data from Google Sheets:', error.message);
        throw error;
    }
}

// In-memory cache
let studentsCache = null;
let cacheTimestamp = null;
const CACHE_DURATION = 5 * 60 * 1000; // 5 minutes

async function getCachedStudents(forceRefresh = false) {
    if (forceRefresh || !studentsCache || !cacheTimestamp || (Date.now() - cacheTimestamp > CACHE_DURATION)) {
        console.log('Refreshing cache from Google Sheets...');
        try {
            studentsCache = await fetchAllStudentsData();
            cacheTimestamp = Date.now();
            console.log(`Cached ${studentsCache.length} students`);
        } catch (e) {
            console.error('Failed to refresh cache, returning empty or old data');
            if (!studentsCache) studentsCache = [];
        }
    }
    return studentsCache;
}

// Middleware to verify JWT token
function authenticateToken(req, res, next) {
    const authHeader = req.headers['authorization'];
    const token = authHeader && authHeader.split(' ')[1];

    if (!token) {
        return res.status(401).json({ success: false, error: 'Access token required' });
    }

    jwt.verify(token, JWT_SECRET, (err, user) => {
        if (err) {
            return res.status(403).json({ success: false, error: 'Invalid or expired token' });
        }
        req.user = user;
        next();
    });
}

// API Endpoint: Register a student
app.post('/api/register', async (req, res) => {
    try {
        const { rollNo, email, password } = req.body; // Added password

        if (!rollNo || !email || !password) { // Check for password
            return res.status(400).json({ success: false, error: 'Roll number, email, and password are required' });
        }

        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRegex.test(email)) {
            return res.status(400).json({ success: false, error: 'Invalid email format' });
        }

        const userNormalizedRollVal = normalizeCode(rollNo);
        const normalizedEmail = email.toLowerCase().trim();

        // Check against Google Sheets
        const students = await getCachedStudents();
        const student = students.find(s => s.normalizedRollNo === userNormalizedRollVal);

        if (!student) {
            return res.status(404).json({ success: false, error: 'Invalid roll number. Please check your roll number and try again.' });
        }

        if (student.officialEmail) {
            if (student.officialEmail !== normalizedEmail) {
                return res.status(403).json({ success: false, error: 'Security Alert: The email you entered does not match our official records.' });
            }
        }

        // Check if student exists in DB
        const existingReg = await findRegistration(userNormalizedRollVal);

        if (existingReg && existingReg.password) {
            return res.status(409).json({ success: false, error: 'This roll number is already registered. Please login instead.' });
        }

        const hashedPassword = await bcrypt.hash(password, 10); // Hash password

        const userData = {
            normalizedRollNo: userNormalizedRollVal,
            rollNo: student.rollNo,
            email: normalizedEmail,
            name: student.name,
            password: hashedPassword, // Save hashed password
            registeredAt: new Date()
        };

        await saveRegistration(userData);

        console.log(`✓ New registration: ${student.rollNo}`);
        res.json({
            success: true,
            message: 'Registration successful!',
            data: { rollNo: student.rollNo, name: student.name }
        });

    } catch (error) {
        console.error('Registration Error:', error);
        res.status(500).json({ success: false, error: 'Internal server error' });
    }
});

// API Endpoint: Login
app.post('/api/login', async (req, res) => {
    try {
        const { rollNo, email, password } = req.body; // Added password

        if (!rollNo || !email || !password) return res.status(400).json({ success: false, error: 'Roll number, email, and password are required' });

        const userNormalizedRollVal = normalizeCode(rollNo);
        const normalizedEmail = email.toLowerCase().trim();

        const registration = await findRegistration(userNormalizedRollVal);

        if (!registration) {
            return res.status(401).json({ success: false, error: 'You are not registered. Please register first.', needsRegistration: true });
        }

        // Check roll and email
        if (registration.email !== normalizedEmail) {
            return res.status(401).json({ success: false, error: 'Invalid roll number or email combination.' });
        }

        // Check for legacy user (no password)
        if (!registration.password) {
            return res.status(401).json({ success: false, error: 'Account update required. Please Register again to set a password.', needsRegistration: true });
        }

        // Check password
        const passwordMatch = await bcrypt.compare(password, registration.password);
        if (!passwordMatch) {
            return res.status(401).json({ success: false, error: 'Invalid password.' });
        }

        const token = jwt.sign(
            { rollNo: registration.rollNo, normalizedRollNo: userNormalizedRollVal, email: normalizedEmail, name: registration.name },
            JWT_SECRET,
            { expiresIn: '24h' }
        );

        res.json({
            success: true,
            message: 'Login successful!',
            token: token,
            user: { rollNo: registration.rollNo, name: registration.name }
        });

    } catch (error) {
        console.error('Login Error:', error);
        res.status(500).json({ success: false, error: 'Internal server error' });
    }
});

// API Endpoint: Get marks
app.get('/api/student/marks', authenticateToken, async (req, res) => {
    try {
        const userNormalizedRoll = req.user.normalizedRollNo || normalizeCode(req.user.rollNo);
        const students = await getCachedStudents();
        const student = students.find(s => s.normalizedRollNo === userNormalizedRoll);

        if (!student) return res.status(404).json({ success: false, error: 'Student data not found' });

        res.json({
            success: true,
            student: { rollNo: student.rollNo, name: student.name, subjects: student.subjects }
        });

    } catch (error) {
        res.status(500).json({ success: false, error: 'Internal server error' });
    }
});

// API Endpoint: Check registration
app.post('/api/check-registration', async (req, res) => {
    try {
        const { rollNo } = req.body;
        if (!rollNo) return res.status(400).json({ success: false, error: 'Roll number is required' });

        const normalizedRollNo = normalizeCode(rollNo);
        const registration = await findRegistration(normalizedRollNo);

        res.json({ success: true, isRegistered: !!registration });
    } catch (error) {
        res.status(500).json({ success: false, error: 'Internal server error' });
    }
});

// API Endpoint: Health
app.get('/api/health', (req, res) => {
    res.json({
        success: true,
        status: 'Server is running',
        sheetsConnected: sheetsAPI !== null,
        dbConnected: isMongoConnected,
        cachedStudents: studentsCache ? studentsCache.length : 0
    });
});

app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'public', 'index-auth.html'));
});

// --- ADMIN API ENDPOINTS ---

// Admin Registration (RESTRICTED TO 1 ADMIN)
app.post('/api/admin/register', async (req, res) => {
    try {
        const { name, email, password } = req.body;

        if (!name || !email || !password) {
            return res.status(400).json({ success: false, error: 'All fields are required' });
        }

        if (!isMongoConnected) return res.status(500).json({ success: false, error: 'Database error' });

        // CRITICAL CHECK: Enforce Single Admin Policy
        const adminCount = await AdminModel.countDocuments({});
        if (adminCount >= 1) {
            return res.status(403).json({
                success: false,
                error: 'Admin registration is closed. This system allows only one administrator.'
            });
        }

        // Check if email already exists
        const existingAdmin = await AdminModel.findOne({ email });
        if (existingAdmin) {
            return res.status(409).json({ success: false, error: 'Email already registered' });
        }

        const hashedPassword = await bcrypt.hash(password, 10);

        const newAdmin = {
            id: Date.now().toString(),
            name,
            email,
            password: hashedPassword,
            role: 'admin',
            createdAt: new Date()
        };

        await saveAdmin(newAdmin);

        res.json({ success: true, message: 'Admin registered successfully' });
    } catch (error) {
        console.error('Admin Register Error:', error);
        res.status(500).json({ success: false, error: 'Registration failed' });
    }
});

// Admin Login
app.post('/api/admin/login', async (req, res) => {
    try {
        const { email, password } = req.body;

        if (!isMongoConnected) return res.status(500).json({ success: false, error: 'Database error' });

        const admin = await AdminModel.findOne({ email });

        if (!admin) {
            return res.status(401).json({ success: false, error: 'Invalid email or password' });
        }

        const match = await bcrypt.compare(password, admin.password);
        if (!match) {
            return res.status(401).json({ success: false, error: 'Invalid email or password' });
        }

        const token = jwt.sign(
            { id: admin.id, email: admin.email, role: 'admin' },
            JWT_SECRET,
            { expiresIn: '12h' }
        );

        res.json({
            success: true,
            token,
            user: { name: admin.name, email: admin.email }
        });

    } catch (error) {
        console.error('Admin Login Error:', error);
        res.status(500).json({ success: false, error: 'Login failed' });
    }
});

// Admin Middleware
function authenticateAdmin(req, res, next) {
    const authHeader = req.headers['authorization'];
    const token = authHeader && authHeader.split(' ')[1];

    if (!token) return res.status(401).json({ error: 'Admin token required' });

    jwt.verify(token, JWT_SECRET, (err, user) => {
        if (err || user.role !== 'admin') return res.status(403).json({ error: 'Invalid admin token' });
        req.admin = user;
        next();
    });
}

// Get All Sheets
app.get('/api/admin/sheets', authenticateAdmin, async (req, res) => {
    try {
        res.header('Cache-Control', 'no-store');
        const sources = await loadMarksSources();

        const mySources = sources.filter(s => s.ownerId === req.admin.id);

        const sourcesWithStatus = mySources.map(s => ({
            _id: s._id, // Pass _id for deletion
            id: s.id,
            name: s.name,
            description: s.description,
            ownerId: s.ownerId,
            status: sourceStatuses[s._id] || { status: 'unknown' }
        }));
        res.json({ success: true, sources: sourcesWithStatus });
    } catch (error) {
        res.status(500).json({ success: false, error: 'Failed to load sources' });
    }
});

// Add New Sheet
app.post('/api/admin/sheets', authenticateAdmin, async (req, res) => {
    try {
        const { id, name, description } = req.body;

        if (!id || !name) return res.status(400).json({ success: false, error: 'Sheet ID and Name are required' });

        const newSource = {
            _id: Date.now().toString() + Math.random().toString(36).substr(2, 5),
            id,
            name,
            description: description || 'New Sheet',
            ownerId: req.admin.id
        };

        if (isMongoConnected) {
            await SourceModel.create(newSource);
        } else {
            return res.status(500).json({ success: false, error: 'Database not connected' });
        }

        await getCachedStudents(true);

        res.json({ success: true, message: 'Sheet added successfully' });
    } catch (error) {
        console.error('Add Sheet Error:', error);
        res.status(500).json({ success: false, error: 'Failed to save source' });
    }
});

// Remove Sheet
app.delete('/api/admin/sheets/:uid', authenticateAdmin, async (req, res) => {
    try {
        const uid = req.params.uid;

        if (isMongoConnected) {
            const source = await SourceModel.findOne({ _id: uid });

            if (!source) {
                return res.status(404).json({ success: false, error: 'Sheet not found' });
            }

            if (source.ownerId && source.ownerId !== req.admin.id) {
                return res.status(403).json({ success: false, error: 'Permission denied' });
            }

            await SourceModel.deleteOne({ _id: uid });
            await getCachedStudents(true);
            res.json({ success: true, message: 'Sheet removed successfully' });
        } else {
            return res.status(500).json({ success: false, error: 'Database not connected' });
        }

    } catch (error) {
        console.error('Delete Sheet Error:', error);
        res.status(500).json({ success: false, error: 'Failed to remove source' });
    }
});

// Start server
async function startServer() {
    await connectDB();
    const sheetsInitialized = await initializeGoogleSheets();

    if (sheetsInitialized) {
        console.log('⟳  Initial data fetch started...');
        getCachedStudents(true).catch(err => console.error('Initial fetch failed:', err.message));
    }

    app.listen(PORT, () => {
        console.log('='.repeat(60));
        console.log(`🚀 Student Marks Portal`);
        console.log(`📡 Server running on http://localhost:${PORT}`);
        console.log(`💾 Storage: ${isMongoConnected ? 'MongoDB' : 'DISCONNECTED'}`);
        console.log('='.repeat(60));
    });
}

// Error handling
process.on('unhandledRejection', (error) => console.error('Unhandled rejection:', error));
process.on('uncaughtException', (error) => { console.error('Uncaught exception:', error); process.exit(1); });

if (require.main === module) {
    startServer();
}

module.exports = app;
