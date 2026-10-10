from pathlib import Path
from array import array
import tempfile
import unittest
import sys
import wave
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from subtitle_lab.audio import mix_to_wav, wav_frames, write_pcm16


class AudioTests(unittest.TestCase):
    def test_negative_start_and_short_mix_end_fail_instead_of_cutting(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'mix.wav'
            with self.assertRaises(ValueError):mix_to_wav([(-1,array('h',[100]))],path,100)
            with self.assertRaises(ValueError):mix_to_wav([(100,array('h',[100]*2400))],path,101)
            self.assertFalse(path.exists())

    def test_overlap_clipping_and_exact_placement(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'mix.wav'
            pcm=array('h',[30000]*24)
            result=mix_to_wav([(1,pcm),(1,pcm)],path,3)
            self.assertEqual(result['clipped_samples'],24)
            data=array('h');data.frombytes(wav_frames(path)[3])
            self.assertEqual(list(data[:24]),[0]*24)
            self.assertEqual(list(data[24:48]),[32767]*24)

    def test_truncated_wav_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'bad.wav';write_pcm16(path,array('h',[100]*100))
            path.write_bytes(path.read_bytes()[:-20])
            with self.assertRaises(ValueError):wav_frames(path)
