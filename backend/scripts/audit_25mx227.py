import os
import certifi
import pymongo
from dotenv import load_dotenv
from bs4 import BeautifulSoup

load_dotenv('backend/.env')
client = pymongo.MongoClient(os.getenv('MONGO_URI'), tlsCAFile=certifi.where())
db = client['ecampus']

user = db.new_users.find_one({'rollNo': '25MX227'})
if not user:
    print('User 25MX227 NOT FOUND in new_users!')
    exit(1)

print('User 25MX227 found!')
print('Name in DB:', user.get('name'))
print('Email in DB:', user.get('email'))

sz1 = user.get('studzone1', {})
pa = sz1.get('parsed_attendance', [])
print('\n--- MONGODB parsed_attendance for 25MX227 ---')
for item in pa:
    print(f"Code: {item.get('code')} | Name: {item.get('name')} | Attended: {item.get('attended')}/{item.get('total_classes')} ({item.get('percentage')})")

pm = sz1.get('parsed_marks', [])
print('\n--- MONGODB parsed_marks (from CA marks) for 25MX227 ---')
for item in pm:
    print(f"Code: {item.get('code')} | Name: {item.get('name')}")

att_html = sz1.get('attendance_html', '')
print('\n--- RAW attendance_html analysis for 25MX227 ---')
if att_html:
    soup = BeautifulSoup(att_html, 'html.parser')
    for tr in soup.find_all('tr'):
        cells = [td.get_text(strip=True) for td in tr.find_all(['th', 'td'])]
        print('  HTML row:', cells)
else:
    print('  No attendance_html found in DB!')

ca_html = sz1.get('ca_marks_html', '')
print('\n--- RAW ca_marks_html analysis for 25MX227 ---')
if ca_html:
    soup = BeautifulSoup(ca_html, 'html.parser')
    for tr in soup.find_all('tr'):
        cells = [td.get_text(strip=True) for td in tr.find_all(['th', 'td'])]
        if cells and len(cells) >= 2:
            print('  CA HTML row:', cells[:3])

print('\n--- GLOBAL subjects COLLECTION ---')
sub_col = db['subjects']
print('Total documents in subjects:', sub_col.count_documents({}))
for doc in sub_col.find({}):
    # print keys and values
    clean_doc = {k: v for k, v in doc.items() if k != '_id'}
    print(' ', clean_doc)
