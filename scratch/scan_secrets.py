import os
import re

patterns = [
    ('MongoDB URI with credentials', re.compile(r'mongodb(?:\+srv)?://[^\s@]+:[^\s@]+@[^\s]+', re.IGNORECASE)),
    ('SMTP Password Assignment', re.compile(r'SMTP_PASSWORD\s*=\s*[\'"][^\'"]+[\'"]', re.IGNORECASE)),
    ('Hardcoded Auth Token', re.compile(r'TOKEN_\d+\s*=\s*[\'"][A-Za-z0-9_\-]{20,}[\'"]', re.IGNORECASE)),
    ('Private Key', re.compile(r'-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----')),
    ('AWS Secret Key', re.compile(r'(?:aws_secret_access_key|aws_access_key_id)\s*[:=]\s*[\'"][A-Za-z0-9/+=]{20,}[\'"]', re.IGNORECASE)),
    ('GitHub Token', re.compile(r'gh[pousr]_[A-Za-z0-9_]{36,}', re.IGNORECASE)),
    ('Slack Token', re.compile(r'xox[baprs]-[A-Za-z0-9_\-]{10,}', re.IGNORECASE)),
    ('Generic Secret Assignment', re.compile(r'(?:api_key|secret_key|app_secret)\s*[:=]\s*[\'"][A-Za-z0-9_\-]{20,}[\'"]', re.IGNORECASE)),
]

ignore_dirs = {'.git', 'node_modules', '.venv', 'venv', '__pycache__', '.pytest_cache', 'dist'}

results = []
for root, dirs, files in os.walk('.'):
    # filter out edge profile directories and ignore dirs
    dirs[:] = [d for d in dirs if d not in ignore_dirs and not d.startswith('edge_')]
    for f in files:
        if f.endswith(('.pyc', '.png', '.jpg', '.ico', '.pma', '.dat', '.log')):
            continue
        rel_path = os.path.normpath(os.path.join(root, f))
        try:
            with open(rel_path, 'r', encoding='utf-8', errors='ignore') as fp:
                content = fp.read()
                for name, pat in patterns:
                    for m in pat.finditer(content):
                        # skip if inside .env file (which will be gitignored)
                        results.append((rel_path, name, m.group(0)[:15] + "..."))
        except Exception as e:
            pass

print(f"Total secret pattern matches: {len(results)}")
for path, name, preview in results:
    print(f"  {path}: {name} (preview: {preview})")
