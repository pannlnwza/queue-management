from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.views import generic

from participant.models import Participant, Notification, QueueHistory
from manager.models import Queue
from manager.views import logger


# Create your views here.
@login_required
def mark_notification_as_read(request, notification_id):
    if request.method == 'POST':
        try:
            notification = Notification.objects.get(id=notification_id)
            notification.is_read = True  # Adjust according to your model's field
            notification.save()
            return JsonResponse({'status': 'success'})
        except Notification.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Notification not found'}, status=404)

    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)


class BaseQueueView(generic.ListView):
    model = Queue
    template_name = 'participant/list_queues.html'
    context_object_name = 'queues'
    queue_category = None

    def get_queryset(self):
        return Queue.objects.filter(category=self.queue_category)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['queue_type'] = self.queue_category.capitalize()
        context['queues'] = self.get_queryset()
        return context


class RestaurantQueueView(BaseQueueView):
    queue_category = 'restaurant'


class GeneralQueueView(BaseQueueView):
    queue_category = 'general'


class HospitalQueueView(BaseQueueView):
    queue_category = 'hospital'


class BankQueueView(BaseQueueView):
    queue_category = 'bank'


class ServiceCenterQueueView(BaseQueueView):
    queue_category = 'service center'


class QueueHistoryView(LoginRequiredMixin, generic.ListView):
    template_name = 'participant/queue_history.html'
    context_object_name = 'history_queues'

    def get_queryset(self):
        """
        Return the history of queues for the logged-in user.
        """
        return QueueHistory.objects.filter(user=self.request.user).order_by('-joined_at')

    def get_context_data(self, **kwargs):
        """
        Add additional context if needed.
        """
        context = super().get_context_data(**kwargs)
        context['title'] = 'Your Queue History'  # You can customize this title as needed
        return context


class BrowseQueueView(generic.ListView):
    model = Queue
    template_name = 'participant/browse_queue.html'


@login_required
def join_queue(request):
    """Customer joins queue using their ticket code."""
    if request.method == 'POST':
        queue_code = request.POST.get('queue_code')
        try:
            participant_slot = Participant.objects.get(queue_code=queue_code)
            queue = participant_slot.queue
            if Participant.objects.filter(user=request.user).exists():
                messages.error(request, f"You're already in a queue.")
                logger.info(
                    f"User: {request.user} attempted to join queue: {queue.name} when they're already in one.")
            elif queue.is_closed:
                messages.error(request, "The queue is closed.")
                logger.info(
                    f'User {request.user.username} attempted to join queue {queue.name} that has been closed.')
            elif participant_slot.user:
                messages.error(request, "Sorry, this slot is already filled by another participant. Are you sure"
                                        " that you have the right code?")
                logger.info(
                    f'User {request.user.username} attempted to join queue {queue.name}, but the participant slot is '
                    f'already occupied.')
            else:
                participant_slot.insert_user(user=request.user)
                participant_slot.save()
                messages.success(request,
                                 f"You have successfully joined the queue with code {queue_code}.")
        except Participant.DoesNotExist:
            messages.error(request, "Invalid queue code. Please try again.")
            return redirect('participant:index')
    return redirect('participant:index')


class IndexView(generic.ListView):
    """
    Display the index page for the user's queues.
    Lists the queues the authenticated user is participating in.

    :param template_name: The name of the template to render.
    :param context_object_name: The name of the context variable to hold the queue list.
    """
    template_name = 'participant/index.html'
    context_object_name = 'queue_list'

    def get_queryset(self):
        """
        Get the list of queues for the authenticated user.
        :returns: A queryset of queues the user is participating in, or an empty queryset if not authenticated.
        """
        if self.request.user.is_authenticated:
            return Queue.objects.filter(participant__user=self.request.user)
        return Queue.objects.none()

    def get_context_data(self, **kwargs):
        """
        Add additional context data to the template.

        :param kwargs: Additional keyword arguments passed to the method.
        :returns: The updated context dictionary with user's queue positions.
        """
        context = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            user_participants = Participant.objects.filter(
                user=self.request.user)
            queue_positions = {
                participant.queue.id: participant.position for participant in
                user_participants
            }
            estimated_wait_time = {
                participant.queue.id: participant.calculate_estimated_wait_time()
                for participant in user_participants
            }
            active_participants = {
                participant.queue.id: participant.id for participant in user_participants
            }
            expected_service_time = {
                participant.queue.id: datetime.now() + timedelta(
                    minutes=participant.calculate_estimated_wait_time())
                for participant in user_participants
            }
            notification = Notification.objects.filter(participant__user=self.request.user).order_by('-created_at')
            context['queue_positions'] = queue_positions
            context['estimated_wait_time'] = estimated_wait_time
            context['expected_service_time'] = expected_service_time
            context['notification'] = notification
            context['active_participants'] = active_participants
        return context
