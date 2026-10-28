"""
Builds the protected stream for a movie: an adaptive AES-128 encrypted HLS ladder.

    source MP4 ──ffmpeg──▶ 1080p/720p/480p .ts segments, encrypted with a random
                           per-movie key ──upload──▶ HLS_STORAGE (Cloudinary raw
                           files, or MEDIA_ROOT locally)

The variant playlists and the key are kept in the MovieStream row and served by
the token-gated stream views, so the segments on the CDN are useless on their
own. Requires the ffmpeg and ffprobe binaries on the worker (see nixpacks.toml).

protect_source() then moves the original MP4 to Cloudinary 'authenticated'
delivery so its old public URL stops working.
"""
import json
import logging
import os
import re
import secrets
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse

import cloudinary
import cloudinary.api
import cloudinary.uploader
import cloudinary.utils
import requests
from django.conf import settings
from django.utils import timezone

from .models import Movie, MovieStream
from .playback import KEY_URI_PLACEHOLDER, cloudinary_video_source

logger = logging.getLogger(__name__)

_KEY_URI_RE = re.compile(r'URI="[^"]*"')


def _configure_cloudinary():
    creds = getattr(settings, 'CLOUDINARY_STORAGE', None)
    if creds:
        cloudinary.config(
            cloud_name=creds['CLOUD_NAME'],
            api_key=creds['API_KEY'],
            api_secret=creds['API_SECRET'],
            secure=True,
        )


def rendition_ladder(source_height):
    """[(height, video_kbps)] from HLS_RENDITIONS, never upscaling the source."""
    ladder = []
    for item in settings.HLS_RENDITIONS.split(','):
        height, kbps = item.strip().split(':')
        ladder.append((int(height), int(kbps)))
    ladder.sort(reverse=True)
    fitting = [r for r in ladder if r[0] <= source_height]
    if fitting:
        return fitting
    # Source smaller than every rung: one rendition at the source's own height.
    return [(source_height - source_height % 2, ladder[-1][1])]


def rewrite_playlist(text, segment_url):
    """Point ffmpeg's playlist at the stored segments and template the key URI."""
    out = []
    for line in text.splitlines():
        if line.startswith('#EXT-X-KEY'):
            line = _KEY_URI_RE.sub(f'URI="{KEY_URI_PLACEHOLDER}"', line)
        elif line and not line.startswith('#'):
            line = segment_url(os.path.basename(line))
        out.append(line)
    return '\n'.join(out) + '\n'


def probe(path):
    """(width, height, duration_seconds) of the first video stream."""
    result = subprocess.run(
        [
            'ffprobe', '-v', 'error', '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height:format=duration', '-of', 'json', str(path),
        ],
        capture_output=True, text=True, check=True,
    )
    info = json.loads(result.stdout)
    stream = info['streams'][0]
    return int(stream['width']), int(stream['height']), float(info['format'].get('duration') or 0)


def ffmpeg_command(source, height, kbps, keyinfo, out_dir):
    seg = settings.HLS_SEGMENT_SECONDS
    return [
        'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
        '-i', str(source),
        '-map', '0:v:0', '-map', '0:a:0?',
        '-vf', f'scale=-2:{height}',
        '-c:v', 'libx264', '-preset', settings.HLS_X264_PRESET, '-profile:v', 'main',
        '-b:v', f'{kbps}k', '-maxrate', f'{int(kbps * 1.07)}k', '-bufsize', f'{kbps * 2}k',
        # Keyframe at every segment boundary so all renditions switch cleanly.
        '-force_key_frames', f'expr:gte(t,n_forced*{seg})', '-sc_threshold', '0',
        '-c:a', 'aac', '-b:a', '128k', '-ac', '2',
        '-f', 'hls', '-hls_time', str(seg), '-hls_playlist_type', 'vod',
        '-hls_key_info_file', str(keyinfo),
        '-hls_segment_filename', str(out_dir / f'{height}_%05d.ts'),
        str(out_dir / 'index.m3u8'),
    ]


def _fetch_source(movie, tmp):
    """Return a local path to the movie's original file, downloading it if needed."""
    url = movie.movie_file
    if not url:
        raise ValueError('Movie has no source file.')

    media_root = getattr(settings, 'MEDIA_ROOT', None)
    path = urlparse(url).path
    if media_root and path.startswith(settings.MEDIA_URL):
        local = Path(media_root) / path[len(settings.MEDIA_URL):]
        if local.is_file():
            return local

    source = cloudinary_video_source(movie)
    if source and source[0] == 'authenticated':
        # Protected originals are only reachable with a server-side signature.
        _configure_cloudinary()
        _, public_id, ext = source
        url = cloudinary.utils.cloudinary_url(
            public_id, resource_type='video', type='authenticated',
            sign_url=True, secure=True, format=ext,
        )[0]

    dest = Path(tmp) / 'source'
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(dest, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8 * 1024 * 1024):
                f.write(chunk)
    return dest


def _store_segments(files, package_id):
    """Upload encrypted segments; returns {filename: url or '/media/...' path}."""
    if settings.HLS_STORAGE == 'local':
        target = Path(settings.MEDIA_ROOT) / 'hls' / package_id
        target.mkdir(parents=True, exist_ok=True)
        urls = {}
        for f in files:
            shutil.copyfile(f, target / f.name)
            urls[f.name] = f'{settings.MEDIA_URL}hls/{package_id}/{f.name}'
        return urls

    _configure_cloudinary()

    def upload(f):
        result = cloudinary.uploader.upload(
            str(f),
            resource_type='raw',
            public_id=f'hls/{package_id}/{f.name}',
            overwrite=True,
            timeout=120,
        )
        return f.name, result['secure_url']

    with ThreadPoolExecutor(max_workers=8) as pool:
        return dict(pool.map(upload, files))


def _delete_package(package_id):
    """Best-effort removal of an old segment set."""
    try:
        if settings.HLS_STORAGE == 'local':
            shutil.rmtree(Path(settings.MEDIA_ROOT) / 'hls' / package_id, ignore_errors=True)
        else:
            _configure_cloudinary()
            cloudinary.api.delete_resources_by_prefix(f'hls/{package_id}/', resource_type='raw')
    except Exception:
        logger.warning('Could not delete old HLS package %s', package_id, exc_info=True)


def package_movie(movie_id):
    """Encode, encrypt and upload the HLS ladder for one movie. Returns the MovieStream."""
    movie = Movie.objects.get(pk=movie_id)
    stream, _ = MovieStream.objects.get_or_create(movie=movie)
    stream.status = 'PROCESSING'
    stream.error = ''
    stream.save(update_fields=['status', 'error', 'updated_at'])

    old_package = stream.package_id
    package_id = secrets.token_hex(16)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = _fetch_source(movie, tmp)
            width, height, duration = probe(source)

            key = os.urandom(16)
            key_file = tmp_path / 'enc.key'
            key_file.write_bytes(key)
            keyinfo = tmp_path / 'enc.keyinfo'
            # Line 1: URI ffmpeg writes into the playlist (replaced per session).
            # Line 3: random IV; ffmpeg otherwise advertises an all-zero IV.
            keyinfo.write_text(f'key-uri\n{key_file}\n{os.urandom(16).hex()}\n')

            variants = []
            for rung_height, kbps in rendition_ladder(height):
                out_dir = tmp_path / f'{rung_height}p'
                out_dir.mkdir()
                subprocess.run(
                    ffmpeg_command(source, rung_height, kbps, keyinfo, out_dir),
                    check=True, capture_output=True, text=True,
                )
                urls = _store_segments(sorted(out_dir.glob('*.ts')), package_id)
                playlist = rewrite_playlist((out_dir / 'index.m3u8').read_text(), urls.__getitem__)
                rung_width = round(width * rung_height / height / 2) * 2
                variants.append({
                    'height': rung_height,
                    'width': rung_width,
                    'bandwidth': (kbps + 128) * 1000,
                    'playlist': playlist,
                })
    except Exception as exc:
        detail = exc.stderr.strip()[-1500:] if isinstance(exc, subprocess.CalledProcessError) else str(exc)
        logger.exception('HLS packaging failed for movie %s', movie_id)
        stream.status = 'FAILED'
        stream.error = detail[:2000]
        stream.save(update_fields=['status', 'error', 'updated_at'])
        _delete_package(package_id)
        raise

    stream.key = key
    stream.package_id = package_id
    stream.variants = variants
    stream.duration = duration
    stream.status = 'READY'
    stream.packaged_at = timezone.now()
    stream.save()
    if old_package and old_package != package_id:
        _delete_package(old_package)
    logger.info('HLS packaging done for movie %s (%d renditions)', movie_id, len(variants))
    return stream


def protect_source(movie):
    """Move the original MP4 to Cloudinary 'authenticated' delivery.

    Its old public URL stops working (Cloudinary also purges its CDN copy), and
    only the backend can fetch it again via a signed URL. Reversible with the
    same rename call using to_type='upload'.
    """
    source = cloudinary_video_source(movie)
    if not source:
        raise ValueError('movie_file is not a Cloudinary video URL.')
    delivery, public_id, ext = source
    if delivery == 'authenticated':
        return movie.movie_file

    _configure_cloudinary()
    result = cloudinary.uploader.rename(
        public_id, public_id,
        resource_type='video', type='upload', to_type='authenticated',
        invalidate=True,
    )
    movie.movie_file = result.get('secure_url') or cloudinary.utils.cloudinary_url(
        public_id, resource_type='video', type='authenticated', secure=True, format=ext,
    )[0]
    movie.save(update_fields=['movie_file'])
    return movie.movie_file
