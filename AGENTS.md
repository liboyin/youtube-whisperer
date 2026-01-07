# YOUTUBE_WHISPERER.md

This file provides combined guidance for developers and users of the `youtube-whisperer` project.

---

# Project Overview

`youtube-whisperer` is a Python application for downloading and transcribing YouTube videos into subtitle files (SRT). It supports both command-line and web service modes. The system can use OpenAI's Whisper model (via the optimized `faster-whisper` library) for local transcription or leverage Microsoft Azure's AI Speech service for cloud-based transcription. It is designed to work efficiently with NVIDIA GPUs for local acceleration but can also run in CPU-only mode.

## Key Features

*   **Video and Transcript Download**: Downloads YouTube videos, playlists, and existing transcripts.
*   **Multi-Transcriber Support**:
    *   **Local**: Uses Whisper (via `faster-whisper`) to generate subtitles when transcripts are unavailable.
    *   **Cloud**: Uses Azure AI Speech for transcription.
*   **Web API**: FastAPI-powered RESTful interface for task management.
*   **CLI Tool**: Provides equivalent functionality directly in the terminal.
*   **Task Queue**: Redis-backed queue system for scalable asynchronous processing.
*   **Containerization**: Docker-based multi-container setup with support for GPU and CPU modes.

---

# Key Technologies

*   **Backend**: Python, FastAPI
*   **Transcription**:
    *   Local: `faster-whisper`, `ctranslate2`, `onnxruntime`
    *   Cloud: `azure-cognitiveservices-speech`
*   **Video/Audio**: `yt-dlp`, `youtube-transcript-api`, `ffmpeg`
*   **Task Queue**: Redis
*   **Containerization**: Docker, Docker Compose

---

# Architecture

The application has two main execution environments:

1.  **FastAPI Web Service** (`youtube_whisperer.fastapi.app`)
    *   Provides REST API endpoints for managing tasks and assets.
    *   Stores tasks in Redis for asynchronous processing.

2.  **Worker Process** (`youtube_whisperer.worker`)
    *   Listens for new tasks from Redis.
    *   Downloads videos or transcripts.
    *   Routes transcription to the appropriate engine (local Whisper or Azure) based on the task definition.
    *   Outputs results as `.srt` subtitle files.

### Component Breakdown

**Downloaders** (`youtube_whisperer.downloaders/`):

*   `video_downloader.py` – Fetches video files with `yt-dlp`.
*   `transcript_downloader.py` – Attempts to fetch YouTube-provided transcripts.
*   `playlist_downloader.py` – Expands playlists into individual video tasks.

**Transcriber** (`youtube_whisperer.transcriber/`):

*   `whisper_transcriber.py` – Core transcription pipeline using `faster-whisper`.
*   `azure_transcriber.py` – Core transcription pipeline using Azure AI Speech service.
*   `model_parameters.py` – Handles local Whisper model selection (CPU/GPU).
*   `waveform_loader.py` – Prepares audio data for transcription.

**Adaptors** (`youtube_whisperer.adaptors/`):

*   `whisper_adaptor.py` – Converts `faster-whisper` segment objects into a standardized SRT format.
*   `azure_adaptor.py` – Converts Azure Speech SDK results into a standardized SRT format.
*   `srt_deduplicator.py` – Cleans and removes duplicate entries from SRT content.
*   `lang_code_adaptor.py` – Handles language code conversions between different services (e.g., ISO 639-1 to BCP 47).

**FastAPI Models** (`youtube_whisperer.fastapi.models`):

*   `Task` – Represents a transcription request (source, language, transcriber, mode).
*   API response models – Define request/response structures for API calls.

### Data Flow

1.  User submits a task (via CLI or REST API), specifying the `transcriber` (`local` or `azure`).
2.  The task is added to the Redis queue.
3.  A worker picks up the task.
4.  For URLs, it attempts to download a pre-existing transcript. If unavailable, it downloads the video/audio.
5.  The worker calls the specified transcription engine (Whisper or Azure).
6.  The corresponding adaptor (`WhisperSegmentAdaptor` or `AzureRecognitionResultAdaptor`) processes the output.
7.  The result is formatted, deduplicated, and stored as an `.srt` file.

### Future Architecture: Multi-Queue System with Azure Task Pool

To better support concurrent workers and mixed workloads (e.g., GPU-bound local tasks and I/O-bound Azure tasks), the task queue system is planned to be updated to a more robust design combining a multi-queue system with a dedicated task pool for Azure requests.

*   **Unprocessed Queue**: A central queue where all new tasks are initially submitted.
*   **Processing Queue**: When a local worker is ready, it atomically moves a task from the unprocessed queue to this queue using the `BRPOPLPUSH` command. This serves as a reliable claim on the task, ensuring that even if the worker crashes, the task is not lost and can be recovered.
*   **Dead-Letter Queue**: If a task fails processing, it is moved from the Processing Queue to this queue for manual inspection. This prevents "poison pill" tasks from repeatedly blocking the system.

#### Azure Task Pool

On top of this queueing system, a dedicated task pool manages Azure transcription tasks to control concurrency.

*   **Concurrency Limiting**: The pool is implemented using a `ThreadPoolExecutor` with a fixed number of worker threads (e.g., 10). This prevents sending too many simultaneous requests to the Azure service, helping to avoid rate-limiting and manage costs.

#### Combined Data Flow

1.  A worker retrieves a task from the **Unprocessed Queue** and moves it to the **Processing Queue**.
2.  If the task is for the `azure` transcriber, it is submitted to the **Azure Task Pool**.
    *   If a thread is available in the pool, the task begins execution immediately.
    *   If all threads are busy, the task waits in the executor's internal queue until a slot becomes free. The worker that submitted the task is not blocked and can continue processing other items if the system is designed to do so.
3.  If an Azure task fails during its execution in the pool, the error is caught, and the task is moved from the **Processing Queue** to the **Dead-Letter Queue**.
4.  If the task is for the `local` transcriber, it is executed directly by a worker (ideally one with dedicated GPU resources).

This hybrid design enables specialized workers, improves scalability, and adds resilience by carefully managing both GPU-bound and I/O-bound workloads.

---

# Building and Running

## Docker

Two Docker Compose setups are provided:

*   **GPU Mode** (requires an NVIDIA GPU):
    ```bash
    docker-compose up -d
    ```
*   **CPU Mode**:
    ```bash
    docker-compose -f docker-compose.cpu.yaml up -d
    ```

The FastAPI service will be available at `http://localhost:8000`.

## CLI Usage

```bash
# Download and transcribe a video
python -m youtube_whisperer <video_url>

# Transcribe a local file
python -m youtube_whisperer local_audio.mp4

# See all options
python -m youtube_whisperer --help
```

## Development Environment

*   Install dependencies:
    ```bash
    pip install .
    # For development tools:
    pip install -e ".[dev]"
    ```
*   Use the provided `.devcontainer` for a consistent development setup.

---

# Development Conventions

### Testing

*   Run all tests: `pytest`
*   Run specific directory: `pytest tests/`
*   Run specific test: `pytest -k "test_name"`

### Type Checking

*   Run type checks with:
    ```bash
    mypy youtube_whisperer/
    ```

### Dependencies

*   Managed with `pip`.
*   `requirements.txt` for core dependencies.
*   Dev dependencies via `.[dev]` extras in `pyproject.toml`.

---

# Configuration

*   `WHISPER_USE_CUDA`: Enables/disables GPU acceleration for the local transcriber (default: whether a CUDA-enabled device exists).
*   `WHISPER_ASSETS_DIR`: Directory for storing outputs (default: `./assets/`).
*   `WHISPER_MODELS_DIR`: Local Whisper model cache location (default: `~/.whisper/`).
*   `AZURE_SPEECH_API_KEY`: API key for Azure AI Speech service.
*   `AZURE_SERVICE_REGION`: Region for the Azure service (e.g., `westus`).

---

# File Formats

*   `.mp4` – Downloaded video
*   `.mkv`, `.mp3`, `.wav` – Intermediate audio formats
*   `.srt` – Final subtitle file

---

# Summary

`youtube-whisperer` is a scalable transcription service supporting both CLI and web modes. It integrates YouTube downloaders with both local (Whisper) and cloud-based (Azure) transcription engines. With automatic fallback from transcript downloads to transcription, it provides a flexible and efficient solution for large-scale subtitle generation.