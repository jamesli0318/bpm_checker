"""
180 BPM Detector - Real-time BPM detection via microphone
"""
from gevent import monkey
monkey.patch_all()

import os
import signal
import sys
import secrets
import logging
from collections import deque

import numpy as np
import sounddevice as sd
import librosa
import gevent
from gevent.lock import RLock
from gevent.event import Event
from flask import Flask, render_template
from flask_socketio import SocketIO, emit

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
# Issue #1: Use secure secret key from environment or generate one
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))

# Issue #9: Explicit CORS configuration
socketio = SocketIO(
    app,
    async_mode='gevent',
    cors_allowed_origins=os.environ.get('CORS_ORIGINS', '*').split(',')
)

# ============================================
# Constants (Issue #17: Named constants)
# ============================================
SAMPLE_RATE = 22050
BUFFER_SECONDS = 3
BUFFER_SIZE = SAMPLE_RATE * BUFFER_SECONDS  # Pre-calculated buffer size
ANALYSIS_INTERVAL = 0.5  # Seconds between BPM analysis
MIN_SAMPLES_FOR_ANALYSIS = SAMPLE_RATE * 2  # Need 2 seconds of audio

TARGET_BPM = 180
TOLERANCE = 5  # ±5 BPM

# ============================================
# Audio State Manager (Issue #2, #5, #6, #7, #12)
# ============================================
class AudioStateManager:
    """
    Manages audio state with proper locking and pre-allocated buffer.
    Addresses: race conditions, memory leaks, global state issues.
    """

    def __init__(self):
        self._lock = RLock()  # Issue #6: Use gevent-compatible lock
        self._shutdown_event = Event()  # Issue #4: Graceful shutdown
        self._is_running = False
        self._audio_stream = None
        self._device_id = None

        # Issue #7: Pre-allocated ring buffer instead of np.concatenate
        self._buffer = np.zeros(BUFFER_SIZE, dtype=np.float32)
        self._buffer_pos = 0
        self._samples_received = 0

    @property
    def is_running(self):
        with self._lock:
            return self._is_running

    @is_running.setter
    def is_running(self, value):
        with self._lock:
            self._is_running = value

    @property
    def device_id(self):
        return self._device_id

    @device_id.setter
    def device_id(self, value):
        self._device_id = value

    def should_shutdown(self):
        return self._shutdown_event.is_set()

    def request_shutdown(self):
        self._shutdown_event.set()

    def add_samples(self, samples):
        """Add samples to ring buffer (thread-safe)."""
        with self._lock:
            n = len(samples)
            if n >= BUFFER_SIZE:
                # If more samples than buffer, keep only the last BUFFER_SIZE
                self._buffer[:] = samples[-BUFFER_SIZE:]
                self._buffer_pos = 0
                self._samples_received = BUFFER_SIZE
            else:
                # Wrap around ring buffer
                end_pos = self._buffer_pos + n
                if end_pos <= BUFFER_SIZE:
                    self._buffer[self._buffer_pos:end_pos] = samples
                else:
                    first_part = BUFFER_SIZE - self._buffer_pos
                    self._buffer[self._buffer_pos:] = samples[:first_part]
                    self._buffer[:n - first_part] = samples[first_part:]
                self._buffer_pos = end_pos % BUFFER_SIZE
                self._samples_received = min(self._samples_received + n, BUFFER_SIZE)

    def get_buffer_copy(self):
        """Get a copy of the current buffer for analysis."""
        with self._lock:
            if self._samples_received < MIN_SAMPLES_FOR_ANALYSIS:
                return None
            # Reconstruct buffer in correct order
            if self._samples_received >= BUFFER_SIZE:
                return np.concatenate([
                    self._buffer[self._buffer_pos:],
                    self._buffer[:self._buffer_pos]
                ])
            else:
                return self._buffer[:self._samples_received].copy()

    def clear_buffer(self):
        """Clear the audio buffer."""
        with self._lock:
            self._buffer.fill(0)
            self._buffer_pos = 0
            self._samples_received = 0

    def start_stream(self):
        """Start audio input stream."""
        with self._lock:
            if self._audio_stream is None or not self._audio_stream.active:
                self._audio_stream = sd.InputStream(
                    device=self._device_id,
                    samplerate=SAMPLE_RATE,
                    channels=1,
                    dtype=np.float32,
                    callback=self._audio_callback,
                    blocksize=1024
                )
                self._audio_stream.start()
                logger.info(f"Audio stream started (device: {self._device_id})")

    def stop_stream(self):
        """Stop audio input stream."""
        with self._lock:
            if self._audio_stream is not None:
                try:
                    if self._audio_stream.active:
                        self._audio_stream.stop()
                    self._audio_stream.close()
                except Exception as e:
                    # Issue #3: Log instead of silently swallowing
                    logger.error(f"Error stopping audio stream: {e}")
                finally:
                    self._audio_stream = None
                    logger.info("Audio stream stopped")

    def _audio_callback(self, indata, frames, time, status):
        """Callback for audio stream."""
        if status:
            logger.warning(f"Audio status: {status}")

        # Convert to mono if stereo
        if len(indata.shape) > 1:
            mono_data = indata[:, 0]
        else:
            mono_data = indata.flatten()

        self.add_samples(mono_data)


# Global state manager instance
state = AudioStateManager()


# ============================================
# BPM Analysis
# ============================================
def analyze_bpm():
    """Analyze the audio buffer and detect BPM."""
    data = state.get_buffer_copy()
    if data is None:
        return None, False

    try:
        tempo, _ = librosa.beat.beat_track(y=data, sr=SAMPLE_RATE)

        # Issue #13: Handle librosa version differences
        if isinstance(tempo, np.ndarray):
            tempo = float(tempo[0]) if len(tempo) > 0 else 0.0
        else:
            tempo = float(tempo)

        is_target_bpm = abs(tempo - TARGET_BPM) <= TOLERANCE
        return round(tempo, 1), is_target_bpm

    except Exception as e:
        logger.error(f"BPM analysis error: {e}")
        return None, False


def bpm_monitor():
    """Background task to monitor BPM and emit updates."""
    logger.info("BPM monitor started")

    # Issue #4: Check shutdown event instead of infinite loop
    while not state.should_shutdown():
        if state.is_running:
            bpm, is_180 = analyze_bpm()
            if bpm is not None:
                socketio.emit('bpm_update', {
                    'bpm': bpm,
                    'is_180': is_180,
                    'target': TARGET_BPM,
                    'tolerance': TOLERANCE
                })
        # Issue #24: Use event wait with timeout for efficient polling
        state._shutdown_event.wait(timeout=ANALYSIS_INTERVAL)

    logger.info("BPM monitor stopped")


# ============================================
# Flask Routes
# ============================================
@app.route('/')
def index():
    return render_template('index.html')


# ============================================
# Socket.IO Event Handlers
# ============================================
@socketio.on('connect')
def handle_connect():
    logger.info('Client connected')
    # Issue #15: Send current state to newly connected client
    emit('status', {'is_running': state.is_running})


@socketio.on('disconnect')
def handle_disconnect():
    logger.info('Client disconnected')


@socketio.on('start')
def handle_start():
    """Handle start event from client."""
    # Issue #11: Basic validation (could add rate limiting here)
    logger.info('Start request received')

    try:
        state.clear_buffer()
        state.start_stream()
        state.is_running = True

        # Issue #14: Send success confirmation to client
        emit('start_ack', {'success': True})
        logger.info('BPM detection started successfully')

    except Exception as e:
        logger.error(f'Error starting BPM detection: {e}')
        # Issue #14: Send error to client
        emit('start_ack', {'success': False, 'error': str(e)})


@socketio.on('stop')
def handle_stop():
    """Handle stop event from client."""
    logger.info('Stop request received')

    state.is_running = False
    state.stop_stream()
    state.clear_buffer()

    # Issue #14: Send confirmation to client
    emit('stop_ack', {'success': True})
    logger.info('BPM detection stopped')


# ============================================
# Device Discovery
# ============================================
def find_input_device():
    """Find an available audio input device."""
    devices = sd.query_devices()
    for i, device in enumerate(devices):
        if device['max_input_channels'] > 0:
            return i, device['name']
    return None, None


# ============================================
# Main Entry Point
# ============================================
if __name__ == '__main__':
    print("Starting 180 BPM Detector...")
    print(f"Target BPM: {TARGET_BPM} (±{TOLERANCE})")

    # Check for input devices
    # Issue #23: Avoid parameter shadowing by using different name
    found_device_id, device_name = find_input_device()
    if found_device_id is None:
        print("\n" + "=" * 50)
        print("ERROR: No audio input device found!")
        print("=" * 50)
        print("\nAvailable devices:")
        print(sd.query_devices())
        print("\nPlease connect a microphone and try again.")
        sys.exit(1)

    state.device_id = found_device_id
    print(f"Using input device: [{found_device_id}] {device_name}")
    print("Open http://localhost:8080 in your browser")
    print("Click 'Start' to begin BPM detection")

    def cleanup(signum=None, frame=None):
        """Graceful shutdown handler."""
        print("\nShutting down...")
        state.request_shutdown()  # Issue #4: Signal shutdown
        state.is_running = False
        state.stop_stream()
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    # Start BPM monitor in background
    socketio.start_background_task(bpm_monitor)

    # Issue #10: Note about production deployment
    # For production, use gunicorn with gevent worker:
    # gunicorn -k geventwebsocket.gunicorn.workers.GeventWebSocketWorker -w 1 app:app
    socketio.run(app, host='0.0.0.0', port=8080, debug=False, allow_unsafe_werkzeug=True)
