from .models import CommitFest


def global_context(request):
    """Add global context variables available in all templates."""
    cfs = CommitFest.relevant_commitfests()
    return {
        "current_cf": cfs.get("in_progress") or cfs.get("open"),
        "open_cf": cfs.get("open"),
    }
