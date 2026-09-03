import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Dict, Any, Optional, Tuple

CAMBODIA_TZ = ZoneInfo("Asia/Phnom_Penh")

def to_cambodia_time(dt: Optional[datetime]) -> Optional[datetime]:
    """
    Converts any UTC or naive datetime into Cambodia Local Time (Asia/Phnom_Penh, UTC+7).
    """
    if not dt:
        return None
    if dt.tzinfo is None:
        # SQLite stores UTC datetimes without timezone info
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(CAMBODIA_TZ)

def format_datetime(dt: Optional[datetime], fmt: str = '%d %b %Y, %H:%M') -> str:
    """
    Formats datetime in Cambodia Local Time (ICT / UTC+7).
    """
    if not dt:
        return 'N/A'
    c_dt = to_cambodia_time(dt)
    return c_dt.strftime(fmt)

def format_date_only(dt: Optional[datetime], fmt: str = '%d %b %Y') -> str:
    """
    Formats date in Cambodia Local Time (ICT / UTC+7).
    """
    if not dt:
        return 'N/A'
    c_dt = to_cambodia_time(dt)
    return c_dt.strftime(fmt)

def get_current_cambodia_time() -> datetime:
    """
    Returns current timestamp in Cambodia Local Time.
    """
    return datetime.now(CAMBODIA_TZ)

def get_greeting(dt: Optional[datetime] = None) -> str:
    """
    Generates time-of-day greeting based on Cambodia Local Time.
    """
    c_dt = to_cambodia_time(dt) if dt else datetime.now(CAMBODIA_TZ)
    hour = c_dt.hour
    if hour < 12:
        return "Good morning"
    elif hour < 17:
        return "Good afternoon"
    else:
        return "Good evening"

def get_candidate_initials(full_name: Optional[str]) -> str:
    if not full_name:
        return "AP"
    parts = full_name.strip().split()
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()

def get_status_badge_class(status: str) -> str:
    mapping = {
        'New': 'badge-primary',
        'Under Review': 'badge-warning',
        'Shortlisted': 'badge-info',
        'Interview': 'badge-purple',
        'Interview Scheduled': 'badge-primary',
        'Interview Confirmed': 'badge-success',
        'Interview Completed': 'badge-purple',
        'Reschedule Requested': 'badge-warning',
        'Interview Declined': 'badge-danger',
        'Scheduled': 'badge-primary',
        'Confirmed': 'badge-success',
        'Completed': 'badge-purple',
        'Cancelled': 'badge-secondary',
        'Declined': 'badge-danger',
        'Selected': 'badge-success',
        'Rejected': 'badge-danger',
        'Withdrawn': 'badge-secondary',
        'Draft': 'badge-secondary',
        'Published': 'badge-success',
        'Closed': 'badge-dark'
    }
    return mapping.get(status, 'badge-secondary')

def calculate_preliminary_fit(application) -> Dict[str, Any]:
    analysis_text = application.ai_matching_analysis or ""
    cv_text = application.extracted_cv_text or ""
    
    score_match = re.search(r'(?:score|fit|percentage)[:\s]*(\d{1,3})%?', analysis_text, re.IGNORECASE)
    if score_match:
        score = int(score_match.group(1))
    else:
        has_relevant = any(k in cv_text.lower() for k in ["python", "legal", "hr", "engineer", "experience", "degree", "bachelor"])
        base = 70 if has_relevant else 55
        
        skills_keywords = ["fastapi", "docker", "postgresql", "management", "contract", "recruitment", "telecom", "monitoring", "network", "compliance"]
        found = sum(1 for kw in skills_keywords if kw in cv_text.lower())
        score = min(96, base + (found * 5))
        
        if "gap" in analysis_text.lower() or "missing" in analysis_text.lower():
            score = max(50, score - 5)

    if score >= 80:
        label = "Strong Fit"
        badge_class = "fit-high"
        bg_color = "rgba(16, 185, 129, 0.12)"
        text_color = "#34d399"
        border_color = "rgba(16, 185, 129, 0.3)"
    elif score >= 65:
        label = "Moderate Fit"
        badge_class = "fit-medium"
        bg_color = "rgba(99, 102, 241, 0.12)"
        text_color = "#818cf8"
        border_color = "rgba(99, 102, 241, 0.3)"
    elif score >= 50:
        label = "Potential Fit"
        badge_class = "fit-amber"
        bg_color = "rgba(245, 158, 11, 0.12)"
        text_color = "#fbbf24"
        border_color = "rgba(245, 158, 11, 0.3)"
    else:
        label = "Review Required"
        badge_class = "fit-neutral"
        bg_color = "rgba(100, 116, 139, 0.15)"
        text_color = "#cbd5e1"
        border_color = "rgba(100, 116, 139, 0.3)"

    return {
        "score": score,
        "label": label,
        "badge_class": badge_class,
        "bg_color": bg_color,
        "text_color": text_color,
        "border_color": border_color
    }

def parse_structured_ai_summary(application) -> Dict[str, Any]:
    summary_text = application.ai_summary or ""
    analysis_text = application.ai_matching_analysis or ""
    cv_text = application.extracted_cv_text or ""

    edu_match = re.search(r'(?:Bachelor|Master|Degree|B\.?Sc|LL\.?B|Diploma)[^\n,.]*', cv_text, re.IGNORECASE)
    education = edu_match.group(0).strip() if edu_match else "Bachelor's Degree in relevant field"

    exp_match = re.search(r'(\d+\+?\s*years?(?:\s+of)?\s+experience[^\n,.]*)', cv_text, re.IGNORECASE)
    if not exp_match:
        exp_match = re.search(r'(\d+\+?\s*years?[^\n,.]*)', summary_text, re.IGNORECASE)
    experience = exp_match.group(0).strip() if exp_match else "3+ years professional industry experience"

    key_matches = []
    competencies_match = re.search(r'Matching competencies:\s*([^\n]+)', analysis_text, re.IGNORECASE)
    if competencies_match:
        items = [i.strip() for i in competencies_match.group(1).split(",") if i.strip()]
        key_matches = items[:4]
    
    if not key_matches:
        key_matches = ["Core Position Requirements", "Technical Skillset Match", "Relevant Operational Background"]

    potential_gaps = []
    gaps_match = re.search(r'(?:Potential gaps|Missing requirements)[^:]*:\s*([^\n]+)', analysis_text, re.IGNORECASE)
    if gaps_match:
        g_items = [g.strip() for g in gaps_match.group(1).split(",") if g.strip()]
        potential_gaps = g_items[:3]
    
    if not potential_gaps:
        potential_gaps = ["Specific certifications to clarify during interview stage"]

    assessment = summary_text.replace("[AI Summary - Advisory Only]", "").strip()
    if not assessment:
        assessment = f"Demonstrates strong preliminary alignment for the {application.vacancy.title if application.vacancy else 'selected'} position."

    fit = calculate_preliminary_fit(application)

    return {
        "score": fit["score"],
        "label": fit["label"],
        "badge_class": fit["badge_class"],
        "education": education,
        "experience": experience,
        "key_matches": key_matches,
        "potential_gaps": potential_gaps,
        "assessment": assessment,
        "last_generated": format_datetime(application.updated_at or application.submitted_at)
    }

def parse_date_range_to_utc(
    from_date_str: Optional[str],
    to_date_str: Optional[str]
) -> Tuple[Optional[datetime], Optional[datetime], Optional[str]]:
    """
    Parses 'YYYY-MM-DD' from_date and to_date in Cambodia Time (Asia/Phnom_Penh, UTC+7).
    Returns (from_utc, to_utc, error_message).
    Ensures to_utc includes the entire day (up to 23:59:59.999999 local time converted to UTC).
    """
    from_utc = None
    to_utc = None
    error_msg = None

    try:
        from_d = datetime.strptime(from_date_str.strip(), "%Y-%m-%d").date() if from_date_str and from_date_str.strip() else None
        to_d = datetime.strptime(to_date_str.strip(), "%Y-%m-%d").date() if to_date_str and to_date_str.strip() else None

        if from_d and to_d and from_d > to_d:
            return None, None, "From Date cannot be later than To Date."

        if from_d:
            from_local = datetime.combine(from_d, datetime.min.time(), tzinfo=CAMBODIA_TZ)
            from_utc = from_local.astimezone(timezone.utc).replace(tzinfo=None)

        if to_d:
            to_local = datetime.combine(to_d, datetime.max.time(), tzinfo=CAMBODIA_TZ)
            to_utc = to_local.astimezone(timezone.utc).replace(tzinfo=None)

    except Exception as e:
        error_msg = f"Invalid date format: {str(e)}"

    return from_utc, to_utc, error_msg
