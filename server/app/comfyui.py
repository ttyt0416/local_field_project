from __future__ import annotations

import asyncio
import json
import re
import secrets
import uuid
from typing import Any
from urllib.error import HTTPError as UrlHTTPError
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

import websockets
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from starlette.responses import StreamingResponse

from .auth import UserResponse, current_user
from .configs.constants import settings
from .danbooru import DanbooruError, search_danbooru_tags, validate_danbooru_tags
from .database import (
    create_image_generation as create_image_generation_record,
    get_image_generation,
    update_image_generation_status,
)
from .prompts import (
    IMAGE_PROMPT_ENHANCEMENT_SYSTEM_PROMPT,
    IMAGE_PROMPT_ENHANCEMENT_TAG_SYSTEM_PROMPT,
    IMAGE_PROMPT_ENHANCEMENT_TAG_USER_PROMPT,
    IMAGE_PROMPT_ENHANCEMENT_USER_PROMPT,
)


router = APIRouter(prefix="/generation/image", tags=["image generation"])
_DEFAULT_NEGATIVE_PROMPT = "worst quality, low quality, score_1, score_2, score_3, blurry, jpeg artifacts, sepia"
_COMFYUI_TIMEOUT_SECONDS = 30
_SSE_HEARTBEAT_SECONDS = 15


class LoraSelection(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    strength: float = Field(default=0.7, ge=-2, le=2)


class ImageGenerationRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=5000)
    prompt_enhancement_enabled: bool = False
    improved_prompt: str | None = Field(default=None, max_length=5000)
    negative_prompt: str = Field(default=_DEFAULT_NEGATIVE_PROMPT, max_length=5000)
    checkpoint: str = Field(min_length=1, max_length=255)
    loras: list[LoraSelection] = Field(default_factory=list, max_length=8)
    cfg: float = Field(default=4, ge=0, le=20)
    steps: int = Field(default=30, ge=1, le=100)
    width: int = Field(default=1024, ge=64, le=2048)
    height: int = Field(default=1024, ge=64, le=2048)
    seed: int | None = Field(default=None, ge=0, le=18_446_744_073_709_551_615)


class ImageGenerationOptions(BaseModel):
    checkpoints: list[str]
    loras: list[str]
    default_checkpoint: str


class ImageOutput(BaseModel):
    url: str
    filename: str
    subfolder: str
    type: str


class ImageGenerationStatus(BaseModel):
    prompt_id: str
    status: str
    images: list[ImageOutput] = Field(default_factory=list)


class PromptEnhancementRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=5000)


class PromptEnhancementContent(BaseModel):
    contents: str = Field(min_length=1, max_length=5000)


class PromptEnhancementResponse(BaseModel):
    improved_prompt: PromptEnhancementContent


@router.get("/options", response_model=ImageGenerationOptions)
def image_options(_: UserResponse = Depends(current_user)) -> ImageGenerationOptions:
    try:
        return _image_options()
    except _ComfyUIError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


@router.post("/enhance-prompt", response_model=PromptEnhancementResponse)
def enhance_prompt(
    payload: PromptEnhancementRequest,
    _: UserResponse = Depends(current_user),
) -> PromptEnhancementResponse:
    try:
        return _enhance_prompt(payload.prompt)
    except (DanbooruError, _VLLMError) as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


@router.post("", response_model=dict[str, str], status_code=status.HTTP_202_ACCEPTED)
def create_image_generation(
    payload: ImageGenerationRequest,
    user: UserResponse = Depends(current_user),
) -> dict[str, str]:
    try:
        options = _image_options()
        _validate_model_choice(payload, options)
        prompt, seed = _build_prompt(payload)
        client_id = str(uuid.uuid4())
        response = _request_json(
            "POST",
            "/prompt",
            {"prompt": prompt, "client_id": client_id},
        )
    except _ComfyUIError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    prompt_id = response.get("prompt_id")
    if not isinstance(prompt_id, str) or not prompt_id:
        raise HTTPException(status_code=502, detail="ComfyUI가 생성 작업 ID를 반환하지 않았습니다.")
    generation_id = create_image_generation_record(
        user_id=user.id,
        prompt_id=prompt_id,
        client_id=client_id,
        prompt=_effective_positive_prompt(payload),
        negative_prompt=payload.negative_prompt,
        checkpoint=payload.checkpoint,
        loras=[lora.model_dump() for lora in payload.loras],
        cfg=payload.cfg,
        steps=payload.steps,
        width=payload.width,
        height=payload.height,
        seed=seed,
    )
    return {
        "prompt_id": prompt_id,
        "status": "queued",
        "client_id": client_id,
        "generation_id": str(generation_id),
    }


@router.get("/{prompt_id}/events")
async def image_generation_events(
    prompt_id: str,
    client_id: str = Query(min_length=1, max_length=128),
    user: UserResponse = Depends(current_user),
) -> StreamingResponse:
    _require_owned_generation(prompt_id, user.id)
    return StreamingResponse(
        _stream_generation_events(prompt_id, client_id, user.id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{prompt_id}", response_model=ImageGenerationStatus)
def image_generation_status(
    prompt_id: str,
    user: UserResponse = Depends(current_user),
) -> ImageGenerationStatus:
    _require_owned_generation(prompt_id, user.id)
    try:
        return _history_generation_status(prompt_id, user.id)
    except _ComfyUIError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


async def _stream_generation_events(prompt_id: str, client_id: str, user_id: uuid.UUID):
    yield _sse_message("queued", _queue_event(prompt_id))

    try:
        current = _history_generation_status(prompt_id, user_id)
        if current.status == "completed":
            yield _sse_message("completed", current.model_dump())
            return
        if current.status == "failed":
            yield _sse_message("failed", {"prompt_id": prompt_id, "status": "failed"})
            return
    except _ComfyUIError:
        pass

    try:
        async with websockets.connect(
            _comfy_websocket_url(client_id),
            open_timeout=10,
            ping_interval=20,
            close_timeout=2,
        ) as socket:
            while True:
                try:
                    raw_message = await asyncio.wait_for(socket.recv(), timeout=_SSE_HEARTBEAT_SECONDS)
                except asyncio.TimeoutError:
                    queue_event = _queue_event(prompt_id)
                    if queue_event["status"] == "queued":
                        yield _sse_message("queued", queue_event)
                    else:
                        yield ": keep-alive\n\n"
                    continue
                except websockets.exceptions.ConnectionClosed:
                    yield _sse_message("error", {"prompt_id": prompt_id, "message": "ComfyUI 진행 연결이 종료되었습니다."})
                    return

                if isinstance(raw_message, bytes):
                    continue
                try:
                    message = json.loads(raw_message)
                except json.JSONDecodeError:
                    continue

                event_name = message.get("type")
                data = message.get("data") if isinstance(message.get("data"), dict) else {}
                event_prompt_id = data.get("prompt_id")
                if event_prompt_id is not None and event_prompt_id != prompt_id:
                    continue

                if event_name == "progress":
                    value = _number(data.get("value"))
                    maximum = _number(data.get("max"))
                    progress = round(min(100, max(0, value / maximum * 100)) if maximum > 0 else 0, 2)
                    yield _sse_message(
                        "progress",
                        {
                            "prompt_id": prompt_id,
                            "status": "processing",
                            "progress": progress,
                            "value": value,
                            "total": maximum,
                            "node": data.get("node"),
                        },
                    )
                elif event_name == "executing":
                    if data.get("node") is None:
                        try:
                            current = _history_generation_status(prompt_id, user_id)
                        except _ComfyUIError:
                            current = None
                        if current and current.status == "completed":
                            yield _sse_message("completed", current.model_dump())
                            return
                        if current and current.status == "failed":
                            yield _sse_message("failed", {"prompt_id": prompt_id, "status": "failed"})
                            return
                    else:
                        yield _sse_message(
                            "processing",
                            {"prompt_id": prompt_id, "status": "processing", "progress": 0, "node": data.get("node")},
                        )
                elif event_name == "execution_success":
                    current = _history_generation_status(prompt_id, user_id)
                    yield _sse_message("completed", current.model_dump())
                    return
                elif event_name in {"execution_error", "execution_interrupted"}:
                    detail = data.get("exception_message") or data.get("message")
                    update_image_generation_status(prompt_id=prompt_id, user_id=user_id, status="failed")
                    yield _sse_message(
                        "failed",
                        {
                            "prompt_id": prompt_id,
                            "status": "failed",
                            "message": str(detail)[:500] if detail else "ComfyUI에서 이미지 생성에 실패했습니다.",
                        },
                    )
                    return
    except (OSError, TimeoutError, websockets.exceptions.WebSocketException) as exc:
        yield _sse_message("error", {"prompt_id": prompt_id, "message": "ComfyUI 진행 연결에 실패했습니다."})


def _history_generation_status(prompt_id: str, user_id: uuid.UUID) -> ImageGenerationStatus:
    history = _request_json("GET", f"/history/{prompt_id}")
    entry = history.get(prompt_id)
    if not isinstance(entry, dict):
        return ImageGenerationStatus(prompt_id=prompt_id, status="queued")

    raw_status = entry.get("status")
    comfy_status: dict[str, Any] = raw_status if isinstance(raw_status, dict) else {}
    status_name = str(comfy_status.get("status_str", ""))
    if status_name in {"error", "failed"}:
        update_image_generation_status(prompt_id=prompt_id, user_id=user_id, status="failed")
        return ImageGenerationStatus(prompt_id=prompt_id, status="failed")
    if comfy_status.get("completed") is True:
        raw_images = _raw_image_outputs(entry.get("outputs"))
        _sync_generation_output(prompt_id, user_id, raw_images)
        return ImageGenerationStatus(
            prompt_id=prompt_id,
            status="completed",
            images=_image_outputs(prompt_id, entry.get("outputs")),
        )
    update_image_generation_status(prompt_id=prompt_id, user_id=user_id, status="processing")
    return ImageGenerationStatus(prompt_id=prompt_id, status="processing")


def _queue_event(prompt_id: str) -> dict[str, Any]:
    try:
        queue = _request_json("GET", "/queue")
    except _ComfyUIError:
        return {"prompt_id": prompt_id, "status": "queued", "progress": 0, "queue_position": None}

    running = queue.get("queue_running", [])
    if _queue_contains(running, prompt_id):
        return {"prompt_id": prompt_id, "status": "processing", "progress": 0, "queue_position": 0}

    pending = queue.get("queue_pending", [])
    for index, item in enumerate(pending, start=1):
        if _queue_item_prompt_id(item) == prompt_id:
            return {"prompt_id": prompt_id, "status": "queued", "progress": 0, "queue_position": index}
    return {"prompt_id": prompt_id, "status": "queued", "progress": 0, "queue_position": None}


def _queue_contains(items: Any, prompt_id: str) -> bool:
    return isinstance(items, list) and any(_queue_item_prompt_id(item) == prompt_id for item in items)


def _queue_item_prompt_id(item: Any) -> str | None:
    return item[1] if isinstance(item, list) and len(item) > 1 and isinstance(item[1], str) else None


def _number(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0


def _sse_message(event_name: str, data: dict[str, Any]) -> str:
    return f"event: {event_name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _require_owned_generation(prompt_id: str, user_id: uuid.UUID) -> dict[str, Any]:
    generation = get_image_generation(prompt_id, user_id)
    if generation is None:
        raise HTTPException(status_code=404, detail="생성 결과를 찾을 수 없습니다.")
    return generation


def _sync_generation_output(prompt_id: str, user_id: uuid.UUID, images: list[dict[str, Any]]) -> None:
    image = images[0] if images else None
    if not isinstance(image, dict):
        update_image_generation_status(prompt_id=prompt_id, user_id=user_id, status="completed")
        return
    filename = image.get("filename")
    if not isinstance(filename, str) or not filename:
        update_image_generation_status(prompt_id=prompt_id, user_id=user_id, status="completed")
        return
    subfolder = image.get("subfolder", "")
    image_type = image.get("type", "output")
    if not isinstance(subfolder, str) or not isinstance(image_type, str):
        update_image_generation_status(prompt_id=prompt_id, user_id=user_id, status="completed")
        return
    path_parts = [image_type, subfolder, filename]
    file_path = "/".join(part for part in path_parts if part)
    update_image_generation_status(
        prompt_id=prompt_id,
        user_id=user_id,
        status="completed",
        file_path=file_path,
        filename=filename,
        subfolder=subfolder,
        image_type=image_type,
    )


@router.get("/{prompt_id}/view")
def view_generated_image(
    prompt_id: str,
    filename: str = Query(min_length=1, max_length=255),
    subfolder: str = Query(default="", max_length=255),
    image_type: str = Query(default="output", alias="type", max_length=32),
    user: UserResponse = Depends(current_user),
) -> Response:
    generation = _require_owned_generation(prompt_id, user.id)
    if (
        generation["filename"] != filename
        or generation["subfolder"] != subfolder
        or generation["image_type"] != image_type
    ):
        raise HTTPException(status_code=404, detail="생성 결과 이미지를 찾을 수 없습니다.")
    try:
        history = _request_json("GET", f"/history/{prompt_id}")
    except _ComfyUIError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    entry = history.get(prompt_id)
    available_images = _raw_image_outputs(entry.get("outputs") if isinstance(entry, dict) else None)
    if not any(
        image.get("filename") == filename
        and image.get("subfolder", "") == subfolder
        and image.get("type", "output") == image_type
        for image in available_images
    ):
        raise HTTPException(status_code=404, detail="생성 결과 이미지를 찾을 수 없습니다.")

    query = urlencode({"filename": filename, "subfolder": subfolder, "type": image_type})
    try:
        content, media_type = _request_bytes(f"/view?{query}")
    except _ComfyUIError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return Response(content=content, media_type=media_type or "image/png")


def _image_options() -> ImageGenerationOptions:
    data = _request_json("GET", "/object_info")
    checkpoints = _anima_choices(data, "UNETLoader", "unet_name")
    loras = _anima_choices(data, "LoraLoaderModelOnly", "lora_name")
    if not checkpoints:
        raise _ComfyUIError("ComfyUI에서 Anima 체크포인트를 찾을 수 없습니다.")
    default_checkpoint = (
        "Anima/anima_aestheticV11.safetensors"
        if "Anima/anima_aestheticV11.safetensors" in checkpoints
        else checkpoints[0]
    )
    return ImageGenerationOptions(
        checkpoints=checkpoints,
        loras=loras,
        default_checkpoint=default_checkpoint,
    )


def _anima_choices(data: dict[str, Any], node_name: str, input_name: str) -> list[str]:
    node = data.get(node_name)
    if not isinstance(node, dict):
        return []
    required = node.get("input", {}).get("required", {})
    values = required.get(input_name, []) if isinstance(required, dict) else []
    choices = values[0] if values and isinstance(values[0], list) else []
    return sorted(value for value in choices if isinstance(value, str) and value.startswith("Anima/"))


def _validate_model_choice(payload: ImageGenerationRequest, options: ImageGenerationOptions) -> None:
    if payload.checkpoint not in options.checkpoints:
        raise HTTPException(status_code=422, detail="선택한 Anima 체크포인트를 찾을 수 없습니다.")
    lora_names = [lora.name for lora in payload.loras]
    if len(lora_names) != len(set(lora_names)):
        raise HTTPException(status_code=422, detail="같은 LoRA를 중복 선택할 수 없습니다.")
    if any(name not in options.loras for name in lora_names):
        raise HTTPException(status_code=422, detail="선택한 Anima LoRA를 찾을 수 없습니다.")
    if payload.width % 8 or payload.height % 8:
        raise HTTPException(status_code=422, detail="이미지 가로·세로 크기는 8의 배수여야 합니다.")


def _effective_positive_prompt(payload: ImageGenerationRequest) -> str:
    base_prompt = payload.prompt.strip()
    if not payload.prompt_enhancement_enabled:
        return base_prompt
    improved_prompt = (payload.improved_prompt or "").strip()
    if not improved_prompt:
        raise HTTPException(status_code=422, detail="개선된 프롬프트를 먼저 생성해 주세요.")
    return improved_prompt


def _build_prompt(payload: ImageGenerationRequest) -> tuple[dict[str, dict[str, Any]], int]:
    seed = payload.seed if payload.seed is not None else secrets.randbelow(18_446_744_073_709_551_616)
    positive_prompt = _effective_positive_prompt(payload)
    model: list[Any] = ["1", 0]
    prompt: dict[str, dict[str, Any]] = {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {"unet_name": payload.checkpoint, "weight_dtype": "default"},
        },
        "3": {
            "class_type": "CLIPLoader",
            "inputs": {
                "clip_name": "qwen_3_06b_base.safetensors",
                "type": "stable_diffusion",
                "device": "default",
            },
        },
        "4": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": "qwen_image_vae.safetensors"},
        },
        "5": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": positive_prompt, "clip": ["3", 0]},
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": payload.negative_prompt, "clip": ["3", 0]},
        },
        "7": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": payload.width, "height": payload.height, "batch_size": 1},
        },
        "8": {
            "class_type": "KSampler",
            "inputs": {
                "model": model,
                "seed": seed,
                "steps": payload.steps,
                "cfg": payload.cfg,
                "sampler_name": "er_sde",
                "scheduler": "simple",
                "positive": ["5", 0],
                "negative": ["6", 0],
                "latent_image": ["7", 0],
                "denoise": 1.0,
            },
        },
        "9": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["8", 0], "vae": ["4", 0]},
        },
        "10": {
            "class_type": "SaveImage",
            "inputs": {"filename_prefix": "LocalField_Anima", "images": ["9", 0]},
        },
    }
    for index, lora in enumerate(payload.loras, start=11):
        prompt[str(index)] = {
            "class_type": "LoraLoaderModelOnly",
            "inputs": {
                "model": model,
                "lora_name": lora.name,
                "strength_model": lora.strength,
            },
        }
        model = [str(index), 0]
    prompt["8"]["inputs"]["model"] = model
    return prompt, seed


def _image_outputs(prompt_id: str, outputs: Any) -> list[ImageOutput]:
    result = []
    for image in _raw_image_outputs(outputs):
        filename = image.get("filename")
        subfolder = image.get("subfolder", "")
        image_type = image.get("type", "output")
        if not isinstance(filename, str):
            continue
        query = urlencode({"filename": filename, "subfolder": subfolder, "type": image_type})
        result.append(
            ImageOutput(
                url=f"/generation/image/{prompt_id}/view?{query}",
                filename=filename,
                subfolder=subfolder,
                type=image_type,
            )
        )
    return result


def _raw_image_outputs(outputs: Any) -> list[dict[str, Any]]:
    if not isinstance(outputs, dict):
        return []
    images = []
    for output in outputs.values():
        if isinstance(output, dict) and isinstance(output.get("images"), list):
            images.extend(image for image in output["images"] if isinstance(image, dict))
    return images


def _request_json(method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = UrlRequest(
        _comfy_url(path),
        data=data,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    try:
        with urlopen(request, timeout=_COMFYUI_TIMEOUT_SECONDS) as response:
            decoded = json.loads(response.read())
    except UrlHTTPError as exc:
        raise _ComfyUIError(f"ComfyUI 요청이 실패했습니다. (HTTP {exc.code})") from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise _ComfyUIError("ComfyUI에 연결할 수 없습니다.") from exc
    if not isinstance(decoded, dict):
        raise _ComfyUIError("ComfyUI 응답 형식이 올바르지 않습니다.")
    return decoded


def _request_bytes(path: str) -> tuple[bytes, str | None]:
    request = UrlRequest(_comfy_url(path), method="GET")
    try:
        with urlopen(request, timeout=_COMFYUI_TIMEOUT_SECONDS) as response:
            return response.read(), response.headers.get_content_type()
    except UrlHTTPError as exc:
        raise _ComfyUIError(f"ComfyUI 이미지 요청이 실패했습니다. (HTTP {exc.code})") from exc
    except (URLError, TimeoutError) as exc:
        raise _ComfyUIError("ComfyUI 이미지에 연결할 수 없습니다.") from exc


def _enhance_prompt(prompt: str) -> PromptEnhancementResponse:
    prompt = prompt.strip()
    candidate_tags = search_danbooru_tags(prompt, limit=96)
    natural_language = _request_structured_content(
        system_prompt=IMAGE_PROMPT_ENHANCEMENT_SYSTEM_PROMPT,
        user_prompt=IMAGE_PROMPT_ENHANCEMENT_USER_PROMPT.format(prompt=prompt),
        max_tokens=768,
        temperature=0.4,
    )
    raw_tags = _request_structured_content(
        system_prompt=IMAGE_PROMPT_ENHANCEMENT_TAG_SYSTEM_PROMPT,
        user_prompt=IMAGE_PROMPT_ENHANCEMENT_TAG_USER_PROMPT.format(
            prompt=prompt,
            candidate_tags=", ".join(candidate_tags),
        ),
        max_tokens=256,
        temperature=0.2,
    )
    valid_tags = validate_danbooru_tags(raw_tags)
    if not valid_tags:
        valid_tags = candidate_tags[:24]
    if not valid_tags:
        raise DanbooruError("사용할 Danbooru 태그를 찾지 못했습니다.")
    improved_prompt = ", ".join((prompt, ", ".join(valid_tags), natural_language))
    return PromptEnhancementResponse(
        improved_prompt=PromptEnhancementContent(contents=improved_prompt[:5000]),
    )


def _request_structured_content(
    *,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int,
    temperature: float,
) -> str:
    response = _request_vllm_json(
        {
            "model": settings.vllm_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "prompt_contents",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "contents": {"type": "string", "minLength": 1, "maxLength": 5000}
                        },
                        "required": ["contents"],
                        "additionalProperties": False,
                    },
                    "strict": True,
                },
            },
            "chat_template_kwargs": {"enable_thinking": False},
        }
    )
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise _VLLMError("vLLM이 구조화된 프롬프트 결과를 반환하지 않았습니다.")
    choice = choices[0]
    if choice.get("finish_reason") == "length":
        raise _VLLMError("vLLM 프롬프트 결과가 길이 제한으로 중단되었습니다.")
    message = choice.get("message")
    raw_content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(raw_content, str):
        raise _VLLMError("vLLM 구조화 응답 형식이 올바르지 않습니다.")
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_content.strip(), flags=re.IGNORECASE)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise _VLLMError("vLLM 구조화 응답을 JSON으로 읽을 수 없습니다.") from exc
    contents = parsed.get("contents") if isinstance(parsed, dict) else None
    if not isinstance(contents, str) or not contents.strip():
        raise _VLLMError("vLLM 구조화 응답의 contents가 비어 있습니다.")
    return contents.strip()[:5000]


def _request_vllm_json(payload: dict[str, Any]) -> dict[str, Any]:
    request = UrlRequest(
        _vllm_url("/v1/chat/completions"),
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=60) as response:
            decoded = json.loads(response.read())
    except UrlHTTPError as exc:
        raise _VLLMError(f"vLLM 프롬프트 강화 요청이 실패했습니다. (HTTP {exc.code})") from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise _VLLMError("vLLM에 연결할 수 없습니다.") from exc
    if not isinstance(decoded, dict):
        raise _VLLMError("vLLM 응답 형식이 올바르지 않습니다.")
    return decoded


def _comfy_url(path: str) -> str:
    return f"{settings.comfyui_url.rstrip('/')}/{path.lstrip('/')}"


def _comfy_websocket_url(client_id: str) -> str:
    base_url = settings.comfyui_url.rstrip("/")
    websocket_scheme = "wss" if base_url.startswith("https://") else "ws"
    base_url = base_url.removeprefix("https://").removeprefix("http://")
    query = urlencode({"clientId": client_id})
    return f"{websocket_scheme}://{base_url}/ws?{query}"


def _vllm_url(path: str) -> str:
    return f"{settings.vllm_url.rstrip('/')}/{path.lstrip('/')}"


class _ComfyUIError(RuntimeError):
    pass


class _VLLMError(RuntimeError):
    pass
