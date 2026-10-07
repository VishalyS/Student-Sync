import os
import json
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv('backend/.env')
uri = os.environ.get('MONGO_URI')
client = MongoClient(uri)
db = client['ecampus']

users = list(db.new_users.find({}))
for u in users:
    roll = u.get('rollNo')
    name = u.get('name')
    print(f"\n==================== USER: {roll} ({name}) ====================")
    for k in ['rollNo', 'name', 'cgpa', 'email', 'attendance', 'marks', 'timetable', 'attendance_table', 'fees', 'hostel', 'scholarships', 'feedback']:
        v = u.get(k)
        val_type = type(v).__name__
        if isinstance(v, str):
            preview = v[:100] + "..." if len(v) > 100 else v
        elif isinstance(v, (list, dict)):
            preview = f"len={len(v)}: " + json.dumps(v, default=str)[:100]
        else:
            preview = str(v)
        print(f"  {k} ({val_type}): {preview}")
