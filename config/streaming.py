import os
import re
import mimetypes
from django.http import (
    StreamingHttpResponse,
    HttpResponse,
    HttpResponseNotFound,
    HttpResponseBadRequest,
)
from django.conf import settings


def media_stream(request, path):
    """
    Streaming media view with HTTP Range request support.

    Django's default static/media serving does not support byte-range requests.
    ExoPlayer (Android video player) requires range requests to:
      - Start playback immediately (reads headers from a small initial range)
      - Seek efficiently (jumps directly to any byte offset)
      - Buffer incrementally (fetches chunks as needed)

    Without this view, ExoPlayer downloads the entire file before playing,
    causing slow start times and broken seeking.
    """
    media_root = getattr(settings, 'MEDIA_ROOT', None)
    if not media_root:
        return HttpResponseNotFound()

    file_path = os.path.join(str(media_root), path)

    # Security: prevent path traversal
    real_path = os.path.realpath(file_path)
    real_root = os.path.realpath(str(media_root))
    if not real_path.startswith(real_root):
        return HttpResponse(status=403)

    if not os.path.isfile(real_path):
        return HttpResponseNotFound()

    file_size = os.path.getsize(real_path)
    content_type, _ = mimetypes.guess_type(real_path)
    content_type = content_type or 'application/octet-stream'

    range_header = request.META.get('HTTP_RANGE', '').strip()

    if range_header:
        m = re.match(r'bytes=(\d+)-(\d*)', range_header)
        if not m:
            return HttpResponseBadRequest('Invalid Range header')

        start = int(m.group(1))
        end = int(m.group(2)) if m.group(2) else file_size - 1

        if start > end or start >= file_size:
            resp = HttpResponse(status=416)
            resp['Content-Range'] = f'bytes */{file_size}'
            return resp

        end = min(end, file_size - 1)
        length = end - start + 1

        response = StreamingHttpResponse(
            _file_iterator(real_path, start, length),
            status=206,
            content_type=content_type,
        )
        response['Content-Range'] = f'bytes {start}-{end}/{file_size}'
        response['Content-Length'] = str(length)
        response['Accept-Ranges'] = 'bytes'
        return response

    # No Range header — serve the full file
    response = StreamingHttpResponse(
        _file_iterator(real_path, 0, file_size),
        status=200,
        content_type=content_type,
    )
    response['Content-Length'] = str(file_size)
    response['Accept-Ranges'] = 'bytes'
    return response


def _file_iterator(path, start, length, chunk_size=64 * 1024):
    """Generator that streams a file slice in chunks (default 64 KB)."""
    with open(path, 'rb') as f:
        f.seek(start)
        remaining = length
        while remaining > 0:
            data = f.read(min(chunk_size, remaining))
            if not data:
                break
            remaining -= len(data)
            yield data
