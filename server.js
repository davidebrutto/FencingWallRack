const fs = require('fs');
const path = require('path');
const http = require('http');
const express = require('express');
const session = require('express-session');
const passport = require('passport');
const LocalStrategy = require('passport-local').Strategy;
const bcrypt = require('bcryptjs');
const nunjucks = require('nunjucks');
const { Server } = require('socket.io');
const { SerialPort } = require('serialport');

const app = express();
const server = http.createServer(app);
const io = new Server(server, {
  cors: { origin: '*' },
  transports: ['websocket'],
  allowUpgrades: false,
  perMessageDeflate: false,
});

const HOST = process.env.HOST || '127.0.0.1';
const PORT = Number(process.env.PORT || 5000);
const SERIAL_PORT = process.env.SERIAL_PORT || '/dev/ttyUSB0';
const SERIAL_BAUD = Number(process.env.SERIAL_BAUD || 38400);
const SERIAL_DATABITS = Number(process.env.SERIAL_DATABITS || 8);
const SERIAL_PARITY = process.env.SERIAL_PARITY || 'none';
const SERIAL_STOPBITS = Number(process.env.SERIAL_STOPBITS || 1);
const SERIAL_RTSCTS = process.env.SERIAL_RTSCTS === '1';
const SERIAL_XON = process.env.SERIAL_XON === '1';
const SERIAL_XOFF = process.env.SERIAL_XOFF === '1';
const DEBUG_SERIAL = process.env.DEBUG_SERIAL === '1';
const SERIAL_IDLE_FLUSH_MS = Number(process.env.SERIAL_IDLE_FLUSH_MS || 1200);

const DATA_FILE = path.join(__dirname, 'scores.json');
const USERS_FILE = path.join(__dirname, 'users.json');

const ROUTES = {
  index: '/',
  index_single: '/index_single',
  register: '/register',
  login: '/login',
  logout: '/logout',
  add_game: '/add_game',
  config_game: '/config',
  video: '/video',
  video_upd: '/video_upd',
  delete_game: '/delete_game/:game_id',
  update_score: '/update_score/:game_id',
  api_scores: '/api/scores',
};

function ensureJsonFile(filePath, fallback) {
  if (!fs.existsSync(filePath)) {
    fs.writeFileSync(filePath, JSON.stringify(fallback, null, 2));
  }
}

function readJson(filePath, fallback) {
  try {
    return JSON.parse(fs.readFileSync(filePath, 'utf-8'));
  } catch (error) {
    return fallback;
  }
}

function writeJson(filePath, payload) {
  fs.writeFileSync(filePath, JSON.stringify(payload, null, 2));
}

function loadScores() {
  return readJson(DATA_FILE, []);
}

function saveScores(scores) {
  writeJson(DATA_FILE, scores);
}

function loadUsers() {
  return readJson(USERS_FILE, []);
}

function saveUsers(users) {
  writeJson(USERS_FILE, users);
}

function applyRouteParams(route, kwargs) {
  if (!kwargs) {
    return route;
  }

  return Object.entries(kwargs).reduce((acc, [key, value]) => {
    return acc.replace(`:${key}`, String(value));
  }, route);
}

function urlFor(name, ...args) {
  if (name === 'static') {
    const maybeKw = args[args.length - 1];
    const filename = maybeKw && maybeKw.__keywords ? maybeKw.filename : '';
    return `/static/${filename || ''}`;
  }

  const route = ROUTES[name];
  if (!route) {
    return '#';
  }

  const maybeKw = args[args.length - 1];
  const kwargs = maybeKw && maybeKw.__keywords ? maybeKw : undefined;
  return applyRouteParams(route, kwargs);
}

const nunjucksEnv = nunjucks.configure(path.join(__dirname, 'templates'), {
  autoescape: true,
  express: app,
});

nunjucksEnv.addGlobal('url_for', urlFor);

app.set('view engine', 'njk');
app.set('views', path.join(__dirname, 'templates'));
app.use('/static', express.static(path.join(__dirname, 'static')));

app.use(express.urlencoded({ extended: true }));
app.use(express.json());

app.use(
  session({
    secret: process.env.SESSION_SECRET || 'supersecretkey',
    resave: false,
    saveUninitialized: false,
  })
);

app.use(passport.initialize());
app.use(passport.session());

passport.use(
  new LocalStrategy(async (username, password, done) => {
    try {
      const users = loadUsers();
      const user = users.find((u) => u.username === username);
      if (!user) {
        return done(null, false);
      }
      const valid = await bcrypt.compare(password, user.password);
      return done(null, valid ? user : false);
    } catch (error) {
      return done(error);
    }
  })
);

passport.serializeUser((user, done) => done(null, user.id));
passport.deserializeUser((id, done) => {
  const users = loadUsers();
  const user = users.find((u) => u.id === id);
  done(null, user || false);
});

function loginRequired(req, res, next) {
  if (req.isAuthenticated && req.isAuthenticated()) {
    return next();
  }
  return res.redirect('/login');
}

function buildColori() {
  return {
    statoDXColor: 'rgba(255,255,255,0%)',
    statoSXColor: 'rgba(255,255,255,0%)',
  };
}

app.get('/', (req, res) => {
  const scores = loadScores();
  res.render('index.html', {
    scores,
    miapath: __dirname,
    instancepath: path.join(__dirname, 'instance'),
    colori: buildColori(),
  });
});

app.get('/index_single', (req, res) => {
  const scores = loadScores();
  res.render('index_single.html', {
    scores,
    miapath: __dirname,
    instancepath: path.join(__dirname, 'instance'),
    colori: buildColori(),
  });
});

app.get('/register', loginRequired, (req, res) => {
  res.render('sign_up.html');
});

app.post('/register', loginRequired, async (req, res) => {
  const { username, password } = req.body;
  const users = loadUsers();

  if (users.some((u) => u.username === username)) {
    return res.render('sign_up.html', { error: 'Username already taken!' });
  }

  const hashedPassword = await bcrypt.hash(password, 10);
  const newUser = {
    id: users.length > 0 ? Math.max(...users.map((u) => u.id)) + 1 : 1,
    username,
    password: hashedPassword,
  };

  users.push(newUser);
  saveUsers(users);
  return res.redirect('/login');
});

app.get('/login', (req, res) => {
  res.render('login.html');
});

app.post('/login', (req, res, next) => {
  passport.authenticate('local', (err, user) => {
    if (err) {
      return next(err);
    }
    if (!user) {
      return res.render('login.html', { error: 'Invalid username or password' });
    }
    return req.logIn(user, (loginErr) => {
      if (loginErr) {
        return next(loginErr);
      }
      return res.redirect('/config');
    });
  })(req, res, next);
});

app.get('/logout', loginRequired, (req, res, next) => {
  req.logout((err) => {
    if (err) {
      return next(err);
    }
    return res.redirect('/');
  });
});

app.get('/add_game', (req, res) => {
  res.render('add_game.html');
});

app.post('/add_game', (req, res) => {
  const scores = loadScores();
  const newGame = {
    id: scores.length > 0 ? Math.max(...scores.map((s) => s.id || 0)) + 1 : 1,
    team1: req.body.team1,
    team2: req.body.team2,
    score1: Number(req.body.score1 || 0),
    score2: Number(req.body.score2 || 0),
    sport: req.body.sport,
    date: new Date().toISOString().slice(0, 16).replace('T', ' '),
    status: req.body.status || 'Live',
  };

  scores.push(newGame);
  saveScores(scores);
  return res.redirect('/');
});

app.get('/config', loginRequired, (req, res) => {
  const scores = loadScores();
  const flagsPath = path.join(__dirname, 'static', 'flags');
  const files = fs.existsSync(flagsPath) ? fs.readdirSync(flagsPath) : [];
  res.render('config.html', { scores, files });
});

app.get('/video', loginRequired, (req, res) => {
  res.render('video.html');
});

app.post('/video_upd', (req, res) => {
  if (req.body.video === 'videoOn') {
    io.emit('video_emit', { video: 'videoOn' });
  }
  if (req.body.video === 'videoOff') {
    io.emit('video_emit', { video: 'videoOff' });
  }
  res.redirect('/video');
});

app.post('/update_score/:game_id', (req, res) => {
  const gameId = Number(req.params.game_id);
  const scores = loadScores();
  let game = null;

  for (const item of scores) {
    if (item.id === gameId) {
      item.team1 = req.body.team1;
      item.team2 = req.body.team2;
      item.country1 = req.body.country1;
      item.country2 = req.body.country2;
      item.flag1 = req.body.flag1;
      item.flag2 = req.body.flag2;
      item.gruppo1 = req.body.gruppo1;
      item.gruppo2 = req.body.gruppo2;
      item.rank1 = req.body.rank1;
      item.rank2 = req.body.rank2;
      item.classgir1 = req.body.classgir1;
      item.classgir2 = req.body.classgir2;
      game = item;
      break;
    }
  }

  saveScores(scores);

  if (game) {
    io.emit('info_emit', { info: game });
  }

  res.redirect('/config');
});

app.get('/delete_game/:game_id', (req, res) => {
  const gameId = Number(req.params.game_id);
  const scores = loadScores().filter((game) => game.id !== gameId);
  saveScores(scores);
  res.redirect('/');
});

app.get('/api/scores', (req, res) => {
  res.json(loadScores());
});

const SOH = 0x01;
const EOT = 0x04;
const CMD_DC4 = 0x14;
const CMD_DC3 = 0x13;
const STX = 0x02;

function boolByteToFlag(value) {
  return value === 0x00 ? '0' : '1';
}

function parseMessage1Frame(frameBuf) {
  // Message 1: [SOH][DC4]R«x»G«x»W«x»w«x»[EOT] => 11 bytes
  if (frameBuf.length !== 11) {
    return null;
  }
  if (frameBuf[0] !== SOH || frameBuf[1] !== CMD_DC4 || frameBuf[10] !== EOT) {
    return null;
  }
  if (frameBuf[2] !== 0x52 || frameBuf[4] !== 0x47 || frameBuf[6] !== 0x57 || frameBuf[8] !== 0x77) {
    return null;
  }

  return {
    R: boolByteToFlag(frameBuf[3]),
    G: boolByteToFlag(frameBuf[5]),
    W: boolByteToFlag(frameBuf[7]),
    w: boolByteToFlag(frameBuf[9]),
  };
}

function normalizeTimerText(raw) {
  // Keep digits and separators, convert non-printables/extended chars to spaces.
  let out = '';
  for (let i = 0; i < raw.length; i += 1) {
    const ch = raw[i];
    const code = raw.charCodeAt(i);
    if ((code >= 0x30 && code <= 0x39) || ch === ':' || ch === '.') {
      out += ch;
    } else {
      out += ' ';
    }
  }
  return out;
}

function parseMessage2Frame(frameBuf) {
  // Message 2: [SOH][DC3]Z[STX]«MM:SS.DC»[EOT] => 13 bytes
  if (frameBuf.length !== 13) {
    return null;
  }
  if (frameBuf[0] !== SOH || frameBuf[1] !== CMD_DC3 || frameBuf[3] !== STX || frameBuf[12] !== EOT) {
    return null;
  }

  const mode = String.fromCharCode(frameBuf[2]);
  if (!['R', 'N', 'J', 'B'].includes(mode)) {
    return null;
  }

  const rawTimer = frameBuf.subarray(4, 12).toString('latin1');
  const timer = normalizeTimerText(rawTimer);

  return {
    timer,
    timerMode: mode,
  };
}

function printableFromByte(byte, fallback = ' ') {
  if (byte >= 0x20 && byte <= 0x7e) {
    return String.fromCharCode(byte);
  }
  return fallback;
}

function segmentToPrintableString(segment) {
  let out = '';
  for (let i = 0; i < segment.length; i += 1) {
    out += printableFromByte(segment[i], ' ');
  }
  return out;
}

function parseMessage3Frame(frameBuf) {
  // Message 3: [SOH][DC3]D[STX]XX:YY[STX]ABb[STX]CDd[STX]P[STX]R[STX]vW[EOT]
  if (frameBuf.length < 12) {
    return null;
  }
  if (frameBuf[0] !== SOH || frameBuf[1] !== CMD_DC3 || frameBuf[2] !== 0x44 || frameBuf[frameBuf.length - 1] !== EOT) {
    return null;
  }

  const segments = [];
  let idx = 3;
  while (idx < frameBuf.length - 1) {
    if (frameBuf[idx] !== STX) {
      return null;
    }
    idx += 1;
    const start = idx;
    while (idx < frameBuf.length - 1 && frameBuf[idx] !== STX) {
      idx += 1;
    }
    segments.push(frameBuf.subarray(start, idx));
  }

  if (segments.length < 6) {
    return null;
  }

  const scoreSeg = segments[0];
  const cardsRightSeg = segments[1];
  const cardsLeftSeg = segments[2];
  const prioritySeg = segments[3];
  const roundSeg = segments[4];

  if (scoreSeg.length < 5 || cardsRightSeg.length < 3 || cardsLeftSeg.length < 3 || prioritySeg.length < 1 || roundSeg.length < 1) {
    return null;
  }

  const XX = `${printableFromByte(scoreSeg[0])}${printableFromByte(scoreSeg[1])}`;
  const sep = printableFromByte(scoreSeg[2], ':');
  const YY = `${printableFromByte(scoreSeg[3])}${printableFromByte(scoreSeg[4])}`;

  const A = printableFromByte(cardsRightSeg[0], '0');
  const B = printableFromByte(cardsRightSeg[1], '0');
  const b = printableFromByte(cardsRightSeg[2], '0');
  const C = printableFromByte(cardsLeftSeg[0], '0');
  const D = printableFromByte(cardsLeftSeg[1], '0');
  const d = printableFromByte(cardsLeftSeg[2], '0');

  const P = printableFromByte(prioritySeg[0], '0');
  const PR = segmentToPrintableString(roundSeg).trim() || '0';

  return {
    XX,
    YY,
    A,
    B,
    b,
    C,
    D,
    d,
    P,
    PR,
    scoreSep: sep,
  };
}

function parseMessage4Frame(frameBuf) {
  // Message 4: [SOH][DC3]I[STX]M[STX]W[STX]S[STX]N[STX]VW[EOT]
  // For now we recognize it to avoid false "skip" logs, but we don't map fields.
  if (frameBuf.length !== 12) {
    return null;
  }
  if (frameBuf[0] !== SOH || frameBuf[1] !== CMD_DC3 || frameBuf[2] !== 0x49 || frameBuf[11] !== EOT) {
    return null;
  }
  if (frameBuf[3] !== STX || frameBuf[5] !== STX || frameBuf[7] !== STX || frameBuf[9] !== STX) {
    return null;
  }

  return {
    M: printableFromByte(frameBuf[4], '0'),
    W: printableFromByte(frameBuf[6], '0'),
    S: printableFromByte(frameBuf[8], '0'),
    N: printableFromByte(frameBuf[10], '0'),
  };
}

function parseKnownFrame(frameBuf) {
  const msg1 = parseMessage1Frame(frameBuf);
  if (msg1) {
    return { type: 'message1_lights', tabellone: msg1 };
  }
  const msg2 = parseMessage2Frame(frameBuf);
  if (msg2) {
    return { type: 'message2_time', tabellone: msg2 };
  }
  const msg3 = parseMessage3Frame(frameBuf);
  if (msg3) {
    return { type: 'message3_competitors', tabellone: msg3 };
  }
  const msg4 = parseMessage4Frame(frameBuf);
  if (msg4) {
    return { type: 'message4_status_info', tabellone: null };
  }
  return null;
}

const lastTabelloneState = {
  R: '0',
  G: '0',
  W: '0',
  w: '0',
  timer: '3:00',
  XX: ' 0',
  YY: ' 0',
  A: '0',
  B: '0',
  b: '0',
  C: '0',
  D: '0',
  d: '0',
  P: '0',
  PR: '0',
  scoreSep: ':',
  timerMode: 'R',
};

function mergeTabelloneState(partial) {
  for (const [key, value] of Object.entries(partial)) {
    if (typeof value !== 'string') {
      continue;
    }
    if (value.length === 0) {
      continue;
    }
    lastTabelloneState[key] = value;
  }

  return { ...lastTabelloneState };
}

function logSerialDebug(event, details = '') {
  if (!DEBUG_SERIAL) {
    return;
  }
  const ts = new Date().toISOString();
  console.log(`[${ts}] ${event}${details ? ` ${details}` : ''}`);
}

function startSerialReader() {
  let rxBuffer = Buffer.alloc(0);

  const port = new SerialPort({
    path: SERIAL_PORT,
    baudRate: SERIAL_BAUD,
    dataBits: SERIAL_DATABITS,
    parity: SERIAL_PARITY,
    stopBits: SERIAL_STOPBITS,
    rtscts: SERIAL_RTSCTS,
    xon: SERIAL_XON,
    xoff: SERIAL_XOFF,
    autoOpen: false,
  });

  port.open((error) => {
    if (error) {
      console.error(`Serial open error (${SERIAL_PORT}):`, error.message);
      return;
    }
    console.log(
      `Serial Start on ${SERIAL_PORT} @ ${SERIAL_BAUD} ` +
      `${SERIAL_DATABITS}${SERIAL_PARITY[0]?.toUpperCase() || 'N'}${SERIAL_STOPBITS} ` +
      `rtscts=${SERIAL_RTSCTS} xon=${SERIAL_XON} xoff=${SERIAL_XOFF}`
    );
  });

  function emitFrame(frameBuf, source) {
    if (!frameBuf || frameBuf.length < 3) {
      logSerialDebug('frame_drop', `source=${source} len=${frameBuf ? frameBuf.length : 0}`);
      return;
    }

    logSerialDebug('frame_complete', `source=${source} len=${frameBuf.length}`);
    const parsed = parseKnownFrame(frameBuf);
    if (!parsed) {
      const hexHead = frameBuf.subarray(0, Math.min(16, frameBuf.length)).toString('hex');
      logSerialDebug('frame_skip', `source=${source} reason=not_scoreboard_frame hex=${hexHead}`);
      return;
    }

    if (!parsed.tabellone) {
      logSerialDebug('frame_ignore', `type=${parsed.type}`);
      return;
    }

    const tabellone = mergeTabelloneState(parsed.tabellone);
    logSerialDebug('ws_emit', `type=${parsed.type} R=${tabellone.R} G=${tabellone.G} W=${tabellone.W} w=${tabellone.w}`);
    io.volatile.emit('punti_emit', { tabellone });
  }

  function extractFramesFromBuffer(source) {
    while (true) {
      const sohIndex = rxBuffer.indexOf(SOH);
      if (sohIndex === -1) {
        if (rxBuffer.length > 0) {
          logSerialDebug('buffer_clear', `source=${source} dropped=${rxBuffer.length}`);
          rxBuffer = Buffer.alloc(0);
        }
        break;
      }

      if (sohIndex > 0) {
        logSerialDebug('buffer_trim', `source=${source} dropped=${sohIndex}`);
        rxBuffer = rxBuffer.subarray(sohIndex);
      }

      const eotIndex = rxBuffer.indexOf(EOT, 1);
      if (eotIndex === -1) {
        if (rxBuffer.length > 4096) {
          logSerialDebug('buffer_overflow', `source=${source} len=${rxBuffer.length}`);
          rxBuffer = rxBuffer.subarray(-512);
        }
        break;
      }

      const frame = rxBuffer.subarray(0, eotIndex + 1);
      rxBuffer = rxBuffer.subarray(eotIndex + 1);
      emitFrame(frame, `${source}:soh_eot`);
    }
  }

  port.on('data', (chunk) => {
    const hexHead = chunk.subarray(0, Math.min(8, chunk.length)).toString('hex');
    logSerialDebug('serial_rx', `bytes=${chunk.length} hex=${hexHead}`);
    rxBuffer = Buffer.concat([rxBuffer, chunk]);
    extractFramesFromBuffer('stream');

    if (rxBuffer.length > 8192) {
      rxBuffer = rxBuffer.subarray(rxBuffer.length - 512);
    }
  });

  port.on('error', (error) => {
    console.error('Serial runtime error:', error.message);
  });
}

ensureJsonFile(DATA_FILE, []);
ensureJsonFile(USERS_FILE, []);

io.on('connection', (socket) => {
  socket.emit('punti_emit', { tabellone: { ...lastTabelloneState } });
});

startSerialReader();

server.listen(PORT, HOST, () => {
  console.log(`dmbScore Node server listening on http://${HOST}:${PORT}`);
});
