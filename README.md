# Connectly — Flask Real-Time Chat

A browser-based direct messaging app with a modern Bootstrap UI, Flask backend, Flask-SocketIO real-time delivery, SQLite history, user registration/login, and desktop notifications.

## Features
- All user actions happen through the browser GUI
- Register and log in with username/password
- Passwords hashed with Werkzeug's password hashing utility
- Real-time direct messaging over Socket.IO
- Contact list and conversation history
- Responsive Bootstrap-inspired chat layout
- Emoji shortcode prompt (e.g. `:smile:`); basic emoji button inserts a shortcode
- Browser notification/toast for messages when the tab is hidden
- SQLite stores accounts and message history

## Requirements
- Python 3.10+
- Internet connection for Bootstrap, Socket.IO client, and fonts from CDNs
- No command-line chat clients; the terminal is only used to start the web server

## Run on Windows / VS Code
1. Extract this ZIP and open the `flask_realtime_chat` folder in VS Code.
2. Open the integrated terminal in the project folder.
3. Create a virtual environment (recommended):

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

4. Install dependencies:

   ```powershell
   python -m pip install -r requirements.txt
   ```

5. Set a session secret for this terminal session:

   ```powershell
   $env:FLASK_SECRET_KEY = "replace-this-with-a-long-random-secret"
   ```

6. Start the web server:

   ```powershell
   python app.py
   ```

7. Open http://127.0.0.1:5000 in your browser.
8. Register a user. To test real-time chat, open a second browser/private window, register another user, and send messages between accounts.

## Database
The application automatically creates `chat.db` in the project folder. It stores usernames, password hashes, and direct messages with timestamps. Passwords are not stored in plaintext.

## Security and privacy
- Messages are stored in readable plaintext in SQLite; they are not encrypted at rest.
- Socket.IO communication is not end-to-end encrypted by this app. On localhost it is intended for development. If deployed, use HTTPS/WSS behind a production server and add appropriate rate limiting, CSRF protections, account recovery, and security review.
- Use unique demo passwords. Do not use credentials from other services.
- Keep `.env` and `chat.db` out of version control.
- This is a student/demo project, not a production-ready secure messenger.

## Troubleshooting
- `ModuleNotFoundError`: activate your virtual environment and run `python -m pip install -r requirements.txt`.
- Port 5000 in use: close the other process or change the port at the bottom of `app.py`.
- Browser page loads but live chat does not: check that the Flask server terminal is still running and the browser has internet access to load the Socket.IO client script from its CDN.
