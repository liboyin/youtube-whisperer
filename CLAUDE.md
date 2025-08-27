# YOUTUBE\_WHISPERER.md

This file provides combined guidance for developers and users of the `youtube-whisperer` project.

---

# Project Overview

`youtube-whisperer` is a Python application for downloading and transcribing YouTube videos into subtitle files (SRT). It supports both command-line and web service modes, using OpenAI's Whisper model (via the optimized `faster-whisper` library). The system is designed to work efficiently with NVIDIA GPUs for acceleration but can also run in CPU-only mode.

## Key Features

* **Video and Transcript Download**: Downloads YouTube videos, playlists, and existing transcripts.
* **Automatic Transcription**: Uses Whisper (via `faster-whisper`, `ctranslate2`, `onnxruntime`) to generate subtitles when transcripts are unavailable.
* **Web API**: FastAPI-powered RESTful interface for task management.
* **CLI Tool**: Provides equivalent functionality directly in the terminal.
* **Task Queue**: Redis-backed queue system for scalable asynchronous processing.
* **Containerization**: Docker-based multi-container setup with support for GPU and CPU modes.

---

# Key Technologies

* **Backend**: Python, FastAPI
* **Transcription**: `faster-whisper`, `ctranslate2`, `onnxruntime`
* **Video/Audio**: `yt-dlp`, `youtube-transcript-api`, `ffmpeg`
* **Task Queue**: Redis
* **Containerization**: Docker, Docker Compose

---

# Architecture

The application has two main execution environments:

1. **FastAPI Web Service** (`youtube_whisperer.fastapi.app`)

   * Provides REST API endpoints for managing tasks and assets.
   * Stores tasks in Redis for asynchronous processing.

2. **Worker Process** (`youtube_whisperer.worker`)

   * Listens for new tasks from Redis.
   * Downloads videos or transcripts.
   * Runs Whisper-based transcription when no transcript is available.
   * Outputs results as `.seg` intermediate files and `.srt` subtitle files.

### Component Breakdown

**Downloaders** (`youtube_whisperer.downloaders/`):

* `video_downloader.py` – Fetches video files with `yt-dlp`.
* `transcript_downloader.py` – Attempts to fetch YouTube-provided transcripts.
* `playlist_downloader.py` – Expands playlists into individual video tasks.

**Transcriber** (`youtube_whisperer.transcriber/`):

* `waveform_transcriber.py` – Core transcription pipeline.
* `model_parameters.py` – Handles Whisper model selection (CPU/GPU).
* `waveform_loader.py` – Prepares audio data for transcription.

**Formatters** (`youtube_whisperer.formatters/`):

* `segment_to_srt_adaptor.py` – Converts transcription segments to `.srt`.
* `srt_deduplicator.py` – Cleans duplicate entries.
* `segment_handler.py` – Manages Whisper segment data.

**FastAPI Models** (`youtube_whisperer.fastapi.models`):

* `Task` – Represents a transcription request (source, language, mode).
* API response models – Define request/response structures for API calls.

### Data Flow

1. User submits a task (via CLI or REST API).
2. Task is added to Redis queue.
3. Worker picks up the task and checks if it’s a URL or file.
4. For URLs: Attempts transcript download → if unavailable, runs Whisper.
5. Transcribed results are stored as `.seg` and `.srt` files.

---

# Building and Running

## Docker

Two Docker Compose setups are provided:

* **GPU Mode** (requires NVIDIA Docker):

  ```bash
  docker-compose up -d
  ```
* **CPU Mode**:

  ```bash
  docker-compose -f docker-compose.cpu.yaml up -d
  ```

The FastAPI service will be available at `http://localhost:8000`.

## CLI Usage

```bash
python -m youtube_whisperer <urls_or_files>
python -m youtube_whisperer --help
```

## Development Environment

* Install dev dependencies:

  ```bash
  pip install -e ".[dev]"
  ```
* Use provided `devcontainer` for consistent development setup.

---

# Development Conventions

### Testing

* Run all tests: `pytest`
* Run specific directory: `pytest tests/`
* Run specific test: `pytest -k "test_name"`

### Type Checking

* Run type checks with:

  ```bash
  mypy youtube_whisperer/
  ```

### Dependencies

* Managed with `pip`.
* `requirements.txt` updated weekly.
* Dev dependencies via `.[dev]` extras.

---

# Configuration

* `WHISPER_USE_CUDA`: Enables/disables GPU acceleration.
* `WHISPER_ASSETS_DIR`: Directory for storing outputs (default: `./assets/`).
* `WHISPER_MODELS_DIR`: Whisper model cache location (default: `~/.whisper/`).

---

# File Formats

* `.mp4` – Downloaded video
* `.mkv`, `.mp3` – Intermediate audio formats
* `.seg` – Whisper intermediate segment data
* `.srt` – Final subtitle file

---

# Summary

`youtube-whisperer` is a scalable transcription service supporting both CLI and web modes. It integrates YouTube downloaders, Whisper transcription, and subtitle formatting in a containerized, GPU-accelerated environment. With automatic fallback between transcript downloads and Whisper transcription, it balances efficiency and accuracy for large-scale subtitle generation.
