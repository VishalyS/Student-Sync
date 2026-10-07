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
notifs = db['notifications_log']

# 1. Backfill description and message for all existing notification docs
for doc in notifs.find({}):
    desc = doc.get('description')
    msg = doc.get('message')
    subj = doc.get('subject')
    
    if not desc and msg:
        notifs.update_one({'_id': doc['_id']}, {'$set': {'description': msg}})
    elif not desc and subj:
        clean = subj.replace('Student Sync — ', '').replace('Student Sync: ', '').strip()
        notifs.update_one({'_id': doc['_id']}, {'$set': {'description': clean, 'title': clean, 'message': clean}})

# 2. Delete any leftover blank rows where neither description nor message exists
notifs.delete_many({
    '$and': [
        {'$or': [{'description': {'$exists': False}}, {'description': ''}, {'description': None}]},
        {'$or': [{'message': {'$exists': False}}, {'message': ''}, {'message': None}]}
    ]
})

remaining = list(notifs.find({}))
print(f'Cleaned & backfilled! Remaining notifications in MongoDB: {len(remaining)}')
for idx, n in enumerate(remaining):
    src = n.get('source', 'Student Sync')
    cat = n.get('category', n.get('type', 'general'))
    title = n.get('title', '')
    desc = n.get('description', '')
    print(f'[{idx+1}] [{src}] ({cat}) {title}: {desc}')
