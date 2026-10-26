from __future__ import annotations

import json
import asyncio
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import uuid
import threading

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field, ValidationError

from .latency import api_user, timed_urlopen
from .audit import exception_message, record_exception, record_remote_error
from .auth import UserResponse, current_user
from .comfyui import _ComfyUIError
from .database import (create_three_d_generation, get_three_d_generation,
                       get_three_d_generation_by_id, record_api_call, update_three_d_generation_status)
from .storage import StorageError, download_file, enabled, upload_file


router = APIRouter(prefix='/generation/3d/rigging', tags=['3D rigging'])
MAX_BYTES = 200 * 1024 * 1024
SYNC_LOCK = threading.RLock()


class RiggingRequest(BaseModel):
    source_generation_id: uuid.UUID | None = None
    temperature: float = Field(default=1, ge=.1, le=2)
    num_beams: int = Field(default=10, ge=1, le=10)


def request_worker(method, path, *, content=None, user_id=None):
    try:
        token = Path(os.getenv('RIGGING_TOKEN_FILE', '/run/secrets/rigging_token')).read_text().strip()
        if not token:
            raise OSError('empty token')
    except OSError as exc:
        record_exception(exc, operation="rigging.credentials", user_id=user_id)
        raise _ComfyUIError('SkinTokens 실행 서비스가 설정되지 않았습니다.') from exc
    request = Request(os.getenv('RIGGING_URL', 'http://host.docker.internal:8190').rstrip('/') + path,
                      method=method, data=content,
                      headers={'Authorization': f'Bearer {token}', 'Content-Type': 'model/gltf-binary'})
    code = 503
    try:
        with api_user(user_id), timed_urlopen(urlopen, request, timeout=120 if content else 15) as response:
            code = response.status
            body = response.read()
            return body if path.endswith('/result') else json.loads(body)
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        code = exc.code if isinstance(exc, HTTPError) else 503
        record_exception(exc, operation='skintokens:' + path.split('?')[0], status_code=code, user_id=user_id)
        raise _ComfyUIError('SkinTokens 실행 서비스에 연결할 수 없습니다.') from exc


@router.get('/options')
def options(user: UserResponse = Depends(current_user)):
    try:
        health = request_worker('GET', '/health', user_id=user.id)
        ready = health.get('ready') is True and enabled()
        return {'ready': ready, 'detail': '' if ready else 'SkinTokens 모델 또는 스토리지 준비가 필요합니다.', 'formats': ['glb'], 'max_size_bytes': MAX_BYTES}
    except _ComfyUIError as exc:
        return {'ready': False, 'detail': str(exc), 'formats': ['glb'], 'max_size_bytes': MAX_BYTES}


@router.post('', status_code=202)
async def create_rigging(payload: str = Form(...), file: UploadFile | None = File(None),
                         user: UserResponse = Depends(current_user)):
    from .three_d import ThreeDGenerationAccepted
    try:
        parsed = RiggingRequest.model_validate_json(payload)
    except ValidationError as exc:
        raise HTTPException(422, '리깅 설정이 올바르지 않습니다.') from exc
    if (file is None) == (parsed.source_generation_id is None):
        raise HTTPException(422, 'GLB 파일 또는 보관함 모델 중 하나를 선택해 주세요.')
    if not enabled():
        raise HTTPException(503, '스토리지 설정이 없습니다.')
    if not (await asyncio.to_thread(options, user))['ready']:
        raise HTTPException(503, 'SkinTokens 실행 서비스가 준비되지 않았습니다.')
    try:
        if parsed.source_generation_id:
            source = get_three_d_generation_by_id(parsed.source_generation_id, user.id)
            if not source or source['status'] != 'completed' or not source.get('storage_file_id'):
                raise HTTPException(404, '사용할 수 있는 보관함 모델을 찾을 수 없습니다.')
            if source.get('generation_mode', 'mesh') != 'mesh':
                raise HTTPException(422, '리깅되지 않은 MESH 결과를 선택해 주세요.')
            if int(source.get('size_bytes') or 0) > MAX_BYTES:
                raise HTTPException(413, 'GLB 파일은 200MB 이하여야 합니다.')
            content, _ = await asyncio.to_thread(download_file, file_id=source['storage_file_id'], owner_id=str(user.id))
            source_file_id = source['storage_file_id']
            filename = source['filename']
        else:
            filename = Path((file.filename or 'model.glb').replace('\\', '/')).name[:240]
            if not filename.lower().endswith('.glb'):
                raise HTTPException(415, 'GLB 파일을 선택해 주세요.')
            content = await file.read(MAX_BYTES + 1)
            source_file_id = None
        if len(content) > MAX_BYTES:
            raise HTTPException(413, 'GLB 파일은 200MB 이하여야 합니다.')
        if len(content) < 12 or content[:4] != b'glTF' or int.from_bytes(content[4:8], 'little') != 2 or int.from_bytes(content[8:12], 'little') != len(content):
            raise HTTPException(422, '올바른 GLB 2.0 파일이 아닙니다.')
        if source_file_id is None:
            source_file_id = await asyncio.to_thread(upload_file, content=content, media_type='model/gltf-binary', owner_id=str(user.id))
        prompt_id, client_id = uuid.uuid4().hex, uuid.uuid4().hex
        generation_id, created_at = create_three_d_generation(user_id=user.id, prompt_id=prompt_id,
            client_id=client_id, preset='standard', seed=0, remove_background=False, padding=0,
            source_file_id=source_file_id, source_filename=filename, generation_mode='rigging',
            rigging_options=parsed.model_dump(mode='json', exclude={'source_generation_id'}))
        try:
            await asyncio.to_thread(request_worker, 'POST', f'/jobs/{prompt_id}?' + urlencode({'temperature': parsed.temperature, 'num_beams': parsed.num_beams}), content=content, user_id=user.id)
        except _ComfyUIError as exc:
            update_three_d_generation_status(prompt_id=prompt_id, user_id=user.id, status='failed', stage='failed', error_message=exception_message(exc))
            raise
    except (StorageError, _ComfyUIError) as exc:
        raise HTTPException(503, str(exc)) from exc
    return ThreeDGenerationAccepted(prompt_id=prompt_id, client_id=client_id, generation_id=str(generation_id),
        status='queued', preset='standard', seed=0, created_at=created_at, generation_mode='rigging')


def history_status(generation, user_id):
    from .three_d import _status_from_row
    with SYNC_LOCK:
        current = get_three_d_generation(generation['prompt_id'], user_id) or generation
        if current['status'] in {'completed', 'failed', 'cancelled'}:
            return _status_from_row(current, user_id)
        return _sync_status(current, user_id)


def cancel_rigging(generation, user_id):
    from .three_d import _status_from_row
    from .generation_events import generation_event_broker, generation_key
    with SYNC_LOCK:
        current = get_three_d_generation(generation['prompt_id'], user_id) or generation
        if current['status'] in {'completed', 'failed', 'cancelled'}:
            return _status_from_row(current, user_id)
        try:
            remote = request_worker('DELETE', f"/jobs/{generation['prompt_id']}", user_id=user_id)
            if remote.get('status') != 'cancelled':
                return history_status(current, user_id)
        except _ComfyUIError as exc:
            raise HTTPException(503, str(exc)) from exc
        update_three_d_generation_status(prompt_id=generation['prompt_id'], user_id=user_id, status='cancelled', stage='cancelled')
        result = _status_from_row(get_three_d_generation(generation['prompt_id'], user_id), user_id)
        generation_event_broker.publish(key=generation_key('3d', user_id, generation['prompt_id']), event='cancelled', data=result.model_dump(mode='json'))
        try:
            request_worker('POST', f"/jobs/{generation['prompt_id']}/ack", user_id=user_id)
        except _ComfyUIError:
            pass
        return result


def _sync_status(generation, user_id):
    from .three_d import _status_from_row
    prompt_id = generation['prompt_id']
    remote = request_worker('GET', f'/jobs/{prompt_id}', user_id=user_id)
    state = remote.get('status')
    if state not in {'queued', 'processing', 'completed', 'failed', 'cancelled'}:
        raise _ComfyUIError('SkinTokens 작업 상태가 올바르지 않습니다.')
    if state == 'completed':
        content = request_worker('GET', f'/jobs/{prompt_id}/result', user_id=user_id)
        if len(content) < 12 or content[:4] != b'glTF':
            raise _ComfyUIError('SkinTokens GLB 결과가 올바르지 않습니다.')
        file_id = upload_file(content=content, media_type='model/gltf-binary', owner_id=str(user_id))
        update_three_d_generation_status(prompt_id=prompt_id, user_id=user_id, status='completed', stage='completed',
            storage_file_id=file_id, filename=f'LocalField_Rigged_{prompt_id[:12]}.glb', size_bytes=len(content))
        try:
            request_worker('POST', f'/jobs/{prompt_id}/ack', user_id=user_id)
        except _ComfyUIError:
            pass
    else:
        message = remote.get('message') if state == 'failed' else None
        update_three_d_generation_status(prompt_id=prompt_id, user_id=user_id, status=state,
                                        stage=remote.get('stage', state), error_message=message)
        if message and generation['status'] != 'failed':
            record_remote_error(remote, operation=f'skintokens:/jobs/{prompt_id}', user_id=user_id)
        if state in {'failed', 'cancelled'}:
            try:
                request_worker('POST', f'/jobs/{prompt_id}/ack', user_id=user_id)
            except _ComfyUIError:
                pass
    current = get_three_d_generation(prompt_id, user_id) or generation
    return _status_from_row(current, user_id, progress={'progress': 100 if state == 'completed' else 0, 'queue_position': remote.get('queue_position')})
