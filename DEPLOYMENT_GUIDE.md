# Clean Deployment Guide

## The Problem
The current system has persistent data issues where Admin B can see Admin A's sheets even after multiple fixes.

## Root Cause
The issue is that old data in MongoDB/files doesn't have `ownerId` fields, and browser caching is showing stale data.

## Clean Solution

### Step 1: Delete Current Vercel Project
1. Go to Vercel Dashboard
2. Settings → Delete Project
3. Confirm deletion

### Step 2: Clean Local Database
Run this command:
```bash
node clear-datastore.js
```

### Step 3: Create Fresh Vercel Project
1. Go to Vercel → New Project
2. Import from GitHub: `student-Subject-marks-portal`
3. Add Environment Variables:
   - `GOOGLE_SHEETS_ID` = Your sheet ID
   - `SHEET_NAME` = Sheet1
   - `JWT_SECRET` = any-random-secret-key-123
   - `MONGODB_URI` = Your MongoDB connection string
   - `GOOGLE_CREDENTIALS_JSON` = Your credentials.json content (entire file)

### Step 4: Test
1. Visit new Vercel URL
2. Register Admin 1 → Add Sheet
3. Register Admin 2 → Should see EMPTY dashboard

## If Still Not Working

The code is correct. The issue is data persistence. You have two options:

**Option A: Use Different MongoDB Database**
- Create a NEW MongoDB cluster
- Use the new connection string
- This guarantees zero old data

**Option B: Manual MongoDB Cleanup**
1. Go to MongoDB Atlas
2. Browse Collections
3. Delete the entire `sources` collection
4. Delete the entire `registrations` collection
5. Redeploy on Vercel

## Verification
After cleanup, the filter logic is:
```javascript
sources.filter(s => s.ownerId && s.ownerId === req.admin.id)
```

This ONLY shows sheets where:
1. `ownerId` exists (not null/undefined)
2. `ownerId` matches the logged-in admin's ID

Any sheet without an `ownerId` is hidden from everyone.
