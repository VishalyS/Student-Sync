# STUDENT SYNC — HOSTEL
# FRONTEND UI QA & REAL-BROWSER VALIDATION REPORT

## 1. Status

READY

## 2. Browser Tested

- **Browser**: Microsoft Edge (Chromium Engine)
- **Executable**: `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`
- **Automation Protocol**: Chrome DevTools Protocol (CDP) via `puppeteer-core`
- **Engine Version**: Chromium 131+ (Win64)

## 3. Routes Tested

- `/hostel` (Direct residency URL)
- `/login` (Unauthenticated redirection target)
- `/dashboard` (Navbar tab transition target)
- `/` (Home page regression verification)
- `/about` (Static page regression verification)

## 4. UI Sections Tested

1. **Header Banner**:
   - Title: "Hostel & Accommodation Hub"
   - Identity: Roll number badge (`25MX232`)
   - Status badge: "Hostel Allotted" (Resident) / "Day Scholar / Unallocated"
   - Actions: "Refresh Records" with synchronization spinner
2. **Hostel & Room Allotment**:
   - Room specification: "FOUR SHARING"
   - Hostel facility: "BOYS HOSTEL 1"
   - Block & Room: "B BLOCK — Room 108"
   - Floor location: "FIRST FLOOR"
   - Date of Joining: "2025-08-14"
   - Warden oversight: "WARDEN NAME"
   - Resident Tutor: "TUTOR NAME"
3. **Mess & Dining Services**:
   - Diet category: "NON-VEG"
   - Allotted mess: "A MESS - SOUTH INDIAN"
   - Mess supervisor: "SUPERVISOR NAME"
   - Member since: "2025-08-14"
   - Token authorizations: "Egg Token: ACTIVE", "Non-Veg: 0"
4. **Fee Ledger & Dues**:
   - Fee Balance Due: `₹ 1500.00`
   - Caution Deposit: `₹ 5000.00`
   - Establishment Fee: `₹ 12000.00`
   - Mess Token Balance: `₹ 0.00`
5. **Leave & Outpass Register**:
   - Leave types & quotas: "CASUAL LEAVE — 10 days"
   - Approval authority: "DR. FACULTY — ID: STF001"
   - Application history: "No past leave applications submitted"
6. **Resident Student Dossier**:
   - Full name, roll number, degree roll, programme & class (`M.C.A. (REGULAR) (MCA-I)`)
   - Contact mobile, parent contact, registered student email
7. **Academic Fee Cycle**:
   - Cycle year: `2025-2026` (`₹75000`)
8. **Loading State**:
   - Verified centered loading spinner with status notice ("Querying PSG Hostel Portal records...")
   - Smooth transition upon API fulfillment without content flashing
9. **Error State**:
   - Verified non-intrusive alert banner with explicit non-technical message
   - Verified active "Retry" button
10. **Day Scholar / Empty State**:
    - Verified clean "No Active Hostel Allotment" empty state with explanation for non-residents
    - Verified "Check Again" button and zero broken cards

## 5. Responsive Testing

| Viewport Name | Dimensions | Layout / Stacking | Horizontal Overflow | Result |
| :--- | :--- | :--- | :--- | :--- |
| **Desktop** | 1920 × 1080 | 3-column grid, persistent sidebar dossier | None (`scrollWidth <= innerWidth`) | **PASS** |
| **Laptop** | 1366 × 768 | 3-column grid, responsive header | None (`scrollWidth <= innerWidth`) | **PASS** |
| **Tablet** | 768 × 1024 | 2-column stacked layout | None (`scrollWidth <= innerWidth`) | **PASS** |
| **Mobile** | 390 × 844 | Single-column cards stack, mobile nav | None (`scrollWidth <= innerWidth`) | **PASS** |

## 6. API Integration

- **Endpoints Called**:
  - `GET /api/v1/hostel/student/<rollno>?auth_token=...`
  - Proxied seamlessly through Vite dev server (`http://localhost:5173/api/...`) to Flask backend (`http://127.0.0.1:5000`)
- **Request Frequency**: Exactly 1 request per page load. Zero infinite loops, zero duplicate request bursts.
- **Refresh Mechanism**: Manual "Refresh Records" button passes `&refresh=true` and synchronizes in place.

## 7. Console

- **Runtime Page Errors**: 0 uncaught exceptions, 0 React hydration failures, 0 rendering crashes.
- **Console Log Hygiene**: Zero developer debug objects (`undefined`, `null`, `NaN`, `[object Object]`, or raw JSON) leaked into the DOM.
- **Handled HTTP Responses**: 401 response codes triggered exclusively during intentional unauthenticated and invalid-token security tests.

## 8. Security

- **Credentials Exposure**: Zero plain passwords, zero secret keys, zero raw authorization headers rendered.
- **Session Tokens**: Bearer tokens are kept in scoped storage and never injected into DOM text nodes or visible badges.
- **Session Cookies**: External ASP.NET Core session cookies are retained in memory only and never exposed to the frontend.
- **Environment**: `.env` is confirmed ignored by git in both workspace repositories.

## 9. Fixes Made

1. **Vite Proxy Route Aliases**: Configured `pyserver.py` route decorators to accept both prefixed (`/api/v1/hostel/...`) and Vite-proxy-rewritten (`/v1/hostel/...`) paths to prevent 404 routing errors through the dev server proxy.
2. **Dev Server Port Alignment**: Configured `react-spd/vite.config.js` to run on `port: 5173` with `http://127.0.0.1:5000` proxy target matching application specifications.
3. **Puppeteer Edge Driver Harness**: Integrated lightweight `puppeteer-core` driving local Microsoft Edge (`msedge.exe`) over CDP to enable automated real-browser testing without relying on cloud Playwright downloads.

## 10. Automated Regression

- **Standalone Hostel Tests**: `166 passed` in 1.17s
- **Hostel Backend Integration Tests**: `9 passed` in 9.95s
- **Existing Academic Baseline (Home, Login, About)**: `ALL PASSED`
- **Frontend Production Build**: `✓ built in 2.48s` (0 compile errors)

## 11. Remaining Issues

NONE
