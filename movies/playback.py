"""
Playback authorization shared by the download, playback-session and stream views.

Every full-movie stream goes through a PlaybackSession: the backend checks the
user's entitlement, mints a short-lived opaque token, and the token alone
unlocks the manifest and the AES key for that one movie. Entitlement is checked
again when the key is fetched, so lapsed subscriptions and revoked sessions stop
new playback even if the client still holds a manifest URL.
"""
import hashlib
import re
import secrets
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from subscriptions.models import UserSubscription
from .models import MovieDownload, PlaybackSession, UserMovieAccess

KEY_URI_PLACEHOLDER = '{{KEY_URI}}'

# res.cloudinary.com/<cloud>/video/<type>/[s--sig--/][v123/]<public_id>.<ext>
_CLOUDINARY_VIDEO_RE = re.compile(
    r'^https?://res\.cloudinary\.com/[^/]+/video/(?P<type>upload|authenticated)/'
    r'(?:s--[^/]+--/)?(?:v\d+/)?(?P<public_id>.+?)(?:\.(?P<ext>[A-Za-z0-9]+))?$'
)


def has_active_premium(user):
    """Return True if the user has an active Premium subscription."""
    return UserSubscription.objects.filter(
        user=user,
        plan__name='PREMIUM',
        status='ACTIVE',
        end_date__gt=timezone.now(),
    ).exists()


def has_paid_for(user, movie):
    """True if the user bought this movie on the Basic pay-per-movie plan.

    Premium users get MovieDownload rows with amount_paid=0 to track access;
    those must not outlive the Premium subscription, so they don't count here.
    """
    return MovieDownload.objects.filter(user=user, movie=movie, amount_paid__gt=0).exists()


def is_entitled(user, movie):
    return has_active_premium(user) or has_paid_for(user, movie)


def access_expired(user, movie):
    """True once the user's 10-day viewing window for this movie has lapsed."""
    active = UserMovieAccess.objects.filter(
        user=user, movie=movie, is_active=True, expires_at__gt=timezone.now(),
    ).exists()
    if active:
        return False
    return UserMovieAccess.objects.filter(user=user, movie=movie, is_active=False).exists()


# ── Source file ──────────────────────────────────────────────────────────────

def parse_cloudinary_video(url):
    """Split a Cloudinary video URL into (delivery_type, public_id, ext), or None."""
    m = _CLOUDINARY_VIDEO_RE.match(url or '')
    if not m:
        return None
    return m.group('type'), m.group('public_id'), m.group('ext') or 'mp4'


def cloudinary_video_source(movie):
    return parse_cloudinary_video(movie.movie_file)


def is_source_protected(movie):
    """The original file has been moved to Cloudinary 'authenticated' delivery."""
    source = cloudinary_video_source(movie)
    return bool(source) and source[0] == 'authenticated'


def public_file_url(movie):
    """The permanent file URL, if it is still publicly reachable; '' once it is protected."""
    if not movie.movie_file or is_source_protected(movie):
        return ''
    return movie.movie_file


# ── Sessions ─────────────────────────────────────────────────────────────────

def hash_token(token):
    return hashlib.sha256(token.encode()).hexdigest()


def _client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    return (forwarded.split(',')[0].strip() or request.META.get('REMOTE_ADDR')) or None


def create_session(request, movie, mode):
    """Create a session for request.user and return (session, raw_token).

    Enforces PLAYBACK_MAX_ACTIVE_SESSIONS per user by revoking the oldest
    sessions, the way streaming services cap simultaneous streams.
    """
    now = timezone.now()
    token = secrets.token_urlsafe(32)
    session = PlaybackSession.objects.create(
        user=request.user,
        movie=movie,
        token_hash=hash_token(token),
        mode=mode,
        expires_at=now + timedelta(seconds=settings.PLAYBACK_SESSION_TTL_SECONDS),
        ip_address=_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', '')[:255],
    )
    active = PlaybackSession.objects.filter(
        user=request.user, revoked_at__isnull=True, expires_at__gt=now,
    ).order_by('-created_at').values_list('id', flat=True)
    stale = list(active[settings.PLAYBACK_MAX_ACTIVE_SESSIONS:])
    if stale:
        PlaybackSession.objects.filter(id__in=stale).update(revoked_at=now)
    return session, token


def get_valid_session(token):
    """Return the live session for a raw token, or None if unknown, expired or revoked."""
    if not token or len(token) > 128:
        return None
    session = (
        PlaybackSession.objects.select_related('movie', 'user', 'movie__stream')
        .filter(token_hash=hash_token(token))
        .first()
    )
    if not session or not session.is_valid or not session.user.is_active:
        return None
    return session


# ── Playlists ────────────────────────────────────────────────────────────────

def render_master_playlist(stream, variant_uri):
    """HLS master playlist listing each rendition; variant_uri(index) builds its URL."""
    lines = ['#EXTM3U', '#EXT-X-VERSION:3', '#EXT-X-INDEPENDENT-SEGMENTS']
    for i, v in enumerate(stream.variants):
        attrs = f'BANDWIDTH={int(v["bandwidth"])}'
        if v.get('width') and v.get('height'):
            attrs += f',RESOLUTION={int(v["width"])}x{int(v["height"])}'
        lines += [f'#EXT-X-STREAM-INF:{attrs}', variant_uri(i)]
    return '\n'.join(lines) + '\n'


def render_variant_playlist(stream, index, key_uri, absolute):
    """A rendition playlist with this session's key URI and absolute segment URLs.

    absolute(path) turns locally stored segment paths ('/media/...') into full URLs.
    """
    playlist = stream.variants[index]['playlist'].replace(KEY_URI_PLACEHOLDER, key_uri)
    return '\n'.join(
        absolute(line) if line.startswith('/') else line for line in playlist.splitlines()
    ) + '\n'
