"""Fetch the exact upstream PatchCore source used by the benchmark."""
import argparse
import json
from pathlib import Path
import urllib.request

from .multiseed import COMMIT


def acquire(destination):
    root=Path(destination)
    root.mkdir(parents=True,exist_ok=False)
    files=('src/patchcore/__init__.py','src/patchcore/backbones.py','src/patchcore/patchcore.py',
           'src/patchcore/common.py','src/patchcore/sampler.py','LICENSE','NOTICE',
           'src/patchcore/datasets/mvtec.py')
    for name in files:
        target=root/name; target.parent.mkdir(parents=True,exist_ok=True)
        url=f'https://raw.githubusercontent.com/amazon-science/patchcore-inspection/{COMMIT}/{name}'
        with urllib.request.urlopen(url,timeout=60) as response: target.write_bytes(response.read())
    (root/'provenance.json').write_text(json.dumps({'repo':'https://github.com/amazon-science/patchcore-inspection','commit':COMMIT},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('data/vendor/patchcore-inspection'))
    acquire(parser.parse_args().output)
