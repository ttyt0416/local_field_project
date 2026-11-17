from __future__ import annotations

import json
import re
from collections.abc import Sequence
from typing import Any


TASK_TYPES = ("keyframe completion", "reference generation", "video editing", "video continuation", "audio reuse", "audio reference")
FIELD_LIMITS = {
    "style": 768, "timeline": 3072, "camera": 384, "audio": 4096, "text": 2048,
    "overall_soundscape": 768, "non_diegetic_music": 768,
    "subject_definitions": 3072, "summary": 1024, "retention_analysis": 3072,
}
_LANGUAGE_NAMES = {"en": "English", "ko": "Korean", "ja": "Japanese"}
_LANGUAGE_CHARS = {
    "en": r"A-Za-z",
    "ko": r"\u1100-\u11FF\u3131-\u318E\uAC00-\uD7A3",
    "ja": r"\u3001-\u303F\u3040-\u309F\u30A0-\u30FF\u3400-\u4DBF\u4E00-\u9FFF\uFF66-\uFF9D",
}
_PUNCTUATION = r"\x20-\x21\x23-\x3B\x3D\x3F-\x40\x5B\x5D-\x60\x7B-\x7E"
_PROTOCOL_LITERALS = ("N/A", "fully_preserved", "partially_preserved", "attribute_transfer", "weak_reference", "fully_copy", "partially_copy", "reference")


_SPEAKER = r'\(S[1-9][0-9]*(?:,S[1-9][0-9]*)*\)'


def _prose_characters(languages: Sequence[str]) -> str:
    if not languages or any(language not in _LANGUAGE_CHARS for language in languages):
        raise ValueError("지원하지 않는 동영상 프롬프트 출력 언어입니다.")
    return _PUNCTUATION + ''.join(_LANGUAGE_CHARS[language] for language in dict.fromkeys(languages))


def field_pattern(field: str, labels: Sequence[str] | None = None, *, languages: Sequence[str] = ("en",)) -> str:
    characters = _prose_characters(languages)
    prose = '[' + characters + r'\x5C\n]'
    dialogue_char = '[' + characters + r'\x22\x5C\n]'
    quoted_char = '[' + characters + r'\x5C]'
    dialogue_languages = '|'.join(_LANGUAGE_NAMES[language] for language in dict.fromkeys(languages))
    assets = r'<(?:Picture|Video|Audio) [1-9][0-9]*>' if labels is None else '|'.join(map(re.escape, labels))
    markers = [r'<Subject [1-9][0-9]*>', *map(re.escape, _PROTOCOL_LITERALS)]
    if assets:
        markers.append(assets)
    if field != "retention_analysis":
        markers.append(_SPEAKER)
    if field == "audio":
        markers.append(rf'<d>\[(?:{dialogue_languages})\](?:<scenetrans>)?{dialogue_char}+(?:<(?:scenetrans|cutoff)>)?</d>')
    if field == "text":
        markers.append('"' + quoted_char + '+"')
    atom = '(?:' + '|'.join((prose, *markers)) + ')'
    word_characters = characters.replace(_PUNCTUATION, '0-9').replace(r"\u3001-\u303F", '')
    start = '(?:' + '|'.join(('[' + word_characters + ']', *markers)) + ')'
    body = start + atom + '*'
    if field == "summary":
        task = '(?:' + '|'.join(map(re.escape, TASK_TYPES)) + ')'
        body = rf'\[{task}(?: \+ {task})*\] ' + body
    return r'^(?=\S)' + body + r'(?<=\S)$'


def _terminal(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _number_range(low: int, high: int) -> str:
    def interval(a: str, b: str) -> str:
        if a == b:
            return _terminal(a)
        if a == '0' * len(a) and b == '9' * len(b):
            return '[0-9]' + (f'{{{len(a)}}}' if len(a) > 1 else '')
        if a[0] == b[0]:
            return _terminal(a[0]) + ' ' + interval(a[1:], b[1:])
        rest = len(a) - 1
        choices = []
        if rest:
            choices.append(_terminal(a[0]) + ' ' + interval(a[1:], '9' * rest))
        else:
            choices.append(_terminal(a[0]))
        if int(b[0]) - int(a[0]) > 1:
            middle = f'[{int(a[0]) + 1}-{int(b[0]) - 1}]'
            choices.append(middle + (f' [0-9]{{{rest}}}' if rest else ''))
        choices.append(_terminal(b[0]) + (' ' + interval('0' * rest, b[1:]) if rest else ''))
        return '(' + ' | '.join(choices) + ')'

    choices = []
    for width in range(len(str(low)), len(str(high)) + 1):
        start = max(low, 0 if width == 1 else 10 ** (width - 1))
        end = min(high, 10 ** width - 1)
        if start <= end:
            choices.append(interval(str(start), str(end)))
    return '(' + ' | '.join(choices) + ')'


def video_prompt_gbnf(schema: dict[str, Any], *, labels: Sequence[str] = (), languages: Sequence[str] = ("en",)) -> str:
    rules = [
        'ws ::= [ \\t\\n\\r]{0,4}',
        'speaker ::= "(S" [1-9] [0-9]{0,2} (",S" [1-9] [0-9]{0,2}){0,15} ")"',
        'subject ::= "<Subject " [1-9] [0-9]{0,2} ">"',
        'cut-tag ::= "<scenetrans>" | "<cutoff>"',
    ]
    characters = _prose_characters(languages)
    visible_characters = characters.replace(r"\x20-\x21", r"\x21")
    word_characters = characters.replace(_PUNCTUATION, '0-9').replace(r"\u3001-\u303F", '')
    rules.extend((
        'prose-char ::= [' + characters + r'] | "\\\\" | "\\n"',
        'prose-visible ::= [' + visible_characters + r'] | "\\\\"',
        'prose-word ::= [' + word_characters + ']',
        'protocol ::= ' + ' | '.join(_terminal(value) for value in _PROTOCOL_LITERALS),
    ))
    if labels:
        rules.append('asset ::= ' + ' | '.join(_terminal(label) for label in dict.fromkeys(labels)))
    rules.extend((
        'quoted-char ::= [' + characters + r'] | "\\\\"',
        'dialogue-char ::= prose-char | ' + _terminal('\\"'),
        'dialogue-language ::= ' + ' | '.join(_terminal(_LANGUAGE_NAMES[language]) for language in dict.fromkeys(languages)),
        'dialogue ::= "<d>[" dialogue-language "]" "<scenetrans>"? dialogue-char{1,2048} cut-tag? "</d>"',
        'visible-text ::= ' + _terminal('\\"') + ' quoted-char{1,1024} ' + _terminal('\\"'),
        'task ::= ' + ' | '.join(_terminal(task) for task in TASK_TYPES),
    ))
    properties = schema['properties']
    shot_schema = properties['shots']
    sample = shot_schema['items']['properties']
    top_fields = [key for key in properties if key != 'shots']
    string_fields = {key: value for key, value in sample.items() if value.get('type') == 'string'}
    string_fields.update({key: properties[key] for key in top_fields})
    for name, field in string_fields.items():
        alternatives = ['prose-char', 'subject', 'protocol']
        if labels:
            alternatives.append('asset')
        if name != 'retention_analysis':
            alternatives.append('speaker')
        if name == 'audio':
            alternatives.append('dialogue')
        if name == 'text':
            alternatives.append('visible-text')
        atom = '(' + ' | '.join(alternatives) + ')'
        prefix = '"[" task (" + " task){0,5} "] " ' if name == 'summary' else ''
        visible = "(" + " | ".join(["prose-visible", *alternatives[1:]]) + ")"
        start = "(" + " | ".join(["prose-word", *alternatives[1:]]) + ")"
        rules.append(name.replace("_", "-") + ' ::= "\\\"" ' + prefix + start + " (" + atom + "{0," + str(field["maxLength"] - 2) + "} " + visible + ')? "\\\""')

    def member(name: str, value: str) -> str:
        return _terminal(json.dumps(name)) + ' ws ":" ws ' + value

    def shot(name: str, definition: dict[str, Any]) -> None:
        members = []
        for key, value in definition['properties'].items():
            if 'const' in value:
                rule = _terminal(str(value['const']))
            elif value['type'] == 'integer':
                rule = _number_range(value['minimum'], value['maximum'])
            else:
                rule = key.replace('_', '-')
            members.append(member(key, rule))
        rules.append(name + ' ::= "{" ws ' + ' ws "," ws '.join(members) + ' ws "}"')

    prefix = shot_schema['prefixItems']
    if shot_schema['minItems'] == shot_schema['maxItems']:
        names = []
        for index, definition in enumerate(prefix):
            name = f'shot-{index + 1}'
            shot(name, definition)
            names.append(name)
        shots = ' ws "," ws '.join(names)
    else:
        shot('first-shot', prefix[0])
        shot('later-shot', shot_schema['items'])
        shots = 'first-shot (ws "," ws later-shot){0,' + str(shot_schema['maxItems'] - 1) + '}'
    members = [member('shots', '"[" ws ' + shots + ' ws "]"')]
    members.extend(member(name, name.replace('_', '-')) for name in top_fields)
    rules.append('root ::= "{" ws ' + ' ws "," ws '.join(members) + ' ws "}"')
    return '\n'.join(rules) + '\n'
