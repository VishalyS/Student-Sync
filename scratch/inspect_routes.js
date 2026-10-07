const { spawn } = require('child_process');
const edgeUserData = 'C:\\Users\\visha\\Downloads\\ACPNS-main\\ACPNS-main\\scratch\\edge_inspect_routes';
const edgeExe = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';

(async () => {
  const edgeProc = spawn(edgeExe, [
    '--headless=new',
    '--remote-debugging-port=9227',
    '--disable-gpu',
    `--user-data-dir=${edgeUserData}`,
    'http://localhost:3000/'
  ]);
  await new Promise(r => setTimeout(r, 2000));
  const targets = await (await fetch('http://127.0.0.1:9227/json/list')).json();
  const pageTarget = targets.find(t => t.type === 'page') || targets[0];
  const ws = new WebSocket(pageTarget.webSocketDebuggerUrl);
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

  // Login 25MX227
  await send('Page.navigate', { url: 'http://localhost:3000/login' });
  await new Promise(r => setTimeout(r, 1500));
  await send('Runtime.evaluate', {
    expression: `
      (async () => {
        const res = await fetch('http://127.0.0.1:5000/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ rollNo: '25MX227', password: '24SEP02' })
        });
        const data = await res.json();
        localStorage.setItem('student_sync_user', JSON.stringify(data));
      })()
    `,
    awaitPromise: true
  });

  // Inspect /schedule
  await send('Page.navigate', { url: 'http://localhost:3000/schedule' });
  await new Promise(r => setTimeout(r, 3500));
  const sRes = await send('Runtime.evaluate', { expression: 'document.body.innerText', returnByValue: true });
  console.log('=== /schedule TEXT (first 800 chars) ===');
  const sText = sRes?.result?.value || '';
  console.log(sText.substring(0, 800));

  // Inspect /grades
  await send('Page.navigate', { url: 'http://localhost:3000/grades' });
  await new Promise(r => setTimeout(r, 3500));
  const gRes = await send('Runtime.evaluate', { expression: 'document.body.innerText', returnByValue: true });
  console.log('=== /grades TEXT (first 800 chars) ===');
  const gText = gRes?.result?.value || '';
  console.log(gText.substring(0, 800));

  ws.close();
  edgeProc.kill('SIGTERM');
  process.exit(0);
})();
