"""Borrow FFmpeg/PyAV for authorized local caption extraction and offline playback."""
from pathlib import Path
from datetime import datetime, timezone
import json
import math
import shutil
import subprocess
from html import escape

from .audio import load_pcm16_mono, mix_to_wav
from .pipeline import file_sha256, validate
from .subtitles import load_cues, summary


def probe(source: Path) -> dict:
    source=source.expanduser().resolve()
    if not source.is_file():raise FileNotFoundError(source)
    import av
    with av.open(str(source),options={'protocol_whitelist':'file,pipe'}) as media:
        streams=[]
        for s in media.streams:
            codec=s.codec_context.name
            streams.append({'index':s.index,'type':s.type,'codec':codec,
                'start_s':float(s.start_time*s.time_base) if s.start_time is not None else None,
                'duration_s':float(s.duration*s.time_base) if s.duration is not None else None,
                'language':s.metadata.get('language')})
        video=next((s for s in media.streams if s.type=='video'),None)
        video_end=None
        video_first=None
        if video:
            bounds=[(float(p.pts*p.time_base),float((p.pts+(p.duration or 0))*p.time_base))
                    for p in media.demux(video) if p.pts is not None]
            if bounds:
                video_first=min(a for a,b in bounds)
                video_end=max(b for a,b in bounds)
        return {'source':str(source),'sha256':file_sha256(source),'pyav_version':av.__version__,
                'streams':streams,'video_first_pts_s':video_first,'video_end_pts_s':video_end}


def _new_output(destination: Path) -> Path:
    destination=destination.expanduser().resolve()
    if destination.exists():raise FileExistsError(f'Refusing to overwrite {destination}')
    destination.mkdir(parents=True)
    return destination


def _ffmpeg(args: list[str], out: Path):
    binary=shutil.which('ffmpeg')
    if not binary:raise RuntimeError('FFmpeg required; use the isolated environment PATH')
    command=[binary,'-hide_banner','-loglevel','error','-nostdin','-n',*args]
    (out/'command.json').write_text(json.dumps(command,indent=2)+'\n')
    result=subprocess.run(command,capture_output=True,text=True,timeout=600)
    (out/'ffmpeg.log').write_text(result.stderr)
    (out/'ffmpeg-version.txt').write_text(subprocess.check_output([binary,'-version'],text=True))
    if result.returncode:raise RuntimeError(f'FFmpeg failed: {result.stderr[-1500:]}')


def _seal_manifest(result: dict, out: Path):
    result['generated_at_utc']=datetime.now(timezone.utc).isoformat()
    result['artifacts']={str(p.relative_to(out)):file_sha256(p) for p in sorted(out.rglob('*')) if p.is_file()}
    (out/'media-manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def extract_captions(source: Path,destination: Path,subtitle_index: int=0) -> dict:
    if type(subtitle_index) is not int or subtitle_index<0:raise ValueError('Subtitle index must be nonnegative')
    info=probe(source)
    tracks=[s for s in info['streams'] if s['type']=='subtitle']
    if subtitle_index>=len(tracks):raise ValueError(f'No subtitle stream {subtitle_index}; {len(tracks)} present')
    selected=tracks[subtitle_index]
    if selected['codec'] not in ('ass','ssa','subrip','srt','webvtt','mov_text','text'):
        raise ValueError(f'Subtitle codec {selected["codec"]} is not a text track; no silent OCR fallback')
    out=_new_output(destination)
    try:
        _ffmpeg(['-protocol_whitelist','file,pipe','-copyts','-i',info['source'],
                 '-map',f'0:{selected["index"]}','-c:s','srt',str(out/'subtitles.srt')],out)
        cues=load_cues(out/'subtitles.srt')
        (out/'cues.json').write_text(json.dumps([c.to_dict() for c in cues],indent=2)+'\n')
        return _seal_manifest({'kind':'caption-extraction-v1','source':info,'selected_stream':selected,
            'summary':summary(cues),'timestamp_policy':'preserve source PTS; no offset guessed',
            'rights_basis':'operator-provided authorized local media'},out)
    except Exception as exc:
        (out/'failure.json').write_text(json.dumps({'exception':type(exc).__name__,'message':str(exc)},indent=2)+'\n')
        raise


def compose_video(source: Path,run: Path,destination: Path,*,background: Path|None=None,
                  background_gain: float=.15,transcode: bool=False) -> dict:
    if not math.isfinite(background_gain) or not 0<=background_gain<=1:
        raise ValueError('Background gain must be finite between 0 and 1')
    validate(run)
    manifest=json.loads((run/'manifest.json').read_text())
    info=probe(source)
    start=info['video_first_pts_s'];end=info['video_end_pts_s']
    if start is None or end is None:raise ValueError('Media has no timestamped video stream')
    if abs(start)>.001:
        raise ValueError('Nonzero video origin needs an explicit clock mapping; this path requires zero-origin media')
    speech_end=max(c['start_ms']+c['speech_duration_ms'] for c in manifest['cues'])/1000
    if speech_end>end+.001:
        raise ValueError(f'Dialogue ends at {speech_end:.3f}s after video {end:.3f}s; refusing truncation')
    out=_new_output(destination)
    try:
        dialogue=load_pcm16_mono(run/'dub.wav')
        placements=[(0,dialogue)]
        if background:
            from array import array
            bed=load_pcm16_mono(background)
            # Only this explicitly supplied bed is mixed; source dialogue is never assumed removed.
            bed=array('h',(round(s*background_gain) for s in bed))
            if len(bed)>math.ceil(end*24000):
                raise ValueError('Background exceeds video length; supply a deliberately prepared bed')
            placements.append((0,bed))
        # The dialogue mix's 200ms final silence is not a speech utterance.
        timeline_ms=max(round(end*1000),round(len(dialogue)*1000/24000))
        mix=mix_to_wav(placements,out/'playback-audio.wav',timeline_ms,gain=1.0)
        args=['-protocol_whitelist','file,pipe','-i',info['source'],
              '-i',str(out/'playback-audio.wav'),'-map','0:v:0','-map','1:a:0']
        if transcode:args+=['-c:v','libx264','-preset','veryfast','-threads','2','-pix_fmt','yuv420p']
        else:args+=['-c:v','copy']
        # -t only removes verified final silence beyond video, never an utterance.
        args+=['-c:a','aac','-b:a','160k','-af','apad', '-t',f'{end:.6f}',
               '-movflags','+faststart',str(out/'dubbed.mp4')]
        _ffmpeg(args,out)
        output_info=probe(out/'dubbed.mp4')
        if not any(s['type']=='audio' for s in output_info['streams']):raise RuntimeError('Mux produced no audio stream')
        if abs(output_info['video_end_pts_s']-end)>.05:raise RuntimeError('Mux changed video clock unexpectedly')
        def stamp(ms):
            return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02}.{ms%1000:03}'
        (out/'captions.vtt').write_text('WEBVTT\n\n'+'\n\n'.join(
            f'{c["index"]}\n{stamp(c["start_ms"])} --> {stamp(c["end_ms"])}\n{escape(c["text"])}'
            for c in manifest['cues'])+'\n')
        (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Subtitle Lab playback</title>'
            '<h1>Offline synchronized playback</h1><video controls preload="metadata" src="dubbed.mp4">'
            '<track kind="captions" srclang="en" label="English" src="captions.vtt" default></video>'
            '<p>Audio and video share one media clock. Pause and seek use native player controls.</p>'
            '<p><a href="dubbed.mp4" download>Download MP4</a></p>')
        return _seal_manifest({'kind':'offline-playback-v1','source':info,
            'render_manifest_sha256':file_sha256(run/'manifest.json'),
            'dialogue_wav_sha256':file_sha256(run/'dub.wav'),
            'original_audio_policy':'discarded; source separation not performed',
            'background':{'source':str(background.resolve()),'sha256':file_sha256(background),'gain':background_gain} if background else None,
            'speech_end_s':speech_end,'video_end_s':end,'mix':mix,'output_probe':output_info,
            'sync_policy':'one muxed file, shared clock','transcoded_video':transcode},out)
    except Exception as exc:
        (out/'failure.json').write_text(json.dumps({'exception':type(exc).__name__,'message':str(exc)},indent=2)+'\n')
        raise


def validate_media(path: Path) -> dict:
    path=path.resolve()
    if path.is_dir():path=path/'media-manifest.json'
    data=json.loads(path.read_text());root=path.parent
    if data.get('kind') not in ('caption-extraction-v1','offline-playback-v1'):
        raise ValueError('Unknown media manifest kind')
    required={'subtitles.srt','cues.json','command.json','ffmpeg-version.txt'} if data['kind']=='caption-extraction-v1' else {'dubbed.mp4','playback-audio.wav','captions.vtt','index.html','command.json','ffmpeg-version.txt'}
    if not required.issubset(data.get('artifacts',{})):
        raise ValueError('Media manifest is missing required artifact hashes')
    for name,digest in data['artifacts'].items():
        target=(root/name).resolve()
        if not target.is_relative_to(root):raise ValueError('Unsafe media artifact path')
        if not target.is_file() or file_sha256(target)!=digest:raise RuntimeError(f'Missing or changed media artifact: {name}')
    return {'status':'PASS','kind':data['kind'],'validated_files':len(data['artifacts'])}
