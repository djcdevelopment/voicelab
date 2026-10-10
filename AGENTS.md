# Agent working contract — Subtitle Lab

Read `README.md`, `docs/ARCHITECTURE.md`, `docs/GATES.md`, and `docs/HARDWARE.md` before implementing.

- The operator is investigating a personal, noncommercial Linux subtitle-to-AI-audio pipeline. Favor a proven vertical slice over premature framework construction.
- **Filesystem boundary:** only alter this repo and its specifically created virtualenv, caches, and local output folders unless the operator explicitly approves broader changes. Do not restart, stop, or reconfigure the workstation's existing vLLM, llama.cpp, HEARTH, AMUX, or other workloads.
- **Hardware:** Intel Core Ultra 9 285K; 128 GB RAM; dual discrete Arc Pro B70 with 32 GB **each**, plus iGPU/NPU. Do not assume `xpu:0` or `xpu:1` correspond to B70; record actual names, integrated flags, driver versions, and visible memory.
- **Model practice:** evaluate existing solutions first. Prefer isolated envs with recorded package/model versions. Fish Audio S2 has upstream Intel XPU guidance but has NOT been proven on this host. Do not treat stated model VRAM as verified operational compatibility.
- **Content:** no credentials in logs; no scraping session secrets; no DRM bypass or protection circumvention. Do not redistribute or commit copyrighted episode frames, speech, subtitles, cloned voices, or raw captures. Fixtures should be synthetic or permissioned.
- **Receipts:** Every meaningful experiment should produce `output/RECEIPTS/<unique-name>/` containing commands, environment/versions, metrics, observed result, artifacts/checksums, failure details, and next decision. Existing receipts are immutable.
- **Tests:** Preserve zero-dependency smoke path; run it before and after changes. Increment tests for parser and timing corner cases. Keep feature claims supported by actual running evidence.
- **Git:** If this is a new repo, `git init` locally is fine. Never push or expose externally without explicit operator approval. Create small commits and add a concise handoff. Avoid inventing benchmarks.
- **Strategic bias:** Subtitle source → normalized cue → TTS → duration fit → timing/mix is the critical path. OCR/speaker recognition/live streaming are later steps unless they unblock verified operator experience.
