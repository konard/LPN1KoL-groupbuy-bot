"""
ML app configuration for GroupBuy Bot.
Integrates plexe for AI-powered procurement analytics.
"""

from django.apps import AppConfig


class MlConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ml"
    verbose_name = "ML Analytics"
