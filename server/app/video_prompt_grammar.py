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
_LANGUAGE_CHARS = {
    "en": r"A-Za-z",
    "ko": r"\u1100-\u11FF\u3131-\u318E\uAC00-\uD7A3",
    "ja": r"\u3001-\u303F\u3040-\u309F\u30A0-\u30FF\u3400-\u4DBF\u4E00-\u9FFF\uFF66-\uFF9D",
}
_PUNCTUATION = r"\x20-\x21\x23-\x3B\x3D\x3F-\x40\x5B\x5D-\x60\x7B-\x7E"
_PROTOCOL_LITERALS = ("N/A", "fully_preserved", "partially_preserved", "attribute_transfer", "weak_reference", "fully_copy", "partially_copy", "reference", "says in an off-screen voiceover")


_SPEAKER = r'\(S[1-9][0-9]*(?:,S[1-9][0-9]*)*\)'
_DIALOGUE = r'<d>\[[A-Za-z][A-Za-z -]{0,39}\][^<>]+(?:<(?:scenetrans|cutoff)>[^<>]*)*</d>'
_QUOTED = r'"[^"\n]+"'
_SOURCE_QUOTES = re.compile(r'<d>\[[^\]]+\](.*?)</d>|"([^"\n]+)"|“([^”\n]+)”|「([^」\n]+)」|『([^』\n]+)』|(?<!\w)\x27([^\x27\n]+)\x27(?!\w)', re.DOTALL)


def _prose_characters(languages: Sequence[str]) -> str:
    if not languages or any(language not in _LANGUAGE_CHARS for language in languages):
        raise ValueError("지원하지 않는 동영상 프롬프트 출력 언어입니다.")
    return _PUNCTUATION + ''.join(_LANGUAGE_CHARS[language] for language in dict.fromkeys(languages))


def source_literals(source: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(re.sub(r'</?(?:scenetrans|cutoff)>', '', next(value for value in match.groups() if value is not None)) for match in _SOURCE_QUOTES.finditer(source)))


def field_pattern(field: str, labels: Sequence[str] | None = None, *, languages: Sequence[str] = ("en",)) -> str:
    assets = r'<(?:Picture|Video|Audio) [1-9][0-9]*>' if labels is None else '|'.join(map(re.escape, labels))
    markers = [r'<Subject [1-9][0-9]*>', *map(re.escape, _PROTOCOL_LITERALS)]
    if assets:
        markers.append(assets)
    if field != "retention_analysis":
        markers.append(_SPEAKER)
    if field == "audio":
        markers.extend((_DIALOGUE, r'<(?:scenetrans|cutoff)>'))
    if field == "text":
        markers.append(_QUOTED)
    prose = '[' + _prose_characters(languages) + r'\x5C\n]'
    atom = '(?:' + '|'.join((prose, *markers)) + ')'
    body = atom + '+'
    if field == "summary":
        task = '(?:' + '|'.join(map(re.escape, TASK_TYPES)) + ')'
        body = rf'\[{task}(?: \+ {task})*\] ' + body
    return r'^(?=\S)' + body + r'(?<=\S)$'


def _terminal(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _json_content(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)[1:-1]


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


def video_prompt_gbnf(schema: dict[str, Any], *, labels: Sequence[str] = (), literals: Sequence[str] = (), languages: Sequence[str] = ("en",)) -> str:
    rules = [
        'ws ::= [ \\t\\n\\r]{0,4}',
        r'unicode-char ::= [^"\\\x00-\x1F<>] | "\\\\" | "\\\""',
        'speaker ::= "(S" [1-9] [0-9]{0,2} (",S" [1-9] [0-9]{0,2}){0,15} ")"',
        'subject ::= "<Subject " [1-9] [0-9]{0,2} ">"',
        'cut-tag ::= "<scenetrans>" | "<cutoff>"',
    ]
    characters = _prose_characters(languages)
    visible_characters = characters.replace(r"\x20-\x21", r"\x21")
    rules.extend((
        'prose-char ::= [' + characters + r'] | "\\\\" | "\\n"',
        'prose-visible ::= [' + visible_characters + r'] | "\\\\"',
        'protocol ::= ' + ' | '.join(_terminal(value) for value in _PROTOCOL_LITERALS),
    ))
    if labels:
        rules.append('asset ::= ' + ' | '.join(_terminal(label) for label in dict.fromkeys(labels)))
    if literals:
        rules.append('original ::= ' + ' | '.join(_terminal(_json_content(value)) for value in literals))
        dialogue_body = 'original'
        quoted_body = 'original'
    else:
        dialogue_body = '(unicode-char | cut-tag){1,2048}'
        quoted_body = 'unicode-char{1,1024}'
    rules.extend((
        'dialogue ::= "<d>[" [A-Za-z] [A-Za-z -]{0,39} "]" " "? cut-tag? ' + dialogue_body + ' cut-tag? "</d>"',
        'visible-text ::= ' + _terminal('\\"') + ' ' + quoted_body + ' ' + _terminal('\\"'),
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
            alternatives.extend(('dialogue', 'cut-tag'))
        if name == 'text':
            alternatives.append('visible-text')
        atom = '(' + ' | '.join(alternatives) + ')'
        prefix = '"[" task (" + " task){0,5} "] " ' if name == 'summary' else ''
        visible = "(" + " | ".join(["prose-visible", *alternatives[1:]]) + ")"
        rules.append(name.replace("_", "-") + ' ::= "\\\"" ' + prefix + visible + " (" + atom + "{0," + str(field["maxLength"] - 2) + "} " + visible + ')? "\\\""')

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
