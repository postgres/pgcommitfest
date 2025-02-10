from django.apps import AppConfig


class CFAppConfig(AppConfig):
    name = "pgcommitfest.commitfest"

    def ready(self):
        from pgcommitfest.auth import auth_user_data_received
        from pgcommitfest.userprofile.util import handle_user_data

        auth_user_data_received.connect(handle_user_data)
