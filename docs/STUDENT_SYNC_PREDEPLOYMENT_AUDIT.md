# Student Sync — Pre-Deployment Reliability & Security Audit

**Audit Date**: October 30, 2026  
**Auditor**: Senior Backend, Systems & Security Review  
**Target Repository**: `https://github.com/VishalyS/Student-Sync`  
**Working Workspace**: `C:\Users\visha\Downloads\ACPNS-main - MCP\ACPNS-main`  
**Protected Projects Verified Untouched**:
- `C:\Users\visha\Downloads\ACPNS-main` (Untouched)
- `C:\Users\visha\OneDrive\Desktop\Student Sync - Hostel` (Untouched)

---

## 1. Executive Summary & Deployment Readiness

### Overall Assessment: **READY FOR CONTROLLED PILOT** (All Critical & High Blockers Cleared)

Following rigorous pre-deployment remediation, **all critical and high severity security blockers (SEC-01, SEC-02, SEC-03) and test isolation defects (TST-01) have been fully resolved and verified with automated test suites**.

| Metric | Pre-Remediation State | Post-Remediation State | Status |
| :--- | :--- | :--- | :--- |
| **Backend Test Suite** | 205 Passed / 1 Failed (206 total) | **219 Passed / 0 Failed (219 total)** | **100% PASS** |
| **Security Audit Suite** | None (Vulnerabilities active) | **13 Passed / 0 Failed (13 total)** | **VERIFIED** |
| **Planner API Suite** | 1 Failed (Atlas DB coupling) | **8 Passed / 0 Failed (Deterministic Mock)** | **VERIFIED** |
| **Notification Reliability** | 14 Passed / 0 Failed | **14 Passed / 0 Failed** | **VERIFIED** |
| **Frontend Production Build** | Vite v5.4.8 (76 modules, 2.57s) | **Vite v5.4.8 (76 modules, 2.65s, 0 errors)** | **CLEAN** |
| **Credential Storage** | Plaintext in MongoDB Atlas | **Fernet Authenticated Encryption (`enc:v1:`)** | **ENCRYPTED** |
| **Password Overwrite (/api/update)** | Unauthenticated IDOR takeover | **Authenticated Ownership + 15m Token/OTP** | **HARDENED** |
| **Chatbot API (/api/chatbot)** | Unauthenticated roll fallback | **Strict Server-Side Auth + 403 Cross-User** | **HARDENED** |
| **Deployment Recommendation** | **BLOCKED** | **READY FOR CONTROLLED PILOT** | **CLEARED** |

---

## 2. Architecture & Actual End-to-End Execution Flow

```mermaid
sequenceDiagram
    autonumber
    actor Student
    participant Browser as React Frontend (react-spd)
    participant Flask as Flask API (pyserver.py)
    participant Crypto as CryptoService (crypto_service.py)
    participant SZ1 as StudZone 1 Portal
    participant SZ2 as StudZone 2 Portal
    participant DB as MongoDB Atlas (ecampus)
    participant Queue as EmailSender (Thread Pool)
    participant Daemon as Synchronizer (speed_ser.py)

    Note over Student,DB: 1. Registration & Encrypted Credential Flow
    Student->>Browser: Enters Roll No, Password, Custom Email
    Browser->>Flask: POST /api/register {rollNo, password, email}
    Flask->>DB: Check if rollNo exists in 'new_users'
    alt Student Already Registered
        Flask-->>Browser: 409 Conflict ("Already registered. Please Login.")
    else New Student
        Flask->>Crypto: encrypt_password(placeholder_password)
        Flask->>DB: Insert uninitialized record (encrypted password, baseline_initialized: false)
        Flask->>SZ1: Authenticate (modern_login) & Scrape initial data
        Flask->>SZ2: Authenticate (legacy_login) & Scrape results/timetable
        alt Portal Auth Fails
            Flask->>DB: Delete uninitialized record (Rollback)
            Flask-->>Browser: 401 Unauthorized ("Invalid credentials")
        else Portal Auth Succeeds
            Flask->>Crypto: encrypt_password(actual_password)
            Flask->>DB: Upsert merged_user (encrypted password, baseline_initialized: true)
            Flask->>Queue: Dispatch Welcome Email to Student & Admin Alert
            Flask-->>Browser: 201 Created (auth_token issued)
        end
    end

    Note over Daemon,DB: 2. Periodic Polling with Decryption In Memory Only (Every 5 Mins)
    loop Every 300 Seconds
        Daemon->>DB: Check .synchronizer.lock & fetch all users (baseline_initialized: true)
        par Concurrent User Sync (max_workers=5)
            Daemon->>Crypto: get_student_portal_password(user) -> decrypted in memory
            Daemon->>SZ1: Scrape fresh attendance, marks, fees, leave
            Daemon->>SZ2: Scrape fresh results, timetable, seating, circulars
            Daemon->>Daemon: change_detector.py compares cached vs fresh data
            alt Genuine Data Change Detected
                Daemon->>Daemon: Generate SHA-256 changeHash
                Daemon->>DB: Insert into 'notifications_log' (changeHash_unique)
                Daemon->>Queue: Queue notification email to student's PSG Tech inbox
            else No Data Change or Portal Timeout
                Daemon->>DB: Preserve previous parsed tables; update portalStatus
            end
            Daemon->>DB: Update 'new_users' with fresh timestamp and sync status (password untouched)
        end
    end

    Note over Student,Browser: 3. Secure Password Recovery Flow
    Student->>Browser: Enters Roll No on /update, clicks "Send Code"
    Browser->>Flask: POST /api/auth/request-reset {rollNo}
    Flask->>Flask: Generate 32-byte secret token & 6-digit numeric OTP (15 min expiry)
    Flask->>DB: Store SHA-256 hashes in 'password_resets'
    Flask->>Queue: Email 6-digit OTP & reset link to student
    Student->>Browser: Submits OTP + New Password
    Browser->>Flask: POST /api/update {rollno, password, otp}
    Flask->>DB: Verify unexpired, unused reset record matching hash
    Flask->>Crypto: encrypt_password(new_password)
    Flask->>DB: Atomically update password in 'new_users' & mark reset token used
    Flask-->>Browser: 200 OK ("Password updated successfully")
```

---

## 3. Findings Classified by Severity & Remediation Evidence

### CRITICAL SEVERITY (Deployment Blockers — ALL RESOLVED)

#### 1. [RESOLVED & VERIFIED] Unauthenticated Password Overwrite / Account Takeover Vulnerability (SEC-01)
- **Original Location**: `backend/pyserver.py:1225-1250` (`update_password`), `react-spd/src/UpdatePassword.jsx:26-30`
- **Original Vulnerability**: The `/api/update` endpoint accepted arbitrary roll numbers and immediately updated the password without checking authentication, sessions, or recovery tokens.
- **Remediation Implemented**:
  1. **Dual-Mode Authorization in `backend/pyserver.py`**:
     - **Mode A (Authenticated)**: Extracts user from `get_authenticated_student(request)`. Validates that `auth_user.rollNo == target_rollNo`. If roll numbers mismatch, returns **HTTP 403 Forbidden**. Optionally validates `current_password` against the student's existing decrypted password.
     - **Mode B (Account Recovery)**: If unauthenticated, requires either a 6-digit `otp` or a 32-byte `reset_token`. Unauthenticated requests without token/OTP immediately return **HTTP 401 Unauthorized**.
  2. **Dedicated Recovery Mechanism**:
     - Added `/api/auth/request-reset` and `/api/request-reset`.
     - Generates cryptographically secure `secrets.token_urlsafe(32)` and 6-digit numeric OTP.
     - Stores SHA-256 hashes of token and OTP in a new `password_resets` collection with a strict 15-minute TTL (`expires_at`).
     - Invalidation of prior tokens upon generating a new one.
     - Single-use enforcement (`used: True`) atomically checked during reset.
     - Dispatches recovery email via asynchronous `EmailSender`.
  3. **Frontend Integration**:
     - Updated `react-spd/src/UpdatePassword.jsx` to pass `Authorization: Bearer <auth_token>` when logged in, or offer an intuitive "Send Code to Email" flow with OTP input when recovering an account.
     - Added "Forgot password?" navigation link on `react-spd/src/Login.jsx` and registered `/update` route in `App.jsx`.
- **Automated Verification Evidence**:
  - `test_security_remediation_audit.py::test_01_unauthenticated_password_update_rejected`: PASSED (HTTP 401).
  - `test_security_remediation_audit.py::test_02_cross_student_password_update_forbidden`: PASSED (HTTP 403).
  - `test_security_remediation_audit.py::test_03_authenticated_password_update_success`: PASSED (HTTP 200).
  - `test_security_remediation_audit.py::test_04_request_reset_token_generation`: PASSED (Token & OTP generated, SHA-256 hashed).
  - `test_security_remediation_audit.py::test_05_valid_recovery_token_password_update`: PASSED (HTTP 200, used flag set).
  - `test_security_remediation_audit.py::test_06_reused_recovery_token_rejected`: PASSED (HTTP 401).
  - `test_security_remediation_audit.py::test_07_expired_recovery_token_rejected`: PASSED (HTTP 401).

---

#### 2. [RESOLVED & VERIFIED] Reversible Plaintext Storage of Institutional Portal Credentials (SEC-02)
- **Original Location**: `backend/pyserver.py:503`, `backend/pyserver.py:918`, `backend/speed_ser.py:247`
- **Original Vulnerability**: Institutional portal passwords were stored in plaintext in MongoDB Atlas `new_users.password` to allow background scraping by `speed_ser.py`.
- **Remediation Implemented**:
  1. **Cryptographic Engine (`backend/crypto_service.py`)**:
     - Built using `cryptography.fernet.Fernet` implementing authenticated symmetric encryption (AES-128-CBC with HMAC-SHA256 authenticated envelope).
     - Distinct ciphertext prefix: `enc:v1:` to safely distinguish encrypted values from legacy plaintext.
     - Master key loaded strictly from environment variable `STUDENT_SYNC_ENCRYPTION_KEY` or `ENCRYPTION_KEY`.
     - **Production Guard**: If `FLASK_ENV == "production"`, `crypto_service` throws a fatal `RuntimeError` at import if the environment encryption key is missing, preventing insecure startup.
     - Key derivation via SHA-256 guarantees valid 32-byte URL-safe base64 Fernet key format.
  2. **In-Memory-Only Decryption**:
     - Helper `get_student_portal_password(student_dict)` safely decrypts the password in memory during active login verification or portal scraping.
     - Never logs decrypted or cleartext credentials (`logger` filters passwords; zero credential printing).
  3. **Zero-Downtime Safe Migration**:
     - `migrate_student_credentials(users_collection)` runs on startup and transparently on login: detects any legacy plaintext passwords, encrypts them in place, and leaves existing `enc:v1:` ciphertexts untouched.
     - Background synchronizer (`speed_ser.py`) uses `get_student_portal_password` and never rewrites the password field during sync cycles.
     - Registration and password update flows encrypt all passwords before calling `users_collection.insert_one` or `update_one`.
- **Automated Verification Evidence**:
  - `test_security_remediation_audit.py::test_08_encryption_roundtrip`: PASSED (Plaintext != Ciphertext, Decrypted == Plaintext).
  - `test_security_remediation_audit.py::test_09_legacy_credential_migration`: PASSED (Plaintext migrated to `enc:v1:`, existing encrypted untouched).
  - `test_security_remediation_audit.py::test_10_tampered_ciphertext_fails_gracefully`: PASSED (Decryption returns None on invalid token signature).

---

### HIGH SEVERITY (ALL RESOLVED)

#### 3. [RESOLVED & VERIFIED] Unauthenticated IDOR Information Disclosure via Chatbot Endpoint (SEC-03)
- **Original Location**: `backend/pyserver.py:2083-2090` (`chatbot_endpoint`)
- **Original Vulnerability**: `/api/chatbot` allowed an unauthenticated request to specify a target `rollNo` in the JSON body or `X-Roll-No` header and returned the target student's full attendance and mark records.
- **Remediation Implemented**:
  1. **Strict Server-Side Authentication**:
     - Removed all fallbacks to `data.get('rollNo')` and `request.headers.get('X-Roll-No')`.
     - Authenticates exclusively via `get_authenticated_student(request)`.
  2. **Cross-Student IDOR Defense**:
     - If an authenticated student (e.g. Roll A) explicitly sends another student's roll number in the request body (Roll B), the server immediately returns **HTTP 403 Forbidden** with error `"Unauthorized access to another student's academic data"`.
  3. **Safe Unauthenticated Guidance**:
     - If unauthenticated (`user is None`), the endpoint returns a generic navigation and capability guide linking to `/login` without accessing MongoDB or disclosing any student data.
- **Automated Verification Evidence**:
  - `test_security_remediation_audit.py::test_11_chatbot_unauthenticated_request_no_leak`: PASSED (Generic response; zero student records queried).
  - `test_security_remediation_audit.py::test_12_chatbot_cross_user_query_forbidden`: PASSED (HTTP 403 Forbidden).
  - `test_security_remediation_audit.py::test_13_chatbot_authenticated_self_query`: PASSED (HTTP 200 with personalized attendance metrics).

---

#### 4. [RESOLVED & VERIFIED] Live Data Coupling and Test Fragility in `test_planner_api.py` (TST-01)
- **Original Location**: `backend/tests/test_planner_api.py:42-45, 170`
- **Original Defect**: `TestPlannerApi` queried the live MongoDB Atlas document `25MX232` and asserted static hardcoded CA counts (`self.assertEqual(ah["total_entered_ca"], 20)`), which failed when live marks changed in Atlas to 21.
- **Remediation Implemented**:
  1. **Deterministic Mock Fixture (`MOCK_STUDENT_25MX232`)**:
     - Replaced Atlas live database queries with an isolated, static in-memory fixture containing 8 complete courses, exact 20 entered CA marks, 30 pending CA marks, an authentic 7-row weekly schedule matrix, and 5 exam slots.
  2. **Unit Test Isolation**:
     - Patched `backend.pyserver.users_collection.find_one`, `update_one`, and `insert_one` in `setUp()` using `unittest.mock.patch`.
     - Zero network calls to MongoDB Atlas during planner unit test execution.
- **Automated Verification Evidence**:
  - `backend/tests/test_planner_api.py`: **8 of 8 tests PASSED in 0.056s** (including `test_complete_response_schema`).

---

### MEDIUM & LOW SEVERITY (Operational & Optimization Items)

#### 5. Synchronous Blocking SMTP in Contact Form (SEC-04)
- **Location**: `backend/pyserver.py:1357-1360` (`send_message`)
- **Severity**: MEDIUM
- **Status**: Non-blocking. Under normal network conditions, contact submissions take <1s. Recommended for post-pilot optimization to enqueue contact submissions through `EmailSender`.

#### 6. Missing Server-Side Session Revocation on Logout (SEC-05)
- **Location**: `react-spd/src/components/Navbar.jsx:73-79`
- **Severity**: LOW
- **Status**: Non-blocking. Stateless HMAC tokens expire automatically after 24 hours. Token replay risk is minimal and mitigated by HTTPS in production.

#### 7. StudZone 2 Legacy ASP.NET CAPTCHA Bottleneck
- **Location**: `backend/scrapers/login.py:68-76`
- **Severity**: MEDIUM
- **Status**: Non-blocking. StudZone 1 (where 90% of dynamic attendance, marks, fees, and timetable data resides) does not use CAPTCHA. If StudZone 2 challenges during background sync, cached results are preserved and the system flags portal status gracefully.

#### 8. Documentation Outdated Template in Root `README.md`
- **Location**: `README.md:1-25`
- **Severity**: LOW
- **Status**: Non-blocking. Root documentation references older Tailwind CLI template; does not affect application runtime.

---

## 4. Audit A — Registration & Account Lifecycle Deep Dive

| Lifecycle Stage | Implementation File & Function | Verified Behavior | Defect / Failure Mode | Post-Audit Status |
| :--- | :--- | :--- | :--- | :--- |
| **Frontend Form** | `react-spd/src/Login.jsx` | Submits `rollNo`, `password`, custom `email` via POST `/api/register`. | None observed. Form cleans whitespace and supports password visibility. | **VERIFIED** |
| **Input Validation** | `backend/pyserver.py:471-476` | Strips whitespace, forces roll number uppercase, rejects missing fields with HTTP 400. | Rejects empty strings. Enforces valid roll number format. | **VERIFIED** |
| **Duplicate Prevention** | `backend/pyserver.py:480-490` | Case-insensitive regex query against `new_users.rollNo`. Returns HTTP 409 Conflict. | Verified: Duplicate registrations are rejected without mutating existing records. | **VERIFIED** |
| **Credential Encryption** | `backend/pyserver.py:503, 526` | Encrypts password using `crypto_service.encrypt_password` before database write. | Encrypted with `enc:v1:` prefix. Plaintext never stored in DB. | **VERIFIED (SEC-02)** |
| **Race-Condition Guard** | `backend/pyserver.py:497-511` | Upserts placeholder doc with `baseline_initialized: False` before portal network calls. | Prevents background synchronizer from scraping student mid-registration. | **VERIFIED** |
| **Initial Portal Scrape** | `backend/pyserver.py:514` (`sync_student_dual_portal`) | Authenticates against StudZone 1 & StudZone 2. Scrapes full academic records. | If portal credentials fail, placeholder is rolled back (`delete_one`), returns HTTP 401. | **VERIFIED** |
| **Baseline Establishment** | `backend/pyserver.py:294, 299` | Sets `baseline_initialized: True`. Bypasses `process_detected_changes`. | Verified: Exactly 0 change alerts emitted on initial registration. | **VERIFIED** |
| **Welcome Emails** | `backend/pyserver.py:530, 638` | Queues student HTML welcome email and sends direct admin registration alert. | Tested & verified: Dispatched reliably with duplicate suppression. | **VERIFIED** |
| **Login Flow** | `backend/pyserver.py:910-960` | Finds student in DB; verifies encrypted password via constant-time HMAC compare; issues Bearer token. | Falls back to cached data if portal is down during login. Auto-migrates plaintext. | **VERIFIED** |
| **Password Update** | `backend/pyserver.py:1225` (`/api/update`) | Requires authenticated ownership OR verified unexpired single-use OTP/token. Encrypts password at rest. | Rejects unauthenticated attempts (HTTP 401) and cross-student attempts (HTTP 403). | **VERIFIED (SEC-01)** |

---

## 5. Audit B — Academic Scraping Coverage Matrix

| Academic Module | Source Portal & URL | Scraper Entry Point | Database Target (`new_users`) | Stale / Timeout Fallback | Missing / Zero Handling | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Student Profile** | SZ1 `/Home/Profile` | `scrape_studzone1_profile` | `profile`, `name` | Retains previous profile | Graceful fallback to attendance headers | **VERIFIED** |
| **Attendance %** | SZ1 `/Attendance/StudentPercentage` | `scrape_studzone1_attendance` | `studzone1.parsed_attendance`, `attendance` | Retains `previous_parsed_attendance` if portal updating | Parses attended/conducted, preserves 0% | **VERIFIED** |
| **CA Marks** | SZ1 `/ContinuousAssessment/CAMarksView` | `scrape_studzone1_ca_marks` | `studzone1.parsed_marks`, `marks` | Preserves existing parsed marks list | Handles missing marks as `"-"`, preserves numeric 0 | **VERIFIED** |
| **Class Timetable** | SZ1 `/Attendance/TimeTable` | `scrape_studzone1_class_timetable` | `studzone1.class_schedule`, `class_timetable_html` | Preserves existing matrix | Validates course codes against regex | **VERIFIED** |
| **Fees & Dues** | SZ1 `/Fees/Fees` | `scrape_studzone1_fees` | `studzone1.fee_items`, `fee_status`, `fees` | Preserves existing fee strings | Accurately detects transition to Rs. 0 | **VERIFIED** |
| **SZ1 Hostel Status** | SZ1 `/Hostel/PaymentStart` | `scrape_studzone1_hostel` | `studzone1.hostel_status`, `hostel` | Preserves existing allocation text | Differentiates Day Scholar from Hosteller | **VERIFIED** |
| **Scholarships** | SZ1 `/Scholar/ScholarshipApply`, `/VallalarScholarship` | `scrape_studzone1_scholarships` | `studzone1.scholarships` | Preserves existing application dict | Parses Resident Status and Room Number | **VERIFIED** |
| **Feedback Forms** | SZ1 `/Feedback/...` | `scrape_studzone1_feedback` | `studzone1.feedback` | Preserves existing list | Handles 0 pending forms cleanly | **VERIFIED** |
| **Leave / OD** | SZ1 `/Attendance/leaveentry` | `scrape_studzone1_leave` | `studzone1.leave_entries`, `leave` | Preserves existing entry list | Parses approval status and entry counts | **VERIFIED** |
| **Semester Results** | SZ2 `/FrmEpsStudResult.aspx` | `scrape_studzone2_results` | `studzone2.parsed_results`, `results` | Preserves existing results list | Calculates numeric GPA and Pass/RA status | **VERIFIED** |
| **CGPA Summary** | SZ2 Calculated / Summary | `calculate_cgpa_from_data` | `cgpa`, `studzone2.cgpa` | Retains previous float | Handles None, 0.0, and positive floats | **VERIFIED** |
| **Exam Timetable** | SZ2 `/FrmEpsTimetable.aspx` | `scrape_studzone2_timetable` | `studzone2.parsed_timetable`, `timetable` | Preserves existing timetable slots | Handles FN/AN sessions and dates | **VERIFIED** |
| **Exam Seating** | SZ2 `/EpsWfSeating.aspx` | `scrape_studzone2_seating` | `studzone2.seating_slots`, `seating` | Explicitly tracks "not_published_yet" | Detects publication from empty to hall/seat | **VERIFIED** |
| **Circulars** | SZ2 `/AttWfStudMenu.aspx` | `scrape_studzone2_circulars` | `studzone2.circulars` | Preserves existing links | Filters PDF links and guidelines | **VERIFIED** |
| **Campus Library** | External OPAC | None (Explicit placeholder) | `library: null` | `syncStatus: not_available_on_portal` | Returns None without crashing UI | **DOCUMENTED GAP** |

---

## 6. Audit C — Notification Reliability Matrix

| Event / Notification Type | Trigger Condition | Change Detection Rule | Deduplication Mechanism | Logged in `notifications_log` | Email Dispatched | Recovery on Failure |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Attendance Change** | Percentage delta or attended count increase | Float change (`old != new`) or drop below 75% | SHA-256 (`attendance||code_old_new`) | ✅ Yes | ✅ Yes (2 workers) | Exponential backoff (2 retries) |
| **CA Marks Published** | CA1, CA2, CA3, or Total updated | String/number mismatch per course code | SHA-256 (`marks||code_ca_score`) | ✅ Yes | ✅ Yes | Stale recovery (>3600s) |
| **Semester Grade Change** | Letter grade updated or result published | Grade string mismatch (`B+` → `A`) | SHA-256 (`results||code_old_new`) | ✅ Yes | ✅ Yes | Delivery uncertain status |
| **CGPA Update** | Net cumulative GPA changed | Float delta (`round(old, 2) != round(new, 2)`) | SHA-256 (`cgpa||cgpa_old_new`) | ✅ Yes | ✅ Yes | Stale recovery |
| **Exam Timetable Shift** | Date, session (FN/AN), or timing change | Structural slot comparison | SHA-256 (`timetable||tt_code_date`) | ✅ Yes | ✅ Yes | Stale recovery |
| **Exam Seating Published** | Hall and seat desk assigned | Transition from null to published | SHA-256 (`seating||seating_pub`) | ✅ Yes | ✅ Yes | Stale recovery |
| **Fees Status Update** | Dues cleared or new bill posted | Status string change | SHA-256 (`fees||fee_old_new`) | ✅ Yes | ✅ Yes | Stale recovery |
| **Hostel Allocation (SZ1)** | Room or block assigned in StudZone 1 | Guarded by verified `HOSTELLER` status | SHA-256 (`hostel||hostel_val`) | ✅ Yes | ✅ Yes | Day scholars receive 0 alerts |
| **Hostel Room / Mess (Live)** | Room or mess changed on Edviewx portal | Comparison against cached hostel doc | SHA-256 (`hostel||hostel_change`) | ✅ Yes | ✅ Yes | Stale recovery |
| **Feedback Form Active** | New faculty feedback form open | Form count delta | SHA-256 (`feedback||...`) | ✅ Yes | ✅ Yes | Stale recovery |
| **Circular Published** | New examination guideline PDF | Circular count increase | SHA-256 (`circulars||...`) | ✅ Yes | ✅ Yes | Stale recovery |
| **Leave / OD Status** | Approval or entry added | Entry count increase or status change | SHA-256 (`leave||...`) | ✅ Yes | ✅ Yes | Stale recovery |

---

## 7. Audit D — Hostel Subsystem Architecture & Isolation

### Independence from Academic Workflows
The hostel subsystem operates through a strictly decoupled architecture:
1. **Isolated Data Store**: All hostel data resides in `hostel_students`. Academic collections (`new_users`, `subjects`) are **never mutated** by hostel operations.
2. **Access Control Barrier**:
   ```python
   # Gated strictly by StudZone 1 verified residential status
   res_info = determine_residential_status(user)
   if not res_info.get("can_access_hostel"):
       return jsonify({"error": "Access restricted to verified hostel residents only"}), 403
   ```
   Day Scholars and unverified students receive HTTP 403 Forbidden on all hostel endpoints (`/api/hostel/student/<rollno>`, `/room`, `/mess`, `/fees`, `/leave`).
3. **Synthetic Data Contamination Protection**:
   `is_synthetic_document()` inspects document metadata (`runId`, `student_name == "TEST RESIDENT"`, `is_synthetic`). Synthetic test fixtures are strictly blocked from being returned to live student sessions.
4. **On-Demand Polling Boundary**:
   The PSG Tech Hostel portal (`https://edviewx.psgtech.ac.in/Hostel`) is **not polled by the background daemon** (`speed_ser.py`). Extractions are initiated on-demand when an authenticated resident accesses their Hostel Dashboard.

---

## 8. Audit E — Automated & Regression Test Results

### Full Test Suite Execution Summary
- **Total Tests Executed**: **219 unit and integration tests** across 36 test files.
- **Pass Count**: **219 passed (100%)**.
- **Fail Count**: **0 failed**.
- **Error Count**: **0 errors**.
- **Execution Time**: **232.422 seconds**.
- **Test Command**: `py -m unittest discover -s backend/tests -p "test_*.py"`
- **Result Status**: **OK**

### Key Subsystem Test Results

| Test Module | Test File | Test Count | Result | Key Verified Behaviors |
| :--- | :--- | :---: | :---: | :--- |
| **Security Remediation Audit** | `test_security_remediation_audit.py` | 13 | **13/13 PASS** | SEC-01 unauth/cross-user rejection, recovery token lifecycle, SEC-02 Fernet encryption & migration, SEC-03 chatbot authorization |
| **Academic Planner API** | `test_planner_api.py` | 8 | **8/8 PASS** | Complete schema, 20 entered / 30 pending CA marks, attendance health, exam conflicts, schedule matrix (Deterministic Mock) |
| **Priority 2 Notification Audit** | `test_priority2_notification_audit.py` | 14 | **14/14 PASS** | Change detection, concurrent deduplication, timeout handling, retry backoff |
| **Priority 1 Portal Audit** | `test_priority1_portal_audit.py` | 20 | **20/20 PASS** | StudZone 1 & 2 field coverage, parsing accuracy, edge-case handlers |
| **Priority 3 Reliability Audit** | `test_priority3_reliability_audit.py` | 17 | **17/17 PASS** | Baseline initialization, stale notification recovery, multi-student isolation |
| **Chatbot & Navigator** | `test_chatbot_navigator.py` | 14 | **14/14 PASS** | Intent classification, bunk calculation rules, contextual routing |
| **Hostel Integration** | `test_hostel_integration.py` | 18 | **18/18 PASS** | Residential status gating, room/mess endpoints, synthetic guard |
| **Academic Calculations** | `test_academic_calculator.py` | 16 | **16/16 PASS** | Attendance percentage, safe bunk counts, GPA & CGPA calculation |

### Frontend Production Build Verification
- **Build Tool**: Vite v5.4.8 (`npm run build` in `react-spd`)
- **Modules Transformed**: **76 modules**
- **Build Duration**: **2.65 seconds**
- **Build Output**:
  - `dist/index.html` (0.46 kB)
  - `dist/assets/index-*.css` (45.34 kB)
  - `dist/assets/index-*.js` (472.04 kB)
- **Errors / Warnings**: **0 errors**, **0 blocking warnings**.

---

## 9. Security & Data Isolation Risks

| Risk ID | Vulnerability Description | Threat Vector | CVSS | Remediation Status | Verification Reference |
| :---: | :--- | :--- | :---: | :---: | :--- |
| **SEC-01** | Missing Authentication on Password Overwrite (`/api/update`) | Any caller can change another student's account password by sending their roll number | 9.8 | **RESOLVED & VERIFIED** | `test_security_remediation_audit.py:1-7` (HTTP 401 unauth, HTTP 403 cross-user, 15m single-use OTP/token recovery) |
| **SEC-02** | Plaintext Storage of Portal Credentials in MongoDB | Database read breach exposes cleartext institutional passwords for all registered students | 8.6 | **RESOLVED & VERIFIED** | `backend/crypto_service.py` (Fernet authenticated encryption at rest, memory-only decryption, automated startup migration) |
| **SEC-03** | Chatbot IDOR Information Disclosure | Unauthenticated requests with `rollNo` in body query target student's academic records | 7.5 | **RESOLVED & VERIFIED** | `test_security_remediation_audit.py:11-13` (Removed roll fallback; strict server auth; HTTP 403 on cross-user query) |
| **SEC-04** | Synchronous Blocking SMTP in Contact Endpoint | Denial-of-service / thread pool exhaustion via repeated contact form submissions | 5.3 | **ACCEPTED RISK (MEDIUM)** | Low volume; isolated contact endpoint; non-blocking for pilot |
| **SEC-05** | Stateless Token Invalidation Gap | Logout clears client localStorage but does not revoke HMAC token on server | 4.3 | **ACCEPTED RISK (LOW)** | 24-hour token expiration; HTTPS in production; non-blocking for pilot |

---

## 10. Verified Working vs Partially Working vs Missing Features

### Verified Working Features (Production Ready)
- [x] Dual-portal academic scraping (StudZone 1 & StudZone 2).
- [x] Authenticated credential encryption at rest (`enc:v1:` Fernet) with zero plaintext storage.
- [x] Hardened password management: authenticated session ownership + 15-minute expiring single-use OTP/token recovery.
- [x] Secured Assistant/Chatbot with verified server-side authentication and cross-user IDOR protection.
- [x] Course-by-course attendance parsing and dynamic safe bunk calculations.
- [x] Continuous assessment (CA1, CA2, CA3) parsing and automated grade mapping.
- [x] Semester examination timetable and room seating arrangement tracking.
- [x] Granular change detection across 11 distinct institutional modules.
- [x] Deterministic SHA-256 hashing and atomic MongoDB deduplication (`changeHash_unique`).
- [x] Asynchronous background email delivery with retry backoff and stale state recovery.
- [x] Background single-instance synchronizer with PID lockfile guard.
- [x] Decoupled Hostel subsystem with strict residential status gating for Day Scholars.
- [x] Single-Page Application (SPA) frontend build and dynamic API endpoint routing.

### Partially Working Features (Post-Pilot Hardening Items)
- [!] **Exam Results Scraper**: Reliably extracts grades and calculates CGPA; however, session recovery requires manual intervention if legacy StudZone 2 challenges with an image CAPTCHA.
- [!] **Frontend Push Updates**: Changes are ingested by background polling every 5 minutes, but the open browser tab requires a manual refresh or navigation to display new notification badges (no WebSocket/SSE).

### Missing Features (Documented Gaps)
- [-] **Campus Library Module**: Marked as placeholder (`not_available_on_portal`). No active OPAC library scraper connected.
- [-] **Formal MCP Protocol Server**: Chatbot is REST-based with direct internal Python calculation calls. No JSON-RPC 2.0 FastMCP server is currently active.

---

## 11. Implemented Remediations Summary

### 1. Password Update & Account Recovery Security (SEC-01)
- **Files Modified**: `backend/pyserver.py`, `backend/database.py`, `react-spd/src/UpdatePassword.jsx`, `react-spd/src/Login.jsx`, `react-spd/src/App.jsx`
- **Implementation**:
  - Implemented `/api/auth/request-reset` generating a 32-byte secret URL token and a 6-digit numeric OTP.
  - Added `password_resets` MongoDB collection with compound indices (`rollNo`, `expires_at`).
  - Hashed reset tokens using SHA-256 before storage; enforced 15-minute expiration and atomic single-use invalidation (`used: True`).
  - Refactored `/api/update`: unauthenticated requests strictly require a valid reset token/OTP (returning HTTP 401 otherwise); authenticated requests verify roll ownership (returning HTTP 403 on mismatch).

### 2. Credential Protection at Rest (SEC-02)
- **Files Added / Modified**: `backend/crypto_service.py`, `backend/pyserver.py`, `backend/speed_ser.py`, `requirements.txt`, `backend/requirements.txt`
- **Implementation**:
  - Implemented Fernet symmetric authenticated encryption (`enc:v1:` prefix) using `STUDENT_SYNC_ENCRYPTION_KEY` or `ENCRYPTION_KEY`.
  - Added production guard raising `RuntimeError` in production if the encryption key is not explicitly provided in the environment.
  - Implemented in-memory-only decryption (`get_student_portal_password`) for scraping and authentication verification.
  - Implemented automatic zero-downtime migration (`migrate_student_credentials`) on startup and login for legacy plaintext passwords.

### 3. Chatbot Authorization & IDOR Elimination (SEC-03)
- **Files Modified**: `backend/pyserver.py` (`chatbot_endpoint`)
- **Implementation**:
  - Eliminated unauthenticated fallbacks to `data.get('rollNo')` and `request.headers.get('X-Roll-No')`.
  - Enforced `get_authenticated_student(request)` as the sole source of identity.
  - Blocked cross-student requests with HTTP 403 Forbidden.
  - Returned a safe, generic assistant capabilities message for unauthenticated users without exposing any student data.

### 4. Test Isolation in Planner API (TST-01)
- **Files Modified**: `backend/tests/test_planner_api.py`
- **Implementation**:
  - Created deterministic mock student fixture (`MOCK_STUDENT_25MX232`) with complete course data, exactly 20 entered and 30 pending CA marks, schedule matrix, and exam timetable.
  - Patched `users_collection.find_one`, `update_one`, and `insert_one` to decouple tests completely from live Atlas MongoDB records.

---

## 12. Deployment Blockers & Clearance Verification

| Blocker | Description | Required Clearance Evidence | Post-Remediation Status |
| :--- | :--- | :--- | :---: |
| **Blocker 1: Unauthenticated Password Reset (SEC-01)** | `/api/update` allowed arbitrary password changes without token authentication. | Automated integration test asserting that unauthenticated request returns HTTP 401, cross-student update returns HTTP 403, and valid OTP/token succeeds. | **CLEARED & VERIFIED** (`test_security_remediation_audit.py:1-7` PASS) |
| **Blocker 2: Plaintext Credentials in Database (SEC-02)** | Student passwords were saved in plaintext in MongoDB Atlas. | Code inspection and tests confirming passwords in `new_users` are encrypted using Fernet (`enc:v1:`) before write and decrypted only in memory during scraping. | **CLEARED & VERIFIED** (`crypto_service.py` active; `test_security_remediation_audit.py:8-10` PASS) |
| **Blocker 3: Chatbot Information Leak (SEC-03)** | `/api/chatbot` allowed querying another student's attendance by passing their roll number without a token. | Automated test confirming unauthenticated queries return generic prompt without data leak, and cross-user queries return HTTP 403. | **CLEARED & VERIFIED** (`test_security_remediation_audit.py:11-13` PASS) |
| **Blocker 4: Failing Test in Test Suite (TST-01)** | `test_planner_api.py` failed with `AssertionError: 21 != 20` due to live database mutation. | Full test suite execution returning `Ran 219 tests: OK` (0 failures, 0 errors). | **CLEARED & VERIFIED** (219/219 tests OK in 232.42s) |

---

### Final Pre-Deployment Verdict
**The Student Sync platform has successfully cleared all pre-deployment security and reliability blockers. The core architecture, dual-portal scraping pipelines, credential encryption at rest, account recovery lifecycle, notification deduplication engine, and frontend production build are fully verified and READY FOR CONTROLLED CAMPUS PILOT.**

*Report generated and verified against live workspace codebase, full backend test execution (219/219 OK), and Vite production build.*
