import eventlet
eventlet.monkey_patch()
from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import json
import os
from datetime import datetime
from flask_socketio import SocketIO, emit
#from flask_socketio import emit, join_room, leave_room
from threading import Thread
import time
#import wx
#from flask_serial import Serial
import serial
import socket



app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///db.sqlite"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = "supersecretkey"

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

socketio = SocketIO(app, cors_allowed_origins='*')

serial_message = ""

# User model
class Users(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(250), unique=True, nullable=False)
    password = db.Column(db.String(250), nullable=False)

# Create database
with app.app_context():
    db.create_all()

def punti_emit(tabellone):
    print(tabellone)
    socketio.emit('punti_emit', {'test': tabellone['XX'], 'testy': tabellone['YY']})
    #flask_socketio.emit('punti_emit', {'tabellone': tabellone})

    socketio.emit('punti_emit', {'tabellone': tabellone})

class SerialReadProgram:
    def __init__(self):
        self._running = True

    def terminate(self):
        self._running = False

    def run(self):

        global serial_message
        ser = serial.Serial("/dev/tty.usbserial-AQ02EBEH", 38400)
        #ser = serial.Serial("/dev/ttyUSB0", 38400)
        print("Serial Start")
        while self._running:
            serial_message = ser.read_until(expected=b'\x02  \x04') # ser.readline().decode().strip()  # read serial port
            s1 = serial_message.decode('utf-8')
            print(s1)
            #local_hostname = socketio.__getattribute__("local_hostname")
            #ip_addresses = socket.gethostbyname_ex(local_hostname)[2]
            #filtered_ips = [ip for ip in ip_addresses if not ip.startswith("127.")]
            #first_ip = filtered_ips[:1]
            #print(local_hostname)
            i = 0
            h = 0
            if s1[2:3] == "N":
                i = 28
            if s1[2:3] == "R":
                i = 0
                if s1[15:16] == "G":
                    h = 11
                if s1[28:29] == "W":
                    h = 0
                    i = 22
                    print(s1[28:29])
            tabellone = dict()
            tabellone['R'] = s1[i+3:i+4]
            tabellone['G'] = s1[i+5:i+6]
            tabellone['W'] = s1[i+7:i+8]
            tabellone['w'] = s1[i+9:i+10]
            tabellone['timer'] = s1[i + h + 15:i + h + 23]
            if s1[i + h + 15:i + h + 17] == " 0":
                if int(s1[i + h + 18:i + h + 20]) <= 9:
                    mioTimer = s1[i + h + 19:i + h + 23]#.replace(".", ":")
                    tabellone['timer'] = mioTimer.replace(".", ":")
            tabellone['XX'] = s1[i+h+28:i+h+30]
            tabellone['YY'] = s1[i+h+31:i+h+33]
            tabellone['A'] = s1[i+h+35:i+h+36]
            tabellone['B'] = s1[i+h+37:i+h+38]
            tabellone['b'] = s1[i+h+38:i+h+39]
            tabellone['C'] = s1[i+h+41:i+h+42]
            tabellone['D'] = s1[i+h+43:i+h+44]
            tabellone['d'] = s1[i+h+44:i+h+45]
            tabellone['P'] = s1[i+h+46:i+h+47]
            tabellone['PR'] = s1[i+h+48:i+h+49]

            #punti_emit(tabellone)
            socketio.emit('punti_emit', {'tabellone': tabellone})
            #print(tabellone)
            time.sleep(0.03)

# Data storage file
DATA_FILE = 'scores.json'


def load_scores():
    """Load scores from JSON file"""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return []

def save_scores(scores):
    """Save scores to JSON file"""
    with open(DATA_FILE, 'w') as f:
        json.dump(scores, f, indent=2)


@app.route('/')
def index():
    """Main page showing all games"""
    scores = load_scores()
    miapath = app.root_path
    instancepath = app.instance_path
    colori = dict()
    colori['statoDXColor'] = 'rgba(255,255,255,0%)'
    colori['statoSXColor'] = 'rgba(255,255,255,0%)'

    return render_template('index.html', scores=scores, miapath=miapath, instancepath=instancepath, colori=colori)

@app.route('/index_single')
def index_single():
    """Main page showing all games"""
    scores = load_scores()
    miapath = app.root_path
    instancepath = app.instance_path
    colori = dict()
    colori['statoDXColor'] = 'rgba(255,255,255,0%)'
    colori['statoSXColor'] = 'rgba(255,255,255,0%)'

    return render_template('index_single.html', scores=scores, miapath=miapath, instancepath=instancepath, colori=colori)

# Load user for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return Users.query.get(int(user_id))


# Register route
@app.route('/register', methods=["GET", "POST"])
@login_required
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if Users.query.filter_by(username=username).first():
            return render_template("sign_up.html", error="Username already taken!")

        hashed_password = generate_password_hash(password, method="pbkdf2:sha256")

        new_user = Users(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for("login"))

    return render_template("sign_up.html")

# Login route
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        user = Users.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for("config_game"))
        else:
            return render_template("login.html", error="Invalid username or password")

    return render_template("login.html")

# Logout route
@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))

@app.route('/add_game', methods=['GET', 'POST'])
def add_game():
    """Add a new game"""
    if request.method == 'POST':
        scores = load_scores()
        
        new_game = {
            'id': len(scores) + 1,
            'team1': request.form['team1'],
            'team2': request.form['team2'],
            'score1': int(request.form.get('score1', 0)),
            'score2': int(request.form.get('score2', 0)),
            'sport': request.form['sport'],
            'date': datetime.now().strftime('%Y-%m-%d %H:%M'),
            'status': request.form.get('status', 'Live')
        }
        
        scores.append(new_game)
        save_scores(scores)
        return redirect(url_for('index'))
    
    return render_template('add_game.html')


@app.route('/config', methods=['GET'])
@login_required
def config_game():
    scores = load_scores()
    miapath = app.root_path #.join(app.static_folder)
    files = os.listdir(miapath+'/static/flags/')

    return render_template('config.html', scores=scores, files=files)

@app.route('/video', methods=['GET'])
@login_required
def video():
    return render_template('video.html')

@app.route('/video_upd', methods=['POST'])
def video_upd():
    if request.form['video'] == 'videoOn':
        socketio.emit('video_emit', {'video': 'videoOn'})
    if request.form['video'] == 'videoOff':
        socketio.emit('video_emit', {'video': 'videoOff'})

    return redirect(url_for('video'))

@app.route('/update_score/<int:game_id>', methods=['POST'])
def update_score(game_id):
    """Update score for a specific game"""
    scores = load_scores()
    
    for game in scores:
        if game['id'] == game_id:
            game['team1'] = request.form['team1']
            game['team2'] = request.form['team2']
            game['country1'] = request.form['country1']
            game['country2'] = request.form['country2']
            game['flag1'] = request.form['flag1']
            game['flag2'] = request.form['flag2']
            game['gruppo1'] = request.form['gruppo1']
            game['gruppo2'] = request.form['gruppo2']
            game['rank1'] = request.form['rank1']
            game['rank2'] = request.form['rank2']
            game['classgir1'] = request.form['classgir1']
            game['classgir2'] = request.form['classgir2']
            break
    
    save_scores(scores)

    socketio.emit('info_emit', {'info': game})

    return redirect(url_for('config_game'))

@app.route('/delete_game/<int:game_id>')
def delete_game(game_id):
    """Delete a game"""
    scores = load_scores()
    scores = [game for game in scores if game['id'] != game_id]
    save_scores(scores)
    return redirect(url_for('index'))

@app.route('/api/scores')
def api_scores():
    """API endpoint to get scores as JSON"""
    return jsonify(load_scores())

if __name__ == '__main__':

    #app.run(host='0.0.0.0', port=5000, debug=True)
    serial_read = SerialReadProgram()
    serial_read_thread = Thread(target=serial_read.run)

    serial_read_thread.start()

    socketio.run(app=app, host='0.0.0.0', port=5000, debug=True, log_output=True)


        #print(s1)
