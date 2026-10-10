from pathlib import Path
import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from subtitle_lab.media import extract_captions,compose_video,probe,validate_media
from subtitle_lab.pipeline import render
from subtitle_lab.subtitles import load_cues
from subtitle_lab.tts import ToneEngine


@unittest.skipUnless(shutil.which('ffmpeg') and importlib.util.find_spec('av'),'optional FFmpeg/PyAV integration')
class MediaTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name)
        self.source=self.base/'source.mkv'
        self.captions=self.base/'source.srt'
        self.captions.write_text('1\n00:00:00,100 --> 00:00:00,900\nA short test.\n')
        subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-nostdin','-n',
            '-f','lavfi','-i','color=c=blue:s=128x96:r=10:d=2',
            '-i',str(self.captions),'-map','0:v:0','-map','1:s:0',
            '-c:v','libx264','-threads','1','-c:s','srt',str(self.source)],check=True)

    def test_extraction_preserves_text_and_exact_clock(self):
        out=self.base/'extract';extract_captions(self.source,out)
        self.assertEqual(load_cues(self.captions),load_cues(out/'subtitles.srt'))
        self.assertEqual(validate_media(out)['status'],'PASS')
        with self.assertRaises(FileExistsError):extract_captions(self.source,out)

    def test_single_file_has_both_streams_and_correct_duration(self):
        run=self.base/'run';render(self.captions,run,ToneEngine(),'tone')
        out=self.base/'playback';compose_video(self.source,run,out)
        info=probe(out/'dubbed.mp4')
        self.assertEqual({s['type'] for s in info['streams']},{'video','audio'})
        self.assertAlmostEqual(info['video_end_pts_s'],2.0,places=2)
        self.assertEqual(validate_media(out)['status'],'PASS')
        self.assertEqual(load_cues(out/'captions.vtt'),load_cues(self.captions))

    def test_speech_beyond_video_is_rejected_before_writing(self):
        self.captions.write_text('1\n00:00:01,900 --> 00:00:02,000\nThis utterance will continue well beyond the video.\n')
        run=self.base/'run';render(self.captions,run,ToneEngine(),'tone')
        out=self.base/'cut'
        with self.assertRaisesRegex(ValueError,'refusing truncation'):compose_video(self.source,run,out)
        self.assertFalse(out.exists())

    def test_missing_track_and_negative_track_index_fail(self):
        with self.assertRaises(ValueError):extract_captions(self.source,self.base/'none',99)
        with self.assertRaises(ValueError):extract_captions(self.source,self.base/'negative',-1)

    def test_media_tamper_is_detected(self):
        out=self.base/'extract';extract_captions(self.source,out)
        (out/'subtitles.srt').write_text('changed')
        with self.assertRaises(RuntimeError):validate_media(out)
