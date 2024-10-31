from django.contrib.auth.decorators import login_required
from django.http import StreamingHttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
import json
import time
from manager.models import RestaurantQueue
from participant.models import RestaurantParticipant

@login_required
def get_restaurant_queue_data(request, queue_id):
    queue = get_object_or_404(RestaurantQueue, id=queue_id)

    waiting_participants = RestaurantParticipant.objects.filter(queue=queue, state='waiting')
    serving_participants = RestaurantParticipant.objects.filter(queue=queue, state='serving')
    completed_participants = RestaurantParticipant.objects.filter(queue=queue, state='completed')

    data = {
        'waiting_list': [
            {
                'id': participant.id,
                'name': participant.name,
                'position': participant.position,
                'party_size': participant.party_size,
                'notes': participant.note,
                'waited': participant.get_wait_time(),
                'seating_preference': participant.seating_preference,
            } for participant in waiting_participants
        ],
        'serving_list': [
            {
                'id': participant.id,
                'name': participant.name,
                'party_size': participant.party_size,
                'notes': participant.note,
                'waited': participant.get_wait_time(),
                'service_duration': participant.get_service_duration(),
                'served': participant.service_started_at.strftime('%d/%m/%Y %H:%M') if participant.service_started_at else None,
                'table': participant.table.name if participant.table else None,
                'seating_preference': participant.seating_preference,
            } for participant in serving_participants
        ],
        'completed_list': [
            {
                'id': participant.id,
                'name': participant.name,
                'party_size': participant.party_size,
                'notes': participant.note,
                'waited': participant.get_wait_time(),
                'service_duration': participant.get_service_duration(),
                'served': participant.service_started_at.strftime('%d/%m/%Y %H:%M') if participant.service_started_at else None,
                'completed': participant.service_completed_at.strftime('%d/%m/%Y %H:%M') if participant.service_completed_at else None,
                'table': participant.table_served if participant.table_served else None,
                'seating_preference': participant.seating_preference,
            } for participant in completed_participants
        ],
    }
    return JsonResponse(data)