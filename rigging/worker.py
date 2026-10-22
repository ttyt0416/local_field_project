import argparse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import signal
import subprocess
import threading
from urllib.parse import parse_qs, urlsplit


ROOT = Path(__file__).resolve().parent
STATE = ROOT / '.runtime'
REPO = Path(os.environ.get('SKINTOKENS_PATH', '/home/yoon/dev/SkinTokens'))
PYTHON = REPO / '.venv/bin/python'
LOCK = threading.RLock()
PROCESSES = {}
STOP = threading.Event()
MAX_BYTES = 200 * 1024 * 1024
READY = False
DETAIL = 'SkinTokens 실행 환경을 확인하고 있습니다.'


def read_job(job_id):
    path = STATE / 'jobs' / job_id / 'job.json'
    return json.loads(path.read_text()) if path.exists() else None


def save_job(job):
    path = STATE / 'jobs' / job['id'] / 'job.json'
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(job, ensure_ascii=False))
    temporary.replace(path)


def jobs():
    return [json.loads(path.read_text()) for path in sorted((STATE / 'jobs').glob('*/job.json'))]


def run_jobs():
    global READY, DETAIL
    try:
        check = subprocess.run([str(PYTHON), str(ROOT / 'infer.py'), '--repo', str(REPO), '--check'],
                               capture_output=True, text=True, timeout=90)
        READY = check.returncode == 0
        DETAIL = '' if READY else 'SkinTokens 실행 환경을 확인해 주세요. ' + check.stderr[-300:]
    except (OSError, subprocess.TimeoutExpired) as exc:
        DETAIL = 'SkinTokens 실행 환경을 확인할 수 없습니다: ' + str(exc)
    with LOCK:
        for job in jobs():
            if job['status'] == 'processing':
                job.update(status='failed', stage='failed', message='리깅 서비스 재시작으로 작업이 중단되었습니다.')
                save_job(job)
    while not STOP.wait(.5):
        if not READY:
            continue
        with LOCK:
            queued = [job for job in jobs() if job['status'] == 'queued']
            if not queued:
                continue
            job = min(queued, key=lambda entry: entry['created_at'])
            folder = STATE / 'jobs' / job['id']
            command = [str(PYTHON), '-u', str(ROOT / 'infer.py'), '--repo', str(REPO),
                       '--input', str(folder / 'input.glb'), '--output', str(folder / 'output.glb'),
                       '--temperature', str(job['temperature']), '--num-beams', str(job['num_beams'])]
            try:
                process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                           start_new_session=True, env={**os.environ, 'PYTHONUNBUFFERED': '1', 'OMP_NUM_THREADS': '8'})
            except Exception as exc:
                job.update(status='failed', stage='failed', message=str(exc))
                save_job(job)
                continue
            PROCESSES[job['id']] = process
            job.update(status='processing', stage='loading_model')
            save_job(job)
        with (folder / 'run.log').open('w') as log:
            for line in process.stdout:
                log.write(line)
                log.flush()
                if line.startswith('LOCAL_FIELD_STAGE:'):
                    with LOCK:
                        current = read_job(job['id'])
                        if current['status'] == 'processing':
                            current['stage'] = line.strip().split(':', 1)[1]
                            save_job(current)
            code = process.wait()
        with LOCK:
            PROCESSES.pop(job['id'], None)
            current = read_job(job['id'])
            if current['status'] != 'cancelled':
                if code == 0 and (folder / 'output.glb').is_file():
                    current.update(status='completed', stage='completed')
                else:
                    tail = (folder / 'run.log').read_text(errors='replace')[-2000:]
                    current.update(status='failed', stage='failed', message='SkinTokens 리깅에 실패했습니다. ' + tail.splitlines()[-1] if tail.splitlines() else 'SkinTokens 리깅에 실패했습니다.')
                save_job(current)


class Handler(BaseHTTPRequestHandler):
    def reply(self, code, data, content_type='application/json'):
        body = json.dumps(data, ensure_ascii=False).encode() if content_type == 'application/json' else data
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def handle_request(self):
        if not secrets.compare_digest(self.headers.get('Authorization', ''), f'Bearer {self.server.token}'):
            self.reply(401, {'detail': 'Unauthorized'})
            return
        route = urlsplit(self.path)
        if route.path == '/health' and self.command == 'GET':
            self.reply(200, {'ready': READY and PYTHON.exists() and all((REPO / path).is_file() for path in (
                'experiments/articulation_xl_quantization_256_token_4/grpo_1400.ckpt',
                'experiments/skin_vae_2_10_32768/last.ckpt', 'models/Qwen3-0.6B/config.json')),
                'detail': DETAIL, 'model': 'SkinTokens', 'formats': ['glb']})
            return
        match = re.fullmatch(r'/jobs/([0-9a-f]{32})(/result|/ack)?', route.path)
        if not match:
            self.reply(404, {'detail': 'Not found'})
            return
        job_id, suffix = match.groups()
        folder = STATE / 'jobs' / job_id
        with LOCK:
            job = read_job(job_id)
            if self.command == 'POST' and not suffix:
                if not READY:
                    self.reply(503, {'detail': DETAIL})
                    return
                if job:
                    self.reply(200, job)
                    return
                if sum(entry['status'] in ('queued', 'processing') for entry in jobs()) >= 8:
                    self.reply(429, {'detail': '리깅 대기열이 가득 찼습니다.'})
                    return
                length = int(self.headers.get('Content-Length', '0'))
                query = parse_qs(route.query)
                temperature = float(query.get('temperature', ['1'])[0])
                beams = int(query.get('num_beams', ['10'])[0])
                if not 12 <= length <= MAX_BYTES or not .1 <= temperature <= 2 or not 1 <= beams <= 10:
                    self.reply(422, {'detail': 'Invalid rigging request'})
                    return
                body = self.rfile.read(length)
                if len(body) != length or body[:4] != b'glTF':
                    self.reply(422, {'detail': '올바른 GLB 파일이 아닙니다.'})
                    return
                folder.mkdir(parents=True, exist_ok=True)
                (folder / 'input.glb').write_bytes(body)
                job = dict(id=job_id, status='queued', stage='queued', temperature=temperature,
                           num_beams=beams, created_at=datetime.now(timezone.utc).isoformat())
                save_job(job)
                self.reply(202, job)
                return
            if job is None:
                self.reply(404, {'detail': '리깅 작업을 찾을 수 없습니다.'})
                return
            if self.command == 'GET' and suffix == '/result' and job['status'] == 'completed' and (folder / 'output.glb').exists():
                self.reply(200, (folder / 'output.glb').read_bytes(), 'model/gltf-binary')
            elif self.command == 'GET' and suffix is None:
                queued = sorted((entry for entry in jobs() if entry['status'] == 'queued'), key=lambda entry: entry['created_at'])
                position = next((i + 1 for i, entry in enumerate(queued) if entry['id'] == job_id), None)
                self.reply(200, {**job, 'queue_position': position})
            elif self.command == 'DELETE' and suffix is None:
                if job['status'] in ('queued', 'processing'):
                    job.update(status='cancelled', stage='cancelled')
                    save_job(job)
                    process = PROCESSES.get(job_id)
                    if process and process.poll() is None:
                        try:
                            os.killpg(process.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                self.reply(200, job)
            elif self.command == 'POST' and suffix == '/ack' and job['status'] in ('completed', 'failed', 'cancelled'):
                for filename in ('input.glb', 'output.glb'):
                    (folder / filename).unlink(missing_ok=True)
                self.reply(200, {'status': 'ok'})
            else:
                self.reply(409, {'detail': '리깅 결과를 아직 사용할 수 없습니다.'})

    def dispatch(self):
        try:
            self.connection.settimeout(120)
            self.handle_request()
        except (ValueError, KeyError) as exc:
            self.reply(422, {'detail': str(exc)})
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            pass

    do_GET = dispatch
    do_POST = dispatch
    do_DELETE = dispatch


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=8190)
    args = parser.parse_args()
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    (STATE / 'jobs').mkdir(exist_ok=True)
    token_file = STATE / 'token'
    if not token_file.exists():
        token_file.write_text(secrets.token_hex(32))
        token_file.chmod(0o600)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.token = token_file.read_text().strip()
    threading.Thread(target=run_jobs, daemon=True).start()
    try:
        server.serve_forever()
    finally:
        STOP.set()
        for process in tuple(PROCESSES.values()):
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
        server.server_close()


if __name__ == '__main__':
    main()
