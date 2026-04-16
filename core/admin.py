from django.contrib import admin

from .models import WaitlistSignup


@admin.register(WaitlistSignup)
class WaitlistSignupAdmin(admin.ModelAdmin):
    list_display = (
        "email",
        "company",
        "role",
        "monthly_sessions",
        "risk_score",
        "revenue_risk",
        "created_at",
    )
    search_fields = ("email", "company", "role", "stack")
    list_filter = ("risk_label", "source", "created_at")
