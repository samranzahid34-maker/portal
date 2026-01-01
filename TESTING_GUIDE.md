# 🧪 Manual Testing Guide - Registration + Login System

## ✅ Test Results Summary

**Automated test completed successfully!**

Registration file created at: `s:\lgu\marksheet\registrations.json`

Sample registration found:
```json
{
  "FA-2021/BSCS/087": {
    "email": "test.student@university.edu",
    "name": "zaid akram",
    "registeredAt": "2025-12-31T12:17:32.200Z"
  }
}
```

---

## 🎯 Manual Testing Steps

### **Test 1: Open the Portal**

1. Open your browser
2. Go to: `http://localhost:3000`
3. ✅ You should see a portal with two tabs: **"Login"** and **"Register"**

---

### **Test 2: Register a New Student**

1. **Click the "Register" tab**
2. **Enter details**:
   - Roll Number: `Fa-2022/BSCS/071` (use a real roll number from your Google Sheet)
   - Email: `your.email@example.com` (use your real email)
3. **Click "Register" button**

**Expected Result:**
- ✅ Success message: "Registration successful! Welcome [Student Name]. You can now login."
- ✅ Auto-switches to Login tab
- ✅ Roll number and email pre-filled in login form

---

### **Test 3: Test Duplicate Roll Number (Security Test)**

1. **Click "Register" tab again**
2. **Enter**:
   - Roll Number: `Fa-2022/BSCS/071` (same as before)
   - Email: `different.email@example.com` (different email)
3. **Click "Register"**

**Expected Result:**
- ❌ Error message: "This roll number is already registered. Please login instead."
- ✅ **SECURITY PASS**: Cannot register same roll number twice

---

### **Test 4: Test Duplicate Email (Security Test)**

1. **Still on Register tab**
2. **Enter**:
   - Roll Number: `Fa-2021/BSCS/087` (different roll number)
   - Email: `your.email@example.com` (same email as Test 2)
3. **Click "Register"**

**Expected Result:**
- ❌ Error message: "This email is already registered with another roll number."
- ✅ **SECURITY PASS**: Cannot use same email for multiple students

---

### **Test 5: Login with Correct Credentials**

1. **Go to "Login" tab**
2. **Enter**:
   - Roll Number: `Fa-2022/BSCS/071`
   - Email: `your.email@example.com`
3. **Click "Login" button**

**Expected Result:**
- ✅ Success! Portal shows your marks
- ✅ You see:
  - Your name
  - Your roll number
  - Total marks
  - Percentage
  - Grade
  - Subject-wise breakdown
  - Performance charts

---

### **Test 6: Login with Wrong Email (Security Test)**

1. **Logout** (click Logout button in top right)
2. **On Login tab, enter**:
   - Roll Number: `Fa-2022/BSCS/071` (correct)
   - Email: `wrong.email@example.com` (wrong)
3. **Click "Login"**

**Expected Result:**
- ❌ Error: "Invalid roll number or email combination."
- ✅ **SECURITY PASS**: Must know BOTH correct roll number AND correct email

---

### **Test 7: Test Session Persistence**

1. **Login successfully** (use correct credentials)
2. **See your marks**
3. **Refresh the page** (press F5)

**Expected Result:**
- ✅ Still logged in!
- ✅ Marks still displayed
- ✅ No need to login again
- ✅ **Session persists** using JWT token

---

### **Test 8: Test Logout**

1. **While logged in, click "Logout" button**

**Expected Result:**
- ✅ Redirected to Login/Register page
- ✅ All session data cleared
- ✅ Cannot see marks anymore

---

### **Test 9: Test Invalid Roll Number**

1. **Go to Register tab**
2. **Enter**:
   - Roll Number: `INVALID-999` (not in Google Sheet)
   - Email: `test@example.com`
3. **Click "Register"**

**Expected Result:**
- ❌ Error: "Invalid roll number. Please check your roll number and try again."
- ✅ **SECURITY PASS**: Only valid students can register

---

### **Test 10: Test Login Before Registration**

1. **Go to Login tab**
2. **Enter credentials for a student who hasn't registered yet**:
   - Roll Number: `Fa-2022/BSCS/060` (valid, but not registered)
   - Email: `notregistered@example.com`
3. **Click "Login"**

**Expected Result:**
- ❌ Error: "You are not registered. Please register first."
- ✅ Auto-suggests to register
- ✅ **SECURITY PASS**: Must register before login

---

## 📊 Security Checklist

Test each security feature:

| Security Feature | Test | Expected Result | Status |
|-----------------|------|-----------------|--------|
| **One Roll Number** | Register same roll number twice | ❌ Error message | ☐ |
| **One Email** | Use same email for 2 students | ❌ Error message | ☐ |
| **Valid Roll Number Only** | Register fake roll number | ❌ Error message | ☐ |
| **Registration Required** | Login without registering | ❌ Error message | ☐ |
| **Email Must Match** | Login with wrong email | ❌ Error message | ☐ |
| **Session Persistence** | Refresh page while logged in | ✅ Stays logged in | ☐ |
| **Secure Logout** | Logout and try to access marks | ❌ Cannot access | ☐ |
| **Token Authentication** | Access marks without login | ❌ Redirects to login | ☐ |

---

## 🎨 UI / UX Checklist

| Feature | Description | Status |
|---------|-------------|--------|
| **Tab Navigation** | Can switch between Login/Register | ☐ |
| **Form Validation** | Required fields marked | ☐ |
| **Error Messages** | Clear, helpful error messages | ☐ |
| **Success Messages** | Confirmation on registration | ☐ |
| **Loading States** | Shows "Loading..." during operations | ☐ |
| **Responsive Design** | Works on mobile/tablet | ☐ |
| **Auto-switch** | After registration, goes to login | ☐ |
| **Logout Button** | Visible and works | ☐ |

---

## 📁 Files to Check

### **1. registrations.json**
Location: `s:\lgu\marksheet\registrations.json`

Check this file to see all registered students:
```bash
cat registrations.json
```

Expected format:
```json
{
  "FA-2021/BSCS/087": {
    "email": "student@example.com",
    "rollNo": "FA-2021/BSCS/087",
    "name": "Student Name",
    "registeredAt": "2025-12-31T12:00:00.000Z"
  }
}
```

### **2. Server Logs**
Check the terminal where you ran `npm run start-auth`

You should see messages like:
```
✓ New registration: FA-2021/BSCS/087 - student@example.com
✓ Successful login: FA-2021/BSCS/087
```

---

## 🐛 Troubleshooting

### **Problem: "Student not found" error**
**Solution**: Make sure the roll number exists in your Google Sheet

### **Problem: "This email is already registered"**
**Solution**: This is expected! It means the security is working. Use a different email.

### **Problem: Can't see Login/Register tabs**
**Solution**: 
1. Make sure you're running `npm run start-auth` (not `npm start`)
2. Clear browser cache (Ctrl+Shift+Delete)
3. Go to `http://localhost:3000` in a new incognito window

### **Problem: "Session expired" message**
**Solution**: Token expired (24 hours). Just login again.

### **Problem: Portal looks different**
**Solution**: You might be on the old version. Make sure:
- Server running: `npm run start-auth` ✅
- Old server stopped: `npm start` ❌

---

## ✅ Quick Verification

Run this command to verify setup:
```bash
# Check if server is running
curl http://localhost:3000/api/health

# Check registration file
cat registrations.json
```

---

## 🎯 Success Criteria

Your system is working perfectly if:

1. ✅ Can register with roll number + email
2. ✅ Cannot register same roll number twice
3. ✅ Cannot use same email for multiple students
4. ✅ Can login with roll number + email
5. ✅ Cannot login with wrong email
6. ✅ Can see marks after login
7. ✅ Session persists on page refresh
8. ✅ Can logout successfully
9. ✅ Invalid roll numbers are rejected
10. ✅ Must register before login

---

## 📸 What You Should See

### **Registration Page**
- Two tabs: "Login" | "Register"
- Register form with:
  - Roll Number field
  - Email field
  - Register button
  - Link to switch to Login

### **After Successful Registration**
- Green success message
- Auto-switches to Login tab
- Fields pre-filled

### **Login Page**
- Login form with:
  - Roll Number field
  - Email field
  - Login button
  - Link to switch to Register

### **Marks Page (After Login)**
- Student name and roll number
- Three summary cards: Total, Percentage, Grade
- Subject-wise table
- Performance charts
- Logout button

---

## 🎉 All Tests Passed?

If all tests pass, your system has:
✅ **Secure Registration** - Only valid students can register
✅ **Email Privacy** - One email per student (no sharing)
✅ **Dual Authentication** - Requires roll number AND email
✅ **Session Management** - JWT tokens with 24-hour expiry
✅ **Data Protection** - Server-side validation
✅ **User Experience** - Smooth registration → login → marks flow

**Your portal is production-ready!** 🚀

---

**Last Updated:** 2025-12-31
**Server:** Run with `npm run start-auth`
**URL:** http://localhost:3000
