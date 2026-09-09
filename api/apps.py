from django.apps import AppConfig
from django.db.models.signals import post_save
from django.contrib.auth import get_user_model


class ApiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "api"

    def ready(self):
        from .models.user_profile import UserProfile

        User = get_user_model()

        def create_user_profile(sender, instance, created, **kwargs):
            if created:
                UserProfile.objects.get_or_create(user=instance)

        post_save.connect(create_user_profile, sender=User)

