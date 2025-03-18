# running/app/middleware.py

# -------------------------------------------------- Import Libraries --------------------------------------------------
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.messages import get_messages


# ------------------------------------------------- Class Declarations -------------------------------------------------
class ClearMessagesMiddleware(MessageMiddleware):
    """
    Middleware for refreshing the messages between pages
    """

    def process_request(self, request):
        storage = get_messages(request)
        for _ in storage:
            pass
