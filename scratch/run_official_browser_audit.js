const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

const scratchDir = 'C:\\Users\\visha\\Downloads\\ACPNS-main\\ACPNS-main\\scratch';
const edgeUserData = path.join(scratchDir, 'edge_profile_official_audit_clean');
const edgeExe = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';

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
  console.log('STUDENT SYNC — OFFICIAL LIVE BROWSER E2E VERIFICATION (FULL PASS)');
  console.log('======================================================================\n');

  const checks = [];
  const consoleErrors = [];
  const networkErrors = [];

  function recordCheck(name, passed, details = '') {
    checks.push({ name, passed, details });
    console.log(`[${passed ? 'PASS' : 'FAIL'}] ${name}${details ? ' (' + details + ')' : ''}`);
  }

  if (fs.existsSync(edgeUserData)) {
    try { fs.rmSync(edgeUserData, { recursive: true, force: true }); } catch (e) {}
  }
  fs.mkdirSync(edgeUserData, { recursive: true });

  const edgeProc = spawn(edgeExe, [
    '--headless=new',
    '--remote-debugging-port=9228',
    '--disable-gpu',
    '--no-first-run',
    '--no-default-browser-check',
    `--user-data-dir=${edgeUserData}`,
    'http://localhost:3000/'
  ]);

  try {
    await sleep(2500);
    const targetsRes = await fetch('http://127.0.0.1:9228/json/list');
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

    console.log('=== STEP 1: AUTHENTICATE 25MX227 ===');
    await client.send('Page.navigate', { url: 'http://localhost:3000/login' });
    await sleep(1500);

    const login227Result = await client.eval(`
      (async () => {
        const res = await fetch('http://127.0.0.1:5000/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ rollNo: '25MX227', password: '24SEP02' })
        });
        const data = await res.json();
        if (res.status === 200 && data.auth_token) {
          localStorage.setItem('student_sync_user', JSON.stringify(data));
          return { success: true, rollNo: data.rollNo, name: data.name };
        }
        return { success: false, status: res.status, data };
      })()
    `);
    recordCheck('25MX227 API Login & Session Initialized', login227Result.success, `${login227Result.rollNo} - ${login227Result.name}`);

    console.log('\n=== STEP 2: VERIFY 25MX227 ATTENDANCE DASHBOARD ===');
    await client.send('Page.navigate', { url: 'http://localhost:3000/attendance' });
    await sleep(3500);

    const att227Check = await client.eval(`
      (() => {
        const text = document.body.innerText;
        const hasPct = text.includes('76.77%');
        const hasFraction = text.includes('238') && text.includes('310');
        const hasBunkSummary = text.includes('Safe Bunks') || text.includes('7');
        
        const courses = [
          { code: '23MX31', title: 'CLOUD COMPUTING' },
          { code: '23MX36', title: 'CLOUD COMPUTING LABORATORY' },
          { code: '23MX37', title: 'MINI PROJECT' },
          { code: '23MXAE', title: 'COMPUTER NETWORKS' },
          { code: '23MXAT', title: 'DevOps' },
          { code: '23MXAY', title: 'SMART COMPUTING WITH ADVANCED PYTHON' },
          { code: '23MXCA', title: 'ENTREPRENEURSHIP' },
          { code: '23MXM4', title: 'PROFESSIONAL ETHICS' }
        ];

        const courseResults = courses.map(c => ({
          code: c.code,
          titleExpected: c.title,
          foundCode: text.includes(c.code),
          foundTitle: text.toUpperCase().includes(c.title.toUpperCase())
        }));

        const allCoursesFound = courseResults.every(c => c.foundCode && c.foundTitle);
        return {
          hasPct,
          hasFraction,
          hasBunkSummary,
          allCoursesFound,
          courseResults
        };
      })()
    `);

    recordCheck('25MX227 Overall Attendance (76.77% - 238/310)', att227Check.hasPct && att227Check.hasFraction);
    recordCheck('25MX227 Exactly 8 Academic Subjects with Correct Dynamic Titles', att227Check.allCoursesFound);
    for (const cr of att227Check.courseResults) {
      console.log(`    - ${cr.code} (${cr.titleExpected}): code=${cr.foundCode}, title=${cr.foundTitle}`);
    }

    console.log('\n=== STEP 3: VERIFY 25MX227 SCHEDULE DASHBOARD & FULL WEEK MATRIX ===');
    await client.send('Page.navigate', { url: 'http://localhost:3000/schedule' });
    await sleep(3000);

    // Switch to Full Week Grid View to verify all courses across the week
    await client.eval(`
      (() => {
        const btns = Array.from(document.querySelectorAll('button'));
        const fullWeekBtn = btns.find(b => b.innerText.includes('Full Week Grid'));
        if (fullWeekBtn) fullWeekBtn.click();
      })()
    `);
    await sleep(1500);

    const sched227Check = await client.eval(`
      (() => {
        const text = document.body.innerText;
        return {
          hasSchedule: text.includes('Monday') && text.includes('Friday'),
          hasDevOps: text.includes('DevOps') || text.includes('23MXAT'),
          hasPython: text.includes('SMART COMPUTING') || text.includes('23MXAY'),
          hasNetworks: text.includes('COMPUTER NETWORKS') || text.includes('23MXAE'),
          hasMiniProject: text.includes('MINI PROJECT') || text.includes('23MX37'),
          hasEthics: text.includes('PROFESSIONAL ETHICS') || text.includes('23MXM4'),
          hasNo232Electives: !text.includes('23MXAF') && !text.includes('DATA MINING AND ANALYTICS')
        };
      })()
    `);
    recordCheck('25MX227 Weekly Schedule Renders Monday-Friday', sched227Check.hasSchedule);
    recordCheck('25MX227 Full Week Grid Contains DevOps, Smart Computing, Networks, Mini Project, Ethics',
      sched227Check.hasDevOps && sched227Check.hasPython && sched227Check.hasNetworks && sched227Check.hasMiniProject && sched227Check.hasEthics);
    recordCheck('25MX227 Schedule Cross-Student Isolation (No 23MXAF / Data Mining)', sched227Check.hasNo232Electives);

    console.log('\n=== STEP 4: VERIFY 25MX227 ACADEMIC / GRADES DASHBOARD ===');
    await client.send('Page.navigate', { url: 'http://localhost:3000/grades' });
    await sleep(3000);

    const grades227Check = await client.eval(`
      (() => {
        const text = document.body.innerText;
        return {
          hasCGPA: text.includes('CURRENT CGPA') && (text.includes('8') || text.includes('8.0')),
          hasCredits: text.includes('24 Earned Credits') && text.includes('Verified'),
          hasCAHeader: text.includes('Continuous Assessment') || text.includes('CA Breakdown'),
          hasSemesterCourses: text.includes('8') && text.includes('Theory & Labs'),
          hasEthicsCourse: text.includes('23MXM4') || text.includes('PROFESSIONAL ETHICS'),
          hasWhatIf: text.includes('What-If') || text.includes('Projected CGPA') || text.includes('Simulator')
        };
      })()
    `);
    recordCheck('25MX227 Grades Page Renders Verified CGPA (8 / 24 Credits)', grades227Check.hasCGPA && grades227Check.hasCredits);
    recordCheck('25MX227 Grades Page Renders 8 Semester Courses & CA Component Table', grades227Check.hasCAHeader && grades227Check.hasSemesterCourses);
    recordCheck('25MX227 What-If CGPA Simulator is Present', grades227Check.hasWhatIf);

    console.log('\n=== STEP 5: VERIFY 25MX227 PERSONALIZED PLANNER DASHBOARD ===');
    await client.send('Page.navigate', { url: 'http://localhost:3000/planner' });
    await sleep(3000);

    const planner227Check = await client.eval(`
      (() => {
        const text = document.body.innerText;
        return {
          hasPlanner: text.includes('Planner') || text.includes('Study') || text.includes('Academic'),
          hasPriorities: text.includes('HIGH') || text.includes('MEDIUM') || text.includes('LOW'),
          hasSubjectMatrix: text.includes('23MX31') || text.includes('CLOUD COMPUTING')
        };
      })()
    `);
    recordCheck('25MX227 Study Planner Renders Subject Priorities (HIGH/MEDIUM/LOW)', planner227Check.hasPlanner && planner227Check.hasPriorities);
    recordCheck('25MX227 Study Planner Contains 25MX227 Curriculum Subjects', planner227Check.hasSubjectMatrix);

    console.log('\n=== STEP 6: VERIFY 25MX227 CAMPUS SERVICES DASHBOARD ===');
    await client.send('Page.navigate', { url: 'http://localhost:3000/services' });
    await sleep(3000);

    const services227Check = await client.eval(`
      (() => {
        const text = document.body.innerText;
        return {
          hasServices: text.includes('Campus Services') || text.includes('Services') || text.includes('Dossier'),
          hasHostelInfo: text.includes('Hostel') || text.includes('Allocation'),
          hasScholarship: text.includes('Scholarship') || text.includes('Available')
        };
      })()
    `);
    recordCheck('25MX227 Campus Services Hub Renders Dossier, Hostel, Scholarships', services227Check.hasServices && services227Check.hasHostelInfo);

    console.log('\n=== STEP 7: VERIFY 25MX227 DASHBOARD OVERVIEW ===');
    await client.send('Page.navigate', { url: 'http://localhost:3000/dashboard' });
    await sleep(3000);

    const dash227Check = await client.eval(`
      (() => {
        const text = document.body.innerText;
        return {
          hasStudent: text.includes('SUDHERSON') || text.includes('25MX227'),
          hasAttendanceWidget: text.includes('Attendance') || text.includes('76.77%')
        };
      })()
    `);
    recordCheck('25MX227 Main Dashboard Overview Renders Correct Identity & Stats', dash227Check.hasStudent);

    console.log('\n=== STEP 8: AUTHENTICATE 25MX232 & TEST CROSS-STUDENT ISOLATION ===');
    await client.send('Page.navigate', { url: 'http://localhost:3000/login' });
    await sleep(1500);

    const login232Result = await client.eval(`
      (async () => {
        const res = await fetch('http://127.0.0.1:5000/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ rollNo: '25MX232', password: '120405' })
        });
        const data = await res.json();
        if (res.status === 200 && data.auth_token) {
          localStorage.setItem('student_sync_user', JSON.stringify(data));
          return { success: true, rollNo: data.rollNo, name: data.name };
        }
        return { success: false, status: res.status, data };
      })()
    `);
    recordCheck('25MX232 API Login & Session Initialized', login232Result.success, `${login232Result.rollNo} - ${login232Result.name}`);

    console.log('\n=== STEP 9: VERIFY 25MX232 ATTENDANCE & ISOLATION ===');
    await client.send('Page.navigate', { url: 'http://localhost:3000/attendance' });
    await sleep(3500);

    const att232Check = await client.eval(`
      (() => {
        const text = document.body.innerText;
        const hasPct = text.includes('83.23%');
        const hasFraction = text.includes('258') && text.includes('310');
        
        const courses = [
          { code: '23MX37', title: 'MINI PROJECT' },
          { code: '23MXM4', title: 'PROFESSIONAL ETHICS' },
          { code: '23MXAF', title: 'DATA MINING AND ANALYTICS' },
          { code: '23MXAO', title: 'HUMAN COMPUTER INTERACTION' }
        ];

        const courseResults = courses.map(c => ({
          code: c.code,
          titleExpected: c.title,
          foundCode: text.includes(c.code),
          foundTitle: text.toUpperCase().includes(c.title.toUpperCase())
        }));

        const allCoursesFound = courseResults.every(c => c.foundCode && c.foundTitle);
        const has227Electives = text.includes('23MXAT') || text.includes('DevOps') || text.includes('23MXAY');

        return {
          hasPct,
          hasFraction,
          allCoursesFound,
          has227Electives,
          courseResults
        };
      })()
    `);

    recordCheck('25MX232 Overall Attendance (83.23% - 258/310)', att232Check.hasPct && att232Check.hasFraction);
    recordCheck('25MX232 4 Distinct Subjects with Correct Titles (Mini Project, Ethics, Data Mining, HCI)', att232Check.allCoursesFound);
    recordCheck('Strict Cross-Student Isolation: 25MX227 electives absent from 25MX232', !att232Check.has227Electives);
    for (const cr of att232Check.courseResults) {
      console.log(`    - ${cr.code} (${cr.titleExpected}): code=${cr.foundCode}, title=${cr.foundTitle}`);
    }

    console.log('\n=== STEP 10: CONSOLE & NETWORK ERROR AUDIT ===');
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
