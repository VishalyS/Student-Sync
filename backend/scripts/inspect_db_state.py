import os
import sys
import certifi
from pymongo import MongoClient
from dotenv import load_dotenv

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

load_dotenv(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.env')))
client = MongoClient(os.getenv('MONGO_URI'), tlsCAFile=certifi.where())
db = client['ecampus']

print("======================================================================")
print("MONGODB CURRENT STATE AUDIT")
print("======================================================================\n")

users = list(db['new_users'].find({}))
print(f"1. [Total Students in new_users]: {len(users)}")
for u in users:
    r = u.get('rollNo')
    name = u.get('name')
    email = u.get('email')
    cgpa = u.get('cgpa')
    synced = u.get('lastSyncedAt')
    print(f"   - Roll: {r} | Name: {name} | Email: {email} | CGPA: {cgpa} | Synced: {synced}")

print(f"\n2. [Total Records in notifications_log]: {db['notifications_log'].count_documents({})}")
notifs = list(db['notifications_log'].find({}))
for idx, n in enumerate(notifs):
    src = n.get('source')
    cat = n.get('category') or n.get('type')
    r = n.get('rollNo')
    title = n.get('title')
    status = n.get('status')
    chash = n.get('changeHash', '')
    recip = n.get('recipient_email') or n.get('changeData', {}).get('studentEmail') or n.get('changeData', {}).get('adminEmail')
    print(f"   [{idx+1}] [{src}] ({cat}) {r}: {title} | Status: {status} | Recipient: {recip} | Hash: {chash[:16]}...")
