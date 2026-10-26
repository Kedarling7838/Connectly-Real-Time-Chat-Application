import os
import sqlite3
import secrets
import hashlib
import hmac
import re
from datetime import datetime
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, abort
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "chat.db")
SECRET_KEY = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32)

app = Flask(__name__)
app.config["SECRET_KEY"] = SECRET_KEY
socketio = SocketIO(app, cors_allowed_origins=[], async_mode="threading")

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )""")
        db.execute("""CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL,
            recipient_id INTEGER NOT NULL,
            body TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(sender_id) REFERENCES users(id),
            FOREIGN KEY(recipient_id) REFERENCES users(id)
        )""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_messages_pair ON messages(sender_id, recipient_id, id)")

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped

def current_user():
    if "user_id" not in session:
        return None
    with get_db() as db:
        return db.execute("SELECT id, username FROM users WHERE id=?", (session["user_id"],)).fetchone()

EMOJI_SHORTCODES = {
    ":smile:": "😄", ":grin:": "😁", ":joy:": "😂", ":heart:": "❤️",
    ":thumbsup:": "👍", ":thumbs_up:": "👍", ":sad:": "😢",
    ":wink:": "😉", ":wave:": "👋", ":fire:": "🔥", ":tada:": "🎉",
    ":thinking:": "🤔"
}

def render_emoji(text):
    for shortcode, emoji in EMOJI_SHORTCODES.items():
        text = text.replace(shortcode, emoji)
    return text

def conversation_messages(user_id, other_id, limit=300):
    with get_db() as db:
        rows = db.execute("""
            SELECT m.id, m.sender_id, m.recipient_id, m.body, m.created_at,
                   u.username AS sender_name
            FROM messages m JOIN users u ON u.id=m.sender_id
            WHERE (m.sender_id=? AND m.recipient_id=?)
               OR (m.sender_id=? AND m.recipient_id=?)
            ORDER BY m.id DESC LIMIT ?
        """, (user_id, other_id, other_id, user_id, limit)).fetchall()
    return [dict(row) for row in reversed(rows)]

@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("chat"))
    return redirect(url_for("login"))

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not re.fullmatch(r"[A-Za-z0-9_]{3,24}", username):
            flash("Username must be 3–24 characters: letters, numbers, or underscores.", "danger")
            return render_template("auth.html", mode="register")
        if len(password) < 8 or len(password) > 128:
            flash("Password must be at least 8 characters.", "danger")
            return render_template("auth.html", mode="register")
        try:
            with get_db() as db:
                db.execute("INSERT INTO users(username, password_hash, created_at) VALUES (?, ?, ?)",
                           (username, generate_password_hash(password), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            flash("Account created. Please log in.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("That username is already taken.", "danger")
    return render_template("auth.html", mode="register")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        with get_db() as db:
            user = db.execute("SELECT id, username, password_hash FROM users WHERE username=?",
                              (username,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect(url_for("chat"))
        flash("Invalid username or password.", "danger")
    return render_template("auth.html", mode="login")

@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/chat")
@login_required
def chat():
    user = current_user()
    with get_db() as db:
        contacts = db.execute("""
            SELECT u.id, u.username,
              (SELECT body FROM messages m
               WHERE (m.sender_id=u.id AND m.recipient_id=?)
                  OR (m.sender_id=? AND m.recipient_id=u.id)
               ORDER BY m.id DESC LIMIT 1) AS last_message,
              (SELECT created_at FROM messages m
               WHERE (m.sender_id=u.id AND m.recipient_id=?)
                  OR (m.sender_id=? AND m.recipient_id=u.id)
               ORDER BY m.id DESC LIMIT 1) AS last_time
            FROM users u WHERE u.id != ? ORDER BY COALESCE(last_time, '') DESC, u.username COLLATE NOCASE
        """, (user["id"], user["id"], user["id"], user["id"], user["id"])).fetchall()
    return render_template("chat.html", user=user, contacts=[dict(c) for c in contacts])

@app.route("/api/messages/<int:other_id>")
@login_required
def api_messages(other_id):
    user = current_user()
    if other_id == user["id"]:
        return jsonify({"messages": []})
    with get_db() as db:
        other = db.execute("SELECT id, username FROM users WHERE id=?", (other_id,)).fetchone()
    if not other:
        return jsonify({"error": "User not found"}), 404
    return jsonify({"messages": conversation_messages(user["id"], other_id),
                    "other": {"id": other["id"], "username": other["username"]}})

@socketio.on("connect")
def on_connect(auth=None):
    if "user_id" not in session:
        return False
    emit("connected", {"username": session.get("username")})

@socketio.on("open_conversation")
def on_open_conversation(data):
    if "user_id" not in session:
        return
    try:
        other_id = int(data.get("other_id"))
    except (TypeError, ValueError, AttributeError):
        return
    user_id = session["user_id"]
    if other_id == user_id:
        return
    with get_db() as db:
        other = db.execute("SELECT id, username FROM users WHERE id=?", (other_id,)).fetchone()
    if not other:
        emit("chat_error", {"message": "That user does not exist."})
        return
    room = f"pair_{min(user_id, other_id)}_{max(user_id, other_id)}"
    join_room(room)
    emit("conversation_history", {
        "other_id": other_id,
        "other_username": other["username"],
        "messages": conversation_messages(user_id, other_id)
    })

@socketio.on("send_message")
def on_send_message(data):
    if "user_id" not in session:
        return
    try:
        recipient_id = int(data.get("recipient_id"))
        body = render_emoji(str(data.get("body", "")).strip())
    except (TypeError, ValueError, AttributeError):
        return
    if not body:
        return
    if len(body) > 2000:
        emit("chat_error", {"message": "Messages must be 2000 characters or fewer."})
        return
    sender_id = session["user_id"]
    if sender_id == recipient_id:
        return
    with get_db() as db:
        recipient = db.execute("SELECT id FROM users WHERE id=?", (recipient_id,)).fetchone()
        if not recipient:
            emit("chat_error", {"message": "Recipient not found."})
            return
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor = db.execute("INSERT INTO messages(sender_id, recipient_id, body, created_at) VALUES (?, ?, ?, ?)",
                            (sender_id, recipient_id, body, created_at))
        message_id = cursor.lastrowid
        sender = db.execute("SELECT username FROM users WHERE id=?", (sender_id,)).fetchone()
        recipient_name = db.execute("SELECT username FROM users WHERE id=?", (recipient_id,)).fetchone()["username"]
    payload = {"id": message_id, "sender_id": sender_id, "recipient_id": recipient_id,
               "sender_name": sender["username"], "body": body, "created_at": created_at}
    room = f"pair_{min(sender_id, recipient_id)}_{max(sender_id, recipient_id)}"
    # Emit to all clients in the pair room; sender joins it when opening the conversation.
    socketio.emit("new_message", payload, to=room)
    # Also notify recipient clients with a personal room so unopened chats can update later.
    socketio.emit("contact_message", {"from_id": sender_id, "from_name": sender["username"],
                                      "body": body, "created_at": created_at},
                  to=f"user_{recipient_id}")

@socketio.on("identify")
def on_identify():
    if "user_id" in session:
        join_room(f"user_{session['user_id']}")

def run():
    init_db()
    socketio.run(app, host="127.0.0.1", port=5000, debug=False, allow_unsafe_werkzeug=True)

if __name__ == "__main__":
    run()
