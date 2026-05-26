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
const DEBUG_SERIAL = process.env.DEBUG_SERIAL === '1';

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

function parseTabellone(serialString) {
  const type = serialString.slice(2, 3);
  if (type !== 'N' && type !== 'R') {
    return null;
  }

  let i = 0;
  let h = 0;

  if (type === 'N') {
    i = 28;
  }

  if (type === 'R') {
    i = 0;
    if (serialString.slice(15, 16) === 'G') {
      h = 11;
    }
    if (serialString.slice(28, 29) === 'W') {
      h = 0;
      i = 22;
    }
  }

  const minLen = i + h + 49;
  if (serialString.length < minLen) {
    return null;
  }

  const tabellone = {
    R: serialString.slice(i + 3, i + 4),
    G: serialString.slice(i + 5, i + 6),
    W: serialString.slice(i + 7, i + 8),
    w: serialString.slice(i + 9, i + 10),
    timer: serialString.slice(i + h + 15, i + h + 23),
    XX: serialString.slice(i + h + 28, i + h + 30),
    YY: serialString.slice(i + h + 31, i + h + 33),
    A: serialString.slice(i + h + 35, i + h + 36),
    B: serialString.slice(i + h + 37, i + h + 38),
    b: serialString.slice(i + h + 38, i + h + 39),
    C: serialString.slice(i + h + 41, i + h + 42),
    D: serialString.slice(i + h + 43, i + h + 44),
    d: serialString.slice(i + h + 44, i + h + 45),
    P: serialString.slice(i + h + 46, i + h + 47),
    PR: serialString.slice(i + h + 48, i + h + 49),
  };

  if (serialString.slice(i + h + 15, i + h + 17) === ' 0') {
    const secondsChunk = serialString.slice(i + h + 18, i + h + 20);
    if (Number.parseInt(secondsChunk, 10) <= 9) {
      tabellone.timer = serialString.slice(i + h + 19, i + h + 23).replace('.', ':');
    }
  }

  return tabellone;
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
  const delimiter = Buffer.from([0x02, 0x20, 0x20, 0x04]);
  let rxBuffer = Buffer.alloc(0);
  let flushTimer = null;
  const SERIAL_IDLE_FLUSH_MS = 25;

  const port = new SerialPort({
    path: SERIAL_PORT,
    baudRate: SERIAL_BAUD,
    autoOpen: false,
  });

  port.open((error) => {
    if (error) {
      console.error(`Serial open error (${SERIAL_PORT}):`, error.message);
      return;
    }
    console.log(`Serial Start on ${SERIAL_PORT} @ ${SERIAL_BAUD}`);
  });

  function emitFrame(frameBuf, source) {
    const serialString = frameBuf.toString('latin1');

    if (!serialString || serialString.length < 8) {
      logSerialDebug('frame_drop', `source=${source} len=${serialString.length}`);
      return;
    }

    logSerialDebug('frame_complete', `source=${source} len=${serialString.length}`);
    const parsedTabellone = parseTabellone(serialString);
    if (!parsedTabellone) {
      logSerialDebug('frame_skip', `source=${source} reason=not_scoreboard_frame`);
      return;
    }
    const tabellone = mergeTabelloneState(parsedTabellone);
    logSerialDebug('ws_emit', `XX=${tabellone.XX} YY=${tabellone.YY} timer=${(tabellone.timer || '').trim()}`);
    io.volatile.emit('punti_emit', { tabellone });
  }

  function flushFramesFromBuffer(source) {
    while (true) {
      const endIndex = rxBuffer.indexOf(delimiter);
      if (endIndex === -1) {
        break;
      }

      const frame = rxBuffer.subarray(0, endIndex);
      rxBuffer = rxBuffer.subarray(endIndex + delimiter.length);
      emitFrame(frame, source);
    }
  }

  function scheduleIdleFlush() {
    if (flushTimer) {
      clearTimeout(flushTimer);
    }

    flushTimer = setTimeout(() => {
      flushTimer = null;
      if (rxBuffer.length > 0) {
        const frame = rxBuffer;
        rxBuffer = Buffer.alloc(0);
        emitFrame(frame, 'idle_flush');
      }
    }, SERIAL_IDLE_FLUSH_MS);
  }

  port.on('data', (chunk) => {
    logSerialDebug('serial_rx', `bytes=${chunk.length}`);
    rxBuffer = Buffer.concat([rxBuffer, chunk]);
    flushFramesFromBuffer('delimiter');
    scheduleIdleFlush();

    if (rxBuffer.length > 8192) {
      rxBuffer = rxBuffer.subarray(rxBuffer.length - 2048);
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
