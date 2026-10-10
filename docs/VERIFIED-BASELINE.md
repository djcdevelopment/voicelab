# Starter validation — 2026-10-10

Executed against the generated project in the **artifact-building container**, NOT the operator's B70/Linux workstation:

```bash
cd subtitle-starter
./scripts/smoke.sh
```

Observed:
- 12 `unittest` checks PASS (SRT, VTT, ASS, timestamps, text normalization, malformed cues, render, import, tamper detection, overrun measurement).
- Synthetic 5-cue `demo.srt` loaded; source duration 16.0s.
- Tone engine generated 5 WAV stems and a 16.2-second mono 24 kHz PCM16 mixed WAV.
- Render receipt validated 6 audio artifacts by SHA256.
- No >250 ms overflow on the five supplied synthetic lines.

This validates only starter logic. **Not tested on the actual operator host:** Intel Arc XPU, Fish S2, Piper server, real speech output, OCR, media synchronization, audio-source separation, browser access. The cold builder must verify these independently and report real results.
