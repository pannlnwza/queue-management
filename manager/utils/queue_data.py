from django.contrib.auth.decorators import login_required
from django.http import StreamingHttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
import json
import time
from manager.models import RestaurantQueue, Queue
from manager.utils.category_handler import CategoryHandlerFactory
from participant.models import Participant, RestaurantParticipant

@login_required
def get_general_queue_data(request, queue_id):
    Participant.remove_old_completed_participants()
    queue = get_object_or_404(Queue, id=queue_id)
    waiting_participants = Participant.objects.filter(queue=queue, state='waiting').order_by('position')[:5]
    serving_participants = Participant.objects.filter(queue=queue, state='serving').order_by('-service_started_at')[:5]
    completed_participants = Participant.objects.filter(queue=queue, state='completed').order_by('-service_completed_at')[:5]

    data = {

        'waiting_list': [
            {
                'id': participant.id,
                'name': participant.name,
                'phone': participant.phone,
                'position': participant.position,
                'notes': participant.note,
                'waited': participant.get_wait_time(),
                'is_notified': participant.is_notified
            } for participant in waiting_participants
        ],
        'serving_list': [
            {
                'id': participant.id,
                'name': participant.name,
                'phone': participant.phone,
                'notes': participant.note,
                'waited': participant.get_wait_time(),
                'service_duration': participant.get_service_duration(),
                'served': participant.service_started_at.strftime('%d %b. %Y %H:%M') if participant.service_started_at else None,
                'is_notified': participant.is_notified
            } for participant in serving_participants
        ],
        'completed_list': [
            {
                'id': participant.id,
                'name': participant.name,
                'phone': participant.phone,
                'notes': participant.note,
                'waited': participant.waited,
                'service_duration': participant.get_service_duration(),
                'served': participant.service_started_at.strftime('%d %b. %Y %H:%M') if participant.service_started_at else None,
                'completed': participant.service_completed_at.strftime('%d %b. %Y %H:%M') if participant.service_completed_at else None,
                'is_notified': participant.is_notified
            } for participant in completed_participants
        ],
    }
    return JsonResponse(data)


@login_required
def get_unique_queue_category_data(request, queue_id):
    Participant.remove_old_completed_participants()
    queue = get_object_or_404(Queue, id=queue_id)
    handler = CategoryHandlerFactory.get_handler(queue.category)
    queue = handler.get_queue_object(queue_id)
    participant = handler.get_participant_set(queue_id)
    waiting_participants = participant.filter(queue=queue, state='waiting').order_by('position')[:5]
    serving_participants = participant.filter(queue=queue, state='serving').order_by('-service_started_at')[:5]
    completed_participants = participant.filter(queue=queue, state='completed').order_by('-service_completed_at')[:5]

    data = {
        'waiting_list': [handler.get_participant_data(participant) for participant in waiting_participants],
        'serving_list': [handler.get_participant_data(participant) for participant in serving_participants],
        'completed_list': [handler.get_participant_data(participant) for participant in completed_participants],
    }
    return JsonResponse(data)
