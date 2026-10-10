from pathlib import Path
import importlib.util
import tempfile
import unittest
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from subtitle_lab.review import create_app
import json
import shutil
from subtitle_lab.review import build_comparison
from subtitle_lab.pipeline import render,file_sha256
from subtitle_lab.tts import ToneEngine


class ComparisonTests(unittest.TestCase):
    def test_mismatched_words_rejected_before_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);runs=[]
            for i,text in enumerate(('Hello there.','Different words.')):
                source=root/f'{i}.srt'
                source.write_text(f'1\n00:00:00,500 --> 00:00:02,000\n{text}\n')
                run=root/f'run{i}';render(source,run,ToneEngine(),'tone');runs.append(run)
            with self.assertRaisesRegex(ValueError,'identical normalized'):
                build_comparison(runs,root/'comparison')
            self.assertFalse((root/'comparison').exists())

    @unittest.skipUnless(shutil.which('ffmpeg'),'optional FFmpeg comparison integration')
    def test_excerpt_preserves_full_original_and_selected_utterance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'source.srt'
            source.write_text('1\n00:00:00,500 --> 00:00:02,000\nHello there.\n\n2\n00:00:03,000 --> 00:00:05,000\nAnother sentence.\n')
            runs=[root/'a',root/'b']
            for run in runs:render(source,run,ToneEngine(),'tone')
            result=build_comparison(runs,root/'comparison',first_cues=1)
            self.assertEqual(file_sha256(root/'comparison/candidate-01.wav'),file_sha256(runs[0]/'dub.wav'))
            self.assertEqual(result['excerpt']['source_start_s'],.5)
            m=json.loads((runs[0]/'manifest.json').read_text())
            self.assertGreaterEqual(result['excerpt']['source_end_s'],(.5+m['cues'][0]['speech_duration_ms']/1000))
            self.assertTrue((root/'comparison/candidate-01-excerpt.wav').is_file())
            self.assertEqual(result['candidates'][0]['quality_verdict'],'awaiting_listener_review')


@unittest.skipUnless(importlib.util.find_spec('flask'),'optional Flask range-response integration')
class ReviewTests(unittest.TestCase):
    def test_byte_ranges_and_directory_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'clip.mp4').write_bytes(bytes(range(100)))
            (root/'index.html').write_text('root');(root/'scene').mkdir();(root/'scene/index.html').write_text('scene')
            client=create_app(root).test_client()
            response=client.get('/clip.mp4',headers={'Range':'bytes=10-19'})
            self.assertEqual(response.status_code,206)
            self.assertEqual(response.data,bytes(range(10,20)))
            self.assertEqual(response.headers['Content-Range'],'bytes 10-19/100')
            self.assertEqual(client.get('/scene/').data,b'scene')
            self.assertEqual(client.get('/').data,b'root')

    def test_hidden_files_and_symlink_escape_are_not_served(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'review';root.mkdir()
            (root/'.env').write_text('synthetic placeholder')
            external=Path(tmp)/'outside.wav';external.write_bytes(b'synthetic')
            (root/'escape.wav').symlink_to(external)
            client=create_app(root).test_client()
            self.assertEqual(client.get('/.env').status_code,404)
            self.assertEqual(client.get('/escape.wav').status_code,404)
            self.assertEqual(client.get('/../outside.wav').status_code,404)
