"""Explicit, auditable voice assignments; never infer a character from text."""
from dataclasses import asdict, dataclass, replace
from pathlib import Path
import json
import math

from .subtitles import Cue


@dataclass(frozen=True)
class VoiceSettings:
    voice: str | None = None
    speed: float = 1.0
    speaker_id: int | None = None
    character: str | None = None

    def to_dict(self):
        return asdict(self)


def _settings(base: VoiceSettings, values: dict) -> VoiceSettings:
    if not isinstance(values, dict) or set(values) - set(base.to_dict()):
        raise ValueError('Cast settings must contain only voice, speed, speaker_id, character')
    result = replace(base, **values)
    if isinstance(result.speed, bool) or not isinstance(result.speed, (float, int)) or not math.isfinite(result.speed) or not .5 <= result.speed <= 2:
        raise ValueError('Speech speed must be finite and between 0.5 and 2')
    if result.speaker_id is not None and (type(result.speaker_id) is not int or result.speaker_id < 0):
        raise ValueError('speaker_id must be a nonnegative integer')
    for name in ('voice', 'character'):
        value = getattr(result, name)
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise ValueError(f'{name} must be nonempty text')
    return result


class VoicePlan:
    def __init__(self, default: VoiceSettings | None = None, path: Path | None = None):
        self.default = _settings(default or VoiceSettings(), {})
        self.path = path.resolve() if path else None
        self.speakers = {}
        self.cues = {}
        if path:
            data = json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(data, dict) or set(data) - {'default', 'speakers', 'cues'}:
                raise ValueError('Cast plan allows only default, speakers, cues')
            self.default = _settings(self.default, data.get('default', {}))
            self.speakers = data.get('speakers', {})
            self.cues = data.get('cues', {})
            if not isinstance(self.speakers, dict) or not isinstance(self.cues, dict):
                raise ValueError('Cast speakers and cues must be objects')
            for key, values in self.cues.items():
                if not key.isdigit() or int(key) <= 0 or str(int(key)) != key:
                    raise ValueError('Cast cue keys must be canonical positive cue indices')
                _settings(self.default, values)
            for values in self.speakers.values():
                _settings(self.default, values)

    def validate_cues(self, cues: list[Cue]):
        missing = set(self.cues) - {str(c.index) for c in cues}
        unknown = set(self.speakers) - {c.speaker for c in cues if c.speaker}
        if missing or unknown:
            raise ValueError(f'Unused cast assignments: cues={sorted(missing)}, speakers={sorted(unknown)}')

    def resolve(self, cue: Cue) -> VoiceSettings:
        settings = self.default
        if cue.speaker in self.speakers:
            settings = _settings(settings, self.speakers[cue.speaker])
        return _settings(settings, self.cues.get(str(cue.index), {}))

    def describe(self) -> dict:
        return {'default': self.default.to_dict(), 'speakers': self.speakers, 'cues': self.cues}
