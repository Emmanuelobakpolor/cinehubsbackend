from django.db import models
from django.conf import settings
from movies.models import Movie


class Review(models.Model):
    # Null for reviews written by an admin under a custom name.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reviews',
        null=True, blank=True,
    )
    display_name = models.CharField(
        max_length=60, blank=True, default='',
        help_text='Name shown publicly. Overrides the author name; required for admin-written reviews.',
    )
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name='reviews')
    rating = models.IntegerField(choices=[(i, i) for i in range(1, 6)])
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'movie')

    @property
    def public_name(self):
        """The name shown on the review. Never exposes an email address."""
        if self.display_name:
            return self.display_name
        user = self.user
        if user is None:
            return 'Cinehubs User'
        # Signup stores the email as username, so only use it when it isn't one.
        if user.username and '@' not in user.username:
            return user.username
        return user.get_full_name() or 'Cinehubs User'

    def __str__(self):
        return f'{self.public_name} - {self.movie.title} - {self.rating}/5'
