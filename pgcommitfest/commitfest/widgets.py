from django.forms import TextInput
from django.utils.safestring import mark_safe


class ThreadPickWidget(TextInput):
    def render(self, name, value, attrs=None, renderer=None):
        attrs["class"] += " threadpick-input"
        html = super().render(name, value, attrs)
        html = (
            html
            + f'&nbsp;<button class="btn btn-secondary attachThreadButton" id="btn_{name}">Find thread</button>'
        )
        return mark_safe(html)
