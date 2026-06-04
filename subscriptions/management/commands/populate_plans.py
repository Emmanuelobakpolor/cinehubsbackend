from django.core.management.base import BaseCommand
from subscriptions.models import SubscriptionPlan


class Command(BaseCommand):
    help = 'Populate subscription plans (BASIC and PREMIUM)'

    def handle(self, *args, **options):
        # Create BASIC plan (₦200 per movie)
        basic, created = SubscriptionPlan.objects.get_or_create(
            name='BASIC',
            defaults={
                'price': 200,
                'duration_days': 1,  # Per download
                'description': 'Pay per movie - ₦200 charged at download time.',
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created BASIC plan: ₦{basic.price} (ID: {basic.id})'))
        else:
            self.stdout.write(f'BASIC plan already exists (ID: {basic.id})')

        # Create PREMIUM plan (₦5,500 per month)
        premium, created = SubscriptionPlan.objects.get_or_create(
            name='PREMIUM',
            defaults={
                'price': 5500,
                'duration_days': 30,  # 30 days
                'description': 'Unlimited access to all movies for 30 days - ₦5,500 per month.',
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created PREMIUM plan: ₦{premium.price} (ID: {premium.id})'))
        else:
            self.stdout.write(f'PREMIUM plan already exists (ID: {premium.id})')

        self.stdout.write(self.style.SUCCESS('Successfully populated subscription plans'))
