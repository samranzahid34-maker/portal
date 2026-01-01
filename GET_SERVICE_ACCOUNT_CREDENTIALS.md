# 🔑 How to Get Service Account Credentials (CORRECT METHOD)

## ⚠️ IMPORTANT: You Need Service Account Credentials, NOT OAuth Credentials!

The file you added is an **OAuth Client Secret** file. This project needs a **Service Account** credentials file instead.

---

## 🚀 Quick 5-Minute Setup Guide

### Step 1: Go to Google Cloud Console
Open: https://console.cloud.google.com/

### Step 2: Select Your Project
- If you already created a project (like "My First Project" or similar), select it
- If not, click **"New Project"** → Name it anything (e.g., "Student Marks Portal") → Click **Create**

### Step 3: Enable Google Sheets API
1. In the search bar at top, type: **"Google Sheets API"**
2. Click on **"Google Sheets API"** in results
3. Click **"ENABLE"** button
4. Wait a few seconds for it to enable

### Step 4: Create Service Account (MOST IMPORTANT!)
1. In left sidebar, click **"Credentials"**
2. At the top, click **"+ CREATE CREDENTIALS"**
3. Select **"Service Account"** (NOT OAuth 2.0!)
4. Fill in:
   - **Service account name**: `student-marks-portal` (or any name)
   - **Service account ID**: (auto-filled)
   - Click **"CREATE AND CONTINUE"**
5. For "Grant this service account access to project":
   - Select role: **"Viewer"** (or skip this)
   - Click **"CONTINUE"**
6. For "Grant users access":
   - Just click **"DONE"** (skip this step)

### Step 5: Download Service Account Key (JSON)
1. You'll be taken back to Credentials page
2. Scroll down to **"Service Accounts"** section
3. Click on the service account you just created (the email address)
4. Go to **"KEYS"** tab at the top
5. Click **"ADD KEY"** → **"Create new key"**
6. Select **"JSON"** format
7. Click **"CREATE"**
8. ⬇️ A JSON file will download automatically! This is your credentials file!

### Step 6: Copy Service Account Email Address
- On the same page, you'll see the service account email
- It looks like: `student-marks-portal@xxxx.iam.gserviceaccount.com`
- **COPY THIS EMAIL** - you'll need it in Step 8!

### Step 7: Rename and Move Credentials File
1. The downloaded file will have a long name like:
   `my-project-123456-a1b2c3d4e5f6.json`
2. **IMPORTANT**: Rename it to exactly: `credentials.json`
3. Move this `credentials.json` file to: `s:\lgu\marksheet\credentials.json`
   - **Replace the existing credentials.json** with this new one!

### Step 8: Share Google Sheet with Service Account
1. Open your Google Sheet: 
   https://docs.google.com/spreadsheets/d/14NqKvdNnWgRG64-8jDuqcgB-BEl3IvuI/edit
2. Click the **"Share"** button (top right)
3. Paste the **service account email** (from Step 6)
4. Make sure role is set to **"Viewer"**
5. **Uncheck** "Notify people" (service accounts don't need notifications)
6. Click **"Share"** or **"Send"**

### Step 9: Format Your Google Sheet Correctly
Your sheet should look exactly like this:

```
| RollNo | Name           | Mathematics | Physics | Chemistry | Computer Science | English |
|--------|----------------|-------------|---------|-----------|------------------|---------|
| CS001  | Alice Johnson  | 85          | 78      | 82        | 92               | 88      |
| CS002  | Bob Smith      | 72          | 68      | 75        | 88               | 80      |
| CS003  | Carol Williams | 95          | 91      | 89        | 97               | 93      |
```

**Rules:**
- Row 1 = Headers (RollNo, Name, then subject names)
- Column A = Roll numbers
- Column B = Student names
- Column C onwards = Marks (can be "85" or "85/100" format)
- No empty rows between header and data

---

## ✅ How to Know You Have the RIGHT File

### ✅ CORRECT Service Account File Contains:
```json
{
  "type": "service_account",
  "project_id": "...",
  "private_key_id": "...",
  "private_key": "-----BEGIN PRIVATE KEY-----\n...",
  "client_email": "...@....iam.gserviceaccount.com",
  ...
}
```

### ❌ WRONG OAuth Client Secret File Contains:
```json
{
  "installed": {
    "client_id": "...",
    "client_secret": "...",
    "redirect_uris": [...],
    ...
  }
}
```

**Your current file is the WRONG type!** You need to follow the steps above to get the correct Service Account credentials.

---

## 🧪 Test After Setup

After replacing credentials.json with the correct Service Account file, run:

```bash
node test-connection.js
```

You should see:
```
✅ Authentication successful!
✅ Successfully fetched X rows!
🎉 SUCCESS! Your Google Sheets integration is working perfectly!
```

---

## 🚀 Then Start Your Server

If test passes, restart your server:

```bash
npm start
```

Look for:
```
✓ Google Sheets API initialized successfully
📊 Google Sheets: Connected
```

---

## ❓ Need Help?

Common issues:
- **"private_key" error**: You're using OAuth file instead of Service Account
- **Permission denied**: You didn't share the sheet with service account email
- **404 error**: Wrong spreadsheet ID in .env file
- **ENOENT**: credentials.json not in correct folder

See GOOGLE_CLOUD_SETUP.md for more detailed troubleshooting!

---

**NEXT STEP**: Follow the steps above to download the correct Service Account credentials file!
