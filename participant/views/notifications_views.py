from django.http import JsonResponse
from participant.models import Notification

from django.views.decorators.http import require_POST


@require_POST
def mark_notification_as_read(request, notification_id):
    """
    Marks the specified notification as read.

    :param request: The HTTP request object.
    :param notification_id: The ID of the notification to mark as read.
    :return: A JSON response indicating success or failure.
    """
    try:
        notification = Notification.objects.get(id=notification_id)
        notification.is_read = True
        notification.save()
        return JsonResponse({"status": "success"})
    except Notification.DoesNotExist:
        return JsonResponse(
            {"status": "error", "message": "Notification not found"},
            status=404
        )
    except Exception as e:
        return JsonResponse(
            {"status": "error", "message": str(e)},
            status=500)
