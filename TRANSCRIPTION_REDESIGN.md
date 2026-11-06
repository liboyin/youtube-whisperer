# Transcription redesign: discussion and experiment handoff

Recorded on 2026-11-06 from the architecture and backend research discussion. This is a proposal and research handoff, not an implemented design or authorization for the entire redesign. [DESIGN.md](DESIGN.md) owns accepted decisions and current product contracts; [TODO.md](TODO.md) owns future assignments and their execution boundaries; [AGENTS.md](AGENTS.md) owns working standards. Promote selected work into bounded TODO tasks when a follow-up session takes it on.

The immediate deliverable is this document. No inference experiments, cloud calls, repository extraction, or runtime changes were performed in this session. Documentation validation consists of checking source claims, references and the diff; application gates and formal adversarial review are not required for this documentation-only change.

## Confirmed direction and unresolved decisions

The user's confirmed direction is recorded in [D53](DESIGN.md#d53). The user wants native Apple silicon acceleration while retaining CUDA and cloud options, accepts different backends when performance justifies them, prioritizes single-file transcription, and wants experiments on both platforms before choosing. The model requested for research is full Whisper `large-v3`.

The user is considering extracting transcription into a reusable project and possibly extracting YouTube downloading and future comment harvesting into another project, leaving this repository as an orchestration layer. These extractions, component interfaces and deployment topology are not settled. Queue ownership and backend choices below are recommendations from the discussion, not accepted implementation decisions.

Working assumption: the principal workload is offline transcription of individual recordings into usable subtitles, rather than live dictation. Recording lengths, exact hardware, acceptable quality differences, memory limits and acceptable integration cost remain to be established. English and Chinese are proposed evaluation languages because the existing product supports them; confirm the actual corpus before measurement.

## Selected project names

The user selected `media-transcriber` for the reusable transcription project and `youtube-collector` for YouTube acquisition, as recorded in [D53](DESIGN.md#d53). `media-transcriber` accommodates audio/video inputs and multiple engines or hardware backends; `youtube-collector` covers media, playlists, channels, captions, metadata and comments. Repository and package-name availability has not been checked. No rename of this orchestration repository was selected.

## Starting architecture and compatibility

The initial assessment inspected revision `aa840dfa13cbbd8e55c5c159e6b76b166ba984ef`. This handoff was prepared at `4dc2b98e6458ccd1c521abaaac9e372691917e3f` inside the devcontainer. An unrelated untracked `.devcontainer/devcontainer-lock.json` was present and was left untouched. No real media library, browser profile, model cache, credentials or Redis state was inspected.

The current design already separates API, YouTube, Whisper and Azure processes and loads engines lazily. Queued transcription sources are concrete filesystem paths; transcribers publish sibling SRT files. The library is the source of truth for completion, and an existing SRT can satisfy work irrespective of its producing engine. See [architecture](DESIGN.md#architecture-and-resource-ownership), [data flow](DESIGN.md#data-flow) and [media behavior](DESIGN.md#media-and-subtitle-behavior).

At the handoff revision, [model parameters](youtube_whisperer/transcriber/model_parameters.py) select CUDA `float32` or CPU `int8`. The [Whisper transcriber](youtube_whisperer/transcriber/whisper_transcriber.py) calls the ordinary `WhisperModel.transcribe` path, not `BatchedInferencePipeline`. A future experiment should preserve this configuration as a baseline and distinguish gains from changing precision or batching from gains from changing engines.

Setup has changed since the initial conversation: follow the current [README](README.md) and [uv dependency policy](DESIGN.md#dependencies-are-locked-and-installed-with-uv), not the earlier requirements.txt instructions. Python 3.12 remains the accepted project interpreter under D51. An experiment needing another toolchain should isolate it rather than silently migrate the application.

Existing compatibility and product constraints remain in force: public Python entry points under D18, language validation, transcription-only behavior, filename and MP4/SRT pairing rules, overwrite policies, atomic publication, output rejection and resource cleanup. Extraction must inventory each behavior and assign an explicit owner; moving code does not authorize removing it.

## Proposed component boundaries

| Component | Proposed responsibilities | Kept outside the reusable component |
|---|---|---|
| Transcription | Audio preparation, resident model lifecycle, engine adapters, normalized timed segments, provenance and subtitle export | YouTube identities, playlist expansion, Redis and workflow routing |
| YouTube acquisition | Video identity, playlist/channel discovery, media download, existing caption retrieval, comment collection | Choosing the transcription engine or deciding whether transcription is necessary |
| Orchestrator | Job dependencies, routing, retry and completion policy, library layout, artifact access and final publication | Engine internals and YouTube extraction implementation |

Resolve the export/publication distinction during interface design: a transcriber may produce a staged SRT or structured result, while orchestration applies library naming, reuse and replacement policy. Do not leave two components believing they own the final write.

The YouTube component should report facts such as “media acquired; captions unavailable.” The orchestrator decides whether to request transcription. That policy currently lives in `YouTubeWorker.process_video` and should move deliberately if extraction proceeds.

A transcription contract should identify input media, source language, requested capabilities and execution profile. Results should include timed segments and provenance such as engine version, model revision, precision and relevant decoding options; SRT is an export. Word timestamps, diarization and other optional capabilities should be explicit rather than represented by misleading empty fields. Exact schemas, cancellation behavior and error taxonomy are open decisions.

Separate packages, repositories and network services are independent choices. Establish a useful library or executable boundary first; create independently released repositories when reuse and release needs justify the coordination cost. Native Swift or C++ execution can sit behind a process interface without requiring the orchestrator to change languages.

## Queue ownership and deployment proposal

Start with one queueing system owned by orchestration, retaining Redis Streams unless experiments expose a reason to change it. Use multiple logical queues where execution compatibility or scheduling requires them: acquisition, comments, Apple transcription, CUDA transcription and cloud transcription are illustrative routes, not a commitment to five queues.

Worker adapters claim jobs, invoke reusable components, publish results and acknowledge completion. Queue protocol, job identity, dependencies and retry policy remain orchestration concerns. A native macOS adapter can consume work from the same broker as Docker workers; neither extracted library needs its own broker. Avoid a queue from which incompatible workers can claim arbitrary jobs.

Keep one authoritative workflow retry policy. Define bounded transport retries separately so retries at multiple layers cannot multiply paid requests or duplicate work. If a hosted provider exposes asynchronous jobs, persist its job ID and resume monitoring instead of resubmitting after every restart. A separate service-owned admission queue becomes reasonable only if transcription later serves independent clients and owns its own scheduling/capacity contract.

The proposed Apple deployment is a native macOS process, potentially alongside a Docker-hosted API and Redis. Standard Docker Desktop Linux-container GPU passthrough is not an Apple Metal/ANE equivalent of CUDA; host-backed inference features are a different mechanism. Recheck supported deployment paths before implementation. See [Docker GPU documentation](https://docs.docker.com/desktop/features/gpu/).

Distinguish a Docker worker calling a hosted speech API from a Docker image performing inference on a rented CUDA machine. Both are cloud options, but only the latter owns the inference runtime. Native macOS execution is necessary to evaluate the proposed Apple paths; the repository's Docker-only working rule still applies to agents, so obtain the required host-execution confirmation in that follow-up session rather than assuming this document waives it.

## Risks to resolve before extraction

| Risk | Proposed treatment or decision needed |
|---|---|
| Container paths do not exist on macOS or remote hosts | Define artifact identities and access separately from local paths. Consider configured shared-root mapping locally, uploads/object storage only when remote execution requires it. |
| Existing SRT reuse hides model/language/provenance differences | Decide explicit reuse and reprocessing rules. Preserve current files; consider provenance sidecars without assuming a database is necessary. |
| Crash, sleeping Mac or long cloud job causes duplicate execution | Define idempotency, acknowledgement ordering, result ownership and appropriate leases/heartbeats. Current idle-time reclamation is a heuristic, not proof of worker death. |
| A result is published but acknowledgement is lost | Make replay safe and distinguish an already committed result from incomplete output. |
| Backend substitution changes transcript quality | Check omissions, repetition, punctuation, language behavior and timestamps; retain rejection guarantees with backend-appropriate implementation. |
| Automatic cloud fallback changes cost and privacy | Require explicit permitted destinations and fallback policy; local unavailability must not silently authorize upload. |
| New remote workers enlarge the trust boundary | Revisit connectivity and authentication deliberately; the existing API is trusted/LAN-only and should not be exposed publicly by the redesign. |
| Independent repositories create release coupling | Version contracts and dependencies; retain compatibility wrappers where required; avoid simultaneous extraction before boundaries are proven. |
| Downloads, inference and comments interfere | Give independent workflow branches appropriate resource limits and failure handling. |

## YouTube comments proposal

Comments belong alongside YouTube acquisition but form an independent workflow branch. Refreshing comments should not require redownloading media, and a comment failure should not block transcription. Decide whether collection is a snapshot or recurring synchronization and what “complete” means when comments are disabled, edited, removed or inaccessible.

Record stable comment/video IDs, reply relationships, collection timestamps, pagination progress and partial-completion status. Choose the collection mechanism and account/quota requirements separately. YouTube's official `commentThreads` response need not contain every reply; full reply retrieval can require `comments.list`. See [comment thread documentation](https://developers.google.com/youtube/v3/docs/commentThreads) and [listing documentation](https://developers.google.com/youtube/v3/docs/commentThreads/list).

## Backend research retained from the session

These are published observations consulted on 2026-11-06, not measurements of this application or guarantees for current releases. Full `large-v3`, `large-v3-turbo` and `distil-large-v3` are different experimental conditions. Do not substitute Turbo or distilled weights when claiming a full large-v3 result. RTF is processing time divided by audio duration (lower is better); RTFx is its inverse (higher is better).

### Historical matched-model leaderboard

The [19 February 2025 CSV](https://huggingface.co/datasets/Steveeeeeeen/whisper-leaderboard-evals/blob/main/19_feb_2025_latest.csv) contains the following full large-v3 rows. The session fetched the raw CSV to verify them. Published [setup at leaderboard commit e1414a9](https://huggingface.co/spaces/hf-audio/open_asr_leaderboard/commit/e1414a982942f9cbe3bf0c0a4c0039342fcce5b7) specifies A100-SXM4 40 GB/CUDA 12.6/batch 64 and M2 Ultra/76 GPU cores/192 GB/macOS 15/batch 1.

| Platform | Backend | RTFx | Average WER |
|---|---|---:|---:|
| CUDA | TensorRT-LLM | 230.69 | 7.07% |
| CUDA | Transformers | 145.51 | 7.44% |
| CUDA | faster-whisper | 19.13 | 7.19% |
| Apple | MLX Whisper | 27.00 | 8.35% |
| Apple | whisper.cpp | 17.00 | 8.26% |
| Apple | WhisperKit | 9.24 | 8.35% |

These historical configurations are not a hardware comparison. Equivalent effective batching, precision and decoding behavior were not established for every backend; the CUDA ratio is not a predicted speedup for this worker. WhisperKit is labeled “Metal” in the CSV, which does not establish ANE-only execution. Engine revisions are not supplied by this summary. WER differences also prevent treating output as identical.

### Additional evidence and exclusions

- [Community MLX benchmark](https://github.com/Casper015/mlx-asr-benchmark): reports full large-v3 FP16 on M5/24 GB at 7.08× realtime over 1,000 conversational turns, and 537.27 seconds for approximately 62.2 minutes of continuous audio (6.94× realtime; reported peak RAM 5,435 MB). It provides scripts, but was not independently reproduced; no source commit was retained, and it is not a same-machine comparison with WhisperKit or whisper.cpp.
- [Relax, ASPLOS 2025, Figure 19 and §5.4](https://yuchenjin.github.io/papers/asplos25-relax.pdf): compares full large-v3 on RTX 4090 and M2 Ultra using one 30-second recording, including faster-whisper 1.0.2 and whisper.cpp commit 5d950c4. Useful corroboration, not a predictor of long-recording completion time.
- [faster-whisper README benchmark](https://github.com/SYSTRAN/faster-whisper#benchmark): the familiar 63-second sequential versus 17-second batch-8 result for 13 minutes of audio uses large-v2, FP16 and RTX 3070 Ti, with faster-whisper 1.1.0. It illustrates configuration sensitivity but is excluded from full large-v3 numerical comparisons.
- [whisper.cpp Core ML documentation](https://github.com/ggml-org/whisper.cpp#core-ml-support): documents ANE encoder acceleration. An encoder speedup over CPU does not prove a full-transcription speedup over Metal. The engine also supports Metal and CUDA, making one engine across platforms possible, though not required.
- [WhisperKit paper, version 1](https://arxiv.org/html/2507.10860v1): primarily concerns large-v3-turbo and streaming/model optimizations. Its headline latency is excluded from full large-v3 offline comparisons.
- [WhisperKit maintainer discussion, 2 November 2024](https://github.com/argmaxinc/argmax-oss-swift/discussions/243): explains that default configurations balance power, thermals, memory and latency. Its GPU+ANE versus ANE-only example uses Turbo and does not establish a full large-v3 winner.
- [NVIDIA encoder-decoder documentation](https://github.com/NVIDIA/TensorRT-LLM/blob/main/docs/source/models/encoder-decoder.md): supports investigating full large-v3 with TensorRT-LLM. Recheck the selected release, hardware requirements and supported decoding/timestamp behavior before investing in integration.

The provisional recommendation was faster-whisper on CUDA and MLX on Apple, with TensorRT-LLM and whisper.cpp as challengers. This is a shortlist, not a selected production architecture. No controlled current evidence reviewed in this session established that ANE-only consistently outperforms Apple GPU execution for full large-v3. Energy efficiency and freeing GPU capacity remain hypotheses to measure.

## Single-file priority and experiment protocol

The user's single-file clarification supersedes any implication that multi-request throughput should drive selection. Primary metric: seconds from submitting one recording to a complete, usable SRT, including decoding/resampling, segmentation, inference and export. Report inference-only time as a diagnostic, not as the sole product metric.

Batching chunks within one recording can reduce that recording's completion time without multiple files in flight. Batching separate user requests primarily improves aggregate throughput and may introduce waiting; it is secondary here. Independent chunk processing can change preceding-text context, segmentation, omissions and timestamps, so measure quality rather than assuming equivalence.

### Shared protocol to establish first

1. Record exact GPU/SoC variant, GPU core count, RAM/VRAM, OS, drivers, power mode and backend versions/commits. Use identical full large-v3 weights or documented conversions with hashes/revisions; distinguish compressed variants.
2. Select an explicitly authorized, experiment-owned corpus with reference transcripts: representative short and long recordings, English/Chinese where relevant, silence, background noise and difficult transitions. Record file hashes, durations and speech fraction. Do not use the real media library or host model cache as scratch storage.
3. Agree acceptable quality differences and a material performance improvement threshold before selecting a winner. No numeric acceptance threshold was settled in this session.
4. Record language settings, beam size, temperature/fallback behavior, prompts, previous-text conditioning, VAD, chunk size/overlap, timestamp mode and precision. Where equivalent settings are unavailable, label separate operating points rather than claiming a controlled engine-only comparison.
5. Measure the existing application's sequential CUDA FP32 baseline, tuned sequential settings and within-file batching separately. Fully consume lazy outputs and synchronize asynchronous device work before stopping timers.
6. Separate download/conversion/first compilation, cold process/model load, and warm resident-model runs. Use warmups and repeated measurements, retain all timings, and report median and variability. Do not restart a native bridge per chunk when assessing a resident worker.
7. Record end-to-end time, RTF/RTFx, peak process/device memory with measurement definitions, failures and, where tooling permits, energy and sustained thermal behavior. Do not equate model file size or process RSS with total device memory.
8. Check English WER, Chinese CER, omissions, repetitions, chunk-boundary continuity and SRT timing/order. Keep timestamp/alignment costs in the product measurement. Store transcripts, configuration and machine-readable raw results alongside the report.

Keep hardware/model benchmarks separate from the automated application suite, which forbids real models and external services. Follow [AGENTS.md](AGENTS.md) for isolation, execution approval and validation obligations; this handoff does not override them. Use dedicated experiment input/output/model directories and synthetic application settings, with no live queues, browser cookies or cloud credentials. Any cloud comparison needs its own authorized scope and spending/data policy.

### Candidate matrix

| Platform | Initial conditions | Additional conditions if useful |
|---|---|---|
| CUDA | Existing faster-whisper FP32 sequential; FP16 and int8_float16 sequential; supported within-file batch sizes | whisper.cpp CUDA for a shared-engine comparison; TensorRT-LLM if single-file gains justify integration |
| Apple | MLX Whisper FP16; whisper.cpp Metal with full large-v3 | WhisperKit with explicit compute selection; whisper.cpp Core ML encoder plus supported decoder path; documented within-file batching where available |

Verify actual execution placement with available diagnostics. A Core ML compute-unit setting permits execution on particular devices; it alone is not evidence that every operation ran on ANE. Report mixed GPU/ANE/CPU execution honestly.

## Suggested follow-up sessions

These are separable session suggestions, not assigned TODO tasks. Each session should first accept a boundary under [TODO maintenance](TODO.md#maintaining-this-plan); architecture-changing choices require confirmation before dependent implementation. CUDA and Apple experiments can proceed independently after agreeing the corpus and protocol.

| Session | Intent and dependencies | Non-goals | Done criteria and handoff |
|---|---|---|---|
| A: Experiment preparation | Establish target hardware, owned corpus, model identity, quality threshold and shared protocol | Production redesign, backend selection | Reproducible configuration and input manifest; runner scope and native-host execution arrangements settled |
| B: CUDA experiment | Depends on A; measure baseline, tuned sequential and within-file batching | Replacing the production worker | Raw results, quality/timing checks, versions and limitations; recommendation for CUDA |
| C: Apple experiment | Depends on A; compare GPU candidates and ANE configurations on the actual Mac | Assuming Linux Docker provides Metal/ANE; changing project Python policy | Same evidence format as B, actual device-placement observations and native packaging implications |
| D: Backend decision | Depends on B/C for supported targets; compare single-file completion, quality and integration cost | Automatic acceptance of leaderboard rankings | User-accepted backend/profile choices recorded in DESIGN; unresolved limitations and revisit triggers |
| E: Transcription boundary and extraction | Depends on agreed contract and D where engine-specific; inventory retained APIs/behavior and artifact ownership | YouTube extraction, new cloud providers or a generic workflow platform | Existing engines remain functional through the boundary, compatibility and publication guarantees verified; selected extraction/package strategy documented |
| F: Native worker integration | Depends on selected Apple backend and artifact/queue contract | Public internet exposure or implicit cloud fallback | One-file end-to-end path across Docker/macOS works; controlled restart/replay and publication behavior verified |
| G: YouTube acquisition and comments | Can be designed independently; extraction depends on agreed responsibilities and comment collection semantics | Making comment success a transcription dependency | Accepted acquisition interface and independent comment workflow; partial/reply completeness and refresh behavior tested before extraction |

## Questions to carry forward

- Which Mac SoC variant and NVIDIA GPU will be used, and are they colocated or remote?
- What are representative recording lengths, languages and subtitle quality requirements?
- How much quality change is acceptable for precision changes, chunking or faster completion?
- Is maximum speed, low energy use or keeping the GPU free the primary Apple goal?
- Which library, CLI or service interface would the new transcriber need for reuse outside this project?
- Which artifact access and provenance/reprocessing policy should replace assumptions about shared absolute paths?
- Are new cloud providers, automatic fallback, diarization or word-level timestamps wanted, or merely future possibilities?
- Does comment collection mean a one-time snapshot or repeat synchronization, and what completeness/retention policy is required?
- Should either component become a separate repository immediately after its boundary is proven, or remain independently packaged here initially?

Future sessions should update TODO and DESIGN as their owning roles require, link experiment evidence at exact revisions, and mark which recommendations this historical handoff has superseded rather than treating its provisional choices as settled.
