"""Frozen ImageNet ResNet18 baseline, with explicit sample alignment/provenance."""
import argparse
import json
from pathlib import Path
import platform
import time

import numpy as np
from PIL import Image, __version__ as pillow_version

from .crops import read_rows, sha256, square_input


def extract_features(manifest, output, cache, batch_size=32, threads=4):
    import torch
    import torchvision
    from torchvision.models import resnet18, ResNet18_Weights
    from torchvision.transforms.functional import to_tensor, normalize

    if batch_size < 1 or threads < 1:
        raise ValueError('batch_size and threads must be positive')
    manifest, output = Path(manifest), Path(output)
    rows = read_rows(manifest)
    if not rows or len({r['sample_id'] for r in rows}) != len(rows):
        raise ValueError('Require nonempty unique sample IDs')
    if output.exists():
        raise FileExistsError(output)
    root = manifest.parent.resolve()
    paths = []
    for row in rows:
        path = (root / row['crop_path']).resolve()
        if not path.is_relative_to(root) or sha256(path) != row['crop_sha256']:
            raise ValueError(f"Invalid crop path or checksum: {row['sample_id']}")
        paths.append(path)
    torch.set_num_threads(threads)
    torch.manual_seed(42)
    torch.use_deterministic_algorithms(True)
    torch.hub.set_dir(str(Path(cache).resolve()))
    weights = ResNet18_Weights.IMAGENET1K_V1
    model = resnet18(weights=weights).eval()
    model.fc = torch.nn.Identity()
    model.requires_grad_(False)
    output.mkdir(parents=True, exist_ok=False)
    features = np.empty((len(rows), 512), dtype=np.float32)
    started = time.perf_counter()
    with torch.inference_mode():
        for start in range(0, len(rows), batch_size):
            batch = []
            for path in paths[start:start + batch_size]:
                with Image.open(path) as image:
                    tensor = to_tensor(square_input(image))
                batch.append(normalize(tensor, [0.485, 0.456, 0.406], [0.229, 0.224, 0.225]))
            values = model(torch.stack(batch))
            norms = values.norm(dim=1, keepdim=True)
            if not torch.isfinite(values).all() or (norms <= 0).any():
                raise ValueError('Nonfinite or zero embeddings')
            features[start:start + len(batch)] = (values / norms).numpy()
            if start % (batch_size * 10) == 0:
                print(f'{start + len(batch)}/{len(rows)} components', flush=True)
    np.save(output / 'features.npy', features, allow_pickle=False)
    (output / 'samples.jsonl').write_text(''.join(json.dumps(dict(r, feature_index=i), ensure_ascii=False) + '\n' for i, r in enumerate(rows)), encoding='utf-8')
    checkpoint = Path(cache) / 'checkpoints' / weights.url.rsplit('/', 1)[-1]
    report = dict(status='complete', shape=list(features.shape), dtype='float32', device='cpu',
                  architecture='resnet18; fc=Identity; global average pooling', weights=str(weights),
                  weights_url=weights.url, weights_sha256=sha256(checkpoint),
                  preprocessing='RGB; center pad to square RGB(124,116,104); PIL bilinear resize 224; ImageNet normalize; L2 output normalize',
                  source_manifest_sha256=sha256(manifest), features_sha256=sha256(output / 'features.npy'),
                  torch=torch.__version__, torchvision=torchvision.__version__, numpy=np.__version__,
                  pillow=pillow_version, python=platform.python_version(), seed=42, threads=threads,
                  batch_size=batch_size, elapsed_seconds=round(time.perf_counter() - started, 2))
    (output / 'run.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cache', type=Path, default=Path('data/torch-cache'))
    parser.add_argument('--batch-size', type=int, default=32)
    parser.add_argument('--threads', type=int, default=4)
    args = parser.parse_args()
    print(json.dumps(extract_features(args.manifest, args.output, args.cache, args.batch_size, args.threads), indent=2))


if __name__ == '__main__':
    main()
