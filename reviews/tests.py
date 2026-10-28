from django.test import TestCase
from rest_framework.test import APIClient

from movies.models import Movie, WatchHistory
from users.models import User
from .models import Review


class ReviewTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            email='admin@example.com', username='admin',
            is_staff=True, is_email_verified=True,
        )
        # Signup stores the email as the username.
        self.user = User.objects.create_user(
            email='jane@example.com', username='jane@example.com',
            first_name='Jane', last_name='Doe', is_email_verified=True,
        )
        self.movie = Movie.objects.create(
            title='Test Movie', synopsis='s', thumbnail='https://example.com/t.jpg',
            movie_file='https://example.com/m.mp4', uploaded_by=self.admin,
        )

    def test_public_reviews_never_expose_email(self):
        self.client.force_authenticate(self.user)
        res = self.client.post(f'/api/reviews/movie/{self.movie.id}/', {'rating': 5, 'comment': 'Great'})
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data['username'], 'Jane Doe')

        res = self.client.get(f'/api/reviews/movie/{self.movie.id}/')
        self.assertNotIn('jane@example.com', str(res.content))
        self.assertEqual(res.data['results'][0]['username'], 'Jane Doe')

    def test_nameless_user_gets_placeholder_not_email(self):
        self.user.first_name = self.user.last_name = ''
        self.user.save()
        review = Review.objects.create(user=self.user, movie=self.movie, rating=4)
        self.assertEqual(review.public_name, 'Cinehubs User')

    def test_admin_creates_custom_review_under_any_name(self):
        self.client.force_authenticate(self.admin)
        payload = {'movie': self.movie.id, 'display_name': 'MovieBuff99', 'rating': 5, 'comment': 'Loved it'}
        res = self.client.post('/api/reviews/admin/', payload)
        self.assertEqual(res.status_code, 201, res.data)
        self.assertTrue(res.data['is_custom'])

        # Several custom reviews may target the same movie.
        res = self.client.post('/api/reviews/admin/', {**payload, 'display_name': 'Ada'})
        self.assertEqual(res.status_code, 201, res.data)

        self.client.force_authenticate(self.user)
        res = self.client.get(f'/api/reviews/movie/{self.movie.id}/')
        names = {r['username'] for r in res.data['results']}
        self.assertEqual(names, {'MovieBuff99', 'Ada'})

    def test_admin_custom_review_requires_name(self):
        self.client.force_authenticate(self.admin)
        res = self.client.post('/api/reviews/admin/', {'movie': self.movie.id, 'display_name': '  ', 'rating': 5})
        self.assertEqual(res.status_code, 400)

    def test_admin_can_edit_and_delete_any_review(self):
        review = Review.objects.create(user=self.user, movie=self.movie, rating=2, comment='meh')
        self.client.force_authenticate(self.admin)
        res = self.client.patch(f'/api/reviews/admin/{review.id}/', {'comment': 'Edited', 'rating': 4})
        self.assertEqual(res.status_code, 200, res.data)
        review.refresh_from_db()
        self.assertEqual((review.comment, review.rating), ('Edited', 4))

        res = self.client.delete(f'/api/reviews/admin/{review.id}/')
        self.assertEqual(res.status_code, 204)

    def test_admin_review_endpoints_reject_regular_users(self):
        self.client.force_authenticate(self.user)
        res = self.client.post('/api/reviews/admin/', {'movie': self.movie.id, 'display_name': 'x', 'rating': 5})
        self.assertEqual(res.status_code, 403)


class DashboardStatsTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            email='admin@example.com', username='admin', is_staff=True, is_email_verified=True,
        )
        self.movie = Movie.objects.create(
            title='Hit', synopsis='s', thumbnail='https://example.com/t.jpg',
            movie_file='https://example.com/m.mp4', uploaded_by=self.admin, views_count=7,
        )
        watcher = User.objects.create_user(email='a@example.com', username='a@example.com', is_email_verified=True)
        User.objects.create_user(email='b@example.com', username='b@example.com', is_email_verified=True)
        WatchHistory.objects.create(user=watcher, movie=self.movie)

    def test_user_and_view_stats(self):
        self.client.force_authenticate(self.admin)
        res = self.client.get('/api/users/dashboard-stats/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['total_users'], 2)
        self.assertEqual(res.data['active_users_30d'], 1)
        self.assertEqual(res.data['active_today'], 1)
        self.assertEqual(res.data['total_views'], 7)

        res = self.client.get('/api/movies/stats/')
        top = res.data['top_movies'][0]
        self.assertEqual((top['title'], top['views_count'], top['unique_viewers']), ('Hit', 7, 1))
