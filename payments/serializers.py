from rest_framework import serializers
from .models import Payment


class PaymentInitSerializer(serializers.Serializer):
    # Clients send plan_name; plan_id is kept for older app builds.
    plan_name = serializers.ChoiceField(choices=['BASIC', 'PREMIUM'], required=False)
    plan_id = serializers.IntegerField(required=False)
    # Optional: where Flutterwave sends the browser after checkout (web app only).
    redirect_url = serializers.URLField(required=False, allow_blank=True)

    def validate(self, attrs):
        if not attrs.get('plan_name') and attrs.get('plan_id') is None:
            raise serializers.ValidationError('plan_name is required.')
        return attrs


class PaymentSerializer(serializers.ModelSerializer):
    plan_name = serializers.CharField(source='plan.name', read_only=True)

    class Meta:
        model = Payment
        fields = '__all__'
        read_only_fields = ['user', 'tx_ref', 'flw_ref', 'status', 'created_at']
