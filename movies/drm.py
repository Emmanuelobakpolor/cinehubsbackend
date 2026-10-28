"""
Commercial multi-DRM adapter (Widevine, PlayReady, FairPlay).

Only Mux is implemented. It is dormant until DRM_PROVIDER='mux' and a Mux
signing key are configured AND a movie's MovieStream.drm_playback_id is set to
a Mux playback ID created with a DRM playback policy. Without those, playback
uses the free AES-128 HLS path instead, and nothing here pretends DRM is active.

Mux reference: https://www.mux.com/docs/guides/protect-videos-with-drm
Tokens are RS256 JWTs signed with a Mux signing key: aud 'v' authorizes the
manifest/segments, aud 'd' authorizes DRM licenses. The private key never
leaves the server; the browser only receives the signed, expiring tokens.
"""
import base64
import time

import jwt
from django.conf import settings

MUX_STREAM_BASE = 'https://stream.mux.com'
MUX_LICENSE_BASE = 'https://license.mux.com'


def drm_enabled():
    return (
        settings.DRM_PROVIDER == 'mux'
        and bool(settings.MUX_SIGNING_KEY_ID)
        and bool(settings.MUX_SIGNING_PRIVATE_KEY)
    )


def _mux_private_key():
    key = settings.MUX_SIGNING_PRIVATE_KEY.strip()
    # Mux returns the key base64-encoded; accept a raw PEM as well.
    return key if key.startswith('-----BEGIN') else base64.b64decode(key).decode()


def _mux_token(playback_id, audience, expires_at):
    claims = {'sub': playback_id, 'aud': audience, 'exp': expires_at}
    if settings.MUX_PLAYBACK_RESTRICTION_ID:
        claims['playback_restriction_id'] = settings.MUX_PLAYBACK_RESTRICTION_ID
    return jwt.encode(
        claims,
        _mux_private_key(),
        algorithm='RS256',
        headers={'kid': settings.MUX_SIGNING_KEY_ID},
    )


def mux_playback(playback_id, ttl_seconds):
    """Manifest URL plus license-server URLs for one DRM playback."""
    expires_at = int(time.time()) + ttl_seconds
    video_token = _mux_token(playback_id, 'v', expires_at)
    drm_token = _mux_token(playback_id, 'd', expires_at)
    lic = f'{MUX_LICENSE_BASE}/license'
    return {
        'manifest_url': f'{MUX_STREAM_BASE}/{playback_id}.m3u8?token={video_token}',
        'drm': {
            'provider': 'mux',
            'widevine': f'{lic}/widevine/{playback_id}?token={drm_token}',
            'playready': f'{lic}/playready/{playback_id}?token={drm_token}',
            'fairplay': f'{lic}/fairplay/{playback_id}?token={drm_token}',
            'fairplay_certificate': f'{MUX_LICENSE_BASE}/appcert/fairplay/{playback_id}?token={drm_token}',
        },
    }
