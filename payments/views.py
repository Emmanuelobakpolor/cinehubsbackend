import uuid
import requests
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny

from .models import Payment
from .serializers import PaymentInitSerializer, PaymentSerializer
from subscriptions.models import SubscriptionPlan, UserSubscription


class InitiatePaymentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PaymentInitSerializer(data=request.data)
        if serializer.is_valid():
            try:
                plan = SubscriptionPlan.objects.get(id=serializer.validated_data['plan_id'])
            except SubscriptionPlan.DoesNotExist:
                return Response({'error': 'Plan not found.'}, status=status.HTTP_404_NOT_FOUND)

            tx_ref = f'MSB-{uuid.uuid4().hex[:12].upper()}'
            payment = Payment.objects.create(
                user=request.user,
                plan=plan,
                amount=plan.price,
                tx_ref=tx_ref,
            )

            payload = {
                'tx_ref': tx_ref,
                'amount': str(plan.price),
                'currency': 'NGN',
                'redirect_url': 'http://localhost:8000/api/payments/verify/',
                'customer': {
                    'email': request.user.email,
                    'name': request.user.username,
                },
                'customizations': {
                    'title': f'{plan.name} Subscription',
                    'description': f'Subscribe to {plan.name} plan',
                },
            }

            # ── TEST MODE: skip Flutterwave, return a fake payment link ──────────
            if getattr(settings, 'PAYMENT_TEST_MODE', True):
                return Response({
                    'message': '[TEST MODE] Payment initiated. Use /verify/ with this tx_ref to activate subscription.',
                    'payment_link': f'http://localhost:8000/api/payments/mock-pay/?tx_ref={tx_ref}',
                    'tx_ref': tx_ref,
                })

            headers = {'Authorization': f'Bearer {settings.FLW_SECRET_KEY}'}
            try:
                response = requests.post(
                    'https://api.flutterwave.com/v3/payments',
                    json=payload,
                    headers=headers,
                )
                data = response.json()
                if data.get('status') == 'success':
                    return Response({
                        'message': 'Payment initiated',
                        'payment_link': data['data']['link'],
                        'tx_ref': tx_ref,
                    })
                return Response({'error': 'Failed to initiate payment.'}, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class VerifyPaymentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        tx_ref = request.data.get('tx_ref')
        transaction_id = request.data.get('transaction_id')

        try:
            payment = Payment.objects.get(tx_ref=tx_ref, user=request.user)
        except Payment.DoesNotExist:
            return Response({'error': 'Payment not found.'}, status=status.HTTP_404_NOT_FOUND)

        # ── TEST MODE: skip Flutterwave, immediately activate subscription ──────
        if getattr(settings, 'PAYMENT_TEST_MODE', True):
            payment.status = 'SUCCESS'
            payment.flw_ref = 'TEST-MODE'
            payment.save()
            plan = payment.plan
            end_date = timezone.now() + timedelta(days=plan.duration_days)
            UserSubscription.objects.update_or_create(
                user=request.user,
                plan=plan,
                defaults={'status': 'ACTIVE', 'end_date': end_date},
            )
            return Response({'message': '[TEST MODE] Payment verified. Subscription activated.'})

        headers = {'Authorization': f'Bearer {settings.FLW_SECRET_KEY}'}
        try:
            response = requests.get(
                f'https://api.flutterwave.com/v3/transactions/{transaction_id}/verify',
                headers=headers,
            )
            data = response.json()
            if data.get('status') == 'success' and data['data']['status'] == 'successful':
                payment.status = 'SUCCESS'
                payment.flw_ref = data['data'].get('flw_ref')
                payment.save()

                plan = payment.plan
                end_date = timezone.now() + timedelta(days=plan.duration_days)
                UserSubscription.objects.update_or_create(
                    user=request.user,
                    plan=plan,
                    defaults={'status': 'ACTIVE', 'end_date': end_date},
                )
                return Response({'message': 'Payment verified. Subscription activated.'})
            else:
                payment.status = 'FAILED'
                payment.save()
                return Response({'error': 'Payment verification failed.'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MyPaymentsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        payments = Payment.objects.filter(user=request.user).order_by('-created_at')
        serializer = PaymentSerializer(payments, many=True)
        return Response(serializer.data)


class AdminPaymentsView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        payments = Payment.objects.all().order_by('-created_at')
        serializer = PaymentSerializer(payments, many=True)
        return Response(serializer.data)
