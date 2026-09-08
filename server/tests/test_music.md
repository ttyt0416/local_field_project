# Music generation tests

`test_music.py`는 Music 3 workflow binding, model readiness, audio output validation, Storage sync를 검증한다. Music vLLM enhancement는 description과 lyrics target을 따로 호출하고, selected language strict schema, blank lyrics generation, duplicate language rejection, 한글-only output의 standard section tag 허용, provider response audit relay를 확인한다.
