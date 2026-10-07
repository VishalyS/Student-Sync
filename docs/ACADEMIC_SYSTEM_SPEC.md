# Academic System Specification (Phase 5)

## 1. Overview
The Academic Marks & CGPA Simulator module provides deep Continuous Assessment (CA) tracking, verified historical examination results analytics, and an interactive in-memory What-If CGPA simulator for Student Sync.

This implementation complies strictly with institutional assessment policies at **PSG College of Technology** and adheres to zero-write database safety standards.

> [!IMPORTANT]
> **SEE target-grade estimation is intentionally not implemented because theory-course relative grading prevents a deterministic individual target without cohort/PAC parameters.**

---

## 2. Continuous Assessment (CA) Architecture

### A. Data Sources
Continuous Assessment evaluations are scraped from Modern StudZone 1 (`/StudZone/ContinuousAssessment/CAMarksView`) and stored in:
- `studzone1.ca_marks_html`: High-fidelity HTML containing the true institutional multi-table structure with exact column headers and component max marks.
- `studzone1.parsed_marks`: Course-level fallback dictionary containing `code`, `name`, and `marks_data`.

### B. Course Categories & Assessment Weightages
Unlike naive implementations that assume fixed CA1/CA2/CA3 columns across all courses, Student Sync identifies and models 4 distinct course categories:

| Course Category | Typical Courses | Component Evaluation Scheme | Converted Total Max | Assessment Split |
| :--- | :--- | :--- | :---: | :---: |
| **Theory** | Cloud Computing, Computer Networks, Data Mining | `T1`, `T2`, `RT`, `RT1`, `RT2`, `Total`, `AP`, `PD/T`, `Total`, `Conv. Total` | **40 Marks** | 40% CA : 60% SEE |
| **Laboratory** | Cloud Computing Lab, Java Lab, Network Lab | `T1`, `T2`, `Total`, `Conv. Total` | **60 Marks** | 60% CA : 40% Practical |
| **Project** | Mini Project, Major Project | `P I -G`, `P I -C`, `P II -G`, `P II -C`, `PRE & VV G`, `PRE & VV C`, `Total`, `Conv. Total` | **100 Marks** | 100% Continuous Assessment |
| **Mandatory / Audit** | Professional Ethics, Induction | `A I`, `A II`, `Total`, `Conv. Total` | **100 Marks** | 100% Internal |

### C. Pending & Non-Applicable Mark Handling
Mark values scraped from the eCampus portal use the following conventions:
- `*` (Asterisk): Denotes a **pending evaluation** (e.g. Test 2 not yet conducted or marks awaiting entry). Asterisks are **strictly NOT treated as zero**; they are categorized with `status: "pending"`.
- `""` (Empty string) or `-` (Hyphen): Denotes an optional or **non-applicable evaluation** (e.g. Retest column when the student did not attend a retest). Categorized with `status: "not_applicable"`.
- Numeric string (e.g., `"14.8"`, `"12"`): Denotes an entered evaluation score. Categorized with `status: "entered"`.

---

## 3. Historical Results & CGPA Analytics

### A. Data Source
Published results are scraped from StudZone 2 (`FrmEpsStudResult.aspx`) and stored in `studzone2.parsed_results`:
- `sem`: Semester index (e.g., `"1"`, `"2"`).
- `code`: Course code (e.g., `"23MX21"`).
- `title`: Course title (e.g., `"SOFTWARE ENGINEERING"`).
- `credits`: Course credits explicitly published on the portal (e.g., `"4"`, `"3"`, `"2"`, `"5"`, `"1"`).
- `grade`: Published letter grade (e.g., `"A"`, `"B+"`, `"A+"`, `"O"`).
- `grade_point`: Published numeric grade point (e.g., `8.0`, `7.0`, `9.0`, `10.0`, `6.5`, `6.0`, `5.0`, `0.0`).
- `result_status`: Result status (e.g., `"Pass"`, `"Reappearance Required"`).

### B. Verified Grade Point Scale (PSG College of Technology)
```
O   -> 10.0 (Outstanding)
A+  ->  9.0 (Excellent)
A   ->  8.0 (Very Good)
B+  ->  7.0 (Good)
B   ->  6.5 (Average)
C+  ->  6.0 (Satisfactory)
C   ->  5.0 (Pass)
RA  ->  0.0 (Reappearance)
F   ->  0.0 (Fail)
W   ->  0.0 (Withdrawal)
SA  ->  0.0 (Shortage of Attendance)
```

### C. Cumulative Grade Point Average (CGPA) Formula
$$\text{CGPA} = \frac{\sum_{i=1}^n (\text{credits}_i \times \text{grade\_point}_i)}{\sum_{i=1}^n \text{credits}_i}$$

**Mathematical Proof Across Production Accounts:**
- For student `25MX232`: 24.0 credits, Total points = 191.0 $\implies \frac{191.0}{24.0} = 7.9583... \implies \mathbf{7.96}$, exactly matching `user.cgpa`.
- Verified across all 5 production users in MongoDB.

---

## 4. Interactive What-If CGPA Simulator

### A. Mathematical Model
The simulator allows students to explore hypothetical scenarios for upcoming semesters or active courses without modifying any official records.

$$\text{Projected CGPA} = \frac{(C_{\text{base}} \times \text{CGPA}_{\text{base}}) + \sum_{j=1}^m (C_{\text{sim}, j} \times GP_{\text{sim}, j})}{C_{\text{base}} + \sum_{j=1}^m C_{\text{sim}, j}}$$

Where:
- $C_{\text{base}}$: Base verified earned credits (e.g., 24.0).
- $\text{CGPA}_{\text{base}}$: Base verified CGPA (e.g., 7.96).
- $C_{\text{sim}, j}$: Explicit credit value entered for hypothetical course $j$.
- $GP_{\text{sim}, j}$: Grade point corresponding to target grade for hypothetical course $j$.

### B. Current-Semester Credit Safety Rule
Because credits for ongoing courses are not published in attendance or CA tables until final result publication, **the simulator strictly avoids defaulting ongoing course credits to 3.0 or any arbitrary value**. Students explicitly input or select credits per hypothetical course.

### C. Zero-Write Guarantee
The simulation engine executes **100% in-memory**. It does not perform any `update_one`, `insert_one`, or modification operations against MongoDB.

---

## 5. Backend API Contracts

### A. GET `/api/academic/marks-summary`
- **Method:** `GET`
- **Authentication:** Bearer token (`Authorization: Bearer <auth_token>`)
- **Query / Param:** Optional `?rollNo=<roll_no>` (must match token identity)
- **Responses:**
  - `200 OK`:
    ```json
    {
      "rollNo": "25MX232",
      "name": "VISHAL",
      "stored_cgpa": 7.96,
      "base_credits": 24.0,
      "base_cgpa": 7.96,
      "ca_marks": {
        "courses": [...],
        "total_courses": 8,
        "entered_evaluations": 14,
        "pending_evaluations": 26,
        "active_semester_notice": "..."
      },
      "results": {
        "courses": [...],
        "total_credits": 24.0,
        "total_grade_points": 191.0,
        "calculated_cgpa": 7.96,
        "stored_cgpa": 7.96,
        "cgpa_verified": true,
        "grade_distribution": {"A": 5, "A+": 2, "B+": 1},
        "semester_breakdown": [...],
        "arrears_count": 0,
        "all_cleared": true
      },
      "grade_point_map": {...}
    }
    ```
  - `401 Unauthorized`: Token missing or invalid.
  - `403 Forbidden`: Authenticated student identity does not match requested roll number.

### B. POST `/api/academic/cgpa-simulate`
- **Method:** `POST`
- **Authentication:** Bearer token (`Authorization: Bearer <auth_token>`)
- **Request Body:**
  ```json
  {
    "base_credits": 24.0,
    "base_cgpa": 7.96,
    "simulated_courses": [
      {
        "course_name": "Cloud Computing Architecture",
        "credits": 4.0,
        "grade": "O"
      }
    ]
  }
  ```
- **Responses:**
  - `200 OK`:
    ```json
    {
      "base_credits": 24.0,
      "base_cgpa": 7.96,
      "simulated_credits": 4.0,
      "total_credits": 28.0,
      "projected_cgpa": 8.25,
      "cgpa_delta": 0.29,
      "courses_simulated": [...],
      "disclaimer": "This is an in-memory mathematical what-if model. Official academic grades and database records remain unmodified."
    }
    ```
  - `400 Bad Request`: Invalid numerical parameters or malformed body.
  - `401 Unauthorized`: Unauthenticated.
  - `403 Forbidden`: Cross-user mismatch.

---

## 6. Security & Isolation Architecture
1. **Cryptographic Token Verification:** Bearer tokens are signed using HMAC-SHA256 (`generate_auth_token`, `verify_auth_token`).
2. **Strict User Isolation:** `get_authenticated_student(request)` ensures that even if a student tampers with query parameters (`?rollNo=...`) or body payloads, cross-user attempts are immediately rejected with `403 Forbidden`.
3. **Protected Subsystems:**
   - `backend/notifications/` remains protected and untouched.
   - `backend/attendance_calculator.py` remains protected and untouched.
   - Portal scrapers remain protected and untouched.

---

## 7. Known Limitations & Postponed Features
1. **SEE Target-Grade Estimator Postponed:**
   Because PSG College of Technology applies **Relative Grading** to core theory courses with $> 30$ students, individual grade cutoffs are dynamically set by the Performance Analysis Committee (PAC) after all semester examination scripts are evaluated. Hardcoding static thresholds (e.g. "80 marks gives A") would be inaccurate and misleading to students.
2. **Current-Semester Syllabus Credits:**
   Credit values for courses currently in session are not stored in StudZone 1 tables. The simulator therefore relies on user-provided course credits.
