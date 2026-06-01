from django.contrib import admin
from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['user', 'plan', 'amount', 'status', 'tx_ref', 'created_at']
    list_filter = ['status', 'plan']
    search_fields = ['user__email', 'tx_ref']
