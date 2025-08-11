from flask import Flask, render_template, jsonify, request
import random
import pyodbc
import logging

app = Flask(__name__)

DATABASE_CONFIG = {
    'server': 'localhost\\SQLEXPRESS', 
    'database': 'Kelimeler',
    'driver': '{ODBC Driver 17 for SQL Server}'
}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self):
        self.connection_string = (
    f"DRIVER={DATABASE_CONFIG['driver']};"
    f"SERVER={DATABASE_CONFIG['server']};"
    f"DATABASE={DATABASE_CONFIG['database']};"
    f"Trusted_Connection=yes;"
)
        self.words_cache = []
        self.load_words()
    
    def get_connection(self):
        try:
            connection = pyodbc.connect(self.connection_string)
            return connection
        except Exception as e:
            logger.error(f"Veritabanı bağlantı hatası: {e}")
            return None
    
    def load_words(self):
        try:
            conn = self.get_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute("SELECT kelime FROM kelimeler WHERE kelime IS NOT NULL")
                rows = cursor.fetchall()
                self.words_cache = [row[0].strip() for row in rows if row[0] and row[0].strip()]
                conn.close()
                logger.info(f"{len(self.words_cache)} kelime yüklendi")
                if not self.words_cache:
                    self.use_default_words()
            else:
                self.use_default_words()
        except Exception as e:
            logger.error(f"Kelime yükleme hatası: {e}")
            self.use_default_words()
    
    def use_default_words(self):
        self.words_cache = [
            "python", "oyun", "bilgisayar", "programlama", "yazılım",
            "klavye", "fare", "ekran", "internet", "teknoloji",
            "merhaba", "kitap", "sanat", "hayat", "sevgi", "aile", "dostluk",
            "sadakat", "ahtapot", "ansiklopedi", "tavuk", "yulaf", "uyku",
            "zaman", "plan", "teleskop", "işlem", "İstanbul", "Türkiye",
            "adam", "araba", "masa", "sandalye", "ev", "okul", "kalem", "defter", "kitaplık",
            "telefon", "saat", "elma", "armut", "kapı", "perde", "halı", "kedi", "köpek", "balık",
            "hello world", "test kelime", "çok güzel"  
        ]
    
    def get_random_word(self):
        if self.words_cache:
            return random.choice(self.words_cache).lower()
        else:
            self.load_words()
            return random.choice(self.words_cache) if self.words_cache else "python"
    
    def refresh_words(self):
        self.load_words()

db_manager = DatabaseManager()
game_sessions = {}

class GameState:
    def __init__(self):
        self.reset_game()
    
    def reset_game(self):
        self.current_word = db_manager.get_random_word()
        self.next_word = self.get_different_word(self.current_word)
        self.typed_letters = ""
        self.current_index = 0
        self.lives = 3
        self.score = 0
        self.game_over = False
        self.word_completed = False
        self.word_count = 0
        self.time_limit = 10.0
        self.game_started = False
        self.skip_spaces()
    
    def get_different_word(self, current):
        next_word = db_manager.get_random_word()
        attempts = 0
        while next_word == current and attempts < 10:
            next_word = db_manager.get_random_word()
            attempts += 1
        return next_word
    
    def skip_spaces(self):
        while (self.current_index < len(self.current_word) and 
               self.current_word[self.current_index] == ' '):
            self.typed_letters += ' '
            self.current_index += 1
    
    def next_word_func(self):
        self.current_word = self.next_word
        self.next_word = self.get_different_word(self.current_word)
        self.typed_letters = ""
        self.current_index = 0
        self.word_completed = False
        self.word_count += 1
        self.game_started = True
        self.time_limit = max(2.0, 10.0 - (self.word_count * 0.5))
        self.skip_spaces()
    
    def handle_keypress(self, key):
        if not self.game_started:
            self.game_started = True

        if (self.current_index < len(self.current_word) and 
            key.lower() == self.current_word[self.current_index].lower()):
            self.typed_letters += self.current_word[self.current_index]  
            self.current_index += 1
            self.score += 10
            self.skip_spaces()
            if self.current_index >= len(self.current_word):
                self.word_completed = True
                self.score += 50
            return {"success": True, "correct": True}
        else:
            if not self.word_completed:
                self.lives -= 1
                if self.lives <= 0:
                    self.game_over = True
            return {"success": True, "correct": False}
    
    def get_state(self):
        return {
            "current_word": self.current_word,
            "next_word": self.next_word,
            "typed_letters": self.typed_letters,
            "current_index": self.current_index,
            "lives": self.lives,
            "score": self.score,
            "game_over": self.game_over,
            "word_completed": self.word_completed,
            "word_count": self.word_count,
            "time_limit": self.time_limit,
            "game_started": self.game_started
        }

@app.route('/')
def index():
    return render_template('game.html')

@app.route('/api/new_game', methods=['POST'])
def new_game():
    session_id = request.json.get('session_id', 'default')
    game_sessions[session_id] = GameState()
    return jsonify(game_sessions[session_id].get_state())

@app.route('/api/keypress', methods=['POST'])
def keypress():
    session_id = request.json.get('session_id', 'default')
    key = request.json.get('key', '')
    
    if session_id not in game_sessions:
        game_sessions[session_id] = GameState()
    
    game = game_sessions[session_id]
    result = game.handle_keypress(key)
    
    response = {
        "keypress_result": result,
        "game_state": game.get_state()
    }
    
    return jsonify(response)

@app.route('/api/next_word', methods=['POST'])
def next_word():
    session_id = request.json.get('session_id', 'default')
    
    if session_id not in game_sessions:
        return jsonify({"error": "Oyun bulunamadı"})
    
    game = game_sessions[session_id]
    
    if game.word_completed:
        game.next_word_func()
    
    return jsonify(game.get_state())

@app.route('/api/game_state', methods=['GET'])
def get_game_state():
    session_id = request.args.get('session_id', 'default')
    
    if session_id not in game_sessions:
        game_sessions[session_id] = GameState()
    
    return jsonify(game_sessions[session_id].get_state())

@app.route('/api/time_up', methods=['POST'])
def time_up():
    session_id = request.json.get('session_id', 'default')
    
    if session_id in game_sessions:
        game_sessions[session_id].game_over = True
        return jsonify(game_sessions[session_id].get_state())
    
    return jsonify({"error": "Oyun bulunamadı"})

@app.route('/api/refresh_words', methods=['POST'])
def refresh_words():
    try:
        db_manager.refresh_words()
        return jsonify({"success": True, "message": f"{len(db_manager.words_cache)} kelime yüklendi"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/api/word_count', methods=['GET'])
def get_word_count():
    return jsonify({"word_count": len(db_manager.words_cache)})

if __name__ == '__main__':
    app.run(debug=True)