# Student Marks Portal - Complete Project Specification

## Project Overview
A secure web-based platform where students can view their marks from Google Sheets. The system includes student authentication and admin management with strict data isolation.

## Core Requirements

### 1. Student Features
- **Registration System**
  - Students register with Roll Number and Email
  - Roll Number must exist in Google Sheets
  - Email must match official email in Google Sheet (if email column exists)
  - One registration per Roll Number
  
- **Login System**
  - Login with Roll Number + Email
  - JWT token-based authentication (24-hour expiry)
  - Secure session management

- **View Marks**
  - Students can ONLY see their own marks
  - Cannot access other students' data
  - Marks displayed in clean, professional UI
  - Shows all subjects from Google Sheet

### 2. Admin Features
- **Admin Registration & Login**
  - Separate admin authentication system
  - Password hashing with bcrypt
  - JWT tokens (12-hour expiry)

- **Google Sheets Management**
  - Admins can connect multiple Google Sheets
  - Each sheet requires: Sheet ID, Tab Name, Description
  - Real-time connection status monitoring
  - Edit/Delete sheet connections

- **CRITICAL: Admin Isolation**
  - Each admin can ONLY see sheets they personally added
  - Admin A cannot see Admin B's sheets
  - Admin B cannot see Admin A's sheets
  - Each sheet is tagged with `ownerId` (admin's unique ID)
  - Filter logic: `sources.filter(s => s.ownerId && s.ownerId === req.admin.id)`

- **System Reset**
  - Red "Reset System" button in admin dashboard
  - Wipes ALL sheets and student registrations
  - Requires double confirmation
  - Used for clean slate after deployment

### 3. Google Sheets Integration
- **Sheet Format**
  ```
  | RollNo | Name | Email (optional) | Subject1 | Subject2 | ... |
  |--------|------|------------------|----------|----------|-----|
  | CS001  | Ali  | ali@uni.edu      | 85       | 90       | ... |
  ```

- **Dynamic Column Detection**
  - Auto-detects Roll Number column (keywords: roll, id, reg)
  - Auto-detects Name column (keywords: name, student)
  - Auto-detects Email column (keywords: email, mail)
  - All other columns treated as subjects

- **Service Account Authentication**
  - Uses Google Service Account credentials
  - Credentials stored in `credentials.json` locally
  - Stored in `GOOGLE_CREDENTIALS_JSON` env var on Vercel
  - Sheets must be shared with service account email

### 4. Data Storage
- **Hybrid Storage System**
  - **Production (Vercel):** MongoDB Atlas
  - **Development (Local):** JSON files
  - Auto-detects based on `MONGODB_URI` presence

- **Collections/Files**
  - `registrations` - Student accounts
  - `admins` - Admin accounts
  - `sources` - Google Sheet connections (with ownerId)

### 5. Security Features
- **Student Security**
  - Roll Number normalization (removes special chars)
  - Email validation and matching
  - JWT token verification
  - Server-side data filtering

- **Admin Security**
  - Password hashing (bcrypt, 10 rounds)
  - Separate admin authentication
  - Ownership-based access control
  - Cannot modify/delete sheets owned by others

- **API Security**
  - CORS enabled
  - JWT middleware for protected routes
  - Input validation
  - Error handling without exposing internals

### 6. Technical Stack
- **Backend**
  - Node.js + Express
  - Google Sheets API (googleapis)
  - MongoDB (mongoose) + File fallback
  - JWT (jsonwebtoken)
  - bcrypt for passwords

- **Frontend**
  - Vanilla HTML/CSS/JavaScript
  - Modern, clean UI design
  - Responsive layout
  - Client-side form validation

- **Deployment**
  - Vercel (serverless)
  - MongoDB Atlas (cloud database)
  - GitHub integration

## Environment Variables

### Required for Vercel:
```
GOOGLE_SHEETS_ID=<default-sheet-id>
SHEET_NAME=Sheet1
JWT_SECRET=<random-secret-key>
MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/dbname
GOOGLE_CREDENTIALS_JSON=<entire-credentials-json-content>
```

### Local Development (.env):
```
GOOGLE_SHEETS_ID=<sheet-id>
SHEET_NAME=Sheet1
GOOGLE_SERVICE_ACCOUNT_KEY_FILE=credentials.json
PORT=3000
MONGODB_URI=<optional-mongodb-uri>
JWT_SECRET=<optional-secret>
```

## File Structure
```
project/
├── server-auth.js          # Main server with authentication
├── public/
│   ├── index-auth.html     # Student portal
│   ├── admin.html          # Admin dashboard
│   ├── main.css           # Shared styles
│   └── script-auth.js     # Student portal JS
├── credentials.json        # Google service account (local only)
├── .env                   # Environment variables (local only)
├── package.json
├── vercel.json            # Vercel deployment config
├── registrations.json     # Student data (file mode)
├── admins.json           # Admin data (file mode)
├── marks_sources.json    # Sheet connections (file mode)
└── clear-datastore.js    # Utility to wipe data

```

## API Endpoints

### Student APIs
- `POST /api/register` - Register student
- `POST /api/login` - Login student
- `GET /api/student/marks` - Get student's marks (protected)

### Admin APIs
- `POST /api/admin/register` - Register admin
- `POST /api/admin/login` - Login admin
- `GET /api/admin/sheets` - Get admin's sheets (filtered by ownerId)
- `POST /api/admin/sheets` - Add new sheet (auto-assigns ownerId)
- `PUT /api/admin/sheets/:uid` - Update sheet (ownership check)
- `DELETE /api/admin/sheets/:uid` - Delete sheet (ownership check)
- `DELETE /api/admin/reset-system` - Wipe all data
- `POST /api/admin/lookup-student` - Debug tool to find student

### Public APIs
- `GET /api/health` - Server health check
- `GET /` - Serves student portal

## Critical Implementation Details

### Admin Isolation Logic
```javascript
// In GET /api/admin/sheets
const sources = await loadMarksSources();
const mySources = sources.filter(s => {
    return s.ownerId && s.ownerId === req.admin.id;
});
```

### Sheet Creation with Owner
```javascript
// In POST /api/admin/sheets
sources.push({
    _id: Date.now().toString() + Math.random().toString(36).substr(2, 5),
    id: googleSheetId,
    name: tabName,
    description: description,
    ownerId: req.admin.id  // CRITICAL: Tag with owner
});
```

### Email Verification (if email column exists)
```javascript
// In parseStudentData
let emailIndex = headers.findIndex(h => h.includes('email'));
student.officialEmail = (emailIndex !== -1 && row[emailIndex]) 
    ? row[emailIndex].toString().trim().toLowerCase() 
    : null;

// In /api/register
if (student.officialEmail && student.officialEmail !== normalizedEmail) {
    return res.status(403).json({ error: 'Email mismatch' });
}
```

## Deployment Steps

### 1. Setup MongoDB Atlas
- Create free cluster
- Create database user
- Whitelist IP (0.0.0.0/0 for Vercel)
- Get connection string

### 2. Setup Google Cloud
- Create project
- Enable Google Sheets API
- Create Service Account
- Download credentials.json
- Share sheets with service account email

### 3. Deploy to Vercel
- Delete old project (if exists)
- Import from GitHub
- Add all environment variables
- Deploy
- Click "Reset System" button after first deployment
- Test admin isolation

## Testing Checklist

### Student Flow
- [ ] Register with valid roll number
- [ ] Cannot register with invalid roll number
- [ ] Cannot register twice with same roll number
- [ ] Login with correct credentials
- [ ] Cannot login with wrong credentials
- [ ] Can view own marks
- [ ] Cannot access other students' marks

### Admin Flow
- [ ] Register admin account
- [ ] Login as admin
- [ ] Add Google Sheet
- [ ] Sheet shows in dashboard
- [ ] Logout and login as different admin
- [ ] Second admin sees EMPTY dashboard
- [ ] Second admin adds their own sheet
- [ ] First admin cannot see second admin's sheet
- [ ] Reset System button wipes all data

## Known Issues & Solutions

### Issue: Admin B sees Admin A's sheets
**Cause:** Old data in database without `ownerId` field
**Solution:** 
1. Click "Reset System" button
2. OR manually delete MongoDB collections
3. OR create fresh Vercel project

### Issue: Deployment shows no UI/UX
**Cause:** `vercel.json` not in Git
**Solution:** Ensure `.gitignore` allows `vercel.json`

### Issue: "Cannot connect to Google Sheets"
**Cause:** Missing/invalid credentials or sheet not shared
**Solution:** 
1. Verify `GOOGLE_CREDENTIALS_JSON` is complete
2. Share sheet with service account email
3. Check sheet ID is correct

## Success Criteria
✅ Students can only see their own marks
✅ Admin A cannot see Admin B's sheets
✅ Admin B cannot see Admin A's sheets
✅ System works on both localhost and Vercel
✅ Data persists in MongoDB (not temporary files)
✅ Clean, professional UI
✅ No security vulnerabilities
