import logging

from django.contrib import messages
from django.contrib.auth import authenticate, login, user_logged_in, user_logged_out, user_login_failed
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.dispatch import receiver
from django.http import Http404, JsonResponse, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.template.loader import render_to_string
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.views import generic
from django.apps import apps
from django.views.decorators.http import require_http_methods

from manager.forms import QueueForm
from manager.utils.participant_handler import ParticipantHandlerFactory
from participant.models import Participant, Notification, RestaurantParticipant
from manager.models import Queue


class CreateQView(LoginRequiredMixin, generic.CreateView):
    """
    Create a new queue.

    Provides a form for authenticated users to create a new queue.

    :param model: The model to use for creating the queue.
    :param form_class: The form class for queue creation.
    :param template_name: The name of the template to render.
    :param success_url: The URL to redirect to on successful queue creation.
    """
    model = Queue
    form_class = QueueForm
    template_name = 'manager/create_q.html'
    success_url = reverse_lazy('participant:index')

    def form_valid(self, form):
        """
        Set the creator of the queue to the current user.

        :param form: The form containing the queue data.
        :returns: The response after the form has been successfully validated and saved.
        """
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class ManageQueuesView(LoginRequiredMixin, generic.ListView):
    """
    Manage queues.

    Allows authenticated users to view, edit, and delete their queues.
    Lists all user-associated queues and provides action options.

    :param model: The model representing the queues.
    :param template_name: Template for displaying the queue list.
    :param context_object_name: Variable name for queues in the template.
    """
    model = Queue
    template_name = 'manager/manage_queues.html'
    context_object_name = 'queues'

    def get_queryset(self):
        """
        Retrieve the queues created by the logged-in user.
        :returns: A queryset of queues created by the current user.
        """
        return Queue.objects.filter(created_by=self.request.user)


class EditQueueView(LoginRequiredMixin, generic.UpdateView):
    """
    Edit an existing queue.

    Allows authenticated users to change the queue's name, delete participants,
    or close the queue.

    :param model: The model to use for editing the queue.
    :param form_class: The form class for queue editing.
    :param template_name: The name of the template to render.
    """
    model = Queue
    form_class = QueueForm
    template_name = 'manager/edit_queue.html'

    def dispatch(self, request, *args, **kwargs):
        """
        Check if the user is the creator of the queue before allowing access.
        """
        queue = self.get_object()
        if queue.created_by != request.user:
            messages.error(self.request,
                           "You do not have permission to edit this queue.")
            logger.warning(
                f"Unauthorized attempt to access edit queue page for queue: {queue.name} by user: {request.user}")
            return redirect('manager:manage_queues')
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        """redirect user back to manage queues page, if the edit was saved successfully."""
        return reverse('manager:manage_queues')

    def get_context_data(self, **kwargs):
        """
        Add additional context data to the template.

        :param kwargs: Additional keyword arguments passed to the method.
        :returns: The updated context dictionary.
        """
        context = super().get_context_data(**kwargs)
        queue = self.object
        context['participants'] = queue.participant_set.all()
        return context

    def post(self, request, *args, **kwargs):
        """
        Handle POST requests to update the queue and manage participants.

        :param request: The HTTP request object containing data for the queue and participants.
        :returns: Redirects to the success URL after processing.
        """
        self.object = self.get_object()

        if request.POST.get('action') == 'queue_status':
            return self.queue_status_handler()
        if request.POST.get('action') == 'edit_queue':
            name = request.POST.get('name')
            description = request.POST.get('description')
            is_closed = request.POST.get('is_closed') == 'true'
            try:
                self.object.edit(name=name, description=description,
                                 is_closed=is_closed)
                messages.success(self.request, "Queue updated successfully.")
            except ValueError as e:
                messages.error(self.request, str(e))
        return super().post(request, *args, **kwargs)

    def queue_status_handler(self):
        """Close the queue."""
        self.object.is_closed = not self.object.is_closed
        self.object.save()
        messages.success(self.request, "Queue status updated successfully.")
        return redirect('manager:manage_queues')


class QueueDashboardView(generic.DetailView):
    model = Queue
    template_name = 'manager/general_dashboard.html'
    context_object_name = 'queue'

    def get(self, request, *args, **kwargs):
        try:
            queue = get_object_or_404(Queue, pk=kwargs.get('pk'))
        except Http404:
            logger.warning(f'User {request.user.username} attempted '
                           f'to access a non-existent queue with ID {kwargs.get("pk")}.')
            messages.error(request, 'Queue does not exist.')
            return redirect('queue:index')
        if queue.created_by != request.user:
            logger.warning(
                f'User {request.user.username} attempted to access the dashboard '
                f'for queue "{queue.name}" (ID: {queue.pk}) without ownership.')
            messages.error(request, 'You are not the owner of this queue.')
            return redirect('queue:index')

        logger.info(f'User {request.user.username} accessed the '
                    f'dashboard for queue "{queue.name}" with ID {queue.pk}.')
        return super().get(request, *args, **kwargs)


@login_required
def add_participant_slot(request, queue_id):
    """Staff adds a participant to the queue and generates a queue code."""
    queue = get_object_or_404(Queue, id=queue_id)

    if queue.is_full():
        messages.error(request,
                       f'Queue has exceeded the limit capacity ({queue.capacity}).')
        logger.info(
            f'{request.user} tried to add participants when the queue was already full.')
        return redirect('queue:dashboard', queue_id)
    last_position = queue.participant_set.count()
    Participant.objects.create(
        position=last_position + 1,
        queue=queue)
    return redirect('manager:dashboard', queue_id)


@login_required
def notify_participant(request, queue_id, participant_id):
    participant = get_object_or_404(Participant, id=participant_id)
    if participant.user is None:
        messages.error(request, "There is no participant for this position.")
        return redirect('manager:dashboard', queue_id)
    queue = get_object_or_404(Queue, id=queue_id)
    message = f"Your turn for {queue.name} is ready! Please proceed to the counter."
    Notification.objects.create(
        queue=queue,
        participant=participant,
        message=message
    )
    time_taken = timezone.now() - participant.joined_at
    time_taken_minutes = int(time_taken.total_seconds() // 60)
    queue.update_estimated_wait_time_per_turn(time_taken_minutes)

    messages.success(request, f"You notified the participant {participant.user.username}.")
    return redirect('manager:dashboard', queue_id)


@login_required
def delete_queue(request, queue_id):
    try:
        queue = Queue.objects.get(pk=queue_id)
    except Queue.DoesNotExist:
        messages.error(request, f"Queue with ID {queue_id} does not exist.")
        logger.error(f"Queue id: {queue_id} does not exist.")
        return redirect('participant:index')
    if queue.created_by != request.user:
        messages.error(request, "You're not authorized to delete this queue.")
        logger.warning(
            f"Unauthorized queue delete attempt by user {request.user} "
            f"for queue: {queue.name} queue_id: {queue.id}.")
        return redirect('participant:index')
    try:
        queue.delete()
        messages.success(request,
                         f"Queue {queue.name} has been deleted successfully.")
        logger.info(
            f"{request.user} successfully deleted queue: {queue.name} id: {queue.id}.")
    except Exception as e:
        messages.error(request, f"Error deleting queue: {e}")
        logger.error(
            f"Failed to delete queue: {queue.name} id: {queue.id} "
            f"by user {request.user}: {e}")
    return redirect('manager:manage_queues')


@login_required
def delete_participant(request, participant_id):
    """Delete a participant from a specific queue if the requester is the queue creator or the participant themselves."""
    try:
        participant = Participant.objects.get(id=participant_id)
    except Participant.DoesNotExist:
        messages.error(request, f"Participant with ID {participant_id} does not exist.")
        logger.error(f"Participant id: {participant_id} does not exist.")
        return redirect('participant:index')

    queue = participant.queue

    if queue.created_by == request.user:
        action = 'completed'
        success_message = f"Participant with code {participant.queue_code} removed successfully."
        log_message = f"Participant with code {participant.queue_code} successfully deleted from queue {queue.id} by user {request.user}."

    elif participant.user == request.user:
        action = 'canceled'
        success_message = "You have successfully left the queue."
        log_message = f"User {request.user} canceled participation in queue {queue.id}."

    else:
        messages.error(request, "You are not authorized to delete participants from this queue.")
        logger.warning(
            f'Unauthorized delete attempt by user {request.user} '
            f'for participant {participant_id} in queue {queue.id}.')
        return redirect('participant:index')

    try:
        QueueHistory.objects.create(
            user=participant.user,
            queue=queue,
            queue_description=queue.description,
            action=action,
            joined_at=participant.joined_at
        )

        removed_position = participant.position
        participant.delete()
        remaining_participants = queue.participant_set.filter(position__gt=removed_position).order_by('position')
        for p in remaining_participants:
            p.position -= 1
            p.save()

        messages.success(request, success_message)
        logger.info(log_message)

    except Exception as e:
        messages.error(request, f"Error removing participant: {e}")
        logger.error(f"Failed to delete participant {participant_id} from queue {queue.id} by user {request.user}: {e}")

    return redirect('participant:index')


class ManageWaitlist(generic.TemplateView):
    template_name = 'manager/queue_waitlist.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queue_id = self.kwargs.get('queue_id')
        queue = get_object_or_404(Queue, id=queue_id)

        if queue.created_by != self.request.user:
            raise PermissionDenied("You do not have permission to manage this queue.")

        handler = ParticipantHandlerFactory.get_handler(queue.category)

        context['waiting_list'] = queue.participant_set.filter(state='waiting')
        context['serving_list'] = queue.participant_set.filter(state='serving')
        context['completed_list'] = queue.participant_set.filter(state='completed')

        context['queue'] = queue
        context['handler'] = handler
        return context


def serve_participant(request, participant_id):
    participant = get_object_or_404(Participant, id=participant_id)
    queue_category = participant.queue.category
    handler = ParticipantHandlerFactory.get_handler(queue_category)

    try:
        if participant.state != 'waiting':
            return JsonResponse({
                'error': f'{participant.name} cannot be served because they are currently in state: {participant.state}.'
            }, status=400)

        handler.assign_to_resource(participant)
        participant.start_service()
        participant.save()

        # Fetch updated lists
        waiting_list = Participant.objects.filter(state='waiting').values()  # Get all waiting participants as dictionaries
        serving_list = Participant.objects.filter(state='serving').values()  # Get all serving participants as dictionaries

        return JsonResponse({
            'waiting_list': list(waiting_list),
            'serving_list': list(serving_list)
        })

    except Exception as e:
        return JsonResponse({
            'error': f'Error: {str(e)}'
        }, status=500)


def complete_participant(request, participant_id):
    participant = get_object_or_404(Participant, id=participant_id)
    queue_category = participant.queue.category
    handler = ParticipantHandlerFactory.get_handler(queue_category)

    try:
        if participant.state != 'serving':
            return JsonResponse({
                'error': f'{participant.name} cannot be marked as completed because they are currently in state: {participant.state}.'
            }, status=400)


        handler.complete_service(participant)
        participant.complete_service()
        participant.save()

        serving_list = Participant.objects.filter(state='serving').values()
        completed_list = Participant.objects.filter(state='completed').values()

        return JsonResponse({
            'serving_list': list(serving_list),
            'completed_list': list(completed_list)
        })

    except Exception as e:
        return JsonResponse({
            'error': f'Error: {str(e)}'
        }, status=500)

def signup(request):
    """
    Register a new user.
    Handles the signup process, creating a new user if the provided data is valid.

    :param request: The HTTP request object containing user signup data.
    :returns: Redirects to the queue index page on successful signup.
    :raises ValueError: If form data is invalid, displays an error message in the signup form.
    """
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            raw_passwd = form.cleaned_data.get('password1')
            user = authenticate(username=username, password=raw_passwd)
            login(request, user)
            logger.info(f'New user signed up: {username}')
            return redirect('participant:index')
    else:
        form = UserCreationForm()
    return render(request, 'registration/signup.html', {'form': form})


logger = logging.getLogger('queue')


def get_client_ip(request):
    """Retrieve the client's IP address from the request."""
    return (
        x_forwarded_for.split(',')[0]
        if (x_forwarded_for := request.META.get('HTTP_X_FORWARDED_FOR'))
        else request.META.get('REMOTE_ADDR')
    )


@receiver(user_logged_in)
def user_login(request, user, **kwargs):
    """Log a message when a user logs in."""
    ip = get_client_ip(request)
    logger.info(f"User {user.username} logged in from {ip}")


@receiver(user_logged_out)
def user_logout(request, user, **kwargs):
    """Log a message when a user logs out."""
    ip = get_client_ip(request)
    logger.info(f"User {user.username} logged out from {ip}")


@receiver(user_login_failed)
def user_login_failed(credentials, request, **kwargs):
    """Log a message when a user login attempt fails."""
    ip = get_client_ip(request)
    logger.warning(f"Failed login attempt for user "
                   f"{credentials.get('username')} from {ip}")