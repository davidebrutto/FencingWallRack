const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../static/underfloor-pause.js'), 'utf8');

function createWindow(minutes) {
  let now = 0;
  let timerId = 0;
  const timers = new Map();
  const intervals = [];
  const handlers = {};
  const slides = [{ style: {}, offsetHeight: 96 }, { style: {}, offsetHeight: 96 }];
  const overlay = { hidden: true, querySelectorAll: () => slides };
  const socket = { on(event, handler) { handlers[event] = handler; }, emit(event, value) { handlers[event]?.(value); } };
  const window = {};
  class FakeDate extends Date { static now() { return now; } }
  class FakeImage { set src(value) { this._src = value; queueMicrotask(() => this.onload?.()); } }
  vm.runInNewContext(source, {
    window, document: { getElementById: () => overlay }, Image: FakeImage,
    Date: FakeDate, JSON, console,
    fetch: async () => ({ ok: true, json: async () => ({ media: [
      { type: 'video', src: '/video.mp4' },
      { type: 'image', underfloorSrc: '/underfloor/01.jpg' },
      { type: 'image', underfloorSrc: '/underfloor/02.jpg' },
    ] }) }),
    setTimeout(fn, delay) { const id = ++timerId; timers.set(id, { fn, due: now + delay }); return id; },
    clearTimeout(id) { timers.delete(id); },
    setInterval(fn) { intervals.push(fn); },
    requestAnimationFrame(fn) { fn(); },
  });
  window.setupUnderfloorPause(socket, minutes);
  return {
    overlay, slides, socket, intervals,
    tick(time) {
      now = time;
      for (const fn of intervals) fn();
      for (const [id, timer] of Array.from(timers)) {
        if (timer.due <= now) { timers.delete(id); timer.fn(); }
      }
    },
  };
}

const flush = () => new Promise((resolve) => setImmediate(resolve));
(async () => {
  const windows = Array.from({ length: 4 }, () => createWindow(1));
  for (const win of windows) win.socket.emit('punti_emit', { tabellone: { timer: '3:00', XX: '0' } });
  for (const win of windows) win.tick(11000);
  await flush();
  for (const win of windows) {
    assert.equal(win.overlay.hidden, false);
    assert.match(win.slides[0].style.backgroundImage, /02\.jpg/);
  }
  for (const win of windows) win.tick(20020);
  await flush();
  for (const win of windows) {
    assert.match(win.slides[1].style.backgroundImage, /01\.jpg/);
    assert.equal(win.slides[1].style.transform, 'translateY(0)');
    assert.equal(win.slides[0].style.transform, 'translateY(-100%)');
    win.socket.emit('punti_emit', { tabellone: { timer: '2:59', XX: '0' } });
    assert.equal(win.overlay.hidden, true);
  }
  const disabled = createWindow(0);
  disabled.tick(11000);
  assert.equal(disabled.overlay.hidden, true);
  assert.equal(disabled.intervals.length, 0);
  console.log('Underfloor pause: synchronized images, upward transition, live exit and NO mode OK');
})().catch((error) => { console.error(error); process.exitCode = 1; });
