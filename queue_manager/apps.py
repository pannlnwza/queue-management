from django.apps import AppConfig


class QueueManagerConfig(AppConfig):
    """
    Configuration class for the Queue Manager application.

    This class configures the Queue Manager app, setting the default
    auto field type and the name of the application.
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'queue_manager'
