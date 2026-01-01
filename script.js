// Configuration
const CONFIG = {
    API_BASE_URL: 'http://localhost:3000/api',
    CACHE_DURATION: 5 * 60 * 1000, // 5 minutes
};

// State management
let currentStudent = null;
let marksCache = null;
let cacheTimestamp = null;

// DOM Elements
const loginSection = document.getElementById('loginSection');
const resultsSection = document.getElementById('resultsSection');
const loginForm = document.getElementById('loginForm');
const rollNumberInput = document.getElementById('rollNumber');
const errorAlert = document.getElementById('errorAlert');
const errorMessage = document.getElementById('errorMessage');
const loadingOverlay = document.getElementById('loadingOverlay');
const logoutBtn = document.getElementById('logoutBtn');
const studentName = document.getElementById('studentName');
const displayRollNumber = document.getElementById('displayRollNumber');
const totalMarks = document.getElementById('totalMarks');
const percentage = document.getElementById('percentage');
const gradeElement = document.getElementById('grade');
const marksTableBody = document.getElementById('marksTableBody');
const performanceChart = document.getElementById('performanceChart');

// Event Listeners
loginForm.addEventListener('submit', handleLogin);
logoutBtn.addEventListener('click', handleLogout);

// Login Handler
async function handleLogin(e) {
    e.preventDefault();

    const rollNo = rollNumberInput.value.trim().toUpperCase();

    if (!rollNo) {
        showError('Please enter your roll number');
        return;
    }

    hideError();
    showLoading();

    try {
        // Fetch student data
        const studentData = await fetchStudentData(rollNo);

        if (!studentData) {
            showError('Roll number not found. Please check and try again.');
            hideLoading();
            return;
        }

        // Store current student
        currentStudent = studentData;

        // Display results
        displayResults(studentData);

        // Hide login, show results
        loginSection.style.display = 'none';
        resultsSection.style.display = 'block';

        hideLoading();

    } catch (error) {
        console.error('Login error:', error);
        showError('Failed to load marks. Please try again later.');
        hideLoading();
    }
}

// Logout Handler
function handleLogout() {
    currentStudent = null;
    rollNumberInput.value = '';
    loginSection.style.display = 'block';
    resultsSection.style.display = 'none';
    hideError();
}

// Fetch Student Data from Backend API
async function fetchStudentData(rollNo) {
    try {
        const response = await fetch(`${CONFIG.API_BASE_URL}/student/${encodeURIComponent(rollNo)}`);

        if (!response.ok) {
            if (response.status === 404) {
                return null; // Student not found
            }
            throw new Error('Failed to fetch data');
        }

        const data = await response.json();

        if (!data.success) {
            throw new Error(data.error || 'Unknown error');
        }

        return data.student || null;

    } catch (error) {
        console.error('Fetch error:', error);

        // Fallback to mock data for testing
        console.warn('Using mock data for testing...');
        return getMockStudentData(rollNo);
    }
}

// Find student in cached data
function findStudentInCache(rollNo) {
    if (!marksCache) return null;
    return marksCache.find(student => student.rollNo.toUpperCase() === rollNo.toUpperCase()) || null;
}

// Display Results
function displayResults(student) {
    // Update student info
    studentName.textContent = student.name;
    displayRollNumber.textContent = student.rollNo;

    // Calculate totals
    const totals = calculateTotals(student.subjects);

    // Update summary cards
    totalMarks.textContent = `${totals.obtained} / ${totals.total}`;
    percentage.textContent = `${totals.percentage}%`;
    gradeElement.textContent = totals.overallGrade;

    // Populate marks table
    populateMarksTable(student.subjects);

    // Generate performance chart
    generatePerformanceChart(student.subjects);
}

// Calculate totals
function calculateTotals(subjects) {
    let totalObtained = 0;
    let totalMarks = 0;

    subjects.forEach(subject => {
        totalObtained += subject.obtained;
        totalMarks += subject.total;
    });

    const percentage = ((totalObtained / totalMarks) * 100).toFixed(2);
    const overallGrade = calculateGrade(percentage);

    return {
        obtained: totalObtained,
        total: totalMarks,
        percentage,
        overallGrade
    };
}

// Calculate grade based on percentage
function calculateGrade(percentage) {
    if (percentage >= 90) return 'A+';
    if (percentage >= 80) return 'A';
    if (percentage >= 70) return 'B+';
    if (percentage >= 60) return 'B';
    if (percentage >= 50) return 'C';
    if (percentage >= 40) return 'D';
    return 'F';
}

// Get grade class for styling
function getGradeClass(grade) {
    if (grade.startsWith('A')) return 'grade-a';
    if (grade.startsWith('B')) return 'grade-b';
    if (grade.startsWith('C')) return 'grade-c';
    return 'grade-d';
}

// Populate marks table
function populateMarksTable(subjects) {
    marksTableBody.innerHTML = '';

    subjects.forEach(subject => {
        const percentage = ((subject.obtained / subject.total) * 100).toFixed(2);
        const grade = calculateGrade(percentage);
        const gradeClass = getGradeClass(grade);

        const row = document.createElement('tr');
        row.innerHTML = `
            <td><strong>${subject.name}</strong></td>
            <td>${subject.obtained}</td>
            <td>${subject.total}</td>
            <td>${percentage}%</td>
            <td><span class="grade-badge ${gradeClass}">${grade}</span></td>
        `;

        marksTableBody.appendChild(row);
    });
}

// Generate performance chart
function generatePerformanceChart(subjects) {
    performanceChart.innerHTML = '';

    subjects.forEach(subject => {
        const percentage = (subject.obtained / subject.total) * 100;

        const bar = document.createElement('div');
        bar.className = 'chart-bar';
        bar.style.height = `${percentage * 2}px`; // Scale for visibility

        const label = document.createElement('div');
        label.className = 'chart-bar-label';
        label.textContent = subject.name.substring(0, 10);

        const value = document.createElement('div');
        value.className = 'chart-bar-value';
        value.textContent = `${percentage.toFixed(0)}%`;

        bar.appendChild(label);
        bar.appendChild(value);
        performanceChart.appendChild(bar);
    });
}

// Show/Hide Error
function showError(message) {
    errorMessage.textContent = message;
    errorAlert.style.display = 'flex';
}

function hideError() {
    errorAlert.style.display = 'none';
}

// Show/Hide Loading
function showLoading() {
    loadingOverlay.style.display = 'flex';
}

function hideLoading() {
    loadingOverlay.style.display = 'none';
}

// Mock Data for Development/Testing
function getMockStudentData(rollNo) {
    const mockDatabase = [
        {
            rollNo: 'CS001',
            name: 'Alice Johnson',
            subjects: [
                { name: 'Mathematics', obtained: 85, total: 100 },
                { name: 'Physics', obtained: 78, total: 100 },
                { name: 'Chemistry', obtained: 82, total: 100 },
                { name: 'Computer Science', obtained: 92, total: 100 },
                { name: 'English', obtained: 88, total: 100 }
            ]
        },
        {
            rollNo: 'CS002',
            name: 'Bob Smith',
            subjects: [
                { name: 'Mathematics', obtained: 72, total: 100 },
                { name: 'Physics', obtained: 68, total: 100 },
                { name: 'Chemistry', obtained: 75, total: 100 },
                { name: 'Computer Science', obtained: 88, total: 100 },
                { name: 'English', obtained: 80, total: 100 }
            ]
        },
        {
            rollNo: 'CS003',
            name: 'Carol Williams',
            subjects: [
                { name: 'Mathematics', obtained: 95, total: 100 },
                { name: 'Physics', obtained: 91, total: 100 },
                { name: 'Chemistry', obtained: 89, total: 100 },
                { name: 'Computer Science', obtained: 97, total: 100 },
                { name: 'English', obtained: 93, total: 100 }
            ]
        }
    ];

    return mockDatabase.find(student => student.rollNo.toUpperCase() === rollNo.toUpperCase()) || null;
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    console.log('Student Marks Portal initialized');
    rollNumberInput.focus();
});
