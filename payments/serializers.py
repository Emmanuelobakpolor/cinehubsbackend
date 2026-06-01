from rest_framework import serializers
from .models import Payment


class PaymentInitSerializer(serializers.Serializer):
    plan_id = serializers.IntegerField()


class PaymentSerializer(serializers.ModelSerializer):
    plan_name = serializers.CharField(source='plan.name', read_only=True)

    class Meta:
        model = Payment
        fields = '__all__'
        read_only_fields = ['user', 'tx_ref', 'flw_ref', 'status', 'created_at']
