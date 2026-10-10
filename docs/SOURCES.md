# Upstream references checked 2026-10-10

This list is for the builder to reverify at implementation time. It is not a lockfile or a claim that every integration has been tested on the operator's GPU.

1. Fish Audio S2 installation, XPU instructions, VRAM: https://github.com/fishaudio/fish-speech/blob/main/docs/en/install.md
2. Fish Audio S2 local API server (POST /v1/tts): https://speech.fish.audio/server/
3. Fish Audio S2 inference/weights: https://speech.fish.audio/inference/
4. PyTorch official Intel XPU installs: https://docs.pytorch.org/docs/main/notes/get_start_xpu.html
5. PyTorch official device properties: https://docs.pytorch.org/docs/main/generated/torch.xpu.get_device_properties.html
6. OHF-Voice Piper server `/synthesize`: https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/API_HTTP.md
7. OHF-Voice Piper CLI: https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/CLI.md
8. `pysubs2` is an optional maintained format parser (ASS/SRT/VTT) for future richer parsing: https://pypi.org/project/pysubs2/

**Status note:** The current parser is a narrow, zero-dependency timer/text extractor. It does not preserve ASS styling, font layering, karaoke animations, VTT timestamp maps, all malformed dialects, or speaker identity beyond explicit cue metadata. Benchmark against a mature library before trying to implement the full subtitle spec in-house.
