import base64
import shutil
import subprocess
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest import mock

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle

from payments.models import Payment
from subscriptions.models import SubscriptionPlan, UserSubscription
from users.models import User
from . import packaging
from .models import Movie, MovieDownload, MovieStream, PlaybackSession, UserMovieAccess, WatchHistory
from .playback import KEY_URI_PLACEHOLDER, hash_token, parse_cloudinary_video

PUBLIC_MP4 = 'https://res.cloudinary.com/demo/video/upload/v1700000000/movies/abc123.mp4'
PROTECTED_MP4 = 'https://res.cloudinary.com/demo/video/authenticated/v1700000001/movies/abc123.mp4'
KEY = bytes(range(16))

VARIANT_PLAYLIST = (
    '#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-TARGETDURATION:6\n#EXT-X-PLAYLIST-TYPE:VOD\n'
    f'#EXT-X-KEY:METHOD=AES-128,URI="{KEY_URI_PLACEHOLDER}"\n'
    '#EXTINF:6.0,\nhttps://res.cloudinary.com/demo/raw/upload/hls/pkg/720_00000.ts\n'
    '#EXTINF:6.0,\n/media/hls/pkg/720_00001.ts\n#EXT-X-ENDLIST\n'
)


class PlaybackTestCase(TestCase):
    def setUp(self):
        cache.clear()  # throttle counters
        self.client = APIClient()
        self.admin = User.objects.create_user(
            email='admin@example.com', username='admin',
            is_staff=True, is_email_verified=True,
        )
        self.user = User.objects.create_user(
            email='viewer@example.com', username='viewer', is_email_verified=True,
        )
        self.movie = Movie.objects.create(
            title='Test Movie', synopsis='s', thumbnail='https://example.com/t.jpg',
            trailer_url='https://example.com/trailer.mp4',
            movie_file=PUBLIC_MP4, uploaded_by=self.admin,
        )
        self.basic, _ = SubscriptionPlan.get_or_create_by_name('BASIC')
        self.premium, _ = SubscriptionPlan.get_or_create_by_name('PREMIUM')

    # helpers
    def make_premium(self, user=None, days=30):
        return UserSubscription.objects.create(
            user=user or self.user, plan=self.premium, status='ACTIVE',
            end_date=timezone.now() + timedelta(days=days),
        )

    def make_paid(self, user=None, ref='tx-1'):
        return MovieDownload.objects.create(
            user=user or self.user, movie=self.movie, amount_paid=self.basic.price, payment_reference=ref,
        )

    def make_stream(self, **kw):
        defaults = dict(
            movie=self.movie, status='READY', package_id='pkg', key=KEY, duration=12,
            variants=[{'height': 720, 'width': 1280, 'bandwidth': 2928000, 'playlist': VARIANT_PLAYLIST}],
        )
        defaults.update(kw)
        return MovieStream.objects.create(**defaults)

    def start(self, user=None):
        self.client.force_authenticate(user or self.user)
        return self.client.post(f'/api/movies/{self.movie.id}/playback/')

    def token_from(self, url):
        return url.split('/api/stream/')[1].split('/')[0]


class MovieFileExposureTests(PlaybackTestCase):
    def test_movie_file_hidden_from_viewers(self):
        self.client.force_authenticate(self.user)
        for url in ['/api/movies/', f'/api/movies/{self.movie.id}/']:
            res = self.client.get(url)
            data = res.data['results'][0] if 'results' in res.data else res.data
            self.assertEqual(data['movie_file'], '', url)
            self.assertEqual(data['trailer_url'], 'https://example.com/trailer.mp4')

    def test_movie_file_visible_to_staff(self):
        self.client.force_authenticate(self.admin)
        res = self.client.get(f'/api/movies/{self.movie.id}/')
        self.assertEqual(res.data['movie_file'], PUBLIC_MP4)

    def test_download_check_hides_protected_source(self):
        self.make_premium()
        self.client.force_authenticate(self.user)
        res = self.client.get(f'/api/movies/{self.movie.id}/download/')
        self.assertEqual(res.data['download_url'], PUBLIC_MP4)

        Movie.objects.filter(pk=self.movie.pk).update(movie_file=PROTECTED_MP4)
        res = self.client.get(f'/api/movies/{self.movie.id}/download/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['download_url'], '')

    def test_my_downloads_hides_protected_source(self):
        self.make_paid()
        Movie.objects.filter(pk=self.movie.pk).update(movie_file=PROTECTED_MP4)
        self.client.force_authenticate(self.user)
        res = self.client.get('/api/movies/my-downloads/')
        self.assertEqual(res.data['results'][0]['movie_file'], '')


class EntitlementTests(PlaybackTestCase):
    def test_lapsed_premium_access_row_no_longer_grants_access(self):
        MovieDownload.objects.create(
            user=self.user, movie=self.movie, amount_paid=0, payment_reference='PREMIUM',
        )
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.get(f'/api/movies/{self.movie.id}/download/').status_code, 402)
        self.assertEqual(self.start().status_code, 402)

    def test_payment_reference_cannot_unlock_two_movies(self):
        Payment.objects.create(
            user=self.user, plan=self.basic, amount=self.basic.price, tx_ref='tx-9', status='SUCCESS',
        )
        other = Movie.objects.create(
            title='Other', synopsis='s', thumbnail='https://example.com/t.jpg',
            movie_file=PUBLIC_MP4, uploaded_by=self.admin,
        )
        self.client.force_authenticate(self.user)
        ok = self.client.post(f'/api/movies/{self.movie.id}/confirm-download/', {'payment_reference': 'tx-9'})
        self.assertEqual(ok.status_code, 200)
        again = self.client.post(f'/api/movies/{other.id}/confirm-download/', {'payment_reference': 'tx-9'})
        self.assertEqual(again.status_code, 402)

    def test_paying_after_lapsed_premium_replaces_access_row(self):
        MovieDownload.objects.create(
            user=self.user, movie=self.movie, amount_paid=0, payment_reference='PREMIUM',
        )
        Payment.objects.create(
            user=self.user, plan=self.basic, amount=self.basic.price, tx_ref='tx-2', status='SUCCESS',
        )
        self.client.force_authenticate(self.user)
        res = self.client.post(f'/api/movies/{self.movie.id}/confirm-download/', {'payment_reference': 'tx-2'})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['reason'], 'paid')
        self.assertEqual(MovieDownload.objects.get(user=self.user, movie=self.movie).payment_reference, 'tx-2')


class PlaybackSessionTests(PlaybackTestCase):
    def test_requires_authentication(self):
        res = self.client.post(f'/api/movies/{self.movie.id}/playback/')
        self.assertEqual(res.status_code, 401)

    def test_requires_verified_email(self):
        self.user.is_email_verified = False
        self.user.save()
        res = self.start()
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.data['code'], 'email_not_verified')

    def test_unentitled_user_must_pay(self):
        self.make_stream()
        res = self.start()
        self.assertEqual(res.status_code, 402)
        self.assertEqual(res.data['status'], 'payment_required')
        self.assertFalse(PlaybackSession.objects.exists())

    def test_expired_subscription_must_pay(self):
        self.make_stream()
        self.make_premium(days=-1)
        self.assertEqual(self.start().status_code, 402)

    def test_premium_user_gets_hls_session(self):
        self.make_stream()
        self.make_premium()
        res = self.start()
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['mode'], 'hls')
        self.assertIsNone(res.data['drm'])
        self.assertIn('/api/stream/', res.data['manifest_url'])
        self.assertNotIn('cloudinary', res.data['manifest_url'])
        token = self.token_from(res.data['manifest_url'])
        session = PlaybackSession.objects.get()
        self.assertEqual(session.token_hash, hash_token(token))
        self.assertNotEqual(session.token_hash, token)
        self.assertTrue(UserMovieAccess.objects.filter(user=self.user, movie=self.movie).exists())

    def test_basic_buyer_gets_hls_session(self):
        self.make_stream()
        self.make_paid()
        self.assertEqual(self.start().data['mode'], 'hls')

    def test_expired_viewing_window_is_refused(self):
        self.make_stream()
        self.make_premium()
        UserMovieAccess.objects.create(
            user=self.user, movie=self.movie, is_active=False,
            expires_at=timezone.now() - timedelta(days=1),
        )
        res = self.start()
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.data['code'], 'access_expired')

    def test_progressive_fallback_until_packaged(self):
        self.make_premium()
        res = self.start()
        self.assertEqual(res.data['mode'], 'progressive')
        self.assertEqual(res.data['manifest_url'], PUBLIC_MP4)

    @override_settings(PLAYBACK_ALLOW_PROGRESSIVE=False)
    def test_no_fallback_when_progressive_disabled(self):
        self.make_premium()
        res = self.start()
        self.assertEqual(res.status_code, 503)
        self.assertEqual(res.data['code'], 'stream_not_ready')

    def test_protected_source_never_falls_back_to_file(self):
        Movie.objects.filter(pk=self.movie.pk).update(movie_file=PROTECTED_MP4)
        self.make_stream(status='PROCESSING')
        self.make_premium()
        self.assertEqual(self.start().status_code, 503)

    @override_settings(PLAYBACK_MAX_ACTIVE_SESSIONS=2)
    def test_concurrent_stream_cap_revokes_oldest(self):
        self.make_stream()
        self.make_premium()
        first = self.token_from(self.start().data['manifest_url'])
        self.start()
        self.start()
        live = PlaybackSession.objects.filter(revoked_at__isnull=True)
        self.assertEqual(live.count(), 2)
        self.assertFalse(live.filter(token_hash=hash_token(first)).exists())
        self.assertEqual(self.client.get(f'/api/stream/{first}/key').status_code, 403)

    def test_playback_is_rate_limited(self):
        self.make_stream()
        self.make_premium()
        with mock.patch.object(ScopedRateThrottle, 'THROTTLE_RATES', {'playback': '2/min', 'stream': '600/hour'}):
            self.assertEqual(self.start().status_code, 200)
            self.assertEqual(self.start().status_code, 200)
            self.assertEqual(self.start().status_code, 429)


class StreamEndpointTests(PlaybackTestCase):
    def setUp(self):
        super().setUp()
        self.make_stream()
        self.make_premium()
        res = self.start()
        self.token = self.token_from(res.data['manifest_url'])
        self.client.force_authenticate(None)  # stream URLs carry their own credential

    def test_master_playlist(self):
        res = self.client.get(f'/api/stream/{self.token}/master.m3u8')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], 'application/vnd.apple.mpegurl')
        self.assertEqual(res['Cache-Control'], 'private, no-store')
        body = res.content.decode()
        self.assertIn('RESOLUTION=1280x720', body)
        self.assertEqual(body.splitlines()[-1], '0.m3u8')

    def test_variant_playlist_injects_session_key_and_absolute_segments(self):
        body = self.client.get(f'/api/stream/{self.token}/0.m3u8').content.decode()
        self.assertIn('URI="key"', body)
        self.assertNotIn(KEY_URI_PLACEHOLDER, body)
        self.assertIn('http://testserver/media/hls/pkg/720_00001.ts', body)
        self.assertIn('https://res.cloudinary.com/demo/raw/upload/hls/pkg/720_00000.ts', body)

    def test_unknown_variant(self):
        self.assertEqual(self.client.get(f'/api/stream/{self.token}/5.m3u8').status_code, 403)

    def test_key(self):
        res = self.client.get(f'/api/stream/{self.token}/key')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.content, KEY)
        self.assertEqual(res['Cache-Control'], 'private, no-store')

    def test_invalid_token(self):
        for path in ['master.m3u8', '0.m3u8', 'key']:
            self.assertEqual(self.client.get(f'/api/stream/not-a-token/{path}').status_code, 403)

    def test_expired_session(self):
        PlaybackSession.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.client.get(f'/api/stream/{self.token}/master.m3u8').status_code, 403)
        self.assertEqual(self.client.get(f'/api/stream/{self.token}/key').status_code, 403)

    def test_revoked_session(self):
        PlaybackSession.objects.update(revoked_at=timezone.now())
        self.assertEqual(self.client.get(f'/api/stream/{self.token}/key').status_code, 403)

    def test_key_refused_after_subscription_lapses(self):
        UserSubscription.objects.update(end_date=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.client.get(f'/api/stream/{self.token}/master.m3u8').status_code, 200)
        self.assertEqual(self.client.get(f'/api/stream/{self.token}/key').status_code, 403)

    def test_key_refused_for_deactivated_account(self):
        User.objects.filter(pk=self.user.pk).update(is_active=False)
        self.assertEqual(self.client.get(f'/api/stream/{self.token}/key').status_code, 403)

    def test_stream_unavailable_while_repackaging(self):
        MovieStream.objects.update(status='PROCESSING')
        self.assertEqual(self.client.get(f'/api/stream/{self.token}/master.m3u8').status_code, 403)

    def test_end_revokes_session(self):
        self.assertEqual(self.client.post(f'/api/stream/{self.token}/end').status_code, 204)
        self.assertEqual(self.client.get(f'/api/stream/{self.token}/key').status_code, 403)
        # Ending twice (or with a bad token) is harmless.
        self.assertEqual(self.client.post(f'/api/stream/{self.token}/end').status_code, 204)


def _rsa_key():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption(),
    )
    return key.public_key(), base64.b64encode(pem).decode()


class DrmTests(PlaybackTestCase):
    def test_drm_ignored_when_provider_not_configured(self):
        self.make_stream(drm_playback_id='mux-pid')
        self.make_premium()
        self.assertEqual(self.start().data['mode'], 'hls')

    def test_mux_drm_session(self):
        public_key, private_b64 = _rsa_key()
        self.make_stream(drm_playback_id='mux-pid')
        self.make_premium()
        with override_settings(
            DRM_PROVIDER='mux', MUX_SIGNING_KEY_ID='kid-1', MUX_SIGNING_PRIVATE_KEY=private_b64,
        ):
            res = self.start()
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['mode'], 'drm')
        self.assertTrue(res.data['manifest_url'].startswith('https://stream.mux.com/mux-pid.m3u8?token='))

        video_token = res.data['manifest_url'].split('token=')[1]
        self.assertEqual(jwt.get_unverified_header(video_token)['kid'], 'kid-1')
        claims = jwt.decode(video_token, public_key, algorithms=['RS256'], audience='v')
        self.assertEqual(claims['sub'], 'mux-pid')

        drm = res.data['drm']
        self.assertEqual(drm['provider'], 'mux')
        self.assertTrue(drm['widevine'].startswith('https://license.mux.com/license/widevine/mux-pid?token='))
        self.assertTrue(drm['fairplay_certificate'].startswith('https://license.mux.com/appcert/fairplay/mux-pid?token='))
        license_claims = jwt.decode(drm['playready'].split('token=')[1], public_key, algorithms=['RS256'], audience='d')
        self.assertGreater(license_claims['exp'], timezone.now().timestamp())
        self.assertNotIn(private_b64, str(res.data))

    def test_drm_requires_entitlement(self):
        _, private_b64 = _rsa_key()
        self.make_stream(drm_playback_id='mux-pid')
        with override_settings(
            DRM_PROVIDER='mux', MUX_SIGNING_KEY_ID='kid-1', MUX_SIGNING_PRIVATE_KEY=private_b64,
        ):
            res = self.start()
        self.assertEqual(res.status_code, 402)
        self.assertNotIn('drm', res.data)


class WatchProgressTests(PlaybackTestCase):
    def test_progress_still_recorded(self):
        self.client.force_authenticate(self.user)
        res = self.client.patch(f'/api/movies/{self.movie.id}/watch-progress/', {'watch_duration': 95}, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(WatchHistory.objects.get(user=self.user).watch_duration, 95)


class PackagingTests(PlaybackTestCase):
    def setUp(self):
        super().setUp()
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)

    def test_parse_cloudinary_video(self):
        self.assertEqual(parse_cloudinary_video(PUBLIC_MP4), ('upload', 'movies/abc123', 'mp4'))
        self.assertEqual(
            parse_cloudinary_video('https://res.cloudinary.com/demo/video/authenticated/s--Ab1--/v2/a/b.mov'),
            ('authenticated', 'a/b', 'mov'),
        )
        self.assertIsNone(parse_cloudinary_video('https://example.com/movie.mp4'))

    @override_settings(HLS_RENDITIONS='1080:5000,720:2800,480:1200')
    def test_rendition_ladder_never_upscales(self):
        self.assertEqual(packaging.rendition_ladder(2160), [(1080, 5000), (720, 2800), (480, 1200)])
        self.assertEqual(packaging.rendition_ladder(720), [(720, 2800), (480, 1200)])
        self.assertEqual(packaging.rendition_ladder(361), [(360, 1200)])

    def test_rewrite_playlist(self):
        ffmpeg_out = (
            '#EXTM3U\n#EXT-X-KEY:METHOD=AES-128,URI="key-uri"\n#EXTINF:6.0,\n720_00000.ts\n#EXT-X-ENDLIST\n'
        )
        out = packaging.rewrite_playlist(ffmpeg_out, lambda name: f'https://cdn/{name}')
        self.assertIn(f'URI="{KEY_URI_PLACEHOLDER}"', out)
        self.assertIn('https://cdn/720_00000.ts', out)

    def test_ffmpeg_command_encrypts_segments(self):
        cmd = packaging.ffmpeg_command('/in.mp4', 720, 2800, Path('/k.keyinfo'), Path('/out'))
        self.assertIn('-hls_key_info_file', cmd)
        self.assertEqual(cmd[cmd.index('-hls_playlist_type') + 1], 'vod')

    def fake_ffmpeg(self, cmd, **kwargs):
        out = Path(cmd[-1]).parent
        height = out.name.rstrip('p')
        for i in range(2):
            (out / f'{height}_{i:05d}.ts').write_bytes(b'encrypted')
        (out / 'index.m3u8').write_text(
            '#EXTM3U\n#EXT-X-KEY:METHOD=AES-128,URI="key-uri"\n'
            f'#EXTINF:6.0,\n{height}_00000.ts\n#EXTINF:6.0,\n{height}_00001.ts\n#EXT-X-ENDLIST\n'
        )
        return subprocess.CompletedProcess(cmd, 0, '', '')

    def test_package_movie_end_to_end_with_local_storage(self):
        source = Path(self.media) / 'src.mp4'
        source.write_bytes(b'mp4')
        with override_settings(HLS_STORAGE='local', MEDIA_ROOT=self.media, HLS_RENDITIONS='720:2800,480:1200'), \
                mock.patch.object(packaging, '_fetch_source', return_value=source), \
                mock.patch.object(packaging, 'probe', return_value=(1920, 1080, 12.0)), \
                mock.patch.object(packaging.subprocess, 'run', side_effect=self.fake_ffmpeg):
            stream = packaging.package_movie(self.movie.id)

        self.assertTrue(stream.is_ready)
        self.assertEqual(len(bytes(stream.key)), 16)
        self.assertEqual([v['height'] for v in stream.variants], [720, 480])
        self.assertEqual(stream.variants[0]['width'], 1280)
        self.assertIn(f'/media/hls/{stream.package_id}/720_00000.ts', stream.variants[0]['playlist'])
        self.assertIn(KEY_URI_PLACEHOLDER, stream.variants[0]['playlist'])
        self.assertTrue((Path(self.media) / 'hls' / stream.package_id / '480_00001.ts').is_file())

    def test_package_failure_is_recorded(self):
        def boom(cmd, **kwargs):
            raise subprocess.CalledProcessError(1, cmd, stderr='Invalid data found when processing input')

        with override_settings(HLS_STORAGE='local', MEDIA_ROOT=self.media), \
                mock.patch.object(packaging, '_fetch_source', return_value=Path('/src')), \
                mock.patch.object(packaging, 'probe', return_value=(1280, 720, 5.0)), \
                mock.patch.object(packaging.subprocess, 'run', side_effect=boom):
            with self.assertRaises(subprocess.CalledProcessError), self.assertLogs('movies.packaging', 'ERROR'):
                packaging.package_movie(self.movie.id)
        stream = MovieStream.objects.get(movie=self.movie)
        self.assertEqual(stream.status, 'FAILED')
        self.assertIn('Invalid data', stream.error)

    def test_new_movie_file_marks_stream_stale(self):
        self.make_stream()
        self.movie.movie_file = 'https://res.cloudinary.com/demo/video/upload/v2/movies/new.mp4'
        self.movie.save()
        self.assertEqual(MovieStream.objects.get().status, 'PENDING')

    def test_protecting_source_keeps_stream_ready(self):
        self.make_stream()
        self.movie.movie_file = PROTECTED_MP4
        self.movie.save()
        self.assertEqual(MovieStream.objects.get().status, 'READY')

    @override_settings(HLS_AUTO_PACKAGE=True)
    def test_auto_package_queues_task(self):
        with mock.patch('movies.tasks.package_movie_stream.delay') as delay, \
                self.captureOnCommitCallbacks(execute=True):
            self.movie.movie_file = 'https://res.cloudinary.com/demo/video/upload/v3/movies/new.mp4'
            self.movie.save()
        delay.assert_called_once_with(self.movie.id)

    def test_protect_command_is_dry_run_by_default(self):
        self.make_stream()
        with mock.patch.object(packaging.cloudinary.uploader, 'rename') as rename:
            call_command('protect_movie_sources', stdout=mock.MagicMock())
        rename.assert_not_called()

    def test_protect_command_moves_source_to_authenticated(self):
        self.make_stream()
        with mock.patch.object(
            packaging.cloudinary.uploader, 'rename', return_value={'secure_url': PROTECTED_MP4},
        ) as rename, mock.patch.object(packaging, '_configure_cloudinary'):
            call_command('protect_movie_sources', '--apply', stdout=mock.MagicMock())
        rename.assert_called_once()
        self.assertEqual(rename.call_args.kwargs['to_type'], 'authenticated')
        self.movie.refresh_from_db()
        self.assertEqual(self.movie.movie_file, PROTECTED_MP4)
