# Class Statistics & Relative Grading Feature

## Overview
This document describes the new **Class Statistics & Relative Grading** functionality added to the admin panel of the Student Marks Portal.

## Feature Description

### What It Does
The system now automatically:
1. **Calculates class averages** for each subject and overall
2. **Assigns grades** based on relative/percentile-based marking (university marking system)
3. **Ranks students** by their total marks
4. **Displays comprehensive statistics** for any selected marksheet
5. **Allows CSV export** of all results with grades

### How It Works

#### Relative Grading Algorithm
The system uses a **percentile-based grading system** that assigns grades based on how students perform relative to their classmates:

- **A+**: Top 10% of class (90th percentile and above)
- **A**: 80th-90th percentile
- **B+**: 70th-80th percentile
- **B**: 60th-70th percentile
- **C+**: 50th-60th percentile
- **C**: 40th-50th percentile
- **D**: 30th-40th percentile
- **F**: Below 30th percentile

This ensures fair grading where:
- Grades reflect relative performance within the class
- Top performers always get recognition
- Distribution is balanced based on class performance

## User Interface

### Admin Panel - New Tab
A new tab called **"Class Statistics & Grades"** has been added to the admin sidebar with three main sections:

#### 1. Sheet Selector
- Dropdown menu showing all configured marksheets
- Admin selects which class/section to analyze

#### 2. Statistics Summary (4 Cards)
- **Total Students**: Number of students in the selected sheet
- **Class Average**: Overall average marks
- **Highest Score**: Top score in the class
- **Lowest Score**: Lowest score in the class

#### 3. Subject-wise Averages
- Grid display showing average marks for each subject
- Helps identify which subjects students find challenging

#### 4. Student Results Table
Features:
- **Ranking**: Students ranked by total marks (🥇🥈🥉 for top 3)
- **All Subject Marks**: Individual marks for each assessment
- **Total Marks**: Sum of all marks
- **Percentage**: Calculated percentage
- **Grade**: Automatically assigned relative grade with color coding
  - Green shades: A+, A
  - Blue shades: B+, B
  - Orange shades: C+, C
  - Red shades: D, F

#### 5. Export Functionality
- **CSV Export Button**: Downloads complete results as CSV file
- Filename format: `{sheet_name}_statistics_{date}.csv`
- Includes all data: rank, roll number, name, all marks, total, percentage, and grade

## Technical Implementation

### Backend (main.py)

#### New API Endpoint
```
GET /api/admin/sheet-statistics/{sheet_id}
```

**Response Structure:**
```json
{
  "success": true,
  "sheetName": "Section A - Morning Batch",
  "students": [
    {
      "rollNumber": "FA-2024/001",
      "name": "Student Name",
      "marks": {
        "Quiz 1": 8,
        "Assignment 1": 9,
        "Mid": 35,
        ...
      },
      "total": 85.5,
      "percentage": 85.5,
      "grade": "A+"
    }
  ],
  "statistics": {
    "totalStudents": 45,
    "classAverage": 72.3,
    "subjectAverages": {
      "Quiz 1": 7.2,
      "Assignment 1": 8.1,
      ...
    },
    "highestScore": 95.0,
    "lowestScore": 45.0,
    "headers": ["Quiz 1", "Assignment 1", "Mid", ...]
  }
}
```

#### Key Functions

1. **`calculate_relative_grade(percentage, all_percentages)`**
   - Calculates percentile rank for a student
   - Assigns grade based on percentile thresholds
   - Handles edge cases (empty data, null values)

2. **`get_sheet_statistics(sheet_id)`**
   - Fetches all student data from specified sheet
   - Calculates class and subject averages
   - Assigns grades to all students
   - Sorts students by total marks (descending)

### Frontend (admin.html)

#### New JavaScript Functions

1. **`populateSheetSelector()`**
   - Loads available marksheets into dropdown
   - Called when statistics tab is opened

2. **`loadClassStatistics(event)`**
   - Fetches statistics from API
   - Handles loading states
   - Displays results

3. **`displayStatistics(data)`**
   - Updates summary cards
   - Renders subject averages
   - Builds dynamic table with all data
   - Applies color coding to grades
   - Adds medal emojis for top 3 students

4. **`exportToCSV()`**
   - Generates CSV file from current data
   - Triggers automatic download
   - Includes all columns with proper formatting

## Usage Instructions

### For Admins

1. **Login** to the admin panel
2. **Navigate** to "Class Statistics & Grades" tab in the sidebar
3. **Select** a marksheet from the dropdown menu
4. **Click** "View Statistics" button
5. **Review** the displayed statistics:
   - Check class performance summary
   - Review subject-wise averages
   - See complete student rankings with grades
6. **Export** results by clicking "📥 Export CSV" button (optional)

### Benefits

1. **Automatic Grade Assignment**: No manual calculation needed
2. **Fair Grading**: Relative grading ensures fair distribution
3. **Comprehensive Analytics**: Complete overview of class performance
4. **Easy Export**: One-click CSV export for record-keeping
5. **Visual Clarity**: Color-coded grades and intuitive layout
6. **Real-time**: Always shows current data from Google Sheets

## Design Features

### Visual Enhancements
- **Gradient Cards**: Beautiful gradient backgrounds for summary statistics
- **Color-coded Grades**: Each grade has a distinct color for quick recognition
- **Medal Icons**: 🥇🥈🥉 for top 3 students
- **Hover Effects**: Interactive table rows with smooth transitions
- **Responsive Design**: Works on all screen sizes

### User Experience
- **Smooth Scrolling**: Auto-scrolls to results after loading
- **Loading States**: Clear feedback during data fetching
- **Error Handling**: Helpful error messages if something goes wrong
- **Intuitive Layout**: Logical flow from selection to results

## Future Enhancements (Possible)

1. **Grade Distribution Chart**: Visual pie/bar chart showing grade distribution
2. **Trend Analysis**: Compare performance across multiple sheets/semesters
3. **Custom Grading Schemes**: Allow admin to configure percentile thresholds
4. **Student Improvement Tracking**: Show individual student progress over time
5. **PDF Export**: Generate formatted PDF reports
6. **Email Reports**: Send statistics to stakeholders automatically

## Notes

- Grades are calculated **dynamically** each time statistics are viewed
- The system uses the **current data** from Google Sheets
- Relative grading ensures **fair distribution** regardless of exam difficulty
- All calculations are done **server-side** for accuracy and security
- CSV export includes **complete data** for external analysis

## Support

For any issues or questions regarding this feature:
1. Ensure Google Sheets are properly configured
2. Verify all marksheets have consistent column structure
3. Check that marks are numeric values (not text)
4. Refresh data using the "↻ Refresh Data" button if needed
