"""Bounded parallel HTTP ranges with ETag and length validation."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import shutil
import urllib.request


def download_ranges(url, destination, workers=12, chunk_size=8*1024*1024):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(destination)
    with urllib.request.urlopen(urllib.request.Request(url, method='HEAD'), timeout=60) as r:
        size = int(r.headers['Content-Length'])
        etag = r.headers['ETag']
    if shutil.disk_usage(destination.parent).free < size + 1024**3:
        raise OSError('Insufficient disk space')
    partial = destination.with_suffix(destination.suffix + '.partial')
    with partial.open('xb') as stream:
        stream.truncate(size)

    def fetch(start):
        end = min(start + chunk_size, size) - 1
        request = urllib.request.Request(url, headers={'Range': f'bytes={start}-{end}', 'If-Match': etag})
        for attempt in range(3):
            try:
                with urllib.request.urlopen(request, timeout=90) as response:
                    if response.status != 206 or response.headers.get('Content-Range') != f'bytes {start}-{end}/{size}':
                        raise ValueError('Unexpected range response')
                    data = response.read()
                if len(data) != end - start + 1:
                    raise ValueError('Truncated range')
                with partial.open('r+b') as stream:
                    stream.seek(start); stream.write(data)
                return len(data)
            except Exception:
                if attempt == 2:
                    raise
    total = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for index, count in enumerate(pool.map(fetch, range(0, size, chunk_size))):
            total += count
            if index % 12 == 0:
                print(f'Validated {total / size:.1%} ({total / 1024**2:.0f} MiB)', flush=True)
    partial.rename(destination)
    return {'url': url, 'bytes': size, 'etag': etag}
