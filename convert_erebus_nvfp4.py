import argparse
import importlib.metadata
import hashlib
import json
import os
from pathlib import Path
import signal
import threading
import time


def available_memory_gib() -> float:
    for line in Path('/proc/meminfo').read_text().splitlines():
        if line.startswith('MemAvailable:'):
            return int(line.split()[1]) / 1024 ** 2
    raise RuntimeError('MemAvailable is missing')


def protect_memory(finished: threading.Event) -> None:
    while not finished.wait(1):
        available = available_memory_gib()
        if available < 20:
            print(f'Stopping NVFP4 conversion: shared RAM reserve reached ({available:.1f} GiB)', flush=True)
            os.kill(os.getpid(), signal.SIGTERM)
            return


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    if available_memory_gib() < 40:
        raise SystemExit('At least 40 GiB shared RAM must be available before conversion')
    provenance = json.loads((args.source / 'source_provenance.json').read_text())
    weights = [item for item in provenance['files'] if item['filename'].endswith('.safetensors')]
    if len(weights) != 11 or not all(item['verified'] for item in weights):
        raise SystemExit('All 11 original checkpoint hashes must be verified before conversion')
    finished = threading.Event()
    threading.Thread(target=protect_memory, args=(finished,), daemon=True).start()
    import torch
    from llmcompressor import model_free_ptq

    torch.set_num_threads(4)
    torch.cuda.set_per_process_memory_fraction(0.15)
    ignored = ['lm_head', 're:.*embed.*', 're:.*router.*', 're:.*vision.*', 're:.*audio.*', 're:.*norm.*']
    started = time.monotonic()
    try:
        model_free_ptq(
            model_stub=args.source,
            save_directory=args.destination,
            scheme='NVFP4A16',
            ignore=ignored,
            max_workers=1,
            device='cuda:0',
        )
        config = json.loads((args.destination / 'config.json').read_text())
        quantization = config['quantization_config']
        if quantization['format'] != 'nvfp4-pack-quantized':
            raise RuntimeError(f'Unexpected quantized format: {quantization["format"]}')
        from safetensors import safe_open
        output_files = []
        packed_count = 0
        expert_packed_count = 0
        preserved = {"vision": 0, "router": 0, "embed": 0}
        for checkpoint in sorted(args.destination.glob('*.safetensors')):
            checkpoint.chmod(0o644)
            with safe_open(checkpoint, framework='pt', device='cpu') as source:
                for name in source.keys():
                    packed_count += name.endswith('.weight_packed')
                    expert_packed_count += '.experts.' in name and name.endswith('.weight_packed')
                    for category in preserved:
                        if category in name and source.get_slice(name).get_dtype() == 'BF16':
                            preserved[category] += 1
            digest = hashlib.sha256()
            with checkpoint.open('rb') as source:
                while block := source.read(8 * 1024 * 1024):
                    digest.update(block)
                os.posix_fadvise(source.fileno(), 0, 0, os.POSIX_FADV_DONTNEED)
            output_files.append({'filename': checkpoint.name, 'size': checkpoint.stat().st_size, 'sha256': digest.hexdigest()})
        text_config = config['text_config']
        expected_experts = 3 * text_config['num_hidden_layers'] * text_config['num_experts']
        if expert_packed_count != expected_experts or not all(preserved.values()):
            raise RuntimeError(f'Incomplete expert quantization or BF16 exclusions: {expert_packed_count}/{expected_experts}, {preserved}')
        provenance['source_files'] = provenance.pop('files')
        provenance['files'] = output_files
        provenance['conversion'] = {
            'scheme': 'NVFP4A16',
            'algorithm': 'model-free RTN',
            'device': 'local GB10 CUDA',
            'max_workers': 1,
            'ignore': ignored,
            'llmcompressor': importlib.metadata.version('llmcompressor'),
            'compressed_tensors': importlib.metadata.version('compressed-tensors'),
            'torch': torch.__version__,
            'quantized_matrix_count': packed_count,
            'expert_quantized_matrix_count': expert_packed_count,
            'preserved_bf16_tensors': preserved,
            'output_hash_origin': 'local NVFP4 conversion',
            'duration_seconds': round(time.monotonic() - started, 2),
        }
        provenance['serving'] = {
            'language_model_only': True,
            'vision_enabled': False,
            'reason': 'User selected original Erebus text-only; source omits 351 vision encoder tensors',
        }
        (args.destination / 'source_provenance.json').write_text(json.dumps(provenance, indent=2))
        print('LOCAL_NVFP4_CONVERSION_COMPLETE', json.dumps(provenance['conversion']), flush=True)
    finally:
        finished.set()


if __name__ == '__main__':
    main()
