# Student Sync — Attendance & Bunk Planner Technical Specification

## 1. Overview
The Student Sync Attendance & Bunk Planner module provides consolidated academic attendance tracking, regulatory threshold status evaluation, mathematical safe-bunk calculation, recovery guidance, and in-memory what-if attendance simulations.

Inspired by PSG Bunker, this system is integrated natively into Student Sync with strict zero-write database guarantees and authorization safeguards.

---

## 2. Attendance Data Source
- **Primary Portal**: PSG College of Technology Modern Portal (StudZone 1).
- **Document Structure**: Stored in MongoDB collection `new_users` under the student document:
  - `studzone1.parsed_attendance`: Array of enrolled courses.
    - Fields per course: `code`, `name`, `attended`, `total_classes` (or `conducted`), `absent`, `exempt_hr`, `percentage`, `percentage_num`, `status`.
  - `studzone1.class_schedule`: 2D timetable matrix representing periods, lecture hours, and weekday course slots.

---

## 3. Mathematical Foundations & Formulas

### A. Attendance Percentage
$$\text{Percentage} = \begin{cases} 0.0 & \text{if } \text{conducted} = 0 \\ \frac{\text{attended}}{\text{conducted}} \times 100 & \text{otherwise} \end{cases}$$
Rounded to 2 decimal places.

### B. Safe Bunks Formula
Calculates the maximum number of upcoming classes a student can miss while maintaining their overall attendance at or above target percentage $T$ (default $75.0\%$):
$$\text{Safe Bunks} = \left\lfloor \frac{\text{attended} - \left(\frac{T}{100}\right) \times \text{conducted}}{\frac{T}{100}} + 10^{-9} \right\rfloor$$
- Float-epsilon guard ($10^{-9}$) ensures that exact boundary scenarios (e.g., $75.0\%$, $80.0\%$) do not suffer from floating-point precision truncation.
- If current attendance $< T$, safe bunks is strictly $0$.

### C. Attendance Recovery Formula
Calculates the minimum number of consecutive future classes a student must attend without missing to raise their attendance to target percentage $T$:
$$\text{Required Classes} = \left\lceil \frac{\left(\frac{T}{100}\right) \times \text{conducted} - \text{attended}}{1 - \frac{T}{100}} - 10^{-9} \right\rceil$$
- If current attendance $\ge T$, required classes is strictly $0$.

### D. Attendance Status Thresholds
- **SAFE**: $\text{Percentage} \ge 75.0\%$
- **WARNING**: $65.0\% \le \text{Percentage} < 75.0\%$
- **CRITICAL**: $\text{Percentage} < 65.0\%$

---

## 4. In-Memory Simulation Model
- **Concept**: Evaluates hypothetical attendance trajectories for any enrolled subject.
- **Formulas**:
  $$\text{Simulated Attended} = \text{Attended}_{\text{orig}} + \Delta_{\text{attended}}$$
  $$\text{Simulated Conducted} = \text{Conducted}_{\text{orig}} + \Delta_{\text{attended}} + \Delta_{\text{bunked}}$$
  $$\text{Simulated Percentage} = \frac{\text{Simulated Attended}}{\text{Simulated Conducted}} \times 100$$
- **100% In-Memory Isolation**: The simulation NEVER updates MongoDB, modifies official baselines, or persists transient state.

---

## 5. API Contracts & Endpoints

### Endpoint 1: `GET /api/attendance/summary` (Alias: `/attendance/summary`)
Returns consolidated metrics, subject breakdown, and today's schedule for the authenticated student.

- **Query Parameters**:
  - `target` *(optional, float)*: Target threshold (default: `75.0`).
  - `day` *(optional, string)*: Weekday filter (default: current system weekday).
- **Security**: Requires Bearer token (`Authorization: Bearer <auth_token>`).
- **Response Format (`HTTP 200`)**:
```json
{
  "rollNo": "25MX232",
  "name": "VISHALY S",
  "total_attended": 258,
  "total_conducted": 310,
  "overall_percentage": 83.23,
  "overall_status": "SAFE",
  "overall_safe_bunks": 34,
  "overall_required_classes": 0,
  "target": 75.0,
  "subjects": [
    {
      "code": "23MX31",
      "name": "CLOUD COMPUTING",
      "attended": 28,
      "conducted": 37,
      "absent": 9,
      "exempt_hr": 0,
      "percentage": 75.68,
      "status": "SAFE",
      "safe_bunks": 0,
      "required_classes": 0
    }
  ],
  "today_schedule": {
    "day": "Tuesday",
    "classes": [
      {
        "period": 1,
        "time": "8.30 - 9.20",
        "code": "23MXAO",
        "name": "HUMAN COMPUTER INTERACTION",
        "is_free": false
      }
    ]
  },
  "last_synced": "2026-10-06T12:54:02Z"
}
```

### Endpoint 2: `POST /api/attendance/simulate` (Alias: `/attendance/simulate`)
Computes projected attendance metrics in-memory.

- **Request Body**:
```json
{
  "subject_code": "23MX31",
  "additional_attended": 2,
  "additional_bunked": 1,
  "target": 75.0
}
```
- **Validation**:
  - `subject_code` must match an enrolled course (`404` if not found).
  - Numerical inputs must be non-negative integers (`400` if negative or invalid).
  - Target must be a valid percentage between $1.0$ and $99.9$ (`400` if out of bounds).
- **Response Format (`HTTP 200`)**:
```json
{
  "subject_code": "23MX31",
  "subject_name": "CLOUD COMPUTING",
  "target": 75.0,
  "original_attendance": {
    "attended": 28,
    "conducted": 37,
    "percentage": 75.68,
    "status": "SAFE",
    "safe_bunks": 0,
    "required_classes": 0
  },
  "simulated_attended": 30,
  "simulated_conducted": 40,
  "simulated_percentage": 75.00,
  "simulated_status": "SAFE",
  "simulated_safe_bunks": 0,
  "simulated_required_classes": 0,
  "simulated": {
    "additional_attended": 2,
    "additional_bunked": 1,
    "percentage_change": -0.68
  }
}
```

---

## 6. Authentication & Authorization Architecture
1. **HMAC-SHA256 Bearer Token**:
   - Generated during `/login`: `generate_auth_token(roll_no)` computes an HMAC signature using server `AUTH_SECRET`.
   - Verified on each request: `verify_auth_token(token)` uses constant-time `hmac.compare_digest` to prevent timing attacks.
2. **Access Control**:
   - **Unauthenticated requests** (`401 Unauthorized`): Rejected immediately.
   - **Cross-User Snooping** (`403 Forbidden`): If a student authenticated as `25MX232` attempts to supply `?rollNo=25MX227` or simulate another user's subject, the mismatch is blocked.
   - **Unknown Student** (`404 Not Found`): If the authenticated roll number is absent from MongoDB.

---

## 7. Frontend Component Architecture
Located in `react-spd/src/`:
- **[`AttendanceDashboard.jsx`](file:///C:/Users/visha/Downloads/ACPNS-main/ACPNS-main/react-spd/src/AttendanceDashboard.jsx)**: Main route container (`/attendance`).
- **[`components/attendance/AttendanceOverview.jsx`](file:///C:/Users/visha/Downloads/ACPNS-main/ACPNS-main/react-spd/src/components/attendance/AttendanceOverview.jsx)**: Primary card, consolidated percentage, status badge, safe bunk reserve, and quick target buttons (`75%`, `80%`, `85%`, `90%`).
- **[`components/attendance/TodaySchedule.jsx`](file:///C:/Users/visha/Downloads/ACPNS-main/ACPNS-main/react-spd/src/components/attendance/TodaySchedule.jsx)**: Class lecture timeline from `studzone1.class_schedule`.
- **[`components/attendance/SubjectAttendanceCard.jsx`](file:///C:/Users/visha/Downloads/ACPNS-main/ACPNS-main/react-spd/src/components/attendance/SubjectAttendanceCard.jsx)**: Subject cards grid with visual progress bars, attended/conducted counts, and safe bunks.
- **[`components/attendance/BunkPlanner.jsx`](file:///C:/Users/visha/Downloads/ACPNS-main/ACPNS-main/react-spd/src/components/attendance/BunkPlanner.jsx)**: Interactive subject planner with target thresholds.
- **[`components/attendance/AttendanceSimulator.jsx`](file:///C:/Users/visha/Downloads/ACPNS-main/ACPNS-main/react-spd/src/components/attendance/AttendanceSimulator.jsx)**: PSG Bunker style dual counter (`+` / `-`), projected attendance, difference pill, and reset button.
- **[`Dashboard.jsx`](file:///C:/Users/visha/Downloads/ACPNS-main/ACPNS-main/react-spd/src/Dashboard.jsx)**: Cross-linked via "Open Interactive Bunk Planner & Simulator →" callout button in the Course Attendance tab.

---

## 8. Production Safety Constraints
1. **Zero Database Mutation**: The simulator and attendance APIs NEVER execute `insert`, `update`, `delete`, or `replace` against MongoDB Atlas.
2. **Notification Engine Untouched**: `change_detector.py`, `speed_ser.py`, and `notifications_log` are untouched and operate independently.
3. **Portal Baseline Integrity**: Official attendance baselines are preserved exactly as scraped from PSG StudZone.
