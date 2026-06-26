"""Real-time speech-to-text for the VRChat chatbox.

Always-on capture: a microphone stream is gated by WebRTC voice-activity
detection. While you speak, the accumulated audio is re-transcribed with
faster-whisper every ``partial_interval`` seconds to produce a live partial,
and a final pass is run once you go quiet for ``silence_timeout`` seconds.

The model and CTranslate2 backend are imported lazily inside ``_load_model``
so the app starts fast and runs fine when the STT deps aren't installed.
"""

import os
import queue
import sys
import threading
import time
import traceback


def _debug_log(msg):
    """Append a line to %APPDATA%\\VRCChatbox\\stt_debug.log.

    Temporary instrumentation: the windowed .exe has no console, so this is how
    we capture what actually happens during model load in a frozen build."""
    try:
        from config import get_config_dir
        with open(get_config_dir() / "stt_debug.log", "a", encoding="utf-8") as f:
            f.write(str(msg).rstrip() + "\n")
    except Exception:
        pass

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

try:
    import sounddevice as sd
    SOUNDDEVICE_AVAILABLE = True
except Exception:
    # sounddevice raises (not just ImportError) when the PortAudio DLL is missing
    SOUNDDEVICE_AVAILABLE = False

try:
    import webrtcvad
    WEBRTCVAD_AVAILABLE = True
except ImportError:
    WEBRTCVAD_AVAILABLE = False

# faster_whisper is imported lazily — see _load_model. This flag only reports
# whether the package is importable, for the GUI dependency hint.
try:
    import importlib.util
    FASTER_WHISPER_AVAILABLE = importlib.util.find_spec("faster_whisper") is not None
except Exception:
    FASTER_WHISPER_AVAILABLE = False

SAMPLE_RATE = 16000
FRAME_MS = 30
FRAME_SAMPLES = SAMPLE_RATE * FRAME_MS // 1000  # 480 samples
FRAME_BYTES = FRAME_SAMPLES * 2                 # int16 mono → 960 bytes

ONSET_FRAMES = 3          # ~90ms of speech to start an utterance
PRE_ROLL_FRAMES = 10      # ~300ms kept before onset so the first word isn't clipped
MAX_UTTERANCE_MS = 30000  # hard cap so a runaway buffer can't grow forever

DEPS_AVAILABLE = (
    NUMPY_AVAILABLE and SOUNDDEVICE_AVAILABLE
    and WEBRTCVAD_AVAILABLE and FASTER_WHISPER_AVAILABLE
)

_cuda_dlls_registered = False


def _models_dir():
    """Where faster-whisper caches downloaded models.

    Kept in %APPDATA%\\VRCChatbox\\models alongside the config files instead of
    the default HuggingFace cache, so everything the app owns lives in one place
    and survives reinstalls."""
    from config import get_config_dir
    d = get_config_dir() / "models"
    d.mkdir(parents=True, exist_ok=True)
    return str(d)


def _register_cuda_dll_dirs():
    """Add the nvidia-*-cu12 pip wheels' bin dirs to the Windows DLL search path.

    Those wheels install cuBLAS/cuDNN under site-packages\\nvidia\\<lib>\\bin,
    which isn't on PATH, so CTranslate2's LoadLibrary("cublas64_12.dll") fails
    without this. No-op on non-Windows (the loader finds them via RPATH there)
    and when the wheels aren't installed."""
    global _cuda_dlls_registered
    if _cuda_dlls_registered or sys.platform != "win32" or not hasattr(os, "add_dll_directory"):
        return
    _cuda_dlls_registered = True

    # Candidate "nvidia" roots that may contain "<lib>/bin" trees:
    #  - the installed nvidia namespace package (running from source), and
    #  - PyInstaller's bundle dirs (running from a frozen build).
    # Each nvidia-*-cu12 wheel is a separate <lib> (cublas, cudnn, cuda_runtime,
    # cuda_nvrtc, …); they depend on each other, so every bin dir must be on the
    # search path — notably cudart64_12.dll from cuda_runtime, which cuBLAS and
    # ctranslate2 both load.
    nvidia_roots = []
    try:
        import importlib.util
        spec = importlib.util.find_spec("nvidia")
        if spec and spec.submodule_search_locations:
            nvidia_roots.append(spec.submodule_search_locations[0])
    except Exception:
        pass
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        meipass = getattr(sys, "_MEIPASS", exe_dir)
        for base in {meipass, exe_dir, os.path.join(exe_dir, "_internal")}:
            nvidia_roots.append(os.path.join(base, "nvidia"))
            # PyInstaller may also flatten DLLs into the bundle root itself.
            if os.path.isdir(base):
                try:
                    os.add_dll_directory(base)
                except Exception:
                    pass

    added = []
    for root in nvidia_roots:
        if not os.path.isdir(root):
            continue
        for lib in os.listdir(root):
            bindir = os.path.join(root, lib, "bin")
            if os.path.isdir(bindir) and bindir not in added:
                try:
                    os.add_dll_directory(bindir)
                except Exception:
                    pass
                added.append(bindir)

    # Two distinct load paths need covering:
    #  - os.add_dll_directory above lets ctypes.CDLL resolve ctranslate2.dll's
    #    static dependencies at import time (it uses LOAD_LIBRARY_SEARCH_USER_DIRS).
    #  - PATH is required because CTranslate2 loads cuBLAS/cuDNN LAZILY at first
    #    GPU compute via a plain LoadLibrary("cublas64_12.dll"), which searches
    #    PATH but NOT the add_dll_directory list. Without this, the model builds
    #    fine and then fails on the first encode with "cublas64_12.dll not found".
    if added:
        os.environ["PATH"] = os.pathsep.join(added) + os.pathsep + os.environ.get("PATH", "")

    _debug_log(f"_register_cuda_dll_dirs: nvidia_roots={nvidia_roots}")
    _debug_log(f"_register_cuda_dll_dirs: added dirs={added}")


class WhisperSTTController:
    def __init__(self, on_partial=None, on_final=None, on_state=None):
        # Callbacks (all optional). Called from the worker thread.
        #   on_partial(text)  — live, growing transcription of the current utterance
        #   on_final(text)    — finalized transcription once speech ends
        #   on_state(active)  — True when speech starts, False when it ends
        self.on_partial = on_partial
        self.on_final = on_final
        self.on_state = on_state

        self.config = {}
        self._model = None
        self._model_key = None        # (model_size, compute_device) the loaded model was built with
        self._status = "Idle"
        self._running = False
        self._lock = threading.Lock()

        self._frame_q = queue.Queue()
        self._stream = None
        self._worker = None

    # ── Public API ───────────────────────────────────────────────────────────

    def get_status(self):
        return self._status

    def is_running(self):
        return self._running

    @staticmethod
    def list_input_devices():
        """Return [(index, name), ...] for available input devices."""
        if not SOUNDDEVICE_AVAILABLE:
            return []
        devices = []
        try:
            for i, dev in enumerate(sd.query_devices()):
                if dev.get("max_input_channels", 0) > 0:
                    devices.append((i, dev.get("name", f"Device {i}")))
        except Exception:
            pass
        return devices

    def update_config(self, config):
        """Apply a new config dict, (re)starting the pipeline as needed."""
        old = self.config
        self.config = dict(config or {})

        enabled = self.config.get("enabled", False)
        model_changed = (
            self.config.get("model_size") != old.get("model_size")
            or self.config.get("compute_device") != old.get("compute_device")
        )
        device_changed = self.config.get("device_index") != old.get("device_index")

        if not enabled:
            if self._running:
                self.stop()
            else:
                self._status = "Disabled"
            return

        if not DEPS_AVAILABLE:
            self._status = "Missing dependencies — see Speech tab"
            return

        if self._running and (model_changed or device_changed):
            self.stop()

        if not self._running:
            self.start()

    def start(self):
        if self._running or not DEPS_AVAILABLE:
            return
        self._running = True
        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()

    def stop(self):
        self._running = False
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        # Drain any buffered frames so a restart begins clean.
        try:
            while True:
                self._frame_q.get_nowait()
        except queue.Empty:
            pass

        # Wait for the worker to exit so no transcription is still touching the
        # model when we free it. Skip the join if we're on the worker thread.
        worker = self._worker
        if worker is not None and worker is not threading.current_thread():
            worker.join(timeout=5)
        self._worker = None

        # Release the model so GPU/CPU memory is freed while STT is disabled. It
        # is reloaded on the next start(); nothing GPU-related runs until then.
        self._release_model()

        self._status = "Disabled" if not self.config.get("enabled") else "Stopped"
        # Make sure the typing indicator gets cleared by the consumer.
        self._emit_state(False)

    def _release_model(self):
        self._model = None
        self._model_key = None
        try:
            import gc
            gc.collect()
        except Exception:
            pass

    def cleanup(self):
        self.stop()

    # ── Worker ───────────────────────────────────────────────────────────────

    def _run(self):
        if not self._load_model():
            self._running = False
            return
        if not self._open_stream():
            self._running = False
            return

        self._status = "Listening"
        vad = webrtcvad.Vad(int(self.config.get("aggressiveness", 2)))

        pre_roll = []
        voiced = []
        triggered = False
        voiced_run = 0
        silence_ms = 0
        last_partial = 0.0

        silence_timeout_ms = max(200, int(self.config.get("silence_timeout", 1.0) * 1000))
        partial_interval = max(0.2, float(self.config.get("partial_interval", 0.8)))

        while self._running:
            try:
                frame = self._frame_q.get(timeout=0.5)
            except queue.Empty:
                continue
            if frame is None or len(frame) != FRAME_BYTES:
                continue

            try:
                is_speech = vad.is_speech(frame, SAMPLE_RATE)
            except Exception:
                is_speech = False

            if not triggered:
                pre_roll.append(frame)
                if len(pre_roll) > PRE_ROLL_FRAMES:
                    pre_roll.pop(0)
                voiced_run = voiced_run + 1 if is_speech else 0
                if voiced_run >= ONSET_FRAMES:
                    triggered = True
                    voiced = list(pre_roll)
                    pre_roll = []
                    voiced_run = 0
                    silence_ms = 0
                    last_partial = time.time()
                    self._status = "Speaking"
                    self._emit_state(True)
            else:
                voiced.append(frame)
                silence_ms = 0 if is_speech else silence_ms + FRAME_MS

                now = time.time()
                if now - last_partial >= partial_interval:
                    last_partial = now
                    text = self._transcribe(voiced)
                    if text:
                        self._emit_partial(text)

                utterance_ms = len(voiced) * FRAME_MS
                if silence_ms >= silence_timeout_ms or utterance_ms >= MAX_UTTERANCE_MS:
                    text = self._transcribe(voiced)
                    self._emit_final(text)
                    triggered = False
                    voiced = []
                    voiced_run = 0
                    silence_ms = 0
                    self._status = "Listening"
                    self._emit_state(False)

        self._status = "Disabled" if not self.config.get("enabled") else "Stopped"

    def _load_model(self):
        key = (self.config.get("model_size", "small"),
               self.config.get("compute_device", "auto"))
        if self._model is not None and self._model_key == key:
            return True

        model_size, compute_device = key

        # Build order. "auto" tries GPU then falls back to CPU. An explicit
        # choice is honoured without fallback so the user's selection is clear.
        if compute_device == "cuda":
            attempts = [("cuda", "float16")]
        elif compute_device == "cpu":
            attempts = [("cpu", "int8")]
        else:
            attempts = [("cuda", "float16"), ("cpu", "int8")]

        _debug_log("=== _load_model ===")
        _debug_log(f"frozen={getattr(sys, 'frozen', False)} "
                   f"executable={sys.executable} "
                   f"_MEIPASS={getattr(sys, '_MEIPASS', None)}")
        _debug_log(f"key={key} attempts={attempts} models_dir={_models_dir()}")

        last_err = None
        for device, compute_type in attempts:
            self._status = f"Loading model ({model_size}, {device})…"
            try:
                self._model = self._build_and_warm(model_size, device, compute_type)
                self._model_key = key
                if device == "cpu" and compute_device != "cpu":
                    self._status = "Loaded on CPU (GPU unavailable)"
                _debug_log(f"SUCCESS on device={device}")
                return True
            except Exception as e:
                last_err = e
                self._model = None
                _debug_log(f"FAILED device={device}: {type(e).__name__}: {e}")
                _debug_log(traceback.format_exc())

        # All attempts failed. Show the raw error so we can see what's actually
        # wrong (full traceback is in stt_debug.log in the config dir).
        self._status = f"Load failed: {type(last_err).__name__}: {last_err}"[:300]
        return False

    def _build_and_warm(self, model_size, device, compute_type):
        """Build a model and run it once on silence.

        The warm-up forces the backend's runtime libraries (cuBLAS/cuDNN for
        GPU) to load now. Without it a missing CUDA DLL only fails later, at the
        first real transcription, defeating the CPU fallback."""
        if device == "cuda":
            _register_cuda_dll_dirs()
        _debug_log(f"_build_and_warm: importing faster_whisper (device={device})")
        from faster_whisper import WhisperModel
        _debug_log("_build_and_warm: faster_whisper imported, constructing model")
        model = WhisperModel(
            model_size,
            device=device,
            compute_type=compute_type,
            download_root=_models_dir(),
        )
        _debug_log("_build_and_warm: model constructed, warming up")
        silent = np.zeros(SAMPLE_RATE // 2, dtype=np.float32)
        segments, _ = model.transcribe(silent, beam_size=1, vad_filter=False)
        list(segments)  # consume the generator so transcription actually runs
        _debug_log("_build_and_warm: warm-up complete")
        return model

    def _open_stream(self):
        device_index = self.config.get("device_index")
        try:
            self._stream = sd.RawInputStream(
                samplerate=SAMPLE_RATE,
                blocksize=FRAME_SAMPLES,
                dtype="int16",
                channels=1,
                device=device_index if device_index is not None else None,
                callback=self._audio_callback,
            )
            self._stream.start()
            return True
        except Exception as e:
            self._status = f"Microphone error: {e}"
            self._stream = None
            return False

    def _audio_callback(self, indata, frames, time_info, status):
        # Runs on PortAudio's thread — copy out of the reusable buffer.
        self._frame_q.put(bytes(indata))

    def _transcribe(self, frames):
        if not frames or self._model is None:
            return ""
        try:
            pcm = b"".join(frames)
            audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
            language = self.config.get("language", "auto")
            language = None if not language or language == "auto" else language
            segments, _ = self._model.transcribe(
                audio,
                language=language,
                beam_size=1,
                vad_filter=False,
            )
            return "".join(seg.text for seg in segments).strip()
        except Exception as e:
            self._status = f"Transcribe error: {e}"
            return ""

    # ── Callback dispatch (swallow consumer errors) ──────────────────────────

    def _emit_partial(self, text):
        if self.on_partial:
            try:
                self.on_partial(text)
            except Exception:
                pass

    def _emit_final(self, text):
        if self.on_final:
            try:
                self.on_final(text)
            except Exception:
                pass

    def _emit_state(self, active):
        if self.on_state:
            try:
                self.on_state(active)
            except Exception:
                pass
