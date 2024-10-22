from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
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
            'status': queue.status
        })
    return JsonResponse(queue_data, safe=False)
