# 180 BPM Detector

Real-time BPM (beats per minute) detection that alerts when music is playing at 180 BPM.

## Features

- Real-time microphone audio analysis
- Visual feedback when target BPM (180) is detected
- Two versions: server-connected and standalone
- Clean, responsive UI

## Quick Start

### Option 1: Standalone (No Server Required)

Simply open `index.html` in your browser. Uses Web Audio API for client-side BPM detection.

### Option 2: Server Version (More Accurate)

```bash
# Install dependencies
pip install -r requirements.txt

# Run server
python app.py

# Open in browser
open http://localhost:8080
```

## Screenshots

The UI displays:
- Large circular BPM indicator
- Green glow when at 180 BPM
- Red indicator when not at target
- Start/Stop controls

## Requirements

### Server Version
- Python 3.9+
- Working microphone
- Modern web browser

### Standalone Version
- Modern web browser with Web Audio API support
- Working microphone

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | Auto-generated | Flask session secret |
| `CORS_ORIGINS` | `*` | Allowed CORS origins |

## How It Works

### Server Version
1. Browser captures microphone audio
2. Audio is streamed to Flask server via WebSocket
3. Server uses librosa for beat tracking
4. BPM updates sent back to browser in real-time

### Standalone Version
1. Browser captures microphone audio via Web Audio API
2. FFT analysis detects bass frequency energy
3. Beat onsets calculated from energy peaks
4. BPM computed from beat intervals

## Production Deployment

For production, use gunicorn instead of the development server:

```bash
gunicorn -k geventwebsocket.gunicorn.workers.GeventWebSocketWorker -w 1 -b 0.0.0.0:8080 app:app
```

See `deploy.md` for detailed deployment instructions.

## Project Structure

```
.
├── app.py                 # Flask server
├── templates/
│   └── index.html         # Server-connected UI
├── index.html             # Standalone UI
├── requirements.txt       # Python dependencies
├── deploy.md              # Deployment guide
├── CLAUDE.md              # AI assistant context
└── README.md              # This file
```

## License

MIT

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

---

Built with Flask, Socket.IO, librosa, and Web Audio API.
