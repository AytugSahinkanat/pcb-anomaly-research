import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pcb_anomaly.download import download_ranges


class Response(io.BytesIO):
    def __init__(self, body=b'', status=200, headers=None):
        super().__init__(body)
        self.status, self.headers = status, headers or {}


class DownloadTests(unittest.TestCase):
    def test_ranges_reassemble_and_pin_etag(self):
        body = b'0123456789abcdef'

        def respond(request, **kwargs):
            if request.get_method() == 'HEAD':
                return Response(headers={'Content-Length': str(len(body)), 'ETag': 'version-1'})
            self.assertEqual(request.get_header('If-match'), 'version-1')
            start, end = map(int, request.get_header('Range').split('=')[1].split('-'))
            return Response(body[start:end+1], 206, {'Content-Range': f'bytes {start}-{end}/{len(body)}'})

        with tempfile.TemporaryDirectory() as temp, patch('urllib.request.urlopen', side_effect=respond):
            dest = Path(temp) / 'archive.tar'
            download_ranges('https://example.org/file', dest, workers=2, chunk_size=3)
            self.assertEqual(dest.read_bytes(), body)

    def test_rejects_server_ignoring_range(self):
        def respond(request, **kwargs):
            return Response(b'123', 200, {'Content-Length': '3', 'ETag': 'v1'})

        with tempfile.TemporaryDirectory() as temp, patch('urllib.request.urlopen', side_effect=respond):
            dest = Path(temp) / 'archive.tar'
            with self.assertRaisesRegex(ValueError, 'range response'):
                download_ranges('https://example.org/file', dest, workers=1)
            self.assertFalse(dest.exists())
