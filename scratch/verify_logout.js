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

  await send('Emulation.setDeviceMetricsOverride', {
    width: 1280,
    height: 900,
    deviceScaleFactor: 1,
    mobile: false
  });

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

  await send('Page.navigate', { url: 'http://localhost:3000/grades' });
  await new Promise(r => setTimeout(r, 2000));

  const buttonsInfo = await send('Runtime.evaluate', {
    expression: `
      (() => {
        const btns = Array.from(document.querySelectorAll('button'));
        return btns.map(b => b.innerText.trim());
      })()
    `,
    returnByValue: true
  });
  console.log('Buttons on /grades:', buttonsInfo.result.value);

  const clickLogout = await send('Runtime.evaluate', {
    expression: `
      (() => {
        const logoutBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Logout'));
        if (!logoutBtn) return { found: false };
        logoutBtn.click();
        return { found: true };
      })()
    `,
    returnByValue: true
  });
  console.log('Logout button found and clicked:', clickLogout.result.value);
  await new Promise(r => setTimeout(r, 1000));

  const remainingUser = await send('Runtime.evaluate', {
    expression: `localStorage.getItem('student_sync_user')`,
    returnByValue: true
  });
  console.log('User in localStorage after logout:', remainingUser.result.value);

  ws.close();
  edgeProc.kill();
})();
