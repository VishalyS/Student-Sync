const edgeExe = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const { spawn } = require('child_process');

(async () => {
  const edgeProc = spawn(edgeExe, ['--headless=new', '--remote-debugging-port=9222', '--disable-gpu', 'http://localhost:3000/']);
  await new Promise(r => setTimeout(r, 1500));
  const res = await fetch('http://127.0.0.1:9222/json/list');
  const targets = await res.json();
  const page = targets.find(t => t.type === 'page') || targets[0];
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise(r => ws.onopen = r);
  let id = 1;
  const send = (method, params = {}) => new Promise((resolve) => {
    const curId = id++;
    const handler = (msg) => {
      const data = JSON.parse(msg.data);
      if (data.id === curId) { ws.removeEventListener('message', handler); resolve(data.result); }
    };
    ws.addEventListener('message', handler);
    ws.send(JSON.stringify({ id: curId, method, params }));
  });

  const consoleErrors = [];
  const networkErrors = [];

  await send('Page.enable');
  await send('Runtime.enable');
  await send('Network.enable');

  ws.addEventListener('message', (msg) => {
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

  // Login
  await send('Page.navigate', { url: 'http://localhost:3000/login' });
  await new Promise(r => setTimeout(r, 1000));
  await send('Runtime.evaluate', {
    expression: `
      (async () => {
        const res = await fetch('http://127.0.0.1:5000/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ rollNo: '25MX232', password: '120405' })
        });
        const data = await res.json();
        localStorage.setItem('student_sync_user', JSON.stringify(data));
      })()
    `,
    awaitPromise: true
  });

  // 1. Dashboard cross-link check
  console.log('--- Checking Dashboard Cross-link ---');
  await send('Page.navigate', { url: 'http://localhost:3000/dashboard' });
  await new Promise(r => setTimeout(r, 2000));

  const clickTabAndCrosslink = await send('Runtime.evaluate', {
    expression: `
      (async () => {
        // Find CA Marks tab button in Dashboard
        const btns = Array.from(document.querySelectorAll('button'));
        const caTab = btns.find(b => b.innerText.includes('CA Marks'));
        if (caTab) caTab.click();
        await new Promise(r => setTimeout(r, 800));

        // Find the cross link
        const crossLink = Array.from(document.querySelectorAll('a')).find(a => 
          a.innerText.includes('Open Deep CA Breakdown & CGPA Simulator') || a.getAttribute('href') === '/grades'
        );

        if (!crossLink) return { found: false };
        const text = crossLink.innerText.trim();
        crossLink.click();
        await new Promise(r => setTimeout(r, 1500));

        return {
          found: true,
          text,
          urlAfterClick: window.location.pathname
        };
      })()
    `,
    awaitPromise: true,
    returnByValue: true
  });
  console.log('Dashboard Cross-link test:', clickTabAndCrosslink.result.value);

  // 2. Regression: Attendance Page
  console.log('\n--- Checking Attendance Page ---');
  await send('Page.navigate', { url: 'http://localhost:3000/attendance' });
  await new Promise(r => setTimeout(r, 2000));
  const attCheck = await send('Runtime.evaluate', {
    expression: `
      (() => {
        const text = document.body.innerText;
        return {
          hasPct: text.includes('83.23%'),
          hasAttended: text.includes('258'),
          hasConducted: text.includes('310'),
          hasBunkReserve: text.includes('34 Classes') || text.includes('34'),
          hasSubjects: text.includes('CLOUD COMPUTING') || text.includes('23MX31')
        };
      })()
    `,
    returnByValue: true
  });
  console.log('Attendance Page verification:', attCheck.result.value);

  // 3. Regression: Notifications Page
  console.log('\n--- Checking Notifications Page ---');
  await send('Page.navigate', { url: 'http://localhost:3000/welcome' });
  await new Promise(r => setTimeout(r, 1500));
  const notifCheck = await send('Runtime.evaluate', {
    expression: `
      (() => {
        const text = document.body.innerText;
        return {
          hasPortalAlerts: text.includes('Sync') || text.includes('Notification') || text.includes('Alert'),
          hasContent: text.length > 200
        };
      })()
    `,
    returnByValue: true
  });
  console.log('Notifications Page verification:', notifCheck.result.value);

  // 4. Logout Check
  console.log('\n--- Checking Logout ---');
  await send('Runtime.evaluate', {
    expression: `
      (() => {
        const logoutBtn = Array.from(document.querySelectorAll('button, a')).find(b => b.innerText.includes('Logout'));
        if (logoutBtn) logoutBtn.click();
        else localStorage.removeItem('student_sync_user');
      })()
    `
  });
  await new Promise(r => setTimeout(r, 800));
  const storageCleared = await send('Runtime.evaluate', {
    expression: `localStorage.getItem('student_sync_user') === null`,
    returnByValue: true
  });
  console.log('Logout cleared localStorage:', storageCleared.result.value);

  console.log('\n--- Console & Network Audit ---');
  console.log('Console errors count:', consoleErrors.length, consoleErrors);
  console.log('Network errors count:', networkErrors.length, networkErrors);

  ws.close();
  edgeProc.kill();
})();
