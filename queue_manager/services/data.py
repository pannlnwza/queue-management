from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404

from queue_manager.models import Queue


@login_required
def get_queue_data(request):
    """Returns data for the queue that the user is participating in."""
    queue_data = []
    users_queues = Queue.objects.filter(participant__user=request.user)
    for queue in users_queues:
        user_position = queue.participant_set.filter(user=request.user).first().position
        queue_data.append({
            'id': queue.id,
            'name': queue.name,
            'position': user_position,
            'participant_count': queue.participant_set.count(),
            'status': queue.status.title(),
        })
    return JsonResponse(queue_data, safe=False)


@login_required
def get_dashboard_queue_data(request, queue_id):
    """Returns statistics for the specified queue for the dashboard."""
    queue = get_object_or_404(Queue, id=queue_id)

    dashboard_data = {
        'id': queue.id,
        'current_queue_length': queue.participant_set.count(),
        'estimated_wait_time': queue.estimated_wait_time,
        'participants_today': queue.get_participants_today(),
        'status': queue.status.title(),
    }
    return JsonResponse(dashboard_data)