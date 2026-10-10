"""Local review files through Werkzeug's maintained conditional/range responses."""
from pathlib import Path


def create_app(root: Path):
    from flask import Flask, abort, send_from_directory
    root=root.expanduser().resolve()
    if not root.is_dir():raise NotADirectoryError(root)
    app=Flask(__name__,static_folder=None)
    allowed={'.html','.wav','.mp3','.mp4','.webm','.vtt','.csv','.png'}

    @app.route('/',defaults={'name':'index.html'})
    @app.route('/<path:name>')
    def asset(name):
        if name.endswith('/'):
            name+='index.html'
        target=(root/name).resolve()
        if not target.is_relative_to(root) or target.suffix.lower() not in allowed or not target.is_file():
            abort(404)
        return send_from_directory(root,name,conditional=True)

    return app


def serve(root: Path,port: int):
    from werkzeug.serving import run_simple
    if not 1024<=port<=65535:raise ValueError('Choose a port from 1024 to 65535')
    app=create_app(root)
    print(f'Player: http://127.0.0.1:{port}/',flush=True)
    run_simple('127.0.0.1',port,app,use_reloader=False,threaded=True)


def build_comparison(runs: list[Path],destination: Path,labels: list[str]|None=None,
                     first_cues: int|None=None) -> dict:
    """Static listening artifacts, preserving WAVs; no quality scores invented."""
    import json
    import shutil
    import subprocess
    from html import escape
    from .pipeline import validate,file_sha256
    if len(runs)<2:raise ValueError('Compare at least two runs')
    if labels is not None and len(labels)!=len(runs):raise ValueError('Provide one label per run')
    manifests=[]
    for run in runs:
        validate(run)
        manifests.append(json.loads((run/'manifest.json').read_text()))
    keys=('index','start_ms','end_ms','text','speaker')
    corpus=[{k:c[k] for k in keys} for c in manifests[0]['cues']]
    if any([{k:c[k] for k in keys} for c in m['cues']]!=corpus for m in manifests[1:]):
        raise ValueError('Comparison requires identical normalized words, speakers and time windows')
    excerpt=None
    if first_cues is not None:
        if type(first_cues) is not int or not 1<=first_cues<=len(corpus):
            raise ValueError('Excerpt cue count must be within this corpus')
        start=corpus[0]['start_ms']/1000
        end=max(max(c['end_ms'],c['start_ms']+c['speech_duration_ms'])
                for m in manifests for c in m['cues'][:first_cues])/1000+.2
        if first_cues<len(corpus) and end>corpus[first_cues]['start_ms']/1000:
            raise ValueError('Clean excerpt boundary overlaps the next cue; select a longer excerpt')
        excerpt={'first_cues':first_cues,'source_start_s':start,'source_end_s':end,
                 'policy':'retain every selected utterance; original full WAV also retained'}
    binary=shutil.which('ffmpeg')
    if not binary:raise RuntimeError('FFmpeg is required for browser-friendly comparison copies')
    if destination.exists():raise FileExistsError(destination)
    destination.mkdir(parents=True)
    candidates=[]
    html=['<!doctype html><meta charset="utf-8"><title>Subtitle Lab listening comparison</title>',
          '<h1>Listening comparison</h1><p>Same words and subtitle windows. Play one candidate at a time.</p>',
          '<p>Listen for phrasing, pauses and comfort. Timing changes alone do not establish quality.</p>']
    if excerpt:
        html.append(f'<p>Players contain the first {first_cues} cues; full WAV downloads are retained.</p>')
    for i,(run,m) in enumerate(zip(runs,manifests),1):
        label=labels[i-1] if labels else run.name
        wav=f'candidate-{i:02}.wav';mp3=f'candidate-{i:02}.mp3'
        shutil.copyfile(run/'dub.wav',destination/wav)
        audio_input=destination/wav
        if excerpt:
            audio_input=destination/f'candidate-{i:02}-excerpt.wav'
            call=[binary,'-hide_banner','-loglevel','error','-nostdin','-n',
                  '-ss',str(excerpt['source_start_s']),'-i',str(destination/wav),
                  '-t',str(excerpt['source_end_s']-excerpt['source_start_s']),'-c:a','pcm_s16le',str(audio_input)]
            completed=subprocess.run(call,capture_output=True,text=True,timeout=180)
            if completed.returncode:raise RuntimeError(f'Excerpt failed: {completed.stderr[-1000:]}')
        command=[binary,'-hide_banner','-loglevel','error','-nostdin','-n','-i',str(destination/wav),
                 '-c:a','libmp3lame','-b:a','128k',str(destination/mp3)]
        command[command.index('-i')+1]=str(audio_input)
        result=subprocess.run(command,capture_output=True,text=True,timeout=180)
        if result.returncode:raise RuntimeError(f'MP3 copy failed: {result.stderr[-1000:]}')
        candidates.append({'label':label,'render':str(run.resolve()),'manifest_sha256':file_sha256(run/'manifest.json'),
            'wav':wav,'wav_sha256':file_sha256(destination/wav),'mp3':mp3,'mp3_sha256':file_sha256(destination/mp3),
            'metrics':m['metrics'],'quality_verdict':'awaiting_listener_review'})
        html+=[f'<h2>{escape(label)}</h2>',f'<audio controls preload="metadata" src="{mp3}"></audio>',
               f'<p>{m["metrics"]["cue_overruns_gt_250ms"]} cues overrun by more than 250 ms. '
               f'<a href="{mp3}" download>MP3</a> · <a href="{wav}" download>Original WAV</a></p>']
    (destination/'index.html').write_text('\n'.join(html))
    result={'kind':'listening-comparison-v1','candidates':candidates,'excerpt':excerpt,
            'listener_feedback':'pending; no ratings synthesized'}
    (destination/'comparison.json').write_text(json.dumps(result,indent=2)+'\n')
    return result
