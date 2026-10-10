from pathlib import Path
import json
import shutil
import tempfile
import unittest
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from subtitle_lab.audio import duration_ms
from subtitle_lab.pipeline import render,validate,file_sha256
from subtitle_lab.tts import ToneEngine,WavDirectoryEngine


class TimingTests(unittest.TestCase):
    def test_manifest_timing_tamper_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);s=base/'cue.srt'
            s.write_text('1\n00:00:00,100 --> 00:00:02,000\nA short test.\n')
            m=render(s,base/'run',ToneEngine(),'tone')
            m['cues'][0]['speech_duration_ms']+=1000
            (base/'run/manifest.json').write_text(json.dumps(m))
            with self.assertRaises(ValueError):validate(base/'run')

    def test_normalized_cues_are_checksummed(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);s=base/'cue.srt'
            s.write_text('1\n00:00:00,100 --> 00:00:02,000\nA short test.\n')
            render(s,base/'run',ToneEngine(),'tone')
            (base/'run/cues.json').write_text('[]')
            with self.assertRaises(RuntimeError):validate(base/'run')

    def test_legacy_v1_manifest_still_validates(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);s=base/'cue.srt'
            s.write_text('1\n00:00:00,100 --> 00:00:02,000\nA short test.\n')
            m=render(s,base/'run',ToneEngine(),'tone');m['schema_version']='subtitle-lab-render-v1'
            (base/'run/manifest.json').write_text(json.dumps(m))
            self.assertEqual(validate(base/'run')['status'],'PASS')

    @unittest.skipUnless(shutil.which('ffmpeg'),'optional FFmpeg integration')
    def test_capped_fit_retains_original_and_reports_remaining_overflow(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);s=base/'cue.srt'
            s.write_text('1\n00:00:00,100 --> 00:00:00,250\nThe utterance is much too long for this window.\n')
            original=render(s,base/'original',ToneEngine(),'tone')
            fitted=render(s,base/'fitted',WavDirectoryEngine(base/'original/stems'),'wav-dir',fit_max_speedup=1.15)
            cue=fitted['cues'][0]
            self.assertEqual(cue['stem_sha256'],original['cues'][0]['stem_sha256'])
            self.assertEqual(cue['fit']['factor'],1.15)
            self.assertGreater(cue['cue_overrun_ms'],0)
            self.assertLess(cue['speech_duration_ms'],cue['original_speech_duration_ms'])
            self.assertEqual(validate(base/'fitted')['status'],'PASS')
            self.assertGreater(duration_ms(base/'fitted/dub.wav'),150)
