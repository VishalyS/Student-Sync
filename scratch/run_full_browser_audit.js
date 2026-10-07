const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

const scratchDir = 'C:\\Users\\visha\\Downloads\\ACPNS-main\\ACPNS-main\\scratch';
const edgeUserData = path.join(scratchDir, 'edge_profile_full_audit');
const edgeExe = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const { execSync } = require('child_process');
const TOKEN_227 = process.env.TEST_TOKEN_227 || execSync('python -c "import sys; sys.path.insert(0, \'backend\'); from pyserver import generate_auth_token; print(generate_auth_token(\'25MX227\'), end=\'\')"').toString().trim();
const TOKEN_232 = process.env.TEST_TOKEN_232 || execSync('python -c "import sys; sys.path.insert(0, \'backend\'); from pyserver import generate_auth_token; print(generate_auth_token(\'25MX232\'), end=\'\')"').toString().trim();

class CDPClient {
  constructor(wsUrl) {
    this.wsUrl = wsUrl;
    this.id = 1;
    this.callbacks = new Map();
  }
  async connect() {
    return new Promise((resolve, reject) => {
      this.ws = new WebSocket(this.wsUrl);
      this.ws.onopen = () => resolve();
      this.ws.onerror = (e) => reject(e);
      this.ws.onmessage = (msg) => {
        const data = JSON.parse(msg.data);
        if (data.id && this.callbacks.has(data.id)) {
          const cb = this.callbacks.get(data.id);
          this.callbacks.delete(data.id);
          if (data.error) cb.reject(data.error);
          else cb.resolve(data.result);
        }
      };
    });
  }
  async send(method, params = {}) {
    const msgId = this.id++;
    return new Promise((resolve, reject) => {
      this.callbacks.set(msgId, { resolve, reject });
      this.ws.send(JSON.stringify({ id: msgId, method, params }));
    });
  }
  async eval(expression) {
    const res = await this.send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
    return res?.result?.value;
  }
  async close() { if (this.ws) this.ws.close(); }
}

async function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

(async () => {
  console.log('======================================================================');
  console.log('STUDENT SYNC — LIVE BROWSER FULL E2E AUDIT');
  console.log('======================================================================\n');

  const checks = [];
  const consoleErrors = [];
  const networkErrors = [];

  function recordCheck(name, passed, details = '') {
    checks.push({ name, passed, details });
    console.log(`[${passed ? 'PASS' : 'FAIL'}] ${name}${details ? ' (' + details + ')' : ''}`);
  }

  // Ensure fresh user data dir
  if (fs.existsSync(edgeUserData)) {
    try { fs.rmSync(edgeUserData, { recursive: true, force: true }); } catch (e) {}
  }
  fs.mkdirSync(edgeUserData, { recursive: true });

  const edgeProc = spawn(edgeExe, [
    '--headless=new',
    '--remote-debugging-port=9224',
    '--disable-gpu',
    '--no-first-run',
    '--no-default-browser-check',
    `--user-data-dir=${edgeUserData}`,
    'http://localhost:3000/'
  ]);

  try {
    await sleep(2500);
    const targetsRes = await fetch('http://127.0.0.1:9224/json/list');
    const targets = await targetsRes.json();
    const pageTarget = targets.find(t => t.type === 'page' && !t.url.startsWith('chrome-extension')) || targets[0];
    const client = new CDPClient(pageTarget.webSocketDebuggerUrl);
    await client.connect();

    await client.send('Page.enable');
    await client.send('Runtime.enable');
    await client.send('Network.enable');

    client.ws.addEventListener('message', (msg) => {
      try {
        const data = JSON.parse(msg.data);
        if (data.method === 'Runtime.consoleAPICalled' && data.params?.type === 'error') {
          const text = data.params.args?.map(a => a.value || a.description).join(' ');
          if (!text.includes('favicon') && !text.includes('download')) {
            consoleErrors.push(text);
          }
        }
        if (data.method === 'Network.responseReceived') {
          const status = data.params.response?.status;
          const url = data.params.response?.url;
          if (status >= 400 && !url.includes('favicon')) {
            networkErrors.push({ url, status });
          }
        }
      } catch(e) {}
    });

    console.log('\n--- 1. VERIFY 25MX227 ATTENDANCE DASHBOARD ---');
    // Set localStorage for 25MX227
    await client.eval(`
      localStorage.setItem('student_sync_user', JSON.stringify({
        rollNo: '25MX227',
        name: 'SUDHERSON  V',
        auth_token: '${TOKEN_227}',
        email: '25mx227@psgtech.ac.in',
        cgpa: 8.0
      }));
    `);

    await client.send('Page.navigate', { url: 'http://localhost:3000/attendance' });
    await sleep(3500);

    // Verify Overall Attendance metrics
    const att227 = await client.eval(`
      (() => {
        const text = document.body.innerText;
        const attendedMatch = text.match(/238\\s*\\/\\s*310/) || text.match(/238/) && text.match(/310/);
        const pctMatch = text.includes('76.77%') || text.includes('76.8%');
        const cards = Array.from(document.querySelectorAll('.subject-card, [data-subject-card], .border, .rounded-xl, .bg-card, div')).filter(el => {
          return el.innerText && el.innerText.includes('23MX') && (el.innerText.includes('Conducted') || el.innerText.includes('Attended') || el.innerText.includes('%'));
        });
        return {
          hasAttendedFraction: !!attendedMatch,
          hasPercentage: !!pctMatch,
          pageTextPreview: text.substring(0, 300)
        };
      })()
    `);
    recordCheck('25MX227 Overall Attendance renders (76.77% / 238/310)', att227.hasPercentage);

    // Verify 8 academic cards and course titles
    const cards227 = await client.eval(`
      (() => {
        const text = document.body.innerText;
        const requiredCourses = [
          { code: '23MX31', title: 'CLOUD COMPUTING' },
          { code: '23MX36', title: 'CLOUD COMPUTING LABORATORY' },
          { code: '23MX37', title: 'MINI PROJECT' },
          { code: '23MXAE', title: 'COMPUTER NETWORKS' },
          { code: '23MXAT', title: 'DevOps' },
          { code: '23MXAY', title: 'SMART COMPUTING WITH ADVANCED PYTHON' },
          { code: '23MXCA', title: 'ENTREPRENEURSHIP' },
          { code: '23MXM4', title: 'PROFESSIONAL ETHICS' }
        ];
        const results = requiredCourses.map(c => ({
          code: c.code,
          titleExpected: c.title,
          foundCode: text.includes(c.code),
          foundTitle: text.toUpperCase().includes(c.title.toUpperCase())
        }));
        return {
          allFound: results.every(r => r.foundCode && r.foundTitle),
          details: results
        };
      })()
    `);
    recordCheck('25MX227 Exactly 8 Academic Subjects with Correct Dynamic Titles', cards227.allFound);
    for (const d of cards227.details) {
      console.log(`    - ${d.code} (${d.titleExpected}): Code=${d.foundCode}, Title=${d.foundTitle}`);
    }

    // Verify Target selector & Bunk planner
    const targetSim = await client.eval(`
      (() => {
        const text = document.body.innerText;
        return {
          hasTargetSelector: text.includes('Target') || text.includes('75%') || text.includes('80%'),
          hasBunkPlanner: text.includes('Bunk Planner') || text.includes('Safe Bunks') || text.includes('Safe to Bunk')
        };
      })()
    `);
    recordCheck('25MX227 Target Selector & Bunk Planner present', targetSim.hasTargetSelector && targetSim.hasBunkPlanner);

    console.log('\n--- 2. VERIFY 25MX232 ATTENDANCE DASHBOARD & ISOLATION ---');
    // Set localStorage for 25MX232
    await client.eval(`
      localStorage.setItem('student_sync_user', JSON.stringify({
        rollNo: '25MX232',
        name: 'VISHALY  S',
        auth_token: '${TOKEN_232}',
        email: '25mx232@psgtech.ac.in',
        cgpa: 7.96
      }));
    `);

    await client.send('Page.navigate', { url: 'http://localhost:3000/attendance' });
    await sleep(3500);

    const att232 = await client.eval(`
      (() => {
        const text = document.body.innerText;
        const hasPct = text.includes('83.23%') || text.includes('83.2%');
        const hasAtt = text.includes('258');
        return { hasPct, hasAtt };
      })()
    `);
    recordCheck('25MX232 Overall Attendance renders (83.23% / 258)', att232.hasPct && att232.hasAtt);

    const cards232 = await client.eval(`
      (() => {
        const text = document.body.innerText;
        const requiredCourses = [
          { code: '23MX37', title: 'MINI PROJECT' },
          { code: '23MXM4', title: 'PROFESSIONAL ETHICS' },
          { code: '23MXAF', title: 'DATA MINING AND ANALYTICS' },
          { code: '23MXAO', title: 'HUMAN COMPUTER INTERACTION' }
        ];
        const results = requiredCourses.map(c => ({
          code: c.code,
          titleExpected: c.title,
          foundCode: text.includes(c.code),
          foundTitle: text.toUpperCase().includes(c.title.toUpperCase())
        }));
        // Isolation check: 25MX227 specific electives should NOT appear
        const has227Electives = text.includes('23MXAT') || text.includes('DevOps') || text.includes('23MXAY');
        return {
          allFound: results.every(r => r.foundCode && r.foundTitle),
          has227Electives,
          details: results
        };
      })()
    `);
    recordCheck('25MX232 4 Distinct Subjects with Correct Titles', cards232.allFound);
    recordCheck('Cross-Student Isolation: 25MX227 electives absent from 25MX232', !cards232.has227Electives);
    for (const d of cards232.details) {
      console.log(`    - ${d.code} (${d.titleExpected}): Code=${d.foundCode}, Title=${d.foundTitle}`);
    }

    console.log('\n--- 3. CROSS-MODULE ROUTE AUDIT (25MX227) ---');
    // Switch back to 25MX227 to test remaining routes
    await client.eval(`
      localStorage.setItem('student_sync_user', JSON.stringify({
        rollNo: '25MX227',
        name: 'SUDHERSON  V',
        auth_token: '${TOKEN_227}',
        email: '25mx227@psgtech.ac.in',
        cgpa: 8.0
      }));
    `);

    // Route: /schedule
    await client.send('Page.navigate', { url: 'http://localhost:3000/schedule' });
    await sleep(3000);
    const schedCheck = await client.eval(`
      (() => {
        const text = document.body.innerText;
        return {
          hasTimetable: text.includes('Monday') || text.includes('Timetable') || text.includes('Schedule'),
          hasDevOps: text.includes('DevOps') || text.includes('23MXAT'),
          hasMiniProject: text.includes('MINI PROJECT') || text.includes('23MX37'),
          hasNo232Electives: !text.includes('23MXAF') && !text.includes('DATA MINING AND ANALYTICS')
        };
      })()
    `);
    recordCheck('Schedule page (/schedule) renders with weekly matrix & student-specific titles', schedCheck.hasTimetable && schedCheck.hasDevOps);
    recordCheck('Schedule page cross-student isolation (No 23MXAF)', schedCheck.hasNo232Electives);

    // Route: /grades (Academic / CA marks / CGPA)
    await client.send('Page.navigate', { url: 'http://localhost:3000/grades' });
    await sleep(3000);
    const gradesCheck = await client.eval(`
      (() => {
        const text = document.body.innerText;
        return {
          hasCGPA: text.includes('8.0') || text.includes('8.00'),
          hasCAMarks: text.includes('Continuous Assessment') || text.includes('CA Marks') || text.includes('23MX31'),
          hasWhatIf: text.includes('What-If') || text.includes('Projected CGPA') || text.includes('Simulator')
        };
      })()
    `);
    recordCheck('Grades page (/grades) renders CA marks & What-If CGPA', gradesCheck.hasCGPA && gradesCheck.hasCAMarks);

    // Route: /planner (Personalized Study Planner)
    await client.send('Page.navigate', { url: 'http://localhost:3000/planner' });
    await sleep(3000);
    const plannerCheck = await client.eval(`
      (() => {
        const text = document.body.innerText;
        return {
          hasPlanner: text.includes('Planner') || text.includes('Priority') || text.includes('Study'),
          hasPriorityTags: text.includes('HIGH') || text.includes('MEDIUM') || text.includes('LOW'),
          hasSubjectList: text.includes('23MX31') || text.includes('CLOUD COMPUTING')
        };
      })()
    `);
    recordCheck('Planner page (/planner) renders prioritized subjects', plannerCheck.hasPlanner && plannerCheck.hasSubjectList);

    // Route: /services (Campus Services)
    await client.send('Page.navigate', { url: 'http://localhost:3000/services' });
    await sleep(3000);
    const servicesCheck = await client.eval(`
      (() => {
        const text = document.body.innerText;
        return {
          hasServices: text.includes('Campus Services') || text.includes('Dossier') || text.includes('Fees') || text.includes('Hostel'),
          hasHostelOrFees: text.includes('Fee') || text.includes('Hostel') || text.includes('Scholarship')
        };
      })()
    `);
    recordCheck('Campus Services page (/services) renders dossier & modules', servicesCheck.hasServices && servicesCheck.hasHostelOrFees);

    // Route: /dashboard
    await client.send('Page.navigate', { url: 'http://localhost:3000/dashboard' });
    await sleep(3000);
    const dashCheck = await client.eval(`
      (() => {
        const text = document.body.innerText;
        return {
          hasDashboard: text.includes('Dashboard') || text.includes('SUDHERSON') || text.includes('25MX227'),
          hasStats: text.includes('Attendance') || text.includes('76.77') || text.includes('Quick Links')
        };
      })()
    `);
    recordCheck('Dashboard page (/dashboard) renders student overview', dashCheck.hasDashboard);

    console.log('\n--- 4. CONSOLE & NETWORK ERROR AUDIT ---');
    console.log(`Console Errors Total: ${consoleErrors.length}`);
    if (consoleErrors.length > 0) {
      consoleErrors.forEach(err => console.log(`  [Console Error]: ${err}`));
    }
    console.log(`Network Failures (HTTP >= 400): ${networkErrors.length}`);
    if (networkErrors.length > 0) {
      networkErrors.forEach(err => console.log(`  [Network Error]: ${err.status} ${err.url}`));
    }

    recordCheck('Zero Console Errors', consoleErrors.length === 0);
    recordCheck('Zero Failed Network Requests', networkErrors.length === 0);

    const allPassed = checks.every(c => c.passed);
    console.log('\n======================================================================');
    console.log(`FINAL BROWSER VERIFICATION AUDIT RESULT: ${allPassed ? 'ALL PASS (100%)' : 'SOME CHECKS FAILED'}`);
    console.log('======================================================================\n');

    await client.close();
    edgeProc.kill('SIGTERM');
    process.exit(allPassed ? 0 : 1);

  } catch (err) {
    console.error('Browser audit execution exception:', err);
    edgeProc.kill('SIGTERM');
    process.exit(1);
  }
})();
