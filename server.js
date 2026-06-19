const fs = require('fs');
const path = require('path');
const http = require('http');
const crypto = require('crypto');
const express = require('express');
const session = require('express-session');
const passport = require('passport');
const LocalStrategy = require('passport-local').Strategy;
const bcrypt = require('bcryptjs');
const multer = require('multer');
const nunjucks = require('nunjucks');
const { Server } = require('socket.io');
const { SerialPort } = require('serialport');
const { DelimiterParser } = require('@serialport/parser-delimiter');
let DatabaseSync = null;
try {
  ({ DatabaseSync } = require('node:sqlite'));
} catch (_) {
  DatabaseSync = null;
}

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
const SERIAL_MODE = process.env.SERIAL_MODE || 'soh_eot';
const DEBUG_SERIAL = process.env.DEBUG_SERIAL === '1';
const SERIAL_IDLE_FLUSH_MS = Number(process.env.SERIAL_IDLE_FLUSH_MS || 1200);
const SERIAL_RECONNECT_MS = Number(process.env.SERIAL_RECONNECT_MS || 1500);
const SERIAL_WATCHDOG_MS = Number(process.env.SERIAL_WATCHDOG_MS || 2000);

const DATA_FILE = path.join(__dirname, 'scores.json');
const USERS_FILE = path.join(__dirname, 'users.json');
const AUTH_DB_FILE = path.join(__dirname, 'instance', 'db.sqlite');
const VIDEO_UPLOAD_DIR = path.join(__dirname, 'static', 'uploads', 'videos');
const VIDEO_STATE_FILE = path.join(__dirname, 'video_state.json');
const MAX_VIDEO_UPLOAD_MB = Number(process.env.MAX_VIDEO_UPLOAD_MB || 500);
const ALLOWED_VIDEO_EXTENSIONS = new Set(['.mp4', '.webm', '.mov', '.m4v', '.ogg']);

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
  video_upload: '/video_upload',
  video_select: '/video_select',
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

function sanitizeFilename(name) {
  return name.replace(/[^a-zA-Z0-9._-]/g, '_');
}

function listUploadedVideos() {
  if (!fs.existsSync(VIDEO_UPLOAD_DIR)) {
    return [];
  }
  return fs
    .readdirSync(VIDEO_UPLOAD_DIR)
    .filter((file) => ALLOWED_VIDEO_EXTENSIONS.has(path.extname(file).toLowerCase()))
    .sort((a, b) => a.localeCompare(b));
}

function buildVideoPublicPath(filename) {
  if (!filename) {
    return '';
  }
  return `/static/uploads/videos/${filename}`;
}

function loadVideoState() {
  const state = readJson(VIDEO_STATE_FILE, {
    selectedVideo: '',
    videoEnabled: false,
  });
  if (!state || typeof state !== 'object') {
    return { selectedVideo: '', videoEnabled: false };
  }
  return {
    selectedVideo: typeof state.selectedVideo === 'string' ? state.selectedVideo : '',
    videoEnabled: Boolean(state.videoEnabled),
  };
}

function saveVideoState(state) {
  writeJson(VIDEO_STATE_FILE, state);
}

function resolveActiveVideoFilename(state) {
  const videos = listUploadedVideos();
  if (state.selectedVideo && videos.includes(state.selectedVideo)) {
    return state.selectedVideo;
  }
  return videos.length > 0 ? videos[videos.length - 1] : '';
}

const videoStorage = multer.diskStorage({
  destination: (_req, _file, cb) => cb(null, VIDEO_UPLOAD_DIR),
  filename: (_req, file, cb) => {
    const ext = path.extname(file.originalname || '').toLowerCase();
    const base = path.basename(file.originalname || 'video', ext);
    const safeBase = sanitizeFilename(base).slice(0, 60) || 'video';
    cb(null, `${Date.now()}_${safeBase}${ext}`);
  },
});

const uploadVideo = multer({
  storage: videoStorage,
  limits: { fileSize: MAX_VIDEO_UPLOAD_MB * 1024 * 1024 },
  fileFilter: (_req, file, cb) => {
    const ext = path.extname(file.originalname || '').toLowerCase();
    if (!ALLOWED_VIDEO_EXTENSIONS.has(ext)) {
      cb(new Error('Unsupported video format'));
      return;
    }
    cb(null, true);
  },
});

let authDb = null;
if (DatabaseSync && fs.existsSync(AUTH_DB_FILE)) {
  try {
    authDb = new DatabaseSync(AUTH_DB_FILE);
    console.log(`Auth DB ready: ${AUTH_DB_FILE}`);
  } catch (error) {
    console.warn(`Auth DB open failed (${AUTH_DB_FILE}): ${error.message}`);
  }
}

function randomSalt(length = 16) {
  const alphabet = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
  let out = '';
  const bytes = crypto.randomBytes(length);
  for (let i = 0; i < length; i += 1) {
    out += alphabet[bytes[i] % alphabet.length];
  }
  return out;
}

function makeFlaskPbkdf2Hash(password, iterations = 1000000) {
  const salt = randomSalt(16);
  const digest = crypto.pbkdf2Sync(password, salt, iterations, 32, 'sha256').toString('hex');
  return `pbkdf2:sha256:${iterations}$${salt}$${digest}`;
}

function verifyPassword(storedHash, plainPassword) {
  if (!storedHash || !plainPassword) {
    return false;
  }

  if (storedHash.startsWith('pbkdf2:')) {
    const parts = storedHash.split('$');
    if (parts.length !== 3) {
      return false;
    }

    const methodPart = parts[0];
    const salt = parts[1];
    const expectedHex = parts[2];
    const methodBits = methodPart.split(':');
    const digest = methodBits[1] || 'sha256';
    const iterations = Number(methodBits[2] || 260000);
    if (!Number.isFinite(iterations) || iterations <= 0) {
      return false;
    }

    try {
      const expectedBuf = Buffer.from(expectedHex, 'hex');
      const derivedBuf = crypto.pbkdf2Sync(plainPassword, salt, iterations, expectedBuf.length, digest);
      if (expectedBuf.length !== derivedBuf.length) {
        return false;
      }
      return crypto.timingSafeEqual(expectedBuf, derivedBuf);
    } catch (_) {
      return false;
    }
  }

  if (storedHash.startsWith('$2a$') || storedHash.startsWith('$2b$') || storedHash.startsWith('$2y$')) {
    return bcrypt.compareSync(plainPassword, storedHash);
  }

  return storedHash === plainPassword;
}

function getAuthUserByUsername(username) {
  if (authDb) {
    try {
      const row = authDb
        .prepare('SELECT id, username, password FROM users WHERE username = ? LIMIT 1')
        .get(username);
      if (row) {
        return row;
      }
    } catch (error) {
      console.warn(`Auth DB query by username failed: ${error.message}`);
    }
  }

  const users = loadUsers();
  return users.find((u) => u.username === username) || null;
}

function getAuthUserById(id) {
  if (authDb) {
    try {
      const row = authDb
        .prepare('SELECT id, username, password FROM users WHERE id = ? LIMIT 1')
        .get(Number(id));
      if (row) {
        return row;
      }
    } catch (error) {
      console.warn(`Auth DB query by id failed: ${error.message}`);
    }
  }

  const users = loadUsers();
  return users.find((u) => Number(u.id) === Number(id)) || null;
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
      const user = getAuthUserByUsername(username);
      if (!user) {
        return done(null, false);
      }
      const valid = verifyPassword(user.password, password);
      return done(null, valid ? user : false);
    } catch (error) {
      return done(error);
    }
  })
);

passport.serializeUser((user, done) => done(null, user.id));
passport.deserializeUser((id, done) => {
  const user = getAuthUserById(id);
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

  if (getAuthUserByUsername(username)) {
    return res.render('sign_up.html', { error: 'Username already taken!' });
  }

  if (authDb) {
    try {
      const hashedPassword = makeFlaskPbkdf2Hash(password, 1000000);
      authDb
        .prepare('INSERT INTO users (username, password) VALUES (?, ?)')
        .run(username, hashedPassword);
    } catch (error) {
      return res.render('sign_up.html', { error: `Registration error: ${error.message}` });
    }
  } else {
    const users = loadUsers();
    const hashedPassword = await bcrypt.hash(password, 10);
    const newUser = {
      id: users.length > 0 ? Math.max(...users.map((u) => Number(u.id) || 0)) + 1 : 1,
      username,
      password: hashedPassword,
    };
    users.push(newUser);
    saveUsers(users);
  }

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
  const state = loadVideoState();
  const uploadedVideos = listUploadedVideos();
  const selectedVideo = resolveActiveVideoFilename(state);
  const activeVideoUrl = selectedVideo ? buildVideoPublicPath(selectedVideo) : '';
  res.render('video.html', {
    uploadedVideos,
    selectedVideo,
    activeVideoUrl,
    videoEnabled: state.videoEnabled,
    maxVideoUploadMb: MAX_VIDEO_UPLOAD_MB,
  });
});

app.post('/video_upload', loginRequired, (req, res) => {
  uploadVideo.single('videoFile')(req, res, (err) => {
    if (err) {
      return res.status(400).render('video.html', {
        uploadedVideos: listUploadedVideos(),
        selectedVideo: '',
        activeVideoUrl: '',
        videoEnabled: false,
        maxVideoUploadMb: MAX_VIDEO_UPLOAD_MB,
        uploadError: err.message || 'Upload error',
      });
    }

    if (!req.file) {
      return res.status(400).render('video.html', {
        uploadedVideos: listUploadedVideos(),
        selectedVideo: '',
        activeVideoUrl: '',
        videoEnabled: false,
        maxVideoUploadMb: MAX_VIDEO_UPLOAD_MB,
        uploadError: 'No file selected',
      });
    }

    const state = loadVideoState();
    state.selectedVideo = req.file.filename;
    saveVideoState(state);

    if (state.videoEnabled) {
      io.emit('video_emit', {
        video: 'videoOn',
        src: buildVideoPublicPath(state.selectedVideo),
      });
    }

    return res.redirect('/video');
  });
});

app.post('/video_select', loginRequired, (req, res) => {
  const filename = String(req.body.selectedVideo || '');
  const videos = listUploadedVideos();
  if (!videos.includes(filename)) {
    return res.status(400).render('video.html', {
      uploadedVideos: videos,
      selectedVideo: '',
      activeVideoUrl: '',
      videoEnabled: false,
      maxVideoUploadMb: MAX_VIDEO_UPLOAD_MB,
      uploadError: 'Selected video not found',
    });
  }

  const state = loadVideoState();
  state.selectedVideo = filename;
  saveVideoState(state);

  if (state.videoEnabled) {
    io.emit('video_emit', {
      video: 'videoOn',
      src: buildVideoPublicPath(state.selectedVideo),
    });
  }

  return res.redirect('/video');
});

app.post('/video_upd', (req, res) => {
  const state = loadVideoState();
  const activeFile = resolveActiveVideoFilename(state);
  state.selectedVideo = activeFile;

  if (req.body.video === 'videoOn') {
    state.videoEnabled = true;
    io.emit('video_emit', {
      video: 'videoOn',
      src: activeFile ? buildVideoPublicPath(activeFile) : '',
    });
  }
  if (req.body.video === 'videoOff') {
    state.videoEnabled = false;
    io.emit('video_emit', { video: 'videoOff' });
  }
  saveVideoState(state);
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

function segmentSlice(segment, start, length, fallback = '') {
  if (segment.length < start + length) {
    return fallback;
  }
  return segmentToPrintableString(segment.subarray(start, start + length));
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

  if (scoreSeg.length < 5 || cardsRightSeg.length < 5 || cardsLeftSeg.length < 5 || prioritySeg.length < 1 || roundSeg.length < 1) {
    return null;
  }

  const XX = `${printableFromByte(scoreSeg[0], ' ')}${printableFromByte(scoreSeg[1], ' ')}`;
  const sep = printableFromByte(scoreSeg[2], ':');
  const YY = `${printableFromByte(scoreSeg[3], ' ')}${printableFromByte(scoreSeg[4], ' ')}`;

  const A = segmentSlice(cardsRightSeg, 0, 2, ' 0');
  const B = segmentSlice(cardsRightSeg, 2, 2, ' 0');
  const b = segmentSlice(cardsRightSeg, 4, 1, '0');
  const C = segmentSlice(cardsLeftSeg, 0, 2, ' 0');
  const D = segmentSlice(cardsLeftSeg, 2, 2, ' 0');
  const d = segmentSlice(cardsLeftSeg, 4, 1, '0');

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

function parseCompetitorInfoFrame(frameBuf) {
  // Message 5/6: [SOH][DC3]N[L/R][STX]Bib[STX]Name[STX]Nat[EOT]
  // We recognize these frames so they never get interpreted as scoreboard data.
  if (frameBuf.length < 10) {
    return null;
  }
  if (frameBuf[0] !== SOH || frameBuf[1] !== CMD_DC3 || frameBuf[2] !== 0x4e || frameBuf[frameBuf.length - 1] !== EOT) {
    return null;
  }

  const sideByte = frameBuf[3];
  if (sideByte !== 0x4c && sideByte !== 0x52) {
    return null;
  }

  const segments = [];
  let idx = 4;
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

  if (segments.length < 3) {
    return null;
  }

  return {
    side: sideByte === 0x4c ? 'left' : 'right',
    bib: segmentToPrintableString(segments[0]).trim(),
    name: segmentToPrintableString(segments[1]).trim(),
    nation: segmentToPrintableString(segments[2]).trim(),
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
  const competitorInfo = parseCompetitorInfoFrame(frameBuf);
  if (competitorInfo) {
    return { type: `message_competitor_info_${competitorInfo.side}`, tabellone: null, info: competitorInfo };
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

function parseLegacyAsciiTabellone(s1) {
  if (!s1 || s1.length < 50) {
    return null;
  }

  let i = 0;
  let h = 0;

  if (s1.slice(2, 3) === 'N') {
    i = 28;
  }
  if (s1.slice(2, 3) === 'R') {
    i = 0;
    if (s1.slice(15, 16) === 'G') {
      h = 11;
    }
    if (s1.slice(28, 29) === 'W') {
      h = 0;
      i = 22;
    }
  }

  const tabellone = {
    R: s1.slice(i + 3, i + 4),
    G: s1.slice(i + 5, i + 6),
    W: s1.slice(i + 7, i + 8),
    w: s1.slice(i + 9, i + 10),
    timer: s1.slice(i + h + 15, i + h + 23),
    XX: s1.slice(i + h + 28, i + h + 30),
    YY: s1.slice(i + h + 31, i + h + 33),
    A: s1.slice(i + h + 35, i + h + 36),
    B: s1.slice(i + h + 37, i + h + 38),
    b: s1.slice(i + h + 38, i + h + 39),
    C: s1.slice(i + h + 41, i + h + 42),
    D: s1.slice(i + h + 43, i + h + 44),
    d: s1.slice(i + h + 44, i + h + 45),
    P: s1.slice(i + h + 46, i + h + 47),
    PR: s1.slice(i + h + 48, i + h + 49),
  };

  if (s1.slice(i + h + 15, i + h + 17) === ' 0') {
    const secChunk = s1.slice(i + h + 18, i + h + 20);
    const secInt = Number.parseInt(secChunk, 10);
    if (!Number.isNaN(secInt) && secInt <= 9) {
      tabellone.timer = s1.slice(i + h + 19, i + h + 23).replace('.', ':');
    }
  }

  return tabellone;
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
  let activePort = null;
  let reconnectTimer = null;
  let watchdogTimer = null;
  let ignoreNextCloseEvent = false;

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

  function scheduleReconnect(reason) {
    if (reconnectTimer) {
      return;
    }
    console.warn(`Serial disconnected (${reason}). Retrying in ${SERIAL_RECONNECT_MS}ms...`);
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null;
      connectSerial();
    }, SERIAL_RECONNECT_MS);
  }

  function closeCurrentPort(reason) {
    if (!activePort) {
      return;
    }

    const portToClose = activePort;
    activePort = null;
    rxBuffer = Buffer.alloc(0);

    try {
      portToClose.removeAllListeners('data');
      portToClose.removeAllListeners('error');
      portToClose.removeAllListeners('close');
      portToClose.removeAllListeners('open');
    } catch (_) {
      // no-op
    }

    if (portToClose.isOpen) {
      ignoreNextCloseEvent = true;
      try {
        portToClose.close(() => {});
      } catch (_) {
        // no-op
      }
    }

    logSerialDebug('serial_teardown', `reason=${reason}`);
  }
  

  function startWatchdog() {
    if (watchdogTimer) {
      clearInterval(watchdogTimer);
    }

    watchdogTimer = setInterval(() => {
      if (!activePort || !activePort.isOpen) {
        return;
      }

      // Some adapters don't emit close/error on unplug. Probe device-path visibility.
      if (!fs.existsSync(SERIAL_PORT)) {
        console.warn(`Serial device path missing: ${SERIAL_PORT}`);
        closeCurrentPort('watchdog_path_missing');
        scheduleReconnect('watchdog_path_missing');
      }
    }, SERIAL_WATCHDOG_MS);
  }

  function setupLegacyMode(port) {
    const parser = port.pipe(
      new DelimiterParser({
        delimiter: Buffer.from([0x02, 0x20, 0x20, 0x04]),
        includeDelimiter: true,
      })
    );

    parser.on('data', (frameBuf) => {
      let normalizedFrame = frameBuf;
      const sohIdx = normalizedFrame.indexOf(0x01);
      if (sohIdx > 0) {
        // After reconnect some devices prepend one junk byte (often 0x00):
        // align to SOH so legacy fixed offsets stay correct.
        normalizedFrame = normalizedFrame.subarray(sohIdx);
        logSerialDebug('legacy_align', `dropped=${sohIdx}`);
      }

      const s1 = normalizedFrame.toString('utf8');
      logSerialDebug('frame_complete', `source=legacy len=${s1.length}`);
      const parsed = parseLegacyAsciiTabellone(s1);
      if (!parsed) {
        const hexHead = normalizedFrame.subarray(0, Math.min(16, normalizedFrame.length)).toString('hex');
        logSerialDebug('frame_skip', `source=legacy reason=short_or_invalid hex=${hexHead}`);
        return;
      }

      const tabellone = mergeTabelloneState(parsed);
      logSerialDebug(
        'ws_emit',
        `mode=legacy XX=${tabellone.XX} YY=${tabellone.YY} timer=${(tabellone.timer || '').trim()}`
      );
      io.volatile.emit('punti_emit', { tabellone });
    });

    parser.on('error', (error) => {
      console.error('Serial parser error:', error.message);
      closeCurrentPort('legacy_parser_error');
      scheduleReconnect(`legacy_parser_error:${error.message}`);
    });
  }

  function setupBinaryMode(port) {
    port.on('data', (chunk) => {
      const hexHead = chunk.subarray(0, Math.min(8, chunk.length)).toString('hex');
      logSerialDebug('serial_rx', `bytes=${chunk.length} hex=${hexHead}`);
      rxBuffer = Buffer.concat([rxBuffer, chunk]);
      extractFramesFromBuffer('stream');

      if (rxBuffer.length > 8192) {
        rxBuffer = rxBuffer.subarray(rxBuffer.length - 512);
      }
    });
  }

  function connectSerial() {
    closeCurrentPort('reconnect_attempt');

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

    activePort = port;
    rxBuffer = Buffer.alloc(0);

    port.on('error', (error) => {
      console.error('Serial runtime error:', error.message);
      closeCurrentPort(`runtime_error:${error.message}`);
      scheduleReconnect(`runtime_error:${error.message}`);
    });

    port.on('close', (err) => {
      if (ignoreNextCloseEvent) {
        ignoreNextCloseEvent = false;
        return;
      }

      const reason = err && err.disconnected ? 'disconnected' : 'closed';
      console.warn(`Serial port closed (${reason})`);
      closeCurrentPort(`close:${reason}`);
      scheduleReconnect(`close:${reason}`);
    });

    if (SERIAL_MODE === 'legacy_read_until') {
      setupLegacyMode(port);
    } else {
      setupBinaryMode(port);
    }

    port.open((error) => {
      if (error) {
        console.error(`Serial open error (${SERIAL_PORT}):`, error.message);
        closeCurrentPort(`open_error:${error.message}`);
        scheduleReconnect(`open_error:${error.message}`);
        return;
      }

      console.log(
        `Serial Start on ${SERIAL_PORT} @ ${SERIAL_BAUD} ` +
        `${SERIAL_DATABITS}${SERIAL_PARITY[0]?.toUpperCase() || 'N'}${SERIAL_STOPBITS} ` +
        `rtscts=${SERIAL_RTSCTS} xon=${SERIAL_XON} xoff=${SERIAL_XOFF}`
      );
    });
  }

  startWatchdog();
  connectSerial();
}

if (!fs.existsSync(VIDEO_UPLOAD_DIR)) {
  fs.mkdirSync(VIDEO_UPLOAD_DIR, { recursive: true });
}
ensureJsonFile(DATA_FILE, []);
ensureJsonFile(USERS_FILE, []);
ensureJsonFile(VIDEO_STATE_FILE, {
  selectedVideo: '',
  videoEnabled: false,
});

io.on('connection', (socket) => {
  socket.emit('punti_emit', { tabellone: { ...lastTabelloneState } });
  const state = loadVideoState();
  const activeFile = resolveActiveVideoFilename(state);
  if (state.videoEnabled && activeFile) {
    socket.emit('video_emit', {
      video: 'videoOn',
      src: buildVideoPublicPath(activeFile),
    });
  }
});

startSerialReader();

server.listen(PORT, HOST, () => {
  console.log(`dmbScore Node server listening on http://${HOST}:${PORT}`);
});
