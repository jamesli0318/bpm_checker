# CLAUDE.md - AI Assistant Context

This file provides context for AI assistants (like Claude) working on this project.

## Project Overview

**180 BPM Detector** - A real-time BPM (beats per minute) detection application that identifies when music is playing at 180 BPM (the target tempo for certain dance music genres).

## Architecture

### Two Products in One Repository

1. **Server-connected version** (`app.py` + `templates/index.html`)
   - Flask-SocketIO backend with gevent
   - Uses librosa for accurate BPM detection
   - Requires Python server running

2. **Standalone version** (`index.html`)
   - Pure client-side Web Audio API
   - No server required
   - Opens directly in browser

### Key Components

```
app.py                  # Flask server with SocketIO
├── AudioStateManager   # Singleton managing audio state with thread-safe ring buffer
├── bpm_monitor()       # Background task for BPM analysis
├── rate_limit()        # Decorator for rate limiting socket events
└── Socket handlers     # connect, disconnect, start, stop

templates/index.html    # Server-connected UI
index.html              # Standalone client-side UI
```

## Development Commands

```bash
# Setup
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run development server
python app.py

# Production (use gunicorn)
gunicorn -k geventwebsocket.gunicorn.workers.GeventWebSocketWorker -w 1 app:app
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | Auto-generated | Flask session secret |
| `CORS_ORIGINS` | `*` | Comma-separated allowed origins |
| `FLASK_ENV` | - | Set to `production` for warnings |

## Code Patterns

### Thread Safety
- All shared state is in `AudioStateManager` class
- Uses `gevent.lock.RLock` for thread safety
- Ring buffer avoids memory allocation in hot path

### Socket.IO Events

| Client -> Server | Server -> Client |
|------------------|------------------|
| `start` | `start_ack` |
| `stop` | `stop_ack` |
| | `bpm_update` |
| | `status` |
| | `error` |

### Rate Limiting
Socket events are rate-limited to 10 calls per 60 seconds per client.

## Testing

```bash
# Manual testing
1. Run: python app.py
2. Open: http://localhost:8080
3. Click Start
4. Play music at ~180 BPM
5. Verify detection

# Standalone testing
1. Open index.html in browser
2. Allow microphone access
3. Click Start
```

## Known Limitations

1. **Single audio source**: All connected clients share one microphone stream (intentional)
2. **BPM accuracy**: ±5 BPM tolerance is configured
3. **Web Audio version**: Client-side detection is less accurate than librosa

## Code Review History

This codebase underwent a 25-point code review. All issues have been addressed:
- See `done.md` for complete fix summary
- Original issues ranged from Critical (security) to Low (code quality)
