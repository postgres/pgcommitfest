from .models import CommitFest


def global_context(request):
    """Add global context variables available in all templates."""
    return {
        "current_cf": CommitFest.get_current(),
        "open_cf": CommitFest.get_open_regular(),
    }
