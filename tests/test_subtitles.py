from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from subtitle_lab.subtitles import load_cues, parse_ass, parse_srt_vtt, plain_text, summary, timestamp_ms

SAMPLES = Path(__file__).resolve().parents[1] / "samples"


class SubtitleParsingTests(unittest.TestCase):
    def test_vtt_note_with_timestamp_is_not_spoken(self):
        source = "WEBVTT\n\nNOTE editor example\n00:00:00.000 --> 00:00:01.000\nDo not speak this.\n\ncue-id\n00:00:02.000 --> 00:00:03.000 align:start\n<v Mai>Keep this.\n"
        cues = parse_srt_vtt(source)
        self.assertEqual(len(cues), 1)
        self.assertEqual((cues[0].start_ms, cues[0].text, cues[0].speaker),
                         (2000, "Keep this.", "Mai"))

    def test_timestamps(self):
        self.assertEqual(timestamp_ms("00:01:23,456"), 83456)
        self.assertEqual(timestamp_ms("01:23.45"), 83450)
        self.assertEqual(timestamp_ms("0:00:02.70"), 2700)
        with self.assertRaises(ValueError):
            timestamp_ms("00:61:00.00")

    def test_srt(self):
        cues = load_cues(SAMPLES / "demo.srt")
        self.assertEqual(len(cues), 5)
        self.assertEqual(cues[0].start_ms, 600)
        self.assertEqual(cues[-1].end_ms, 16000)
        self.assertEqual(summary(cues)["overlapping_source_cues"], 0)

    def test_vtt(self):
        cues = load_cues(SAMPLES / "demo.vtt")
        self.assertEqual(len(cues), 5)
        self.assertEqual(cues[0].speaker, "Narrator")
        self.assertIn("subtitle timing", cues[1].text)
        self.assertNotIn("<i>", cues[1].text)

    def test_ass(self):
        cues = load_cues(SAMPLES / "demo.ass")
        self.assertEqual(len(cues), 5)
        self.assertEqual(cues[0].speaker, "Narrator")
        self.assertEqual(cues[0].start_ms, 600)
        self.assertEqual(cues[1].text, "It should preserve subtitle timing.")

    def test_multiline_and_entities(self):
        cues = parse_srt_vtt("00:00:00.100 --> 00:00:01.200\nA &amp; B\nC <b>fine</b>\n")
        self.assertEqual(cues[0].text, "A & B C fine")

    def test_ass_commas_are_dialogue_content(self):
        source = """[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:01.00,0:00:03.00,Default,Mai,0,0,0,,Hello, everyone!\\NStay here.
"""
        cues = parse_ass(source)
        self.assertEqual(cues[0].text, "Hello, everyone! Stay here.")

    def test_reject_invalid_or_empty(self):
        with self.assertRaises(ValueError):
            parse_srt_vtt("00:00:01.000 --> 00:00:00.500\nOut of order\n")
        self.assertEqual(parse_srt_vtt("WEBVTT\n\nNOTE empty\n"), [])
        self.assertEqual(plain_text("{\\an8}Now\\Nthen", ass=True), "Now then")


if __name__ == "__main__":
    unittest.main()
