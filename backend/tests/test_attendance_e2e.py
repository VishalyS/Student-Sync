import os
import sys
import json
import pytest
from datetime import datetime
from dotenv import load_dotenv

# Ensure backend path is on sys.path
_current_dir = os.path.dirname(os.path.abspath(__file__))
_backend_dir = os.path.dirname(_current_dir)
_parent_dir = os.path.dirname(_backend_dir)
for p in [_parent_dir, _backend_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)

load_dotenv(os.path.join(_backend_dir, '.env'))

from backend.pyserver import app, db, users_collection, generate_auth_token, verify_auth_token


@pytest.fixture(scope="module")
def client():
    """Flask test client for end-to-end integration testing."""
    app.config['TESTING'] = True
    with app.test_client() as test_client:
        yield test_client


class TestAttendanceEndToEnd:
    """
    Complete End-to-End Test Suite for Student Sync Attendance & Bunk Planner.
    Verifies authentication, authorization, live summary, dynamic target recalculations,
    in-memory simulation, and zero MongoDB writes.
    """

    @classmethod
    def setup_class(cls):
        """Read-only test setup targeting existing 25MX232 student context."""
        cls.roll_no = "25MX232"
        cls.other_roll_no = "25MX227"
        
        # Verify student exists in MongoDB
        assert users_collection is not None, "MongoDB users collection unavailable"
        user = users_collection.find_one({"rollNo": cls.roll_no})
        assert user is not None, f"Student {cls.roll_no} must exist in MongoDB"
        cls.password = user.get("password", "120405")
        
        # Generate authenticated token
        cls.auth_token = generate_auth_token(cls.roll_no)
        assert cls.auth_token is not None
        cls.auth_headers = {
            "Authorization": f"Bearer {cls.auth_token}",
            "Content-Type": "application/json"
        }

    # =========================================================================
    # A. AUTHENTICATION FLOW
    # =========================================================================

    def test_01_login_authenticates_and_generates_token(self, client):
        """
        Verify that login with valid 25MX232 credentials authenticates successfully
        and returns a signed HMAC auth_token without breaking existing login contracts.
        """
        login_res = client.post(
            "/login",
            data=json.dumps({"rollNo": self.roll_no, "password": self.password}),
            content_type="application/json"
        )
        assert login_res.status_code == 200
        data = login_res.get_json()
        assert data.get("rollNo") == self.roll_no
        assert "auth_token" in data
        assert data["auth_token"] is not None
        assert len(data["auth_token"]) > 30

        # Verify HMAC token validity
        verified_roll = verify_auth_token(data["auth_token"])
        assert verified_roll == self.roll_no

    def test_02_unauthenticated_request_rejected(self, client):
        """
        Verify that requesting attendance summary without authentication returns HTTP 401.
        """
        res = client.get("/api/attendance/summary")
        assert res.status_code == 401
        data = res.get_json()
        assert "error" in data
        assert "Authentication required" in data["error"]

    # =========================================================================
    # B. AUTHORIZATION & USER ISOLATION
    # =========================================================================

    def test_03_authenticated_student_accesses_own_records(self, client):
        """
        Verify that 25MX232 can access its own attendance records via Bearer token.
        """
        res = client.get("/api/attendance/summary", headers=self.auth_headers)
        assert res.status_code == 200
        data = res.get_json()
        assert data.get("rollNo") == self.roll_no
        assert data.get("name") is not None
        assert "overall_percentage" in data

    def test_04_cross_user_access_attempt_forbidden(self, client):
        """
        Verify that a token belonging to 25MX232 attempting to access 25MX227's data
        is detected as an unauthorized cross-user attempt and rejected with HTTP 403.
        """
        res = client.get(
            f"/api/attendance/summary?rollNo={self.other_roll_no}",
            headers=self.auth_headers
        )
        assert res.status_code == 403
        data = res.get_json()
        assert "Cross-user access denied" in data.get("error", "")

    # =========================================================================
    # C. ATTENDANCE SUMMARY (TARGET = 75.0%)
    # =========================================================================

    def test_05_attendance_summary_matches_production_baseline(self, client):
        """
        Verify that target=75 returns exact consolidated attendance metrics:
        258 attended, 310 conducted, 83.23%, status SAFE, safe bunks 34.
        """
        res = client.get("/api/attendance/summary?target=75.0", headers=self.auth_headers)
        assert res.status_code == 200
        data = res.get_json()

        assert data["total_attended"] == 258
        assert data["total_conducted"] == 310
        assert data["overall_percentage"] == 83.23
        assert data["overall_status"] == "SAFE"
        assert data["overall_safe_bunks"] == 34
        assert data["overall_required_classes"] == 0
        assert data["target"] == 75.0

        # Verify subject list
        subjects = data.get("subjects", [])
        assert len(subjects) == 8
        for subj in subjects:
            assert "code" in subj
            assert "name" in subj
            assert "attended" in subj
            assert "conducted" in subj
            assert "percentage" in subj
            assert "status" in subj
            assert "safe_bunks" in subj
            assert "required_classes" in subj

    # =========================================================================
    # D. DYNAMIC TARGET THRESHOLDS & SCHEDULE
    # =========================================================================

    def test_06_dynamic_target_recalculation(self, client):
        """
        Verify that varying the target threshold (75%, 80%, 85%, 90%)
        recalculates safe bunks and recovery requirements accurately without DB writes.
        """
        # Target 75%
        res75 = client.get("/api/attendance/summary?target=75.0", headers=self.auth_headers)
        d75 = res75.get_json()
        assert d75["overall_safe_bunks"] == 34
        assert d75["overall_required_classes"] == 0

        # Target 80%
        # floor((258 - 0.80 * 310) / 0.80) = floor((258 - 248) / 0.80) = floor(10 / 0.80) = 12
        res80 = client.get("/api/attendance/summary?target=80.0", headers=self.auth_headers)
        d80 = res80.get_json()
        assert d80["overall_safe_bunks"] == 12
        assert d80["overall_required_classes"] == 0

        # Target 85%
        # 83.23% < 85.0% -> safe_bunks = 0, recovery = ceil((0.85 * 310 - 258) / 0.15) = ceil(5.5 / 0.15) = 37
        res85 = client.get("/api/attendance/summary?target=85.0", headers=self.auth_headers)
        d85 = res85.get_json()
        assert d85["overall_safe_bunks"] == 0
        assert d85["overall_required_classes"] == 37

        # Target 90%
        # 83.23% < 90.0% -> safe_bunks = 0, recovery = ceil((0.90 * 310 - 258) / 0.10) = ceil(21 / 0.10) = 210
        res90 = client.get("/api/attendance/summary?target=90.0", headers=self.auth_headers)
        d90 = res90.get_json()
        assert d90["overall_safe_bunks"] == 0
        assert d90["overall_required_classes"] == 210

    def test_07_today_schedule_matrix_integrity(self, client):
        """
        Verify that today_schedule is extracted dynamically for the current weekday,
        entries contain valid period/time/course information, and no malformed rows exist.
        Does NOT hardcode a specific weekday, course count, or course title.
        """
        res = client.get("/api/attendance/summary", headers=self.auth_headers)
        assert res.status_code == 200
        data = res.get_json()

        today_sched = data.get("today_schedule")
        assert today_sched is not None, "today_schedule must be present in response"
        assert isinstance(today_sched, dict), "today_schedule must be a dictionary"

        # Verify weekday correspondence
        current_day_name = datetime.now().strftime("%A")
        assert today_sched.get("day") == current_day_name, (
            f"Schedule day '{today_sched.get('day')}' must match current weekday '{current_day_name}'"
        )

        # Verify class entries structure
        classes = today_sched.get("classes", [])
        assert isinstance(classes, list), "classes must be a list"
        
        # If classes are scheduled for current weekday, validate each slot's integrity
        for slot in classes:
            assert isinstance(slot, dict)
            assert "period" in slot
            assert "time" in slot
            assert "code" in slot
            assert "name" in slot
            assert "is_free" in slot
            # Ensure time and period are non-empty strings/ints
            assert slot["period"] is not None
            assert len(str(slot["time"]).strip()) > 0

    # =========================================================================
    # E & F. IN-MEMORY SIMULATION & STRICT DATABASE ISOLATION
    # =========================================================================

    def test_08_simulation_accuracy_and_zero_mongodb_writes(self, client):
        """
        Verify simulation for subject 23MX31:
        Inputs: additional_attended = 2, additional_bunked = 1, target = 75.0.
        Expected:
          simulated_attended = 30
          simulated_conducted = 40
          simulated_percentage = 75.00%
          difference = -0.68%
          simulated_status = SAFE
          safe_bunks = 0
        Strict isolation:
          Verify MongoDB attendance values for 25MX232 before and after are 100% identical.
        """
        # Step 1: Capture MongoDB values BEFORE simulation
        user_before = users_collection.find_one({"rollNo": self.roll_no})
        assert user_before is not None
        courses_before = user_before.get("studzone1", {}).get("parsed_attendance", [])
        orig_23mx31_db = next((c for c in courses_before if c.get("code") == "23MX31"), None)
        assert orig_23mx31_db is not None
        db_att_before = int(orig_23mx31_db.get("attended", 0))
        db_cond_before = int(orig_23mx31_db.get("total_classes", orig_23mx31_db.get("conducted", 0)))
        db_pct_before = float(orig_23mx31_db.get("percentage_num", 76.0))
        total_users_before = users_collection.count_documents({})

        # Step 2: Run simulation POST request
        sim_payload = {
            "subject_code": "23MX31",
            "additional_attended": 2,
            "additional_bunked": 1,
            "target": 75.0
        }
        sim_res = client.post(
            "/api/attendance/simulate",
            data=json.dumps(sim_payload),
            headers=self.auth_headers
        )
        assert sim_res.status_code == 200
        sim_data = sim_res.get_json()

        # Step 3: Validate exact mathematical simulation results
        assert sim_data["subject_code"] == "23MX31"
        assert sim_data["simulated_attended"] == 30
        assert sim_data["simulated_conducted"] == 40
        assert sim_data["simulated_percentage"] == 75.00
        assert sim_data["simulated"]["percentage_change"] == -0.68
        assert sim_data["simulated_status"] == "SAFE"
        assert sim_data["simulated_safe_bunks"] == 0

        # Step 4: Verify MongoDB state AFTER simulation is strictly unchanged
        user_after = users_collection.find_one({"rollNo": self.roll_no})
        assert user_after is not None
        courses_after = user_after.get("studzone1", {}).get("parsed_attendance", [])
        orig_23mx31_after = next((c for c in courses_after if c.get("code") == "23MX31"), None)
        assert orig_23mx31_after is not None
        db_att_after = int(orig_23mx31_after.get("attended", 0))
        db_cond_after = int(orig_23mx31_after.get("total_classes", orig_23mx31_after.get("conducted", 0)))
        db_pct_after = float(orig_23mx31_after.get("percentage_num", 76.0))
        total_users_after = users_collection.count_documents({})

        # Zero DB write assertions
        assert total_users_before == total_users_after == 5
        assert db_att_before == db_att_after == 28, "Database attended hours must not change!"
        assert db_cond_before == db_cond_after == 37, "Database conducted hours must not change!"
        assert db_pct_before == db_pct_after, "Database percentage must not change!"
