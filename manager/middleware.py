from django.contrib import messages

class RemoveMessagesMiddleware:
    """
    Middleware to remove specific messages from the messages storage.
    """
    def __init__(self, get_response):
        """
        Initializes the middleware.

        :param get_response: A callable that takes a request object and returns a response object.
        """
        self.get_response = get_response

    def __call__(self, request):
        """
        Processes the request and filters messages for authentication-related pages.

        :param request: The HTTP request object.
        :return: The HTTP response object.
        """
        response = self.get_response(request)
        if request.path.startswith('/accounts/'):  # Only for auth-related pages
            storage = messages.get_messages(request)
            # Convert messages to a list to avoid "used" flag issues
            messages_list = list(storage)
            # Clear the storage
            storage.used = True
            # Re-add messages we want to keep (if any)
            for message in messages_list:
                if not ("You have signed out." in str(message) or
                       "Successfully signed in as" in str(message)):
                    storage.add(message.level, message.message, message.extra_tags)
        return response
