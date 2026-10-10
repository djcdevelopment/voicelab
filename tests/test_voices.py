from pathlib import Path
import json
import tempfile
import unittest
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from subtitle_lab.voices import VoicePlan, VoiceSettings
from subtitle_lab.subtitles import Cue


class VoicePlanTests(unittest.TestCase):
    def test_manual_precedence_preserves_other_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'cast.json'
            p.write_text(json.dumps({'default':{'speed':.95},'speakers':{'Mai':{'voice':'af_heart','character':'Mai'}},'cues':{'2':{'voice':'am_michael'}}}))
            plan=VoicePlan(path=p)
            cues=[Cue(1,0,1000,'First','Mai'),Cue(2,1000,2000,'Second','Mai')]
            plan.validate_cues(cues)
            self.assertEqual(plan.resolve(cues[1]).voice,'am_michael')
            self.assertEqual(plan.resolve(cues[1]).speed,.95)
            self.assertEqual(plan.resolve(cues[1]).character,'Mai')

    def test_invalid_speed_and_unrecognized_setting_fail(self):
        for speed in [float('nan'),float('inf'),0,3,True]:
            with self.subTest(speed=speed), self.assertRaises(ValueError):
                VoicePlan(VoiceSettings(speed=speed))
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'cast.json';p.write_text('{"default":{"speeed":1}}')
            with self.assertRaises(ValueError):VoicePlan(path=p)

    def test_unused_assignments_are_not_silently_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'cast.json';p.write_text('{"cues":{"9":{"character":"Mai"}}}')
            plan=VoicePlan(path=p)
            with self.assertRaises(ValueError):plan.validate_cues([Cue(1,0,1000,'First')])
