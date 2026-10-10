"""Optional CPU speech libraries, imported only when selected.

Models must already exist locally. No automatic download or device fallback.
"""
from pathlib import Path
from importlib.metadata import version
import json
import os
import wave

from .tts import Engine
from .voices import VoicePlan


def bound_cpu(threads: int):
    if type(threads) is not int or not 1 <= threads <= 8:
        raise ValueError('CPU threads must be an integer from 1 to 8')
    if not hasattr(os, 'sched_getaffinity'):
        raise RuntimeError('Local CPU speech currently requires Linux affinity support')
    allowed = sorted(os.sched_getaffinity(0))
    chosen = allowed[:threads]
    os.sched_setaffinity(0, chosen)
    # Also restrict threads created before engine initialization.
    for task in Path('/proc/self/task').iterdir():
        try:
            os.sched_setaffinity(int(task.name), chosen)
        except ProcessLookupError:
            pass
    return chosen


class PiperLocalEngine(Engine):
    def prepare(self, cues):
        self.plan.validate_cues(cues)

    def __init__(self, model: Path, plan: VoicePlan, threads: int = 2):
        if not model.is_file() or not Path(str(model)+'.json').is_file():
            raise FileNotFoundError(f'Piper requires local model and .onnx.json: {model}')
        self.cpus = bound_cpu(threads)
        from piper import PiperVoice
        from piper.config import PiperConfig, SynthesisConfig
        import onnxruntime as ort
        options = ort.SessionOptions()
        options.intra_op_num_threads = threads
        options.inter_op_num_threads = 1
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        options.add_session_config_entry('session.intra_op.allow_spinning', '0')
        options.add_session_config_entry('session.inter_op.allow_spinning', '0')
        self.model = model.resolve()
        self.plan = plan
        self.config_type = SynthesisConfig
        self.voice = PiperVoice(config=PiperConfig.from_dict(json.loads(Path(str(model)+'.json').read_text())),
            session=ort.InferenceSession(str(model), sess_options=options, providers=['CPUExecutionProvider']))
        self.last_result = {}

    def synthesize(self, cue, destination):
        settings = self.plan.resolve(cue)
        if settings.voice is not None:
            raise ValueError('Piper-local voice is chosen by --model; use speaker_id for multi-speaker models')
        if settings.speaker_id is not None and settings.speaker_id >= self.voice.config.num_speakers:
            raise ValueError('Piper speaker_id exceeds model speaker count')
        config = self.config_type(speaker_id=settings.speaker_id, length_scale=1/settings.speed)
        with wave.open(str(destination), 'wb') as wav:
            self.voice.synthesize_wav(cue.text, wav, syn_config=config)
        self.last_result = {'voice_settings': settings.to_dict()}

    def describe(self):
        return {'backend':'piper-local', 'versions':{'piper-tts':version('piper-tts'), 'onnxruntime':version('onnxruntime')},
                'device':'cpu', 'cpu_affinity':self.cpus, 'cast':self.plan.describe(),
                'model_files':[str(self.model),str(self.model)+'.json']}


class KokoroEngine(Engine):
    def prepare(self, cues):
        self.plan.validate_cues(cues)

    def __init__(self, model_dir: Path, plan: VoicePlan, threads: int = 2):
        self.model_dir = model_dir.resolve()
        for name in ['config.json','kokoro-v1_0.pth']:
            if not (model_dir/name).is_file():
                raise FileNotFoundError(f'Missing local Kokoro file: {model_dir/name}')
        self.cpus = bound_cpu(threads)
        # Keep any optional library caches within this model's repo environment.
        os.environ['HF_HUB_OFFLINE'] = '1'
        os.environ['HF_HUB_DISABLE_IMPLICIT_TOKEN'] = '1'
        os.environ.setdefault('HF_HOME',str(self.model_dir.parent.parent/'.cache/huggingface'))
        import torch
        from kokoro import KModel, KPipeline
        torch.set_num_threads(threads)
        if torch.get_num_interop_threads() != 1:
            torch.set_num_interop_threads(1)
        self.torch = torch
        self.plan = plan
        model = KModel(repo_id='hexgrad/Kokoro-82M', config=str(model_dir/'config.json'),
                       model=str(model_dir/'kokoro-v1_0.pth')).to('cpu').eval()
        self.pipeline = KPipeline(lang_code='a',repo_id='hexgrad/Kokoro-82M',model=model,device='cpu')
        if self.pipeline.g2p.fallback is None:
            raise RuntimeError('Kokoro espeak fallback missing; refusing unspoken unknown words')
        self.voices = {}
        self.last_result = {}

    def synthesize(self, cue, destination):
        import numpy as np
        import soundfile as sf
        settings = self.plan.resolve(cue)
        if settings.speaker_id is not None:
            raise ValueError('Kokoro uses named voices, not speaker_id')
        voice = settings.voice or 'af_heart'
        if not voice.startswith('a') or Path(voice).name != voice:
            raise ValueError('Kokoro English voice must be a local American-English stock voice name')
        path = self.model_dir/'voices'/f'{voice}.pt'
        if not path.is_file():
            raise FileNotFoundError(f'Missing local voice: {path}')
        if voice not in self.voices:
            self.voices[voice] = self.pipeline.load_voice(str(path))
        self.torch.manual_seed(42)
        chunks = list(self.pipeline(cue.text,voice=self.voices[voice],speed=settings.speed))
        if not chunks:
            raise RuntimeError(f'No Kokoro speech for cue {cue.index}')
        for chunk in chunks:
            for token in chunk.tokens or []:
                if any(c.isalpha() for c in token.text) and not token.phonemes:
                    raise RuntimeError(f'Unspoken token {token.text!r} in cue {cue.index}')
            if len(chunk.phonemes)>510:
                raise RuntimeError('Kokoro phoneme limit exceeded')
        audio = np.concatenate([c.audio.numpy() for c in chunks])
        if not len(audio) or not np.isfinite(audio).all():
            raise RuntimeError('Kokoro returned empty or nonfinite audio')
        sf.write(destination,audio,24000,subtype='PCM_16')
        self.last_result = {'voice_settings':{**settings.to_dict(),'voice':voice},
                            'phonemes':[c.phonemes for c in chunks],
                            'float_samples_outside_pcm_range':int(np.count_nonzero((audio < -1)|(audio >= 1)))}

    def describe(self):
        return {'backend':'kokoro', 'versions':{name:version(name) for name in ['kokoro','torch','misaki']},
                'device':'cpu','cpu_affinity':self.cpus,'seed_per_cue':42,'cast':self.plan.describe(),
                'model_files':[str(self.model_dir/'config.json'),str(self.model_dir/'kokoro-v1_0.pth')]+
                              [str(self.model_dir/'voices'/f'{v}.pt') for v in sorted(self.voices)]}
