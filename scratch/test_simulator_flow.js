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

  // Click "What-If CGPA Simulator"
  await send('Runtime.evaluate', {
    expression: `
      (() => {
        const btns = Array.from(document.querySelectorAll('button'));
        const simBtn = btns.find(b => b.innerText.includes('What-If CGPA Simulator'));
        if (simBtn) simBtn.click();
      })()
    `
  });
  await new Promise(r => setTimeout(r, 1000));

  // Add 1st Course: 4.0 credits, O (10.0)
  const addRes1 = await send('Runtime.evaluate', {
    expression: `
      (() => {
        const nameInput = document.querySelector('input[placeholder*=\"Cloud\"]');
        const crInput = document.querySelector('input[placeholder*=\"4.0\"]');
        const gradeSelect = document.querySelector('form select');
        const submitBtn = document.querySelector('form button[type=\"submit\"]');

        const setVal = (el, val) => {
          const s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
          s.call(el, val);
          el.dispatchEvent(new Event('input', { bubbles: true }));
          el.dispatchEvent(new Event('change', { bubbles: true }));
        };
        const setSelect = (el, val) => {
          const s = Object.getOwnPropertyDescriptor(window.HTMLSelectElement.prototype, 'value').set;
          s.call(el, val);
          el.dispatchEvent(new Event('change', { bubbles: true }));
        };

        if (!crInput || !submitBtn) return { error: 'Inputs not found' };

        if (nameInput) setVal(nameInput, 'Hypothetical Course 1');
        setVal(crInput, '4.0');
        if (gradeSelect) setSelect(gradeSelect, 'O');
        submitBtn.click();
        return { success: true };
      })()
    `,
    returnByValue: true
  });
  console.log('Add Course 1 attempt:', addRes1.result.value);
  await new Promise(r => setTimeout(r, 1000));

  // Check state after Course 1
  const check1 = await send('Runtime.evaluate', {
    expression: `
      (() => {
        const text = document.body.innerText;
        return {
          has825: text.includes('8.25'),
          hasDelta29: text.includes('+0.29'),
          has28Cr: text.includes('28')
        };
      })()
    `,
    returnByValue: true
  });
  console.log('After Course 1 (Expected 8.25, +0.29):', check1.result.value);

  // Add 2nd Course: 3.0 credits, A+ (9.0)
  const addRes2 = await send('Runtime.evaluate', {
    expression: `
      (() => {
        const nameInput = document.querySelector('input[placeholder*=\"Cloud\"]');
        const crInput = document.querySelector('input[placeholder*=\"4.0\"]');
        const gradeSelect = document.querySelector('form select');
        const submitBtn = document.querySelector('form button[type=\"submit\"]');

        const setVal = (el, val) => {
          const s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
          s.call(el, val);
          el.dispatchEvent(new Event('input', { bubbles: true }));
          el.dispatchEvent(new Event('change', { bubbles: true }));
        };
        const setSelect = (el, val) => {
          const s = Object.getOwnPropertyDescriptor(window.HTMLSelectElement.prototype, 'value').set;
          s.call(el, val);
          el.dispatchEvent(new Event('change', { bubbles: true }));
        };

        if (nameInput) setVal(nameInput, 'Hypothetical Course 2');
        setVal(crInput, '3.0');
        if (gradeSelect) setSelect(gradeSelect, 'A+');
        submitBtn.click();
        return { success: true };
      })()
    `,
    returnByValue: true
  });
  console.log('Add Course 2 attempt:', addRes2.result.value);
  await new Promise(r => setTimeout(r, 1000));

  // Check state after Course 2
  const check2 = await send('Runtime.evaluate', {
    expression: `
      (() => {
        const text = document.body.innerText;
        return {
          has832: text.includes('8.32'),
          hasDelta36: text.includes('+0.36'),
          has31Cr: text.includes('31')
        };
      })()
    `,
    returnByValue: true
  });
  console.log('After Course 2 (Expected 8.32, +0.36):', check2.result.value);

  // Test Removing Course 2
  console.log('Removing Course 2...');
  await send('Runtime.evaluate', {
    expression: `
      (() => {
        const trashBtns = Array.from(document.querySelectorAll('button')).filter(b => b.className.includes('rose') || b.title?.includes('Remove'));
        if (trashBtns.length > 0) {
          trashBtns[trashBtns.length - 1].click();
        }
      })()
    `
  });
  await new Promise(r => setTimeout(r, 1000));

  const checkRemove = await send('Runtime.evaluate', {
    expression: `
      (() => {
        const text = document.body.innerText;
        return {
          has825: text.includes('8.25'),
          hasDelta29: text.includes('+0.29')
        };
      })()
    `,
    returnByValue: true
  });
  console.log('After Removing Course 2 (Expected revert to 8.25):', checkRemove.result.value);

  // Test Reset button
  console.log('Clicking Reset button...');
  await send('Runtime.evaluate', {
    expression: `
      (() => {
        const resetBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.trim() === 'Reset');
        if (resetBtn) resetBtn.click();
      })()
    `
  });
  await new Promise(r => setTimeout(r, 1000));

  const checkReset = await send('Runtime.evaluate', {
    expression: `
      (() => {
        const text = document.body.innerText;
        return {
          has796: text.includes('7.96'),
          hasNeutral: text.includes('0.00 (Neutral)'),
          has0SimCourses: text.includes('0 simulated courses')
        };
      })()
    `,
    returnByValue: true
  });
  console.log('After Reset (Expected 7.96, Neutral, 0 simulated courses):', checkReset.result.value);

  ws.close();
  edgeProc.kill();
})();
