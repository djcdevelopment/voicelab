#!/usr/bin/env python3
"""Bounded CPU Piper experiment; run with the isolated Piper Python."""
from pathlib import Path
import argparse
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--cpus', help='Two allowed Linux CPU indices, e.g. 4,5')
    args = parser.parse_args()
    allowed = os.sched_getaffinity(0)
    cpus = sorted(int(c) for c in args.cpus.split(',')) if args.cpus else sorted(allowed)[:2]
    if len(set(cpus)) != 2 or not set(cpus) <= allowed:
        parser.error('select exactly two distinct CPUs in the current allowed affinity')
    out = args.output.resolve()
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
        server = subprocess.Popen(['taskset', '-c', ','.join(map(str, cpus)),
            sys.executable, str(ROOT / 'scripts/piper_cpu_server.py'), '-m',
            'en_US-lessac-medium', '--data-dir', str(ROOT / 'models/piper'),
            '--host', '127.0.0.1', '--port', str(port)], env=environment, stdout=log, stderr=log)
        samples = []
        stop = threading.Event()
        def sample():
            while not stop.wait(.1):
                try:
                    fields = Path(f'/proc/{server.pid}/stat').read_text().split()
                    thread_cpus = set()
                    for task in Path(f'/proc/{server.pid}/task').iterdir():
                        try:
                            thread_cpus.update(os.sched_getaffinity(int(task.name)))
                        except ProcessLookupError:
                            pass
                    samples.append({'at_s': time.perf_counter()-started,
                        'cpu_ticks': int(fields[13])+int(fields[14]),
                        'allowed_cpus': sorted(os.sched_getaffinity(server.pid)),
                        'all_thread_allowed_cpus': sorted(thread_cpus),
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
            if any(not set(s['all_thread_allowed_cpus']) <= set(cpus) for s in samples):
                raise RuntimeError('Server worker thread escaped requested CPU affinity')
            (out/'benchmark.json').write_text(json.dumps({'startup_s':startup,
                'onnx_session':{'intra_op_threads':2, 'inter_op_threads':1, 'spinning':False},
                'all_sampled_threads_affinity_verified':True,
                'server_allowed_cpus':cpus,
                'observed_resource_span_s':samples[-1]['at_s']-samples[0]['at_s'],
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
