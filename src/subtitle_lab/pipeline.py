"""Local subtitle → original/processed utterances → synchronized WAV + evidence."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import math
import shutil
import time

from .audio import duration_ms, load_pcm16_mono, mix_to_wav, tempo_pcm
from .subtitles import load_cues, summary
from .tts import Engine, SAMPLE_RATE


def file_sha256(path: Path) -> str:
    hasher = sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024*1024), b''):
            hasher.update(chunk)
    return hasher.hexdigest()


def speech_activity(pcm) -> dict:
    active = [i for i, sample in enumerate(pcm) if abs(sample) >= 327]
    # A fixed amplitude threshold is only a signal diagnostic, not word alignment.
    return {'activity_threshold_pcm16':327,
            'leading_low_level_ms':round((active[0] if active else len(pcm))*1000/SAMPLE_RATE),
            'trailing_low_level_ms':round((len(pcm)-1-active[-1] if active else len(pcm))*1000/SAMPLE_RATE),
            'peak_abs_pcm16':max((abs(x) for x in pcm),default=0),
            'saturated_pcm_samples':sum(x in (-32768,32767) for x in pcm)}


def render(source: Path, destination: Path, engine: Engine, engine_name: str,
           *, fit_max_speedup: float | None = None) -> dict:
    source = source.expanduser().resolve()
    destination = destination.expanduser().resolve()
    cues = sorted(load_cues(source), key=lambda c:(c.start_ms,c.index))
    if destination.exists():
        raise FileExistsError(f'Refusing to overwrite existing run: {destination}')
    if fit_max_speedup is not None and (not math.isfinite(fit_max_speedup) or not 1 <= fit_max_speedup <= 1.5):
        raise ValueError('Explicit fit speedup cap must be between 1 and 1.5')
    extraction=source.parent/'media-manifest.json'
    extraction_snapshot=None
    if source.name=='subtitles.srt' and extraction.is_file():
        from .media import validate_media
        validate_media(extraction)
        provenance=json.loads(extraction.read_text())
        if provenance['kind']!='caption-extraction-v1':
            raise ValueError('Subtitle extraction provenance has unexpected kind')
        if provenance['artifacts']['subtitles.srt']!=file_sha256(source):
            raise ValueError('Extraction provenance does not match subtitle source')
        extraction_snapshot='source-extraction.json'
    engine.prepare(cues)
    destination.mkdir(parents=True)
    began = time.perf_counter()
    try:
        stems = destination/'stems'; stems.mkdir()
        if fit_max_speedup is not None:
            (destination/'processed').mkdir()
        snapshot = destination/('source'+source.suffix.lower())
        shutil.copyfile(source,snapshot)
        if extraction_snapshot:shutil.copyfile(extraction,destination/extraction_snapshot)
        (destination/'cues.json').write_text(json.dumps([asdict(c) for c in cues],ensure_ascii=False,indent=2)+'\n')
        (destination/'transcript.txt').write_text('\n'.join(
            f'[{c.start_ms/1000:08.3f} -> {c.end_ms/1000:08.3f}] '
            f'{c.speaker+": " if c.speaker else ""}{c.text}' for c in cues)+'\n')
        placements=[];records=[];utterance_end=0
        for ordinal,cue in enumerate(cues):
            stem=stems/f'{cue.index:04}.wav'
            started=time.perf_counter();engine.synthesize(cue,stem)
            generation_ms=round((time.perf_counter()-started)*1000)
            started=time.perf_counter();pcm=load_pcm16_mono(stem)
            normalization_ms=round((time.perf_counter()-started)*1000)
            if not pcm:
                raise RuntimeError(f'Empty utterance for cue {cue.index}')
            original_ms=round(len(pcm)*1000/SAMPLE_RATE)
            window=cue.end_ms-cue.start_ms
            fit={'requested':fit_max_speedup is not None,'factor':1.0,'changed':False}
            processed=None
            fit_ms=0
            if fit_max_speedup is not None and original_ms>window:
                factor=min(fit_max_speedup,len(pcm)*1000/SAMPLE_RATE/window)
                if factor>1:
                    processed=destination/'processed'/stem.name
                    started=time.perf_counter();pcm=tempo_pcm(pcm,processed,factor)
                    fit_ms=round((time.perf_counter()-started)*1000)
                    fit.update(factor=factor,changed=True)
            spoken_ms=round(len(pcm)*1000/SAMPLE_RATE)
            fit['residual_overrun_ms']=max(0,spoken_ms-window)
            utterance_end=max(utterance_end,cue.start_ms+spoken_ms)
            placements.append((cue.start_ms,pcm))
            next_start=cues[ordinal+1].start_ms if ordinal+1<len(cues) else None
            record={**asdict(cue),'stem':f'stems/{stem.name}','stem_sha256':file_sha256(stem),
                'original_speech_duration_ms':original_ms,'speech_duration_ms':spoken_ms,
                'original_cue_overrun_ms':max(0,original_ms-window),
                'generation_wall_ms':generation_ms,'normalization_wall_ms':normalization_ms,
                'fit_wall_ms':fit_ms,'fit':fit,'engine_details':engine.cue_details(),
                'cue_overrun_ms':max(0,cue.start_ms+spoken_ms-cue.end_ms),
                'speech_overlap_next_ms':max(0,cue.start_ms+spoken_ms-next_start) if next_start is not None else 0,
                'gap_to_next_start_ms':max(0,next_start-cue.start_ms-spoken_ms) if next_start is not None else None,
                'speech_slack_ms':max(0,window-spoken_ms),**speech_activity(pcm)}
            if processed:
                record.update(processed_stem=f'processed/{stem.name}',processed_sha256=file_sha256(processed))
            records.append(record)
        mix_started=time.perf_counter()
        audio=destination/'dub.wav'
        mix=mix_to_wav(placements,audio,end_ms=max(max(c.end_ms for c in cues),utterance_end)+200)
        mix_ms=round((time.perf_counter()-mix_started)*1000)
        warnings=[]
        over=sum(c['cue_overrun_ms']>250 for c in records)
        overlap=sum(c['speech_overlap_next_ms']>250 for c in records)
        if over: warnings.append(f'{over} cues exceed source subtitle window by >250ms')
        if overlap: warnings.append(f'{overlap} speech clips overlap next start by >250ms')
        if mix['clipped_samples']: warnings.append(f'Mixed PCM clipped at {mix["clipped_samples"]} samples')
        description=engine.describe()
        description['model_sha256']={name:file_sha256(Path(name)) for name in description.get('model_files',[])}
        result={'schema_version':'subtitle-lab-render-v2',
            'generated_at_utc':datetime.now(timezone.utc).isoformat(),
            'source_path':str(source),'source_sha256':file_sha256(snapshot),
            'source_snapshot':snapshot.name,'engine':engine_name,'engine_provenance':description,
            'sample_rate':SAMPLE_RATE,'input_summary':summary(cues),
            'audio':{'file':'dub.wav','sha256':file_sha256(audio),**mix},
            'metrics':{'cue_count':len(records),'cue_overruns_gt_250ms':over,
                'speech_overlap_next_gt_250ms':overlap,
                'aggregate_generation_ms':sum(c['generation_wall_ms'] for c in records),
                'aggregate_normalization_ms':sum(c['normalization_wall_ms'] for c in records),
                'aggregate_fit_ms':sum(c['fit_wall_ms'] for c in records),'mix_wall_ms':mix_ms,
                'pipeline_wall_ms':round((time.perf_counter()-began)*1000),
                'utterance_duration_ms':sum(c['speech_duration_ms'] for c in records),
                'original_utterance_duration_ms':sum(c['original_speech_duration_ms'] for c in records),
                'fit_changed_cues':sum(c['fit']['changed'] for c in records),
                'source_length_ms':max(c.end_ms for c in cues)},
            'timing_policy':{'mode':'tempo-cap' if fit_max_speedup is not None else 'preserve',
                             'max_speedup':fit_max_speedup,'target':'source-cue-window','truncate':False},
            'warnings':warnings,'cues':records}
        if extraction_snapshot:result['source_extraction_snapshot']=extraction_snapshot
        report=['# Subtitle Lab render','',f'Engine: {engine_name}. Original stems are retained.',
                f'Cues: {len(records)}; >250 ms overruns: {over}; next-start overlaps: {overlap}.',
                f'Timing policy: {result["timing_policy"]["mode"]}; adjusted cues: {result["metrics"]["fit_changed_cues"]}.',
                f'Mixed clipped samples: {mix["clipped_samples"]}.','',
                'No forced alignment, automatic character inference, text rewriting or source separation.',
                'Voice assignments are explicit. Tempo fitting is optional and can leave residual overflow.',
                'Amplitude-threshold leading/trailing diagnostics are not word timestamps.',
                'Tone is a beep diagnostic; voice quality requires listening.','',
                'Warnings: '+('; '.join(warnings) if warnings else 'none at measured thresholds')]
        (destination/'report.md').write_text('\n'.join(report)+'\n')
        result['artifacts']={str(p.relative_to(destination)):file_sha256(p) for p in sorted(destination.rglob('*')) if p.is_file()}
        (destination/'manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        return result
    except Exception as exc:
        (destination/'failure.json').write_text(json.dumps({'status':'FAILED','exception':type(exc).__name__,
            'message':str(exc),'completed_cues':len(records) if 'records' in locals() else 0},indent=2)+'\n')
        raise


def validate(path: Path) -> dict:
    path=path.resolve()
    if path.is_dir():path=path/'manifest.json'
    manifest=json.loads(path.read_text());root=path.parent
    schema=manifest['schema_version']
    if schema == 'subtitle-lab-speech-v1':
        from .speech import validate_speech
        return validate_speech(root, manifest)
    if schema not in ('subtitle-lab-render-v1','subtitle-lab-render-v2'):
        raise ValueError('Unknown manifest schema')
    expected=[(manifest['audio']['file'],manifest['audio']['sha256'])]
    for record in manifest['cues']:
        expected.append((record['stem'],record['stem_sha256']))
        if 'processed_stem' in record:expected.append((record['processed_stem'],record['processed_sha256']))
    if schema.endswith('v2'):
        expected.extend(manifest['artifacts'].items())
        if manifest.get('timing_policy',{}).get('truncate') is not False:
            raise ValueError('Unexpected truncation policy')
        required={manifest['source_snapshot'],'cues.json','transcript.txt','report.md',manifest['audio']['file']}
        if manifest.get('source_extraction_snapshot'):required.add(manifest['source_extraction_snapshot'])
        required.update(c['stem'] for c in manifest['cues'])
        required.update(c['processed_stem'] for c in manifest['cues'] if 'processed_stem' in c)
        if not required <= manifest['artifacts'].keys():
            raise ValueError('Manifest omits required artifact hashes')
    for name,digest in expected:
        target=(root/name).resolve()
        if not target.is_relative_to(root):raise ValueError(f'Unsafe receipt file path: {name}')
        if not target.is_file() or file_sha256(target)!=digest:
            raise RuntimeError(f'Missing or changed render artifact: {name}')
    if schema.endswith('v2'):
        if file_sha256(root/manifest['source_snapshot'])!=manifest['source_sha256']:
            raise ValueError('Source snapshot hash disagrees with source identity')
        cues=json.loads((root/'cues.json').read_text())
        if cues != [ {k:c[k] for k in ('index','start_ms','end_ms','text','speaker')} for c in manifest['cues']]:
            raise ValueError('Cue manifest does not match normalized source cues')
        for c in manifest['cues']:
            actual=duration_ms(root/c.get('processed_stem',c['stem']))
            if abs(actual-c['speech_duration_ms'])>1:
                raise ValueError('Reported speech duration disagrees with WAV')
            if c['cue_overrun_ms']!=max(0,c['start_ms']+actual-c['end_ms']):
                raise ValueError('Reported overrun disagrees with WAV timing')
        if duration_ms(root/manifest['audio']['file'])+1 < max(c['start_ms']+c['speech_duration_ms'] for c in manifest['cues']):
            raise ValueError('Mixed track truncates a reported utterance')
    return {'status':'PASS','validated_files':len({name for name,_ in expected}),
            'source_sha256':manifest['source_sha256'],
            'mixed_wav_duration_ms':duration_ms(root/manifest['audio']['file']), 'warnings':manifest['warnings']}
