from .models import SearchSummary


def can_publish(summary: SearchSummary) -> bool:
    return summary.all_ok
