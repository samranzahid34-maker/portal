// Enhanced Student Marks Portal with Registration + Login
const API_BASE_URL = '/api';

// DOM Elements
const authSection = document.getElementById('authSection');
const resultsSection = document.getElementById('resultsSection');
const loginForm = document.getElementById('loginForm');
const registerForm = document.getElementById('registerForm');
const logoutBtn = document.getElementById('logoutBtn');
const logoutSection = document.getElementById('logoutSection'); // Navbar item

// Check if user is already logged in
document.addEventListener('DOMContentLoaded', () => {
    const token = localStorage.getItem('authToken');
    if (token) {
        // Verify token and load marks
        fetchStudentMarks(token);
    }
});

// Registration Form Handler
if (registerForm) {
    registerForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        hideAlert();

        const rollNo = document.getElementById('registerRollNumber').value.trim();
        const email = document.getElementById('registerEmail').value.trim();
        const name = document.getElementById('registerName').value.trim();
        const password = document.getElementById('registerPassword').value;

        if (!rollNo || !email || !name || !password) {
            showAlert('Please fill in all fields', 'error');
            return;
        }

        try {
            const response = await fetch(`${API_BASE_URL}/register`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ rollNo, email, name, password })
            });

            const data = await response.json();

            if (data.success) {
                showAlert(`Registration successful! Welcome ${data.data.name}. You can now login.`, 'success');
                setTimeout(() => {
                    switchTab('login');
                    if (document.getElementById('loginRollNumber')) document.getElementById('loginRollNumber').value = rollNo;
                    if (document.getElementById('loginEmail')) document.getElementById('loginEmail').value = email;
                }, 2000);
            } else {
                showAlert(data.error || 'Registration failed', 'error');
            }
        } catch (error) {
            showAlert('Network error. Please check your connection.', 'error');
            console.error('Registration error:', error);
        }
    });
}

// Login Form Handler
if (loginForm) {
    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        hideAlert();

        const rollNo = document.getElementById('loginRollNumber').value.trim();
        const email = document.getElementById('loginEmail').value.trim();
        const password = document.getElementById('loginPassword').value;

        if (!rollNo || !email || !password) {
            showAlert('Please fill in all fields', 'error');
            return;
        }

        try {
            const response = await fetch(`${API_BASE_URL}/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ rollNo, email, password })
            });

            const data = await response.json();

            if (data.success) {
                localStorage.setItem('authToken', data.token);
                localStorage.setItem('userRollNo', data.user.rollNo);
                localStorage.setItem('userName', data.user.name);
                await fetchStudentMarks(data.token);
            } else {
                if (data.needsRegistration) {
                    showAlert(data.error + ' Click here to register.', 'error');
                    setTimeout(() => switchTab('register'), 2000);
                } else {
                    showAlert(data.error || 'Login failed', 'error');
                }
            }
        } catch (error) {
            showAlert('Network error. Please check your connection.', 'error');
            console.error('Login error:', error);
        }
    });
}

// Fetch Student Marks
async function fetchStudentMarks(token) {
    try {
        const response = await fetch(`${API_BASE_URL}/student/marks`, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });

        const data = await response.json();

        if (data.success) {
            displayMarks(data.student);
            showResultsSection();
        } else {
            localStorage.clear();
            showAlert('Session expired. Please login again.', 'error');
            showAuthSection();
        }
    } catch (error) {
        showAlert('Failed to load marks. Please try again.', 'error');
        console.error('Fetch marks error:', error);
    }
}

// Display Marks
function displayMarks(student) {
    if (document.getElementById('studentName')) document.getElementById('studentName').textContent = student.name;
    if (document.getElementById('displayRollNumber')) document.getElementById('displayRollNumber').textContent = student.rollNo;

    let totalObtained = 0;
    student.subjects.forEach(subject => {
        // Parse "85" or "85/100"
        let val = 0;
        const str = subject.obtained.toString();
        if (str.includes('/')) {
            val = parseFloat(str.split('/')[0]);
        } else {
            val = parseFloat(str);
        }
        if (!isNaN(val)) totalObtained += val;
    });

    if (document.getElementById('totalMarks')) document.getElementById('totalMarks').textContent = `${totalObtained}`;

    const table = document.getElementById('marksTable');
    if (!table) return;

    const thead = table.querySelector('thead');
    const tbody = table.querySelector('tbody');

    thead.innerHTML = '';
    tbody.innerHTML = '';

    // Create header row
    const headerRow = document.createElement('tr');
    student.subjects.forEach(subject => {
        const th = document.createElement('th');
        th.textContent = subject.name;
        headerRow.appendChild(th);
    });

    thead.appendChild(headerRow);

    // Create data row
    const dataRow = document.createElement('tr');
    student.subjects.forEach(subject => {
        const td = document.createElement('td');
        td.textContent = subject.obtained;
        dataRow.appendChild(td);
    });

    tbody.appendChild(dataRow);
}

// Logout Handler
if (logoutBtn) {
    logoutBtn.addEventListener('click', () => {
        localStorage.clear();
        showAuthSection();
        if (loginForm) loginForm.reset();
        if (registerForm) registerForm.reset();
        hideAlert();
    });
}

// UI Helper Functions
function showAuthSection() {
    if (authSection) authSection.classList.remove('hidden');
    if (resultsSection) resultsSection.classList.add('hidden');
    if (logoutSection) logoutSection.classList.add('hidden');
}

function showResultsSection() {
    if (authSection) authSection.classList.add('hidden');
    if (resultsSection) resultsSection.classList.remove('hidden');
    if (logoutSection) logoutSection.classList.remove('hidden');
}

function showAlert(message, type = 'error') {
    const errorAlert = document.getElementById('errorAlert');
    const successAlert = document.getElementById('successAlert');

    if (type === 'error') {
        if (document.getElementById('errorMessage')) document.getElementById('errorMessage').textContent = message;
        if (errorAlert) errorAlert.classList.remove('hidden');
        if (successAlert) successAlert.classList.add('hidden');
    } else {
        if (document.getElementById('successMessage')) document.getElementById('successMessage').textContent = message;
        if (successAlert) successAlert.classList.remove('hidden');
        if (errorAlert) errorAlert.classList.add('hidden');
    }
}

function hideAlert() {
    if (document.getElementById('errorAlert')) document.getElementById('errorAlert').classList.add('hidden');
    if (document.getElementById('successAlert')) document.getElementById('successAlert').classList.add('hidden');
}
