import uuid
import logging
import hmac
import json
import requests
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny

from .models import Payment
from .serializers import PaymentInitSerializer, PaymentSerializer
from subscriptions.models import SubscriptionPlan, UserSubscription

logger = logging.getLogger(__name__)


def activate_subscription(payment, flw_ref=None):
    """
    Activates user subscription for a payment.
    Idempotent: does nothing if payment is already SUCCESS and subscription is live.
    Returns (success: bool, message: str)
    """
    # Idempotency check — skip only if subscription is already live
    if payment.status == 'SUCCESS':
        subscription = UserSubscription.objects.filter(user=payment.user, plan=payment.plan, status='ACTIVE').first()
        if subscription and subscription.end_date > timezone.now():
            return True, 'Subscription already active'

    with transaction.atomic():
        payment.status = 'SUCCESS'
        payment.flw_ref = flw_ref or 'UNKNOWN'
        payment.save()

        plan = payment.plan
        end_date = timezone.now() + timedelta(days=plan.duration_days)
        UserSubscription.objects.update_or_create(
            user=payment.user,
            plan=plan,
            defaults={'status': 'ACTIVE', 'end_date': end_date},
        )
    return True, 'Subscription activated'


def verify_flutterwave_signature(signature, secret_hash):
    """
    Flutterwave webhook verification is plain string equality:
        request.headers["verif-hash"]  ==  FLW_WEBHOOK_SECRET
    No HMAC, no body signing. hmac.compare_digest is used only to prevent
    timing-based attacks on the comparison itself.
    """
    if not signature or not secret_hash:
        return False
    return hmac.compare_digest(signature, secret_hash)


def verify_payment_invariants(payment, flw_data):
    """
    Verifies payment invariants match between local record and Flutterwave response.
    Returns (is_valid: bool, error_message: str)
    """
    # Check amount matches (Flutterwave returns as string)
    flw_amount = flw_data.get('amount')
    if flw_amount:
        try:
            flw_amount = float(flw_amount)
            if float(payment.amount) != flw_amount:
                return False, f'Amount mismatch: expected {payment.amount}, got {flw_amount}'
        except (ValueError, TypeError):
            return False, f'Invalid amount from Flutterwave: {flw_amount}'

    # Check currency matches
    flw_currency = flw_data.get('currency', 'NGN').upper()
    if flw_currency != payment.currency.upper():
        return False, f'Currency mismatch: expected {payment.currency}, got {flw_currency}'

    # Check tx_ref matches
    flw_tx_ref = flw_data.get('tx_ref')
    if flw_tx_ref and flw_tx_ref != payment.tx_ref:
        return False, f'tx_ref mismatch: expected {payment.tx_ref}, got {flw_tx_ref}'

    # Check customer email matches (if provided)
    customer = flw_data.get('customer') or {}
    flw_email = customer.get('email', '').lower() if isinstance(customer, dict) else ''
    payment_email = payment.user.email.lower()
    if flw_email and flw_email != payment_email:
        logger.error(f'SECURITY: customer email mismatch: expected {payment_email}, got {flw_email}')
        return False, f'Customer email mismatch: payment does not belong to this account'

    return True, None


class InitiatePaymentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PaymentInitSerializer(data=request.data)
        if serializer.is_valid():
            try:
                plan = SubscriptionPlan.objects.get(id=serializer.validated_data['plan_id'])
            except SubscriptionPlan.DoesNotExist:
                return Response({'error': 'Plan not found.'}, status=status.HTTP_404_NOT_FOUND)

            # Mark stale PENDING payments (> 30 min old) as FAILED to keep the DB tidy.
            # We do NOT reuse existing tx_refs because Flutterwave marks a link as
            # expired once its underlying transaction is completed — reusing a tx_ref
            # that was already paid causes "This link has expired" on retry.
            Payment.objects.filter(
                user=request.user,
                plan=plan,
                status='PENDING',
                created_at__lt=timezone.now() - timedelta(minutes=30),
            ).update(status='FAILED')

            tx_ref = f'MSB-{uuid.uuid4().hex[:12].upper()}'
            payment = Payment.objects.create(  # noqa: F841
                user=request.user,
                plan=plan,
                amount=plan.price,
                tx_ref=tx_ref,
            )

            payload = {
                'tx_ref': tx_ref,
                'amount': str(plan.price),
                'currency': 'NGN',
                'redirect_url': settings.PAYMENT_REDIRECT_URL,
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
            if getattr(settings, 'PAYMENT_TEST_MODE', False):
                base_url = getattr(settings, 'BASE_URL', 'http://localhost:8000').rstrip('/')
                return Response({
                    'message': '[TEST MODE] Payment initiated. Use /verify/ with this tx_ref to activate subscription.',
                    'payment_link': f'{base_url}/api/payments/mock-pay/?tx_ref={tx_ref}',
                    'tx_ref': tx_ref,
                })

            headers = {'Authorization': f'Bearer {settings.FLW_SECRET_KEY}'}
            try:
                response = requests.post(
                    'https://api.flutterwave.com/v3/payments',
                    json=payload,
                    headers=headers,
                    timeout=(10, 30),
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

    def get_permissions(self):
        # Flutterwave's redirect is an unauthenticated browser GET — allow it.
        # The actual payment verification always comes from a separate POST with a JWT.
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAuthenticated()]

    def get(self, request):
        """
        Flutterwave redirects the user's browser here after payment completes.
        Returns a styled HTML page instead of raw JSON so users see something clean.
        The Flutter WebView detects this URL via onLoadStop and fires a separate POST
        to /verify/ for actual subscription activation — this GET is display-only.
        """
        tx_ref = request.query_params.get('tx_ref', '')
        payment_status = request.query_params.get('status', '').lower()
        is_success = payment_status == 'successful'
        is_failed = payment_status in ('failed', 'cancelled')
        icon = '✅' if is_success else ('❌' if is_failed else '↩️')
        heading = (
            'Payment Successful!' if is_success else
            'Payment Not Completed' if is_failed else
            'Payment Cancelled'
        )
        body_text = (
            'Your subscription is being activated. Please return to the Cinehubs app.'
            if is_success else
            'Your payment did not go through. No money was deducted. Please try again in the app.'
            if is_failed else
            'You closed the payment screen before completing. No money was deducted. You can try again in the app.'
        )
        ref_html = (
            f'<p style="margin-top:8px;font-size:11px;color:#444">Ref: {tx_ref}</p>'
            if tx_ref else ''
        )

        html = (
            '<!DOCTYPE html><html lang="en"><head>'
            '<meta charset="UTF-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1.0">'
            '<title>Payment — Cinehubs</title>'
            '<style>'
            '*{box-sizing:border-box;margin:0;padding:0}'
            'body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;'
            'background:#0f0f0f;color:#fff;display:flex;align-items:center;'
            'justify-content:center;min-height:100vh;padding:24px}'
            '.card{background:#1a1a1a;border-radius:24px;padding:48px 32px;'
            'text-align:center;max-width:420px;width:100%;border:1px solid #2a2a2a}'
            '.icon{font-size:56px;margin-bottom:20px}'
            'h1{font-size:22px;font-weight:700;margin-bottom:10px}'
            'p{color:#888;font-size:14px;line-height:1.6}'
            '.note{margin-top:24px;color:#555;font-size:12px}'
            '</style></head>'
            '<body><div class="card">'
            f'<div class="icon">{icon}</div>'
            f'<h1>{heading}</h1>'
            f'<p>{body_text}</p>'
            f'{ref_html}'
            '<p class="note">You may close this window and return to the app.</p>'
            '</div></body></html>'
        )
        return HttpResponse(html, content_type='text/html')

    def post(self, request):
        tx_ref = request.data.get('tx_ref')
        transaction_id = request.data.get('transaction_id')

        try:
            payment = Payment.objects.get(tx_ref=tx_ref, user=request.user)
        except Payment.DoesNotExist:
            return Response({'error': 'Payment not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Idempotency: check if already processed
        if payment.status == 'SUCCESS':
            subscription = UserSubscription.objects.filter(
                user=request.user, plan=payment.plan, status='ACTIVE'
            ).first()
            if subscription and subscription.end_date > timezone.now():
                return Response({'message': 'Payment already verified. Subscription active.'})

        # ── TEST MODE: skip Flutterwave, immediately activate subscription ──────
        if getattr(settings, 'PAYMENT_TEST_MODE', False):
            if not transaction_id:
                return Response({'error': 'transaction_id is required in test mode'}, status=status.HTTP_400_BAD_REQUEST)
            success, message = activate_subscription(payment, transaction_id)
            return Response({'message': f'[TEST MODE] {message}'})

        headers = {'Authorization': f'Bearer {settings.FLW_SECRET_KEY}'}
        try:
            response = requests.get(
                f'https://api.flutterwave.com/v3/transactions/{transaction_id}/verify',
                headers=headers,
                timeout=(10, 30),
            )
            data = response.json()

            if data.get('status') == 'success' and data['data']['status'] == 'successful':
                flw_data = data['data']

                # Payment invariant checks
                is_valid, error_msg = verify_payment_invariants(payment, flw_data)
                if not is_valid:
                    logger.error(f'Payment invariant check failed: {error_msg}')
                    payment.status = 'FAILED'
                    payment.save()
                    return Response({'error': f'Payment validation failed: {error_msg}'}, status=status.HTTP_400_BAD_REQUEST)

                # Activate subscription (idempotent)
                success, message = activate_subscription(payment, flw_data.get('flw_ref'))
                return Response({'message': message})
            else:
                payment.status = 'FAILED'
                payment.save()
                return Response({'error': 'Payment verification failed.'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception('Error verifying payment')
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class FlutterwaveWebhookView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        # Strip to catch accidental whitespace/newlines when copy-pasting into Railway
        webhook_secret = getattr(settings, 'FLW_WEBHOOK_SECRET', '').strip()
        signature = (request.headers.get('verif-hash') or '').strip()

        logger.debug(
            "Flutterwave webhook received",
            extra={
                "verif_hash_present": bool(signature),
                "webhook_secret_configured": bool(webhook_secret),
                "received_hash": signature,
                "configured_hash_length": len(webhook_secret),
                "received_hash_length": len(signature),
            },
        )

        if not verify_flutterwave_signature(signature, webhook_secret):
            logger.warning(
                "Invalid Flutterwave webhook signature rejected",
                extra={
                    "path": request.path,
                    "received_hash": signature,
                    "received_hash_length": len(signature),
                    "configured_hash_length": len(webhook_secret),
                    "match": signature == webhook_secret,
                },
            )
            if not getattr(settings, 'PAYMENT_TEST_MODE', False):
                return Response({'error': 'Invalid signature'}, status=status.HTTP_401_UNAUTHORIZED)

        # Parse webhook data
        event = request.data.get('event')
        data = request.data.get('data') or {}

        logger.info(
            "Flutterwave webhook received",
            extra={
                "path": request.path,
                "event": event,
                "tx_ref": data.get('tx_ref'),
                "status": data.get('status'),
            },
        )

        # Handle payment completion events
        if event in ['payment.completed', 'charge.completed', 'card_charge.success']:
            tx_ref = data.get('tx_ref')
            transaction_status = data.get('status')

            if transaction_status != 'successful':
                logger.info(f'Webhook received but status is not successful: {transaction_status}')
                return Response({"status": "acknowledged"}, status=status.HTTP_200_OK)

            try:
                with transaction.atomic():
                    # select_for_update locks the row so concurrent webhook
                    # retries for the same tx_ref wait rather than double-process.
                    payment = Payment.objects.select_for_update().get(tx_ref=tx_ref)

                    # Idempotency: skip if already processed
                    if payment.status == 'SUCCESS':
                        logger.info(f'Webhook: payment {tx_ref} already processed, skipping')
                        return Response({"status": "acknowledged"}, status=status.HTTP_200_OK)

                    # Payment invariant checks
                    is_valid, error_msg = verify_payment_invariants(payment, data)
                    if not is_valid:
                        logger.error(f'Webhook payment invariant check failed: {error_msg}')
                        return Response({"status": "error", "message": error_msg}, status=status.HTTP_400_BAD_REQUEST)

                    # Activate subscription
                    _, message = activate_subscription(payment, data.get('flw_ref'))
                    logger.info(f'Webhook subscription activation: {message}')

            except Payment.DoesNotExist:
                logger.error(f'Webhook: Payment not found for tx_ref: {tx_ref}')
                return Response({"status": "acknowledged"}, status=status.HTTP_200_OK)

        return Response({"status": "acknowledged"}, status=status.HTTP_200_OK)


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


class MockPaymentView(APIView):
    """Test endpoint for simulating payment completion in test mode."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tx_ref = request.query_params.get('tx_ref')
        if not tx_ref:
            return Response({'error': 'tx_ref required'}, status=status.HTTP_400_BAD_REQUEST)

        if not getattr(settings, 'PAYMENT_TEST_MODE', False):
            return Response({'error': 'Mock payment only available in test mode'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            payment = Payment.objects.get(tx_ref=tx_ref, user=request.user)
        except Payment.DoesNotExist:
            return Response({'error': 'Payment not found'}, status=status.HTTP_404_NOT_FOUND)

        # Auto-verify in test mode
        success, message = activate_subscription(payment, 'TEST-MOCK')
        return Response({
            'message': f'[TEST MODE] {message}',
            'tx_ref': tx_ref,
            'payment_status': payment.status,
        })
