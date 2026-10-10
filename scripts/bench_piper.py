#!/usr/bin/env python3
"""Bounded CPU Piper experiment; run with the isolated Piper Python."""
from pathlib import Path
import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from subtitle_lab.pipeline import render, validate
from subtitle_lab.tts import PiperHttpEngine


def main():
    out = Path(sys.argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=False)
    port = 18573
    with socket.socket() as check:
        check.bind(('127.0.0.1', port))
    environment = dict(os.environ)
    environment['PATH'] = str(ROOT / '.venv/bin') + os.pathsep + environment['PATH']
    os.environ['PATH'] = environment['PATH']
    environment.update(OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2')
    started = time.perf_counter()
    with (out / 'server.log').open('w') as log:
        server = subprocess.Popen([sys.executable, '-m', 'piper.http_server', '-m',
            'en_US-lessac-medium', '--data-dir', str(ROOT / 'models/piper'),
            '--host', '127.0.0.1', '--port', str(port)], env=environment, stdout=log, stderr=log)
        samples = []
        stop = threading.Event()
        def sample():
            while not stop.wait(.1):
                try:
                    fields = Path(f'/proc/{server.pid}/stat').read_text().split()
                    samples.append({'at_s': time.perf_counter()-started,
                        'cpu_ticks': int(fields[13])+int(fields[14]),
                        'rss_bytes': int(fields[23])*os.sysconf('SC_PAGE_SIZE')})
                except (FileNotFoundError, ProcessLookupError):
                    break
        monitor = threading.Thread(target=sample, daemon=True)
        monitor.start()
        try:
            endpoint = f'http://127.0.0.1:{port}'
            for _ in range(300):
                if server.poll() is not None:
                    raise RuntimeError('Piper exited before readiness; see server.log')
                try:
                    with urllib.request.urlopen(endpoint + '/voices', timeout=1) as response:
                        (out / 'voices.json').write_bytes(response.read())
                    break
                except OSError:
                    time.sleep(.1)
            else:
                raise TimeoutError('Piper startup exceeded 30 seconds')
            startup = time.perf_counter()-started
            engine = PiperHttpEngine(endpoint + '/synthesize')
            results = []
            for label, source in [('cold-demo', ROOT/'samples/demo.srt')] + [
                (f'warmup-{i+1}', ROOT/'samples/dialogue20.srt') for i in range(3)] + [
                (f'measured-{i+1:02}', ROOT/'samples/dialogue20.srt') for i in range(10)]:
                began = time.perf_counter()
                manifest = render(source, out/label, engine, 'piper-http')
                elapsed = time.perf_counter()-began
                validate(out/label)
                speech = sum(c['speech_duration_ms'] for c in manifest['cues'])/1000
                generation = manifest['metrics']['aggregate_generation_ms']/1000
                results.append({'label':label, 'pipeline_wall_s':elapsed,
                    'generation_s':generation, 'speech_s':speech, 'generation_rtf':generation/speech,
                    'pipeline_rtf':elapsed/speech, 'metrics':manifest['metrics'],
                    'clipped_samples':manifest['audio']['clipped_samples']})
                print(label, round(elapsed,3), flush=True)
            (out/'benchmark.json').write_text(json.dumps({'startup_s':startup,
                'runs':results, 'server_observed_peak_rss_bytes':max(s['rss_bytes'] for s in samples),
                'server_cpu_s':(samples[-1]['cpu_ticks']-samples[0]['cpu_ticks'])/os.sysconf('SC_CLK_TCK'),
                'resource_sampling_interval_s':.1, 'gpu_used_by_piper':False,
                'listening_verdict':'unassessed; operator listening required'}, indent=2)+'\n')
        finally:
            stop.set()
            monitor.join()
            (out/'server-resources.json').write_text(json.dumps(samples, indent=2)+'\n')
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()

if __name__ == '__main__':
    main()
