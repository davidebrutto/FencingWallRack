
from flask import Flask, render_template, request, redirect, url_for, jsonify
import json
import os
from datetime import datetime
import wx
from flask_serial import Serial
import serial


app = Flask(__name__)
app.config['SERIAL_TIMEOUT'] = 0
app.config['SERIAL_PORT'] = '/dev/tty.usbserial-AQ02EBEH' #'/dev/tty.usbserial-B0043XM7'
app.config['SERIAL_BAUDRATE'] = 38400
app.config['SERIAL_BYTESIZE'] = 8
app.config['SERIAL_PARITY'] = 'N'
app.config['SERIAL_STOPBITS'] = 1

ser = serial.Serial('/dev/tty.usbserial-AQ02EBEH', 38400)

#ser =Serial(app)

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

    while True:
        s = ser.read_until(expected=b'\x02  \x04')
        s1 = s.decode('utf-8')

        puntiDX = s1[29:30]
        puntiSX = s1[32:33]
        scores = load_scores()
        for game in scores:
            if game['id'] == 1:
                game['score1'] = int(puntiDX)
                game['score2'] = int(puntiSX)
                game['status'] = 'Live'
                break

        save_scores(scores)

        # with app.app_context():
        #     api_scores(s1)
        return render_template('index.html', scores=scores, miapath=miapath, instancepath=instancepath, colori=colori)

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

@app.route('/update_score/<int:game_id>', methods=['POST'])
def update_score(game_id):
    """Update score for a specific game"""
    scores = load_scores()
    
    for game in scores:
        if game['id'] == game_id:
            game['score1'] = int(request.form['score1'])
            game['score2'] = int(request.form['score2'])
            game['status'] = request.form.get('status', 'Live')
            break
    
    save_scores(scores)
    return redirect(url_for('index'))

@app.route('/delete_game/<int:game_id>')
def delete_game(game_id):
    """Delete a game"""
    scores = load_scores()
    scores = [game for game in scores if game['id'] != game_id]
    save_scores(scores)
    return redirect(url_for('index'))

@app.route('/api/scores')
def api_scores(msg):
    msg1 = msg.decode('utf-8')
    print(msg1)
    #app.logger.info('Received message: {}'.format(msg))

    """API endpoint to get scores as JSON"""
    return jsonify(load_scores())
def utf8len(s):
    return len(s.encode('utf-8'))

#@ser.on_message()
#def handle_message(msg):
#    api_scores(msg)

if __name__ == '__main__':

    app.run(host='0.0.0.0', port=5000, debug=True)


        #print(s1)
