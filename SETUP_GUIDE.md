# Quick Setup Guide - Student Marks Portal

This guide will walk you through setting up the Student Marks Portal with Google Drive integration.

## 📋 What You Need

1. ✅ Node.js installed (already have dependencies installed!)
2. ☐ Google Cloud Project
3. ☐ Google Spreadsheet with student marks
4. ☐ Service Account credentials

---

## 🚀 Option 1: Quick Test (No Google Sheets Setup Required)

**Want to see it working right away? Follow these steps:**

1. **Start the server:**
   ```bash
   npm start
   ```

2. **Open your browser:**
   - Navigate to: `http://localhost:3000`

3. **Test with mock data:**
   - Roll Number: `CS001` (Alice Johnson)
   - Roll Number: `CS002` (Bob Smith)
   - Roll Number: `CS003` (Carol Williams)

4. **That's it!** You can see the system working with mock data immediately.

---

## 🔧 Option 2: Full Setup with Google Sheets

### Step 1: Create Your Google Spreadsheet

1. Go to [Google Sheets](https://sheets.google.com)
2. Create a new spreadsheet
3. Format it like this:

| RollNo | Name          | Mathematics | Physics | Chemistry | Computer Science | English |
|--------|---------------|-------------|---------|-----------|------------------|---------|
| CS001  | Alice Johnson | 85          | 78      | 82        | 92               | 88      |
| CS002  | Bob Smith     | 72          | 68      | 75        | 88               | 80      |
| CS003  | Carol Williams| 95          | 91      | 89        | 97               | 93      |

**Important:**
- First row = Headers
- Column A = Roll Number
- Column B = Student Name
- Columns C+ = Subject marks (you can change subject names)

### Step 2: Get the Spreadsheet ID

From your spreadsheet URL:
`https://docs.google.com/spreadsheets/d/`**`1ABC...XYZ`**`/edit`

Copy the ID (the part between `/d/` and `/edit`)

### Step 3: Set Up Google Cloud Project

1. **Go to [Google Cloud Console](https://console.cloud.google.com/)**

2. **Create a new project** (or use existing)
   - Click "Select a project" → "New Project"
   - Name it (e.g., "Student Marks Portal")
   - Click "Create"

3. **Enable Google Sheets API**
   - Go to "APIs & Services" → "Library"
   - Search for "Google Sheets API"
   - Click "Enable"

4. **Create Service Account**
   - Go to "APIs & Services" → "Credentials"
   - Click "Create Credentials" → "Service Account"
   - Give it a name (e.g., "marks-portal-service")
   - Click "Create and Continue"
   - Skip optional steps, click "Done"

5. **Create and Download Key**
   - Click on the service account you just created
   - Go to "Keys" tab
   - Click "Add Key" → "Create New Key"
   - Choose "JSON"
   - Click "Create"
   - **Important:** Save this file as `credentials.json` in your project folder

6. **Share Your Spreadsheet**
   - Open your Google Sheet
   - Click "Share" button
   - Copy the service account email (looks like: `xxx@xxx.iam.gserviceaccount.com`)
   - Paste it and give "Viewer" access
   - Click "Send"

### Step 4: Configure Environment Variables

1. **Create `.env` file** (copy from template):
   ```bash
   copy .env.example .env
   ```

2. **Edit `.env` file** with your details:
   ```
   GOOGLE_SHEETS_ID=your_actual_spreadsheet_id_here
   SHEET_NAME=Sheet1
   GOOGLE_SERVICE_ACCOUNT_KEY_FILE=credentials.json
   PORT=3000
   NODE_ENV=production
   ```

3. **Replace** `your_actual_spreadsheet_id_here` with your actual ID from Step 2

### Step 5: Place credentials.json

Make sure `credentials.json` (from Step 3.5) is in the same folder as `server.js`

### Step 6: Start the Server

```bash
npm start
```

You should see:
```
🚀 Student Marks Portal Server
📡 Server running on http://localhost:3000
📊 Google Sheets: Connected
```

---

## 🎯 Using the Portal

1. **Open** `http://localhost:3000` in your browser
2. **Enter** your roll number (e.g., CS001)
3. **View** your marks, grades, and performance chart
4. **Logout** to login as another student

---

## 🔒 Security Features

✅ Students can ONLY see their own marks  
✅ No access to other students' data  
✅ Roll number authentication  
✅ Server-side validation  
✅ Data cached securely  

---

## ❓ Troubleshooting

### Server won't start
- Check if port 3000 is already in use
- Run: `netstat -ano | findstr :3000` to check
- Change PORT in `.env` if needed

### "Google Sheets API not initialized"
- Check `credentials.json` is in the correct location
- Verify service account has access to your sheet
- Check spreadsheet ID in `.env` is correct

### "Student not found"
- Verify roll number matches exactly (case-insensitive)
- Check student exists in your Google Sheet
- Restart server to refresh cache

### Mock data instead of real data
- This means Google Sheets connection failed
- Check server console for error messages
- Verify all setup steps completed

---

## 📱 Access from Other Devices

To access from mobile or other computers on the same network:

1. Find your computer's IP address:
   ```bash
   ipconfig
   ```
   Look for "IPv4 Address" (e.g., 192.168.1.100)

2. Update `script.js` line 3:
   ```javascript
   API_BASE_URL: 'http://YOUR_IP_ADDRESS:3000/api',
   ```

3. Access from other devices:
   ```
   http://YOUR_IP_ADDRESS:3000
   ```

---

## 🎨 Customization

### Change Colors
Edit `styles.css` variables (line 2-15)

### Change Grading System
Edit `script.js` `calculateGrade()` function (line 163-171)

### Add More Subjects
Just add more columns to your Google Sheet!

### Change Port
Edit `.env` file: `PORT=8080`

---

## 📞 Need Help?

Check the main README.md for more detailed information!
