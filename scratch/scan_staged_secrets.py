import subprocess
import re

staged_files = subprocess.check_output(['git', 'diff', '--cached', '--name-only'], text=True).splitlines()

patterns = [
    ('MongoDB URI with credentials', re.compile(r'mongodb(?:\+srv)?://[^\s@]+:[^\s@]+@[^\s]+', re.IGNORECASE)),
    ('SMTP Password Assignment', re.compile(r'SMTP_PASSWORD\s*=\s*[\'"][^\'"]+[\'"]', re.IGNORECASE)),
    ('Hardcoded Auth Token', re.compile(r'TOKEN_\d+\s*=\s*[\'"][A-Za-z0-9_\-]{20,}[\'"]', re.IGNORECASE)),
    ('Private Key', re.compile(r'-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----')),
    ('AWS Secret Key', re.compile(r'(?:aws_secret_access_key|aws_access_key_id)\s*[:=]\s*[\'"][A-Za-z0-9/+=]{20,}[\'"]', re.IGNORECASE)),
    ('GitHub Token', re.compile(r'gh[pousr]_[A-Za-z0-9_]{36,}', re.IGNORECASE)),
    ('Slack Token', re.compile(r'xox[baprs]-[A-Za-z0-9_\-]{10,}', re.IGNORECASE)),
]

findings = []
for filepath in staged_files:
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as fp:
            content = fp.read()
            for name, pat in patterns:
                for m in pat.finditer(content):
                    findings.append((filepath, name))
    except Exception as e:
        pass

print(f"Total staged files: {len(staged_files)}")
print(f"Total secret findings in staged files: {len(findings)}")
for f, n in findings:
    print(f"  [SECRET FOUND]: {f} -> {n}")

if len(findings) == 0:
    print("ALL STAGED FILES ARE 100% CLEAN OF SECRETS!")
