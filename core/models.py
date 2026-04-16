from django.db import models


class WaitlistSignup(models.Model):
    email = models.EmailField(unique=True)
    company = models.CharField(max_length=120, blank=True)
    role = models.CharField(max_length=120, blank=True)
    stack = models.CharField(max_length=160, blank=True)
    monthly_sessions = models.IntegerField(null=True, blank=True)
    biggest_pain = models.TextField(blank=True)
    risk_score = models.IntegerField(null=True, blank=True)
    risk_label = models.CharField(max_length=20, blank=True)
    revenue_risk = models.FloatField(null=True, blank=True)
    source = models.CharField(max_length=40, default="landing")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.email
