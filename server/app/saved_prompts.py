from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .database import get_connection


router = APIRouter(prefix="/saved-prompts", tags=["saved prompts"])
PromptKind = Literal["image", "video"]
_FIELDS = "id, kind, name, content, created_at, updated_at"


class PromptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: PromptKind
    name: str = Field(min_length=1, max_length=100)
    content: str = Field(min_length=1, max_length=5000)

    @field_validator("name", "content")
    @classmethod
    def nonempty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("이름과 프롬프트 내용을 입력해 주세요.")
        return value.strip()


class PromptResponse(BaseModel):
    id: UUID
    kind: PromptKind
    name: str
    content: str
    created_at: datetime
    updated_at: datetime


def _response(row: tuple) -> PromptResponse:
    return PromptResponse(**dict(zip(("id", "kind", "name", "content", "created_at", "updated_at"), row)))


@router.get("", response_model=list[PromptResponse])
def list_prompts(kind: PromptKind=Query()) -> list[PromptResponse]:
    with get_connection() as connection:
        rows = connection.execute(f"SELECT {_FIELDS} FROM saved_prompts WHERE kind = %s ORDER BY updated_at DESC, id", (kind,)).fetchall()
    return [_response(row) for row in rows]


@router.post("", response_model=PromptResponse, status_code=201)
def create_prompt(payload: PromptRequest) -> PromptResponse:
    with get_connection() as connection:
        row = connection.execute(f"INSERT INTO saved_prompts (id, kind, name, content) VALUES (%s, %s, %s, %s) RETURNING {_FIELDS}", (uuid4(), payload.kind, payload.name, payload.content)).fetchone()
    return _response(row)


@router.put("/{prompt_id}", response_model=PromptResponse)
def update_prompt(prompt_id: UUID, payload: PromptRequest) -> PromptResponse:
    with get_connection() as connection:
        row = connection.execute(f"UPDATE saved_prompts SET kind = %s, name = %s, content = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s RETURNING {_FIELDS}", (payload.kind, payload.name, payload.content, prompt_id)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="저장된 프롬프트를 찾을 수 없습니다.")
    return _response(row)


@router.delete("/{prompt_id}", status_code=204)
def delete_prompt(prompt_id: UUID) -> Response:
    with get_connection() as connection:
        row = connection.execute("DELETE FROM saved_prompts WHERE id = %s RETURNING id", (prompt_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="저장된 프롬프트를 찾을 수 없습니다.")
    return Response(status_code=204)
