from django.contrib import messages

class RemoveMessagesMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
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
