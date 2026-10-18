import json
import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MossLayoutElement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["object", "character", "text"] = "object"
    caption: str = Field(default="", max_length=500)
    text: str = Field(default="", max_length=200)
    x: float = Field(ge=0, lt=1)
    y: float = Field(ge=0, lt=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def within_canvas(self) -> "MossLayoutElement":
        if self.x + self.width > 1.000001 or self.y + self.height > 1.000001:
            raise ValueError("레이아웃 박스는 캔버스 안에 있어야 합니다.")
        if not (self.text.strip() if self.kind == "text" else self.caption.strip()):
            raise ValueError("레이아웃 영역의 설명 또는 표시할 텍스트를 입력해 주세요.")
        return self


class MossSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    layout_enabled: bool = False
    elements: list[MossLayoutElement] = Field(default_factory=list, max_length=32)


def layout_prompt(prompt: str, settings: MossSettings, width: int, height: int) -> str:
    if not settings.layout_enabled or not settings.elements:
        return prompt
    items = []
    for element in settings.elements:
        item = {
            "label": element.kind,
            "caption": element.caption.strip(),
            "bbox": [
                math.floor(element.y * height) - height // 2,
                math.floor(element.x * width) - width // 2,
                math.ceil((element.y + element.height) * height) - height // 2,
                math.ceil((element.x + element.width) * width) - width // 2,
            ],
        }
        if element.kind == "text":
            item["text"] = element.text.strip()
        items.append(item)
    result = json.dumps({"summary": {"caption": prompt}, "items": items, "bbox_coord_space": "abs_centralized", "bbox_format": "yxyx"}, ensure_ascii=False, separators=(",", ":"))
    if len(result) > 14000:
        raise ValueError("레이아웃 설명이 너무 깁니다. 영역별 설명을 줄여 주세요.")
    return result
