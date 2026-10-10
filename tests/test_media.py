from pathlib import Path
import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from subtitle_lab.media import extract_captions,compose_video,probe,validate_media,audit_captions
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

    def test_caption_audit_rejects_longer_movie_captions_before_synthesis(self):
        self.assertEqual(audit_captions(self.source,self.captions)['status'],'PASS')
        self.captions.write_text('1\n00:01:47,250 --> 00:01:50,500\nWrong release captions.\n')
        result=audit_captions(self.source,self.captions)
        self.assertEqual(result['status'],'FAIL')
        self.assertEqual(result['out_of_bounds_cues'][0]['beyond_video_ms'],108500)
        self.assertFalse((self.base/'speech').exists())

    def test_media_tamper_is_detected(self):
        out=self.base/'extract';extract_captions(self.source,out)
        (out/'subtitles.srt').write_text('changed')
        with self.assertRaises(RuntimeError):validate_media(out)

    def shifted_source(self):
        shifted=self.base/'shifted.mkv'
        subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-nostdin','-n',
            '-copyts','-itsoffset','2','-i',str(self.source),'-map','0','-c','copy',str(shifted)],check=True)
        combined=self.base/'early-audio.mkv'
        subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-nostdin','-n',
            '-copyts','-i',str(shifted),'-f','lavfi','-i','sine=frequency=180:duration=4',
            '-map','0:v:0','-map','0:s:0','-map','1:a:0','-c:v','copy','-c:s','copy',
            '-c:a','pcm_s16le',str(combined)],check=True)
        return combined

    def test_explicit_video_clock_ignores_earlier_original_audio_origin(self):
        source=self.shifted_source()
        info=probe(source)
        self.assertEqual(info['video_first_pts_s'],2)
        self.assertEqual(next(s for s in info['streams'] if s['type']=='audio')['start_s'],0)
        out=self.base/'mapped';result=extract_captions(source,out,clock='video')
        self.assertEqual(load_cues(out/'subtitles.srt'),load_cues(self.captions))
        self.assertEqual(load_cues(out/'source-subtitles.srt')[0].start_ms,2100)
        self.assertEqual(result['clock_mapping']['subtitle_offset_ms'],2000)
        self.assertEqual(audit_captions(source,out/'source-subtitles.srt',clock='source')['status'],'PASS')
        self.assertEqual(audit_captions(source,out/'subtitles.srt',clock='video')['status'],'PASS')
        self.assertEqual(audit_captions(source,out/'subtitles.srt',clock='source')['status'],'FAIL')
        run=self.base/'speech';render(out/'subtitles.srt',run,ToneEngine(),'tone')
        with self.assertRaisesRegex(ValueError,'clock mappings disagree'):
            compose_video(source,run,self.base/'unmapped')
        different=self.base/'different-source.mkv';different.write_bytes(self.source.read_bytes())
        with self.assertRaisesRegex(ValueError,'different source media'):
            compose_video(different,run,self.base/'wrong-source',clock='video')
        playback=self.base/'playback';compose_video(source,run,playback,clock='video')
        played=probe(playback/'dubbed.mp4')
        self.assertAlmostEqual(played['video_first_pts_s'],0,places=3)
        self.assertAlmostEqual(played['video_end_pts_s'],2,places=3)
        self.assertEqual(validate_media(playback)['status'],'PASS')

    def test_captions_before_video_are_preserved_as_failure_not_clipped(self):
        shifted=self.shifted_source();source=self.base/'early-captions.mkv'
        subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-nostdin','-n',
            '-copyts','-i',str(shifted),'-i',str(self.captions),'-map','0:v:0','-map','1:s:0',
            '-c:v','copy','-c:s','srt',str(source)],check=True)
        out=self.base/'failed-extraction'
        with self.assertRaisesRegex(ValueError,'refusing to discard or clip'):
            extract_captions(source,out,clock='video')
        self.assertEqual(load_cues(out/'source-subtitles.srt'),load_cues(self.captions))
        self.assertTrue((out/'failure.json').is_file())
        self.assertFalse((out/'subtitles.srt').exists())
