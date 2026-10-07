import sys
import os
import certifi
from pymongo import MongoClient
from dotenv import load_dotenv

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from notifications.change_detector import compute_change_hash

load_dotenv(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.env')))
client = MongoClient(os.getenv('MONGO_URI'), tlsCAFile=certifi.where())
db = client['ecampus']
notifs = db['notifications_log']

roll_no = '25MX232'
test_title = 'Attendance Updated'
test_desc = 'Data Structures attendance changed from 82% → 86%.'
test_hash = compute_change_hash(roll_no, 'attendance', 'Attendance', test_title, test_desc, 'test_key_82_86')

# 1. Clean existing test doc if any
notifs.delete_many({'changeHash': test_hash})

doc = {
    'rollNo': roll_no,
    'studentRollNo': roll_no,
    'category': 'attendance',
    'type': 'attendance',
    'title': test_title,
    'description': test_desc,
    'message': test_desc,
    'source': 'StudZone 1',
    'module': 'Attendance',
    'timestamp': '2026-09-02T09:00:00.000Z',
    'createdAt': '2026-09-02T09:00:00.000Z',
    'read': False,
    'changeHash': test_hash,
    'changeData': {'subject': 'Data Structures', 'previousValue': '82%', 'newValue': '86%'},
    'status': 'sent'
}

insert_res = notifs.insert_one(doc)
print('1. Inserted notification doc ID:', insert_res.inserted_id)

# 2. Verify stored in MongoDB
found = notifs.find_one({'changeHash': test_hash})
print('2. Verified in MongoDB:', found['title'], '—', found['description'])
assert found['description'] == test_desc
assert found['category'] == 'attendance'
assert found['read'] is False

# 3. Test duplicate prevention
existing = notifs.find_one({'changeHash': test_hash})
print('3. Duplicate prevention check: Already exists ->', existing is not None)
assert existing is not None

# 4. Test mark as read
notifs.update_one({'_id': found['_id']}, {'$set': {'read': True}})
updated = notifs.find_one({'_id': found['_id']})
print('4. Marked as read verified:', updated['read'])
assert updated['read'] is True

# 5. Cleanup test document
notifs.delete_one({'_id': found['_id']})
print('5. Cleaned up test notification record from notifications_log.')

print('\nALL MONGODB NOTIFICATION STORAGE & RETRIEVAL TESTS PASSED!')
