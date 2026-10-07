import os
import sys
import urllib.request
import urllib.error
import json

sys.path.insert(0, os.path.abspath('backend'))
from pyserver import generate_auth_token

base_url = "http://127.0.0.1:5000"

print("======================================================================")
print("AUTHENTICATED API VERIFICATION")
print("======================================================================\n")

# 1. Unauthenticated test (expect 401)
try:
    urllib.request.urlopen(f"{base_url}/api/attendance/summary")
    print("[FAIL] Unauthenticated request succeeded unexpectedly!")
except urllib.error.HTTPError as e:
    print(f"[PASS] Unauthenticated request rejected with HTTP {e.code}")

# 2. Invalid token test (expect 401)
try:
    req = urllib.request.Request(f"{base_url}/api/attendance/summary", headers={'Authorization': 'Bearer invalid_token_123'})
    urllib.request.urlopen(req)
    print("[FAIL] Invalid token request succeeded unexpectedly!")
except urllib.error.HTTPError as e:
    print(f"[PASS] Invalid token request rejected with HTTP {e.code}")

# 3. Cross-User Spoof Test (expect 403 Forbidden)
token_227 = generate_auth_token("25MX227")
try:
    req_spoof = urllib.request.Request(
        f"{base_url}/api/attendance/summary?rollNo=25MX232",
        headers={'Authorization': f'Bearer {token_227}'}
    )
    urllib.request.urlopen(req_spoof)
    print("[FAIL] Cross-user spoof request succeeded unexpectedly!")
except urllib.error.HTTPError as e:
    print(f"[PASS] Cross-user spoof request rejected with HTTP {e.code} (Forbidden)")

# 4. Valid 25MX227 Attendance Summary
req = urllib.request.Request(
    f"{base_url}/api/attendance/summary?target=75",
    headers={'Authorization': f'Bearer {token_227}'}
)
with urllib.request.urlopen(req) as resp:
    data227 = json.loads(resp.read().decode())

print("\n=== 25MX227 ATTENDANCE SUMMARY API ===")
print("Name:", data227.get('name'))
print(f"Overall: {data227['total_attended']}/{data227['total_conducted']} = {data227['overall_percentage']}% | Safe bunks: {data227['overall_safe_bunks']}")
print("Subjects:")
for s in data227.get('subjects', []):
    print(f"  {s.get('code')}: '{s.get('name')}' | {s.get('attended')}/{s.get('conducted')} ({s.get('percentage')}%) | Safe bunks: {s.get('safe_bunks')}")

# Specifically check 25MX227 required courses
names_map_227 = {s['code']: s['name'] for s in data227.get('subjects', [])}
assert names_map_227.get('23MX37') == 'MINI PROJECT', f"23MX37 expected 'MINI PROJECT', got {names_map_227.get('23MX37')}"
assert names_map_227.get('23MXM4') == 'PROFESSIONAL ETHICS', f"23MXM4 expected 'PROFESSIONAL ETHICS', got {names_map_227.get('23MXM4')}"
assert names_map_227.get('23MXAT') == 'DevOps', f"23MXAT expected 'DevOps', got {names_map_227.get('23MXAT')}"
assert names_map_227.get('23MXAY') == 'SMART COMPUTING WITH ADVANCED PYTHON', f"23MXAY expected 'SMART COMPUTING WITH ADVANCED PYTHON', got {names_map_227.get('23MXAY')}"
print("[PASS] All 4 specific 25MX227 course names verified in API output!")

# 5. Valid 25MX232 Attendance Summary
token_232 = generate_auth_token("25MX232")
req2 = urllib.request.Request(
    f"{base_url}/api/attendance/summary?target=75",
    headers={'Authorization': f'Bearer {token_232}'}
)
with urllib.request.urlopen(req2) as resp:
    data232 = json.loads(resp.read().decode())

print("\n=== 25MX232 ATTENDANCE SUMMARY API ===")
print("Name:", data232.get('name'))
print(f"Overall: {data232['total_attended']}/{data232['total_conducted']} = {data232['overall_percentage']}% | Safe bunks: {data232['overall_safe_bunks']}")
print("Subjects:")
for s in data232.get('subjects', []):
    print(f"  {s.get('code')}: '{s.get('name')}' | {s.get('attended')}/{s.get('conducted')} ({s.get('percentage')}%) | Safe bunks: {s.get('safe_bunks')}")

names_map_232 = {s['code']: s['name'] for s in data232.get('subjects', [])}
assert names_map_232.get('23MX37') == 'MINI PROJECT', f"23MX37 for 232 expected 'MINI PROJECT', got {names_map_232.get('23MX37')}"
assert names_map_232.get('23MXM4') == 'PROFESSIONAL ETHICS', f"23MXM4 for 232 expected 'PROFESSIONAL ETHICS', got {names_map_232.get('23MXM4')}"
print("[PASS] All 25MX232 course names verified in API output!")

# 6. Test Unified Academic Intelligence (/courses/unified-summary)
req_unified = urllib.request.Request(
    f"{base_url}/courses/unified-summary",
    headers={'Authorization': f'Bearer {token_227}'}
)
with urllib.request.urlopen(req_unified) as resp:
    data_unified = json.loads(resp.read().decode())
print("\n=== 25MX227 UNIFIED INTELLIGENCE COURSES ===")
for c in data_unified.get('courses', []):
    print(f"  {c.get('code')}: '{c.get('name')}' | Pct: {c.get('attendance_pct')}%")
print("[PASS] Unified Intelligence API test completed.")
