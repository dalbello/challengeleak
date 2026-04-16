import re
from django.db import OperationalError, ProgrammingError, connection
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from .models import WaitlistSignup


EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def home(request):
    return render(request, "home.html")


def _to_float(value, default=0.0, min_value=None, max_value=None):
    try:
        parsed = float(str(value).strip())
    except (TypeError, ValueError):
        parsed = default
    if min_value is not None:
        parsed = max(min_value, parsed)
    if max_value is not None:
        parsed = min(max_value, parsed)
    return parsed


def _to_int(value, default=0, min_value=None, max_value=None):
    try:
        parsed = int(float(str(value).strip()))
    except (TypeError, ValueError):
        parsed = default
    if min_value is not None:
        parsed = max(min_value, parsed)
    if max_value is not None:
        parsed = min(max_value, parsed)
    return parsed


def _risk_label(score):
    if score >= 80:
        return "low"
    if score >= 60:
        return "moderate"
    if score >= 40:
        return "high"
    return "critical"


def _action_weight(action):
    a = (action or "").strip().lower()
    if a in {"block", "managed_challenge"}:
        return 1.25
    if a in {"js_challenge", "challenge"}:
        return 1.1
    if a in {"log", "skip"}:
        return 0.8
    return 1.0


def _parse_rules(rule_text, revenue_risk):
    rows = []
    for raw in (rule_text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 4:
            continue
        name = parts[0][:120]
        traffic_share = _to_float(parts[1], 0.0, 0.0, 100.0)
        impact = _to_float(parts[2], 0.0, 0.0, 100.0)
        action = parts[3][:40]
        weight = max(0.1, traffic_share / 100.0) * max(0.1, impact / 10.0) * _action_weight(action)
        rows.append(
            {
                "rule": name,
                "action": action,
                "traffic_share": round(traffic_share, 2),
                "impact": round(impact, 2),
                "weight": weight,
            }
        )

    if not rows:
        rows = [
            {
                "rule": "Bot Fight Mode + default managed challenge",
                "action": "managed_challenge",
                "traffic_share": 65.0,
                "impact": 24.0,
                "weight": 1.0,
            },
            {
                "rule": "WAF custom rule: high-risk ASN block",
                "action": "block",
                "traffic_share": 35.0,
                "impact": 31.0,
                "weight": 0.9,
            },
        ]

    total_weight = sum(r["weight"] for r in rows) or 1.0
    for row in rows:
        row["revenue_at_risk"] = round(revenue_risk * (row["weight"] / total_weight), 2)
        row.pop("weight", None)

    rows.sort(key=lambda r: r["revenue_at_risk"], reverse=True)
    return rows[:5]


@require_POST
def process(request):
    monthly_sessions = _to_int(request.POST.get("monthly_sessions"), 0, 0)
    baseline_cvr = _to_float(request.POST.get("baseline_cvr"), 2.0, 0.01, 100.0)
    avg_order_value = _to_float(request.POST.get("avg_order_value"), 120.0, 1.0)

    challenge_rate = _to_float(request.POST.get("challenge_rate"), 0.0, 0.0, 100.0)
    solve_rate = _to_float(request.POST.get("solve_rate"), 0.0, 0.0, 100.0)
    blocked_human_rate = _to_float(request.POST.get("blocked_human_rate"), 0.0, 0.0, 100.0)
    conversion_drop = _to_float(request.POST.get("conversion_drop"), 0.0, 0.0, 100.0)

    if monthly_sessions <= 0:
        return JsonResponse({"status": "error", "message": "Enter monthly sessions greater than zero."}, status=400)

    challenged_sessions = monthly_sessions * (challenge_rate / 100.0)
    unsolved_challenges = challenged_sessions * max(0.0, (100.0 - solve_rate) / 100.0)
    falsely_blocked = monthly_sessions * (blocked_human_rate / 100.0)

    baseline_conversions = monthly_sessions * (baseline_cvr / 100.0)
    lost_conversions = baseline_conversions * (conversion_drop / 100.0)
    revenue_risk = lost_conversions * avg_order_value

    at_risk_sessions = round(unsolved_challenges + falsely_blocked)

    score = 100
    score -= min(35, conversion_drop * 1.1)
    score -= min(30, (100.0 - solve_rate) * 0.45)
    score -= min(25, blocked_human_rate * 7)
    score -= min(15, challenge_rate * 0.25)
    score = max(0, int(round(score)))
    risk = _risk_label(score)

    recommendations = []
    if blocked_human_rate >= 1.0:
        recommendations.append("Split strict block rules into challenge-first mode for paid traffic paths.")
    if solve_rate < 75:
        recommendations.append("Tune challenge action by device/geo and bypass known high-intent routes (checkout, lead forms).")
    if conversion_drop >= 10:
        recommendations.append("Correlate rule deploy timestamps with ad-set level ROAS drops before rolling broad blocks.")
    if challenge_rate >= 20:
        recommendations.append("Add bot score thresholds and verified bot allowlists before managed challenge on all traffic.")
    if not recommendations:
        recommendations.append("Current config looks stable. Keep monitoring rule changes against conversion cohorts.")

    top_rules = _parse_rules(request.POST.get("rules"), revenue_risk)

    return JsonResponse(
        {
            "status": "ok",
            "score": score,
            "risk": risk,
            "at_risk_sessions": at_risk_sessions,
            "lost_conversions": round(lost_conversions, 2),
            "revenue_at_risk": round(revenue_risk, 2),
            "top_rules": top_rules,
            "recommendations": recommendations,
            "assumptions": {
                "monthly_sessions": monthly_sessions,
                "baseline_cvr": round(baseline_cvr, 2),
                "avg_order_value": round(avg_order_value, 2),
                "challenge_rate": round(challenge_rate, 2),
                "solve_rate": round(solve_rate, 2),
                "blocked_human_rate": round(blocked_human_rate, 2),
                "conversion_drop": round(conversion_drop, 2),
            },
        }
    )


def _ensure_waitlist_table():
    table = WaitlistSignup._meta.db_table
    if table not in connection.introspection.table_names():
        with connection.schema_editor() as schema_editor:
            schema_editor.create_model(WaitlistSignup)


@require_POST
def waitlist(request):
    email = (request.POST.get("email") or "").strip().lower()
    company = (request.POST.get("company") or "").strip()
    role = (request.POST.get("role") or "").strip()
    stack = (request.POST.get("stack") or "").strip()
    biggest_pain = (request.POST.get("biggest_pain") or "").strip()
    monthly_sessions = _to_int(request.POST.get("monthly_sessions"), 0, 0)
    risk_score = _to_int(request.POST.get("risk_score"), 0, 0, 100)
    risk_label = (request.POST.get("risk_label") or "").strip().lower()[:20]
    revenue_risk = _to_float(request.POST.get("revenue_risk"), 0.0, 0.0)

    if not EMAIL_RE.match(email):
        return JsonResponse({"status": "error", "message": "Enter a valid email."}, status=400)

    try:
        _ensure_waitlist_table()
        obj, created = WaitlistSignup.objects.get_or_create(
            email=email,
            defaults={
                "company": company,
                "role": role,
                "stack": stack,
                "biggest_pain": biggest_pain,
                "monthly_sessions": monthly_sessions or None,
                "risk_score": risk_score or None,
                "risk_label": risk_label,
                "revenue_risk": revenue_risk or None,
                "source": "landing",
            },
        )
    except (OperationalError, ProgrammingError):
        return JsonResponse({"status": "ok", "message": "You are in. We'll reach out when private beta opens."})

    if not created:
        changed = False
        updates = {
            "company": company,
            "role": role,
            "stack": stack,
            "biggest_pain": biggest_pain,
            "monthly_sessions": monthly_sessions or None,
            "risk_score": risk_score or None,
            "risk_label": risk_label,
            "revenue_risk": revenue_risk or None,
        }
        for field, value in updates.items():
            if value and getattr(obj, field) != value:
                setattr(obj, field, value)
                changed = True
        if changed:
            obj.save()
        return JsonResponse({"status": "ok", "message": "You're already on the waitlist. We updated your details."})

    return JsonResponse({"status": "ok", "message": "You're in. We'll send your private beta invite soon."})


def privacy(request):
    return render(request, "privacy.html")


def terms(request):
    return render(request, "terms.html")
