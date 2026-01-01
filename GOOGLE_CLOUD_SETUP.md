# 🔐 Google Cloud Setup for Student Marks Portal

## Current Status
✅ Your spreadsheet ID is configured: `14NqKvdNnWgRG64-8jDuqcgB-BEl3IvuI`  
✅ `.env` file created  
☐ Google Cloud Service Account needs to be set up

---

## 🚀 Complete Setup Instructions

### Step 1: Create Google Cloud Project

1. **Go to [Google Cloud Console](https://console.cloud.google.com/)**

2. **Create a New Project:**
   - Click the project dropdown at the top (next to "Google Cloud")
   - Click "NEW PROJECT"
   - Project name: `Student-Marks-Portal` (or any name you prefer)
   - Click "CREATE"
   - Wait for project creation (a few seconds)

3. **Select Your Project:**
   - Make sure your new project is selected in the dropdown

---

### Step 2: Enable Google Sheets API

1. **Navigate to APIs & Services:**
   - Click the hamburger menu (☰) → "APIs & Services" → "Library"

2. **Find and Enable Sheets API:**
   - Search for: `Google Sheets API`
   - Click on it
   - Click the blue "ENABLE" button
   - Wait for it to enable (~10 seconds)

---

### Step 3: Create Service Account

1. **Go to Credentials:**
   - Click "APIs & Services" → "Credentials"

2. **Create Service Account:**
   - Click "+ CREATE CREDENTIALS" at the top
   - Select "Service Account"

3. **Fill in Service Account Details:**
   - **Service account name:** `marks-portal-service`
   - **Service account ID:** (auto-filled, leave as is)
   - **Description:** `Service account for Student Marks Portal`
   - Click "CREATE AND CONTINUE"

4. **Grant Access (Skip this step):**
   - Click "CONTINUE" (no role needed)

5. **Grant Users Access (Skip this step):**
   - Click "DONE"

---

### Step 4: Create and Download JSON Key

1. **Find Your Service Account:**
   - You'll see a list of service accounts
   - Click on the email of the service account you just created
   - It looks like: `marks-portal-service@your-project-id.iam.gserviceaccount.com`

2. **Create Key:**
   - Click the "KEYS" tab (at the top)
   - Click "ADD KEY" → "Create new key"
   - Select "JSON" format
   - Click "CREATE"

3. **Download and Rename:**
   - A JSON file will download automatically
   - **IMPORTANT:** Move this file to: `s:\lgu\marksheet\`
   - **IMPORTANT:** Rename it to: `credentials.json`

---

### Step 5: Share Your Google Sheet with Service Account

1. **Copy the Service Account Email:**
   - From the credentials.json file, OR
   - From the Google Cloud Console (it's shown in the service account details)
   - It looks like: `marks-portal-service@student-marks-portal-XXXXX.iam.gserviceaccount.com`

2. **Open Your Google Sheet:**
   - Go to: https://docs.google.com/spreadsheets/d/14NqKvdNnWgRG64-8jDuqcgB-BEl3IvuI/edit

3. **Share the Sheet:**
   - Click the green "Share" button (top right)
   - Paste the service account email
   - Set permission to: **Viewer** (or Editor if you want the server to modify data)
   - **UNCHECK** "Notify people" (no need to send email)
   - Click "Share" or "Send"

---

### Step 6: Format Your Google Sheet Correctly

**Your spreadsheet MUST follow this exact format:**

| RollNo | Name           | Subject1    | Subject2 | Subject3  | Subject4          | Subject5 |
|--------|----------------|-------------|----------|-----------|-------------------|----------|
| 001    | Alice Johnson  | 85/100      | 78/100   | 82/100    | 92/100            | 88/100   |
| 002    | Bob Smith      | 72          | 68       | 75        | 88                | 80       |
| 003    | Carol Williams | 95/100      | 91/100   | 89/100    | 97/100            | 93/100   |

**Important Rules:**
- ✅ **Row 1:** Header row with column names
- ✅ **Column A:** Roll numbers (can be numbers or text like "CS001")
- ✅ **Column B:** Student names
- ✅ **Column C onwards:** Subject marks
- ✅ **Marks format:** Either `85/100` or just `85` (assumes /100)
- ✅ **Subject names:** Use actual subject names in header row

**Example with Real Subjects:**

| RollNo | Name           | Mathematics | Physics | Chemistry | Computer Science | English |
|--------|----------------|-------------|---------|-----------|------------------|---------|
| CS001  | Alice Johnson  | 85          | 78      | 82        | 92               | 88      |
| CS002  | Bob Smith      | 72          | 68      | 75        | 88               | 80      |

---

### Step 7: Verify credentials.json Location

Make sure your `credentials.json` file is in the correct location:

```
s:\lgu\marksheet\credentials.json
```

**File structure should look like:**
```
s:\lgu\marksheet\
├── credentials.json     ← This file!
├── .env
├── server.js
├── index.html
├── script.js
├── styles.css
└── package.json
```

---

### Step 8: Restart Your Server

1. **Stop the current server:**
   - Press `Ctrl + C` in the terminal

2. **Start the server again:**
   ```bash
   npm start
   ```

3. **Look for success message:**
   ```
   ✓ Google Sheets API initialized successfully
   🚀 Student Marks Portal Server
   📡 Server running on http://localhost:3000
   📊 Google Sheets: Connected
   ```

---

## ✅ Testing the System

1. **Open:** http://localhost:3000
2. **Enter a roll number** from your spreadsheet (e.g., `CS001`, `001`, etc.)
3. **Check the results** - student should ONLY see their own marks

---

## 🔒 Security Verification

Your system is secure because:
- ✅ Students only enter their roll number
- ✅ Backend validates and returns ONLY that student's data
- ✅ No student can access another student's marks
- ✅ Google Sheet is accessed server-side (students never see the sheet directly)
- ✅ Service account has read-only access

---

## ❌ Troubleshooting

### Error: "Google Sheets API not initialized"
**Solution:**
- Check `credentials.json` is in the correct folder
- Check the file is named exactly `credentials.json` (not `.txt`)
- Verify the service account email is shared with the Google Sheet

### Error: "Student not found"
**Solution:**
- Check roll number matches exactly (case-insensitive)
- Verify student exists in the Google Sheet
- Check Column A has the roll numbers
- Restart the server to refresh cache

### Using Mock Data Instead
**Solution:**
- This means Google Sheets connection failed
- Check server console for error messages
- Verify all steps above are completed
- Check `GOOGLE_SHEETS_ID` in `.env` matches your sheet ID

### Permission Denied Error
**Solution:**
- Go to your Google Sheet
- Click Share
- Make sure the service account email is added as Viewer/Editor

---

## 📋 Quick Checklist

Before asking for help, verify:
- [ ] Google Cloud Project created
- [ ] Google Sheets API enabled
- [ ] Service Account created
- [ ] `credentials.json` downloaded and renamed
- [ ] `credentials.json` in correct location: `s:\lgu\marksheet\credentials.json`
- [ ] Service account email shared with the Google Sheet
- [ ] Google Sheet formatted correctly (RollNo | Name | Subjects...)
- [ ] `.env` file exists with correct `GOOGLE_SHEETS_ID`
- [ ] Server restarted after setup

---

## 🎯 Next Steps

Once setup is complete:
1. Test with different roll numbers
2. Share the portal URL with students
3. Monitor server logs for any issues
4. Update Google Sheet as needed (changes reflect after cache expires - 5 minutes)

---

**Need help?** Check the error messages in the terminal where the server is running!
