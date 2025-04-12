# running/app/apps.py

# -------------------------------------------------- Import Libraries --------------------------------------------------
from django.apps import AppConfig as DjangoAppConfig


# ------------------------------------------------- Class Declarations -------------------------------------------------
class AppConfig(DjangoAppConfig):
    """
    Define the app configuration.
    """

    # use the default primary key
    default_auto_field = "django.db.models.BigAutoField"

    # define the application name, must match the app directory name
    name = "app"
