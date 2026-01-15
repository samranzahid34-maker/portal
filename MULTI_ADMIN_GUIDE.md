# 🎓 Multi-Admin (Multi-Teacher) Support Guide

## 📋 Overview

The Student Marks Portal now supports **multiple teachers (admins)** registering and managing their own student marksheets independently. Each teacher can only see and manage their own students' data, ensuring complete privacy and data isolation.

---

## ✨ Key Features

### 1. **Multiple Teacher Registration**
- ✅ Any teacher can register as an admin
- ✅ No limit on the number of admin accounts
- ✅ Each teacher has their own login credentials

### 2. **Data Isolation**
- ✅ Teachers only see their own student sheets
- ✅ Dashboard shows statistics only for their students
- ✅ Complete privacy between different teachers' data

### 3. **Shared Infrastructure**
- ✅ All admin accounts stored in the same Google Sheet (`admin_data` tab)
- ✅ All student sheet references stored in the same `Sources` tab
- ✅ Ownership tracked via email in Column D

---

## 🚀 How It Works

### For Teachers (Admins)

#### **Step 1: Registration**
1. Navigate to the admin panel
2. Click "Register" 
3. Enter your details:
   - Name
   - Email (this becomes your unique identifier)
   - Password
4. Click "Register"

#### **Step 2: Login**
1. Use your registered email and password
2. You'll be redirected to your personal dashboard

#### **Step 3: Add Your Student Sheets**
1. Go to "Data Sources" section
2. Click "Add New Source"
3. Enter:
   - **Sheet ID**: Your Google Sheets ID containing student marks
   - **Range**: e.g., `Sheet1!A2:Z`
   - **Name**: A friendly name for this class/section
4. Click "Add Source"

**Important**: The system automatically associates this sheet with your email, so only you can see it.

#### **Step 4: View Statistics & Grades**
- Navigate to "Class Statistics & Grades"
- Select your sheet from the dropdown
- View statistics, apply grading rules, export data

---

## 🔧 Technical Implementation

### Backend Changes

#### 1. **Database Schema**

**Admin Sheet (`admin_data` tab)**:
```
| Role  | Roll No | Name          | Email                | Password (Hashed) |
|-------|---------|---------------|----------------------|-------------------|
| admin | Admin   | John Teacher  | john@school.com      | $2b$12$...       |
| admin | Admin   | Mary Teacher  | mary@school.com      | $2b$12$...       |
```

**Sources Sheet (`Sources` tab)**:
```
| Sheet ID              | Range        | Name           | Owner Email         |
|-----------------------|--------------|----------------|---------------------|
| 1abc...xyz            | Sheet1!A2:Z  | Class 10A      | john@school.com     |
| 2def...uvw            | Sheet1!A2:Z  | Class 10B      | mary@school.com     |
```

#### 2. **Key Functions Modified**

**`get_sheet_sources(owner_email=None)`**:
- If `owner_email` is provided: Returns only sheets owned by that email
- If `owner_email` is `None`: Returns all sheets (for student portal)

**`append_source_to_sheet(sheet_id, range, name, owner_email)`**:
- Saves the source with the owner's email in Column D

**`add_source` endpoint**:
- Extracts admin email from JWT token
- Passes it to `append_source_to_sheet`

**`get_admin_dashboard` endpoint**:
- Extracts admin email from JWT token
- Calls `get_sheet_sources(owner_email=admin_email)`
- Shows statistics only for that admin's sheets

#### 3. **Removed Restrictions**

**Before**:
```python
# STRICT SECURITY: Only 1 Admin Allowed
if len(sheet_admins) > 0:
    raise HTTPException(status_code=403, detail="Registration Closed...")
```

**After**:
```python
# MULTI-ADMIN SUPPORT: Removed single-admin restriction
# Multiple teachers can now register
```

---

## 📊 Data Flow

### When Teacher A Logs In:
1. **Login** → JWT token contains `email: teacher-a@school.com`
2. **Dashboard** → Fetches sources where `owner_email = teacher-a@school.com`
3. **Statistics** → Calculates stats only from Teacher A's sheets
4. **Add Source** → New sheet tagged with `teacher-a@school.com`

### When Teacher B Logs In:
1. **Login** → JWT token contains `email: teacher-b@school.com`
2. **Dashboard** → Fetches sources where `owner_email = teacher-b@school.com`
3. **Statistics** → Calculates stats only from Teacher B's sheets
4. **Add Source** → New sheet tagged with `teacher-b@school.com`

### When Students Search:
- Student portal calls `get_sheet_sources()` with **no email filter**
- Returns **all sheets** from all teachers
- Students can find their marks regardless of which teacher added them

---

## 🔒 Security & Privacy

### ✅ What's Protected:
- Each teacher can only see their own sheets in the admin panel
- Dashboard statistics are isolated per teacher
- Manual grades are scoped to sheet ID (inherently isolated)

### ✅ What's Shared:
- Student portal shows all sheets (students can search across all teachers)
- All admin accounts stored in same Google Sheet
- All source references in same `Sources` tab (but filtered by owner)

---

## 🧪 Testing Checklist

After deployment, verify:

- [ ] Multiple teachers can register successfully
- [ ] Each teacher can log in with their credentials
- [ ] Teacher A cannot see Teacher B's sheets in dropdown
- [ ] Teacher A's dashboard shows only their students
- [ ] When Teacher A adds a source, it's tagged with their email
- [ ] Students can still search and find marks from any teacher
- [ ] Manual grading works correctly for each teacher's sheets

---

## 📝 Migration Notes

### For Existing Deployments:

If you already have sources in the `Sources` tab **without** the `Owner Email` column:

1. **Legacy Sources**: Will show to all admins (backward compatibility)
2. **New Sources**: Will be tagged with owner email
3. **Recommendation**: Manually add owner emails to existing rows in Column D

**Example Migration**:
```
Before:
| Sheet ID    | Range       | Name      |
|-------------|-------------|-----------|
| 1abc...     | Sheet1!A2:Z | Class 10A |

After:
| Sheet ID    | Range       | Name      | Owner Email      |
|-------------|-------------|-----------|------------------|
| 1abc...     | Sheet1!A2:Z | Class 10A | admin@school.com |
```

---

## 🎯 Summary

### What Changed:
✅ **Removed single-admin restriction**  
✅ **Added owner email tracking in Sources**  
✅ **Filtered data access by owner email**  
✅ **Updated dashboard to show only owned data**  

### Impact:
- 🏫 **Schools**: Can now have multiple teachers using the same system
- 👨‍🏫 **Teachers**: Each has their own private workspace
- 👨‍🎓 **Students**: Can still search across all teachers' data

**Your portal is now a true multi-tenant system! 🎉**
