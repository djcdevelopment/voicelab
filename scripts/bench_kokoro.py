#!/usr/bin/env python3
"""Generate stock-voice Kokoro CPU WAV stems, then use the existing WAV adapter."""
from pathlib import Path
import argparse
import json
import os
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from subtitle_lab.subtitles import load_cues
from subtitle_lab.pipeline import render, validate
from subtitle_lab.tts import WavDirectoryEngine


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--cpus', default=None)
    parser.add_argument('--model-dir', type=Path, default=ROOT/'models/kokoro')
    parser.add_argument('--warmups', type=int, default=3)
    parser.add_argument('--repetitions', type=int, default=10)
    args = parser.parse_args()
    allowed = os.sched_getaffinity(0)
    cpus = sorted(map(int, args.cpus.split(','))) if args.cpus else sorted(allowed)[:2]
    if len(set(cpus)) != 2 or not set(cpus) <= allowed:
        parser.error('select exactly two distinct allowed CPUs')
    if args.warmups < 0 or args.repetitions < 1:
        parser.error('warmups >= 0 and repetitions >= 1 required')
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    os.sched_setaffinity(0, cpus)
    os.environ.update(HF_HOME=str(ROOT/'.cache/huggingface'),
        HF_HUB_DISABLE_IMPLICIT_TOKEN='1', HF_HUB_OFFLINE='1',
        XDG_CACHE_HOME=str(ROOT/'.cache'), TORCH_HOME=str(ROOT/'.cache/torch'))
    started = time.perf_counter()
    samples = []
    stop = threading.Event()
    def sample():
        while not stop.wait(.1):
            fields = Path('/proc/self/stat').read_text().split()
            union = set()
            for task in Path('/proc/self/task').iterdir():
                try:
                    union.update(os.sched_getaffinity(int(task.name)))
                except ProcessLookupError:
                    pass
            samples.append({'at_s':time.perf_counter()-started,
                'cpu_ticks':int(fields[13])+int(fields[14]),
                'rss_bytes':int(fields[23])*os.sysconf('SC_PAGE_SIZE'),
                'all_thread_allowed_cpus':sorted(union)})
    monitor = threading.Thread(target=sample, daemon=True)
    monitor.start()
    try:
        import numpy as np
        import soundfile as sf
        import torch
        from kokoro import KModel, KPipeline
        torch.set_num_threads(2)
        torch.set_num_interop_threads(1)
        torch.manual_seed(42)
        model = KModel(repo_id='hexgrad/Kokoro-82M',
            config=str(args.model_dir/'config.json'),
            model=str(args.model_dir/'kokoro-v1_0.pth')).to('cpu').eval()
        pipeline = KPipeline(lang_code='a', repo_id='hexgrad/Kokoro-82M', model=model, device='cpu')
        if pipeline.g2p.fallback is None:
            raise RuntimeError('Missing espeak fallback; refusing silent unknown-word omission')
        voices = {name:pipeline.load_voice(str(args.model_dir/'voices'/f'{name}.pt'))
                  for name in ['af_heart', 'am_michael']}
        startup = time.perf_counter()-started
        runs = []
        sets = [('cold-demo', ROOT/'samples/demo.srt')]+[
            (f'warmup-{i+1}',ROOT/'samples/dialogue20.srt') for i in range(args.warmups)]+[
            (f'measured-{i+1:02}',ROOT/'samples/dialogue20.srt') for i in range(args.repetitions)]
        for label, source in sets:
            run = out/label
            stems = run/'source-stems'
            stems.mkdir(parents=True)
            began = time.perf_counter()
            cpu_began = time.process_time()
            records = []
            for cue in load_cues(source):
                voice = 'af_heart' if cue.index % 2 else 'am_michael'
                torch.manual_seed(42)
                cue_began = time.perf_counter()
                chunks = list(pipeline(cue.text, voice=voices[voice], speed=1.0))
                if not chunks:
                    raise RuntimeError(f'No speech for cue {cue.index}')
                for chunk in chunks:
                    if len(chunk.phonemes) > 510:
                        raise RuntimeError('Kokoro phoneme limit exceeded')
                    for token in chunk.tokens or []:
                        if any(c.isalpha() for c in token.text) and not token.phonemes:
                            raise RuntimeError(f'Unspoken token in cue {cue.index}: {token.text!r}')
                audio = np.concatenate([c.audio.numpy() for c in chunks])
                if not len(audio) or not np.isfinite(audio).all():
                    raise RuntimeError(f'Invalid speech samples for cue {cue.index}')
                float_clipped = int(np.count_nonzero((audio < -1)|(audio >= 1)))
                sf.write(stems/f'{cue.index:04}.wav',audio,24000,subtype='PCM_16')
                records.append({'index':cue.index,'voice':voice,'text':cue.text,
                    'phonemes':[c.phonemes for c in chunks],
                    'generation_wall_s':time.perf_counter()-cue_began,
                    'speech_s':len(audio)/24000,'float_samples_outside_pcm_range':float_clipped})
            generated = time.perf_counter()
            manifest = render(source,run/'render',WavDirectoryEngine(stems),'wav-dir:kokoro-cpu')
            elapsed = time.perf_counter()-began
            generation = sum(c['generation_wall_s'] for c in records)
            speech = sum(c['speech_s'] for c in records)
            validate(run/'render')
            (run/'synthesis.json').write_text(json.dumps(records,indent=2)+'\n')
            runs.append({'label':label,'pipeline_wall_s':elapsed,
                'generation_s':generation,'speech_s':speech,'generation_rtf':generation/speech,
                'pipeline_rtf':elapsed/speech,'composition_wall_s':time.perf_counter()-generated,
                'cpu_s':time.process_time()-cpu_began,'metrics':manifest['metrics'],
                'clipped_samples':manifest['audio']['clipped_samples'],
                'stem_clipped_samples':sum(c['float_samples_outside_pcm_range'] for c in records)})
            (out/'partial-runs.json').write_text(json.dumps(runs,indent=2)+'\n')
            print(label,round(elapsed,3),flush=True)
        if any(not set(s['all_thread_allowed_cpus']) <= set(cpus) for s in samples):
            raise RuntimeError('Worker thread escaped requested CPU affinity')
        (out/'benchmark.json').write_text(json.dumps({'startup_s':startup,'runs':runs,
            'cpu_affinity':cpus,'torch_threads':2,'torch_interop_threads':1,
            'all_sampled_threads_affinity_verified':True,'device':str(model.device),
            'seed_per_cue':42,'speed':1.0,'voice_mapping':'odd af_heart; even am_michael',
            'process_observed_peak_rss_bytes':max(s['rss_bytes'] for s in samples),
            'cpu_s':(samples[-1]['cpu_ticks']-samples[0]['cpu_ticks'])/os.sysconf('SC_CLK_TCK'),
            'observed_resource_span_s':samples[-1]['at_s']-samples[0]['at_s'],
            'resource_sampling_interval_s':.1,
            'listening_verdict':'unassessed; operator listening required'},indent=2)+'\n')
    except Exception as exc:
        (out/'failure.json').write_text(json.dumps({'exception':type(exc).__name__,
            'message':str(exc)},indent=2)+'\n')
        raise
    finally:
        stop.set()
        monitor.join()
        (out/'resources.json').write_text(json.dumps(samples,indent=2)+'\n')

if __name__ == '__main__':
    main()
