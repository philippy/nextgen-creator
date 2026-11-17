from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.core.exceptions import ObjectDoesNotExist


ALLOWED_USERNAME = "phil"


class PhilOnlyBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        username_field = get_user_model().USERNAME_FIELD
        username = username or kwargs.get(username_field)
        if username != ALLOWED_USERNAME:
            return None
        return super().authenticate(request, username=username, password=password, **kwargs)

    def get_user(self, user_id):
        user_model = get_user_model()
        try:
            user = user_model._default_manager.get(
                pk=user_id,
                **{user_model.USERNAME_FIELD: ALLOWED_USERNAME},
            )
        except (ObjectDoesNotExist, ValueError, TypeError):
            return None
        return user if self.user_can_authenticate(user) else None
