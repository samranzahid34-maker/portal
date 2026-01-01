// Node.js Server for Student Marks Portal with Google Drive Integration
const express = require('express');
const cors = require('cors');
const { google } = require('googleapis');
const path = require('path');
require('dotenv').config();

const app = express();
const PORT = process.env.PORT || 3000;

// Middleware
app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname)));

// Google Sheets Configuration
const SPREADSHEET_ID = process.env.GOOGLE_SHEETS_ID;
const SHEET_NAME = process.env.SHEET_NAME || 'Sheet1';

// Initialize Google Sheets API
let sheetsAPI = null;

async function initializeGoogleSheets() {
    try {
        // Authentication using Service Account
        const auth = new google.auth.GoogleAuth({
            keyFile: process.env.GOOGLE_SERVICE_ACCOUNT_KEY_FILE || 'credentials.json',
            scopes: ['https://www.googleapis.com/auth/spreadsheets.readonly'],
        });

        const authClient = await auth.getClient();
        sheetsAPI = google.sheets({ version: 'v4', auth: authClient });

        console.log('✓ Google Sheets API initialized successfully');
        return true;
    } catch (error) {
        console.error('✗ Failed to initialize Google Sheets API:', error.message);
        return false;
    }
}

// Parse student data from sheet rows
function parseStudentData(rows) {
    if (!rows || rows.length < 2) {
        return [];
    }

    const headers = rows[0]; // First row contains headers
    const students = [];

    // Expected format:
    // RollNo | Name | Subject1 | Subject2 | ... | SubjectN
    // CS001  | Alice | 85      | 78       | ... | 88

    for (let i = 1; i < rows.length; i++) {
        const row = rows[i];

        if (!row || row.length < 3) continue; // Skip invalid rows

        const student = {
            rollNo: row[0]?.toString().trim(),
            name: row[1]?.toString().trim(),
            subjects: []
        };

        // Parse subjects (starting from column 2)
        for (let j = 2; j < headers.length; j++) {
            const subjectName = headers[j]?.toString().trim();
            const marks = row[j]?.toString().trim();

            if (subjectName && marks) {
                // Support format: "85/100" or just "85"
                let obtained, total;

                if (marks.includes('/')) {
                    [obtained, total] = marks.split('/').map(m => parseInt(m.trim()));
                } else {
                    obtained = parseInt(marks);
                    total = 100; // Default total
                }

                if (!isNaN(obtained) && !isNaN(total)) {
                    student.subjects.push({
                        name: subjectName,
                        obtained,
                        total
                    });
                }
            }
        }

        if (student.rollNo && student.name && student.subjects.length > 0) {
            students.push(student);
        }
    }

    return students;
}

// Fetch all students data from Google Sheets
async function fetchAllStudentsData() {
    try {
        if (!sheetsAPI) {
            throw new Error('Google Sheets API not initialized');
        }

        const response = await sheetsAPI.spreadsheets.values.get({
            spreadsheetId: SPREADSHEET_ID,
            range: `${SHEET_NAME}!A:Z`, // Adjust range as needed
        });

        const rows = response.data.values;
        return parseStudentData(rows);
    } catch (error) {
        console.error('Error fetching data from Google Sheets:', error.message);
        throw error;
    }
}

// In-memory cache
let studentsCache = null;
let cacheTimestamp = null;
const CACHE_DURATION = 5 * 60 * 1000; // 5 minutes

// API Endpoint: Get student marks by roll number
app.get('/api/student/:rollNo', async (req, res) => {
    try {
        const rollNo = req.params.rollNo.toUpperCase().trim();

        if (!rollNo) {
            return res.status(400).json({
                success: false,
                error: 'Roll number is required'
            });
        }

        // Check cache
        if (!studentsCache || !cacheTimestamp || (Date.now() - cacheTimestamp > CACHE_DURATION)) {
            console.log('Refreshing cache from Google Sheets...');
            studentsCache = await fetchAllStudentsData();
            cacheTimestamp = Date.now();
            console.log(`Cached ${studentsCache.length} students`);
        }

        // Find student
        const student = studentsCache.find(s => s.rollNo.toUpperCase() === rollNo);

        if (!student) {
            return res.status(404).json({
                success: false,
                error: 'Student not found'
            });
        }

        // Return only requested student's data (security measure)
        res.json({
            success: true,
            student: {
                rollNo: student.rollNo,
                name: student.name,
                subjects: student.subjects
            }
        });

    } catch (error) {
        console.error('API Error:', error);
        res.status(500).json({
            success: false,
            error: 'Internal server error'
        });
    }
});

// API Endpoint: Health check
app.get('/api/health', (req, res) => {
    res.json({
        success: true,
        status: 'Server is running',
        sheetsConnected: sheetsAPI !== null,
        cachedStudents: studentsCache ? studentsCache.length : 0
    });
});

// Serve index.html for root route
app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'index.html'));
});

// Start server
async function startServer() {
    // Initialize Google Sheets API
    const sheetsInitialized = await initializeGoogleSheets();

    if (!sheetsInitialized) {
        console.warn('⚠ Warning: Server will start but Google Sheets integration is not available');
        console.warn('⚠ Make sure to set up credentials.json and environment variables');
    }

    app.listen(PORT, () => {
        console.log('='.repeat(50));
        console.log(`🚀 Student Marks Portal Server`);
        console.log(`📡 Server running on http://localhost:${PORT}`);
        console.log(`📊 Google Sheets: ${sheetsInitialized ? 'Connected' : 'Not Connected'}`);
        console.log('='.repeat(50));
    });
}

// Error handling
process.on('unhandledRejection', (error) => {
    console.error('Unhandled rejection:', error);
});

process.on('uncaughtException', (error) => {
    console.error('Uncaught exception:', error);
    process.exit(1);
});

// Start the server
startServer();
