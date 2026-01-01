# ✅ Setup Progress Checklist

## Current Status

### Completed ✅
- [x] Node.js dependencies installed
- [x] Google Sheets ID configured in .env file
- [x] Spreadsheet ID: `14NqKvdNnWgRG64-8jDuqcgB-BEl3IvuI`
- [x] Project structure set up
- [x] Server code ready

### To Complete ☐
- [ ] Google Cloud Project created
- [ ] Google Sheets API enabled
- [ ] Service Account created
- [ ] credentials.json downloaded and placed in project folder
- [ ] Google Sheet shared with service account email
- [ ] Google Sheet formatted correctly (see format below)
- [ ] Connection tested with `node test-connection.js`
- [ ] Server started successfully with Google Sheets connection

---

## 📋 Next Steps

### 1. Set Up Google Cloud (15-20 minutes)
Follow the detailed guide: **[GOOGLE_CLOUD_SETUP.md](./GOOGLE_CLOUD_SETUP.md)**

**Quick Summary:**
1. Go to https://console.cloud.google.com/
2. Create new project
3. Enable Google Sheets API
4. Create Service Account
5. Download credentials.json → Save to `s:\lgu\marksheet\credentials.json`
6. Copy service account email
7. Share your Google Sheet with that email (Viewer access)

### 2. Format Your Google Sheet
Your spreadsheet MUST look like this:

| RollNo | Name           | Mathematics | Physics | Chemistry | Computer Science | English |
|--------|----------------|-------------|---------|-----------|------------------|---------|
| CS001  | Alice Johnson  | 85          | 78      | 82        | 92               | 88      |
| CS002  | Bob Smith      | 72          | 68      | 75        | 88               | 80      |
| CS003  | Carol Williams | 95          | 91      | 89        | 97               | 93      |

**Important:**
- Row 1 = Headers (RollNo, Name, then subject names)
- Column A = Student roll numbers
- Column B = Student names  
- Column C onwards = Marks (can be "85/100" or just "85")

### 3. Test Connection
After setting up credentials, run:
```bash
node test-connection.js
```

If successful, you'll see:
```
✅ Authentication successful!
✅ Successfully fetched X rows!
🎉 SUCCESS! Your Google Sheets integration is working perfectly!
```

### 4. Start the Server
```bash
npm start
```

Look for:
```
✓ Google Sheets API initialized successfully
📊 Google Sheets: Connected
```

### 5. Test the Portal
1. Open http://localhost:3000
2. Enter a roll number from your sheet
3. Verify the student sees ONLY their marks
4. Test with different roll numbers

---

## 🔒 Security Verification

After setup, verify these security features:
- [ ] Students can only enter roll number (no sheet access)
- [ ] Each student sees ONLY their own data
- [ ] Invalid roll numbers show "Student not found"
- [ ] No way to enumerate or guess other students' data

---

## ❌ Common Issues

### "ENOENT: credentials.json not found"
→ Download credentials.json and place in `s:\lgu\marksheet\`

### "Permission denied" or "403 error"
→ Share the Google Sheet with the service account email

### "Student not found"
→ Check roll number spelling matches exactly in Column A

### "Using mock data for testing"
→ Google Sheets connection failed, check console for errors

---

## 📞 Help

- **Detailed setup:** See GOOGLE_CLOUD_SETUP.md
- **General info:** See README.md
- **Setup guide:** See SETUP_GUIDE.md

---

**Last Updated:** 2025-12-31
