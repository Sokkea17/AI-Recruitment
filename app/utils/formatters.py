from datetime import datetime

def format_datetime(dt: datetime, fmt: str = '%d %b %Y, %H:%M') -> str:
    if not dt:
        return 'N/A'
    return dt.strftime(fmt)

def get_status_badge_class(status: str) -> str:
    mapping = {
        'New': 'badge-primary',
        'Under Review': 'badge-warning',
        'Shortlisted': 'badge-info',
        'Interview': 'badge-purple',
        'Selected': 'badge-success',
        'Rejected': 'badge-danger',
        'Withdrawn': 'badge-secondary',
        'Draft': 'badge-secondary',
        'Published': 'badge-success',
        'Closed': 'badge-dark'
    }
    return mapping.get(status, 'badge-secondary')
