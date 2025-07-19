import logging
import os
import threading
import datetime
import json
import time
from functools import wraps
from flask import (
    Flask, request, render_template_string, redirect, url_for, Response, session
)
from plexapi.server import PlexServer
from dotenv import load_dotenv

load_dotenv()

# Logging setup
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
log_file = os.path.join(LOG_DIR, "starsync.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'supersecretkey')

import time
app_start_time = time.time()

@app.before_request
def force_logout_on_restart():
    last_start = session.get('app_start_time')
    if last_start != app_start_time:
        session.clear()
        session['app_start_time'] = app_start_time

# Helper functions for environment variables without fallback defaults
def getenv_str(name):
    val = os.getenv(name)
    return val if val else None

def getenv_float(name):
    val = getenv_str(name)
    if val is None:
        return None
    try:
        return float(val)
    except ValueError:
        return None

def getenv_int(name):
    val = getenv_str(name)
    if val is None:
        return None
    try:
        return int(val)
    except ValueError:
        return None

def getenv_bool(name):
    val = getenv_str(name)
    if val is None:
        return False
    return val.lower() in ('true', '1', 'yes')

def getenv_list(name):
    val = getenv_str(name)
    if val:
        return [v.strip() for v in val.split(',') if v.strip()]
    return []

# Credentials from env, no fallbacks
APP_USERNAME = getenv_str('APP_USERNAME')
APP_PASSWORD = getenv_str('APP_PASSWORD')

CONFIG_FILE = "config/settings.json"
PLEX_URL = getenv_str('PLEX_URL')
PLEX_TOKEN = getenv_str('PLEX_TOKEN')
BATCH_SIZE = getenv_int('BATCH_SIZE')

DEFAULT_SETTINGS = {
    "libraries": getenv_list('LIBRARY_NAME'),
    "rating_style": getenv_str('RATING_STYLE'),
    "rating_value": getenv_float('TARGET_RATING'),
    "override_rating": getenv_bool('OVERRIDE_RATING'),
    "batch_interval_minutes": getenv_int('BATCH_INTERVAL_MINUTES'),
}

# Globals and locks
rating_log = []
log_lock = threading.Lock()
listeners = []

batch_lock = threading.Lock()
batch_running = False

def add_log_entry(text):
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_line = f"{timestamp} - {text}"
    with log_lock:
        rating_log.append(log_line)
        if len(rating_log) > 500:
            rating_log.pop(0)
        for q in listeners:
            q.append(log_line)
    logging.info(text)

def save_settings(settings):
    try:
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
        add_log_entry("Settings saved.")
    except Exception as e:
        add_log_entry(f"Error saving settings: {e}")

def load_settings():
    if not os.path.isfile(CONFIG_FILE):
        add_log_entry("Settings file not found. Creating from environment/defaults.")
        save_settings(DEFAULT_SETTINGS)
        return DEFAULT_SETTINGS.copy()

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        add_log_entry("Settings loaded from file.")
        merged = {**DEFAULT_SETTINGS, **data}
        merged['override_rating'] = bool(merged.get('override_rating', False))
        return merged
    except Exception as e:
        add_log_entry(f"Failed to load settings: {e}")
        return DEFAULT_SETTINGS.copy()

plex = PlexServer(PLEX_URL, PLEX_TOKEN)

def get_music_libraries():
    try:
        return [s.title for s in plex.library.sections() if s.type in ('music', 'artist')]
    except Exception as e:
        add_log_entry(f"Error fetching libraries: {e}")
        return []

def get_music_lib(name):
    try:
        return plex.library.section(name)
    except Exception as e:
        add_log_entry(f"Library fetch error for {name}: {e}")
        return None

def load_music_libs(lib_names):
    libs = []
    for name in lib_names:
        lib = get_music_lib(name)
        if lib:
            libs.append(lib)
        else:
            add_log_entry(f"Warning: Library '{name}' not found or unavailable")
    return libs

settings = load_settings()
SELECTED_LIBRARIES = settings["libraries"]
music_libs = load_music_libs(SELECTED_LIBRARIES)
TARGET_RATING_STYLE = settings["rating_style"]
TARGET_RATING_VALUE = settings["rating_value"]
OVERRIDE_RATING = settings["override_rating"]
BATCH_INTERVAL_MINUTES = settings.get("batch_interval_minutes", 60)

add_log_entry("=== Starting StarSync ===")
add_log_entry(f"Libraries: {SELECTED_LIBRARIES}")
add_log_entry(f"Rating style: {TARGET_RATING_STYLE}")
add_log_entry(f"Target rating value: {TARGET_RATING_VALUE}")
add_log_entry(f"Override rating: {OVERRIDE_RATING}")
add_log_entry(f"Batch interval (minutes): {BATCH_INTERVAL_MINUTES}")

def check_auth(username, password):
    return username == APP_USERNAME and password == APP_PASSWORD

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        if check_auth(username, password):
            session['logged_in'] = True
            next_page = request.args.get('next') or url_for('home')
            return redirect(next_page)
        else:
            error = "Invalid credentials"
    return render_template_string('''
        <!DOCTYPE html>
        <html>
        <head><title>Login - StarSync</title></head>
        <body style="background:#111; color:#eee; font-family:sans-serif; padding:20px;">
            <h2>Login to StarSync</h2>
            {% if error %}
            <p style="color:red;">{{ error }}</p>
            {% endif %}
            <form method="POST">
                <label>Username:<br><input name="username" required></label><br><br>
                <label>Password:<br><input name="password" type="password" required></label><br><br>
                <button type="submit">Login</button>
            </form>
        </body>
        </html>
    ''', error=error)

@app.route('/logout')
@login_required
def logout():
    session.clear()
    return redirect(url_for('login'))

def convert_to_plex_rating(style, value):
    try:
        if style == '1star':
            return 10 if value >= 1 else 0
        return max(2, min(10, (value / 5.0) * 10))
    except Exception:
        return 6

def rate_tracks(tracks):
    rated, updated, skipped = 0, 0, 0
    plex_rating = convert_to_plex_rating(TARGET_RATING_STYLE, TARGET_RATING_VALUE)

    for idx, track in enumerate(tracks, 1):
        try:
            curr = track.userRating
            if curr is None:
                track.rate(plex_rating)
                rated += 1
                add_log_entry(f"[{idx}] Rated: {track.title}")
            elif OVERRIDE_RATING and abs(curr - plex_rating) > 0.01:
                track.rate(plex_rating)
                updated += 1
                add_log_entry(f"[{idx}] Updated: {track.title}")
            else:
                skipped += 1
        except Exception as e:
            add_log_entry(f"Error rating track {track.title}: {e}")
    return rated, updated, skipped

def rate_new_tracks(limit=None):
    global batch_running
    if not batch_lock.acquire(blocking=False):
        add_log_entry("Batch already running, skipping this trigger.")
        return
    batch_running = True
    try:
        for lib in music_libs:
            add_log_entry(f"Processing library: {lib.title}")
            try:
                tracks = lib.searchTracks(sort='addedAt:desc', maxresults=limit)
                if not tracks:
                    add_log_entry(f"No tracks in {lib.title}")
                    continue
                rated, updated, skipped = rate_tracks(tracks)
                add_log_entry(f"{lib.title}: Rated {rated}, Updated {updated}, Skipped {skipped}")
            except Exception as e:
                add_log_entry(f"Fetch error in {lib.title}: {e}")
    finally:
        batch_running = False
        batch_lock.release()

batch_thread = None
batch_thread_stop_event = threading.Event()

def periodic_batch_trigger():
    add_log_entry(f"Periodic batch trigger thread started, interval: {BATCH_INTERVAL_MINUTES} minutes")
    while not batch_thread_stop_event.is_set():
        if BATCH_INTERVAL_MINUTES == 0:
            add_log_entry("Batch interval is 0 - periodic batch trigger disabled.")
            break

        time.sleep(BATCH_INTERVAL_MINUTES * 60)
        if batch_thread_stop_event.is_set():
            break
        add_log_entry("Periodic batch trigger started")
        rate_new_tracks(limit=BATCH_SIZE)
        add_log_entry("Periodic batch trigger finished")

def start_batch_thread():
    global batch_thread, batch_thread_stop_event
    if batch_thread is not None and batch_thread.is_alive():
        batch_thread_stop_event.set()
        batch_thread.join()
    batch_thread_stop_event.clear()
    if BATCH_INTERVAL_MINUTES > 0:
        batch_thread = threading.Thread(target=periodic_batch_trigger, daemon=True)
        batch_thread.start()
        add_log_entry(f"Batch thread started with interval {BATCH_INTERVAL_MINUTES} minutes")
    else:
        add_log_entry("Batch thread NOT started because batch interval is set to 0")

start_batch_thread()

@app.route('/')
@login_required
def home():
    return render_template_string('''
    <html><head><title>StarSync</title>
    <style>body{font-family:sans-serif;background:#111;color:#eee;padding:20px}
    button{padding:10px;margin:5px;background:#444;color:white;border:none;cursor:pointer}
    pre{background:#222;padding:10px;height:400px;overflow-y:scroll;white-space:pre-wrap;word-break:break-word;}
    </style>
    <script>
        let es = new EventSource("/stream");
        es.onmessage = e => {
            let box = document.getElementById("log");
            box.textContent += e.data + "\\n";
            box.scrollTop = box.scrollHeight;
        };
        function disableForms() {
            document.querySelectorAll("button").forEach(btn => btn.disabled = true);
        }
    </script>
    </head><body>
        <h1>StarSync</h1>
        <p><a href="{{ url_for('logout') }}" style="color:#faa;">Logout</a></p>
        <form method="POST" action="/manual-trigger" onsubmit="disableForms()">
            <button>Trigger: All Tracks</button>
        </form>
        <form method="POST" action="/trigger-last-batch" onsubmit="disableForms()">
            <button>Trigger: Last Batch</button>
        </form>
        <form method="GET" action="/settings">
            <button>Settings</button>
        </form>
        <form method="POST" action="/reset-ratings" onsubmit="disableForms()">
            <button style="background:#a44;">Reset Ratings</button>
        </form>
        <pre id="log">{{ log_content }}</pre>
    </body></html>
    ''', log_content='\n'.join(rating_log))

@app.route('/stream')
@login_required
def stream():
    def event_stream(q):
        while True:
            if q:
                line = q.pop(0)
                yield f"data: {line}\n\n"
            else:
                time.sleep(0.1)
    q = []
    listeners.append(q)
    return Response(event_stream(q), content_type='text/event-stream')

@app.route('/manual-trigger', methods=['POST'])
@login_required
def manual_trigger():
    threading.Thread(target=lambda: rate_new_tracks(limit=None), daemon=True).start()
    return redirect(url_for('home'))

@app.route('/trigger-last-batch', methods=['POST'])
@login_required
def trigger_last_batch():
    threading.Thread(target=lambda: rate_new_tracks(limit=BATCH_SIZE), daemon=True).start()
    return redirect(url_for('home'))

@app.route('/plex-webhook', methods=['POST'])
def plex_webhook():
    add_log_entry("Webhook received - start")
    try:
        payload = request.form.get('payload')
        if not payload:
            add_log_entry("No payload received in form data")
            return 'Bad Request: Missing payload', 400

        data = json.loads(payload)
        event = data.get('event', '')
        section = data.get("Metadata", {}).get("librarySectionTitle", '')
        add_log_entry(f"Webhook: {event} in {section}")

        if 'new' in event.lower() and section in SELECTED_LIBRARIES:
            threading.Thread(target=lambda: rate_new_tracks(limit=BATCH_SIZE), daemon=True).start()
            return '', 204

        return 'Ignored', 200
    except Exception as e:
        add_log_entry(f"Webhook error: {e}")
        return 'Error', 500

@app.route('/reset-ratings', methods=['POST'])
@login_required
def reset_ratings():
    def reset():
        for lib in music_libs:
            try:
                tracks = lib.searchTracks()
                for track in tracks:
                    if track.userRating is not None:
                        track.rate(None)
                        add_log_entry(f"Cleared: {track.title}")
            except Exception as e:
                add_log_entry(f"Error in {lib.title}: {e}")
    threading.Thread(target=reset, daemon=True).start()
    return redirect(url_for('home'))

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    global TARGET_RATING_STYLE, TARGET_RATING_VALUE, SELECTED_LIBRARIES, music_libs, OVERRIDE_RATING, BATCH_INTERVAL_MINUTES
    
    libraries = get_music_libraries()

    if request.method == 'POST':
        libs = request.form.getlist('libraries')
        style = request.form.get('rating_style')
        val = request.form.get('rating_value')
        override = request.form.get('override_rating')
        batch_interval = request.form.get('batch_interval_minutes')

        valid_libs = [lib for lib in libs if lib in libraries]
        if valid_libs:
            SELECTED_LIBRARIES[:] = valid_libs
            music_libs[:] = load_music_libs(SELECTED_LIBRARIES)
            add_log_entry(f"Libraries changed to: {', '.join(SELECTED_LIBRARIES)}")
        else:
            add_log_entry("Invalid library selection attempted or no libraries selected.")

        if style in ['1star', '5stars', '5stars_half']:
            TARGET_RATING_STYLE = style
        else:
            add_log_entry(f"Invalid rating style: {style}")

        try:
            if TARGET_RATING_STYLE == '1star':
                val_f = float(val)
                if val_f < 0 or val_f > 1:
                    raise ValueError("1star rating must be 0 or 1")
            elif TARGET_RATING_STYLE == '5stars':
                val_f = int(val)
                if val_f < 1 or val_f > 5:
                    raise ValueError("5stars rating must be 1-5 integer")
            elif TARGET_RATING_STYLE == '5stars_half':
                val_f = float(val)
                if val_f < 1 or val_f > 5 or (val_f * 2) % 1 != 0:
                    raise ValueError("5stars_half rating must be 1-5 in 0.5 steps")
            else:
                val_f = 5.0
            TARGET_RATING_VALUE = val_f
        except Exception as e:
            add_log_entry(f"Invalid rating value submitted: {val} ({e})")

        OVERRIDE_RATING = (override == 'on')

        try:
            batch_int = int(batch_interval)
            if batch_int < 0:
                raise ValueError("Batch interval must be >= 0")
            BATCH_INTERVAL_MINUTES = batch_int
            add_log_entry(f"Batch interval set to {BATCH_INTERVAL_MINUTES} minutes")
        except Exception as e:
            add_log_entry(f"Invalid batch interval submitted: {batch_interval} ({e})")
        
        add_log_entry(f"Rating style set to: {TARGET_RATING_STYLE}, Rating value set to: {TARGET_RATING_VALUE}")
        add_log_entry(f"Override rating set to: {OVERRIDE_RATING}")

        new_settings = {
            "libraries": SELECTED_LIBRARIES,
            "rating_style": TARGET_RATING_STYLE,
            "rating_value": TARGET_RATING_VALUE,
            "override_rating": OVERRIDE_RATING,
            "batch_interval_minutes": BATCH_INTERVAL_MINUTES,
        }
        save_settings(new_settings)
        start_batch_thread()
        return redirect(url_for('home'))

    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Settings - StarSync</title>
        <style>
            body { font-family: Arial, sans-serif; background: #111; color: #eee; padding: 20px; }
            label { display: block; margin-top: 15px; }
            input, select, button { font-size: 1em; padding: 5px; margin-top: 5px; }
            button { cursor: pointer; }
            .info { font-size: 0.9em; color: #ccc; margin-top: 5px; }
        </style>
        <script>
            function updateRatingValueInput() {
                const style = document.getElementById('rating_style').value;
                const valInput = document.getElementById('rating_value');
                if (style === '1star') {
                    valInput.min = 0;
                    valInput.max = 1;
                    valInput.step = 1;
                    valInput.value = Math.round(valInput.value);
                } else if (style === '5stars') {
                    valInput.min = 1;
                    valInput.max = 5;
                    valInput.step = 1;
                    valInput.value = Math.round(valInput.value);
                } else if (style === '5stars_half') {
                    valInput.min = 1;
                    valInput.max = 5;
                    valInput.step = 0.5;
                }
            }
        </script>
    </head>
    <body>
        <h1>Settings</h1>
        <form method="POST">
            <label>Libraries (select one or more):
                <select name="libraries" multiple size="5" required>
                    {% for lib in libraries %}
                        <option value="{{ lib }}" {% if lib in selected_libraries %}selected{% endif %}>{{ lib }}</option>
                    {% endfor %}
                </select>
            </label>
            <label>Rating Style:
                <select name="rating_style" id="rating_style" onchange="updateRatingValueInput()">
                    <option value="1star" {% if rating_style == '1star' %}selected{% endif %}>1 star</option>
                    <option value="5stars" {% if rating_style == '5stars' %}selected{% endif %}>5 stars (integers)</option>
                    <option value="5stars_half" {% if rating_style == '5stars_half' %}selected{% endif %}>5 stars (half steps)</option>
                </select>
            </label>
            <label>Rating Value:
                <input id="rating_value" name="rating_value" type="number" value="{{ rating_value }}" step="1" min="1" max="5" required>
            </label>
            <label>
                <input type="checkbox" name="override_rating" {% if override_rating %}checked{% endif %}> Override existing ratings
            </label>
            <label>Batch Interval (minutes):
                <input type="number" name="batch_interval_minutes" value="{{ batch_interval }}" min="0" required>
                <div class="info">Set 0 to disable periodic batch triggers</div>
            </label>
            <button type="submit">Save Settings</button>
            <a href="{{ url_for('home') }}" style="color:#ccc; margin-left: 15px;">Return To Home</a>
        </form>
        <script>updateRatingValueInput();</script>
    </body>
    </html>
    """, 
    libraries=libraries,
    selected_libraries=SELECTED_LIBRARIES,
    rating_style=TARGET_RATING_STYLE,
    rating_value=TARGET_RATING_VALUE,
    override_rating=OVERRIDE_RATING,
    batch_interval=BATCH_INTERVAL_MINUTES)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5454)
