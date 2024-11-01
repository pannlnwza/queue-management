import logging

from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404, Http404
from django.views import generic
from queue_manager.models import *
from django.contrib.auth import login, authenticate
from django.contrib.auth.forms import UserCreationForm
from .forms import QueueForm
from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.signals import user_logged_in, user_logged_out, \
    user_login_failed
from django.dispatch import receiver
from datetime import datetime, timedelta

logger = logging.getLogger('queue')


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
            return redirect('queue:index')
    else:
        form = UserCreationForm()
    return render(request, 'registration/signup.html', {'form': form})


class IndexView(generic.ListView):
    """
    Display the index page for the user's queues.
    Lists the queues the authenticated user is participating in.

    :param template_name: The name of the template to render.
    :param context_object_name: The name of the context variable to hold the queue list.
    """
    template_name = 'queue_manager/home.html'
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
    template_name = 'queue_manager/create_q.html'
    success_url = reverse_lazy('queue:index')

    def form_valid(self, form):
        """
        Set the creator of the queue to the current user.

        :param form: The form containing the queue data.
        :returns: The response after the form has been successfully validated and saved.
        """
        form.instance.created_by = self.request.user
        return super().form_valid(form)


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
            return redirect('queue:index')
    return redirect('queue:index')


class BrowseQueueView(generic.ListView):
    model = Queue
    template_name = 'queue_manager/browse_queue.html'


class BaseQueueView(generic.ListView):
    model = Queue
    template_name = 'queue_manager/list_queues.html'
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
    template_name = 'queue_manager/manage_queues.html'
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
    template_name = 'queue_manager/edit_queue.html'

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
            return redirect('queue:manage_queues')
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        """redirect user back to manage queues page, if the edit was saved successfully."""
        return reverse('queue:manage_queues')

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
        return redirect('queue:manage_queues')


class QueueDashboardView(generic.DetailView):
    model = Queue
    template_name = 'queue_manager/general_dashboard.html'
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


class QueueHistoryView(LoginRequiredMixin, generic.ListView):
    template_name = 'queue_manager/queue_history.html'
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
    return redirect('queue:dashboard', queue_id)


@login_required
def delete_participant(request, participant_id):
    """Delete a participant from a specific queue if the requester is the queue creator or the participant themselves."""
    try:
        participant = Participant.objects.get(id=participant_id)
    except Participant.DoesNotExist:
        messages.error(request, f"Participant with ID {participant_id} does not exist.")
        logger.error(f"Participant id: {participant_id} does not exist.")
        return redirect('queue:index')

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
        return redirect('queue:index')

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

    return redirect('queue:index')


@login_required
def delete_queue(request, queue_id):
    try:
        queue = Queue.objects.get(pk=queue_id)
    except Queue.DoesNotExist:
        messages.error(request, f"Queue with ID {queue_id} does not exist.")
        logger.error(f"Queue id: {queue_id} does not exist.")
        return redirect('queue:index')
    if queue.created_by != request.user:
        messages.error(request, "You're not authorized to delete this queue.")
        logger.warning(
            f"Unauthorized queue delete attempt by user {request.user} "
            f"for queue: {queue.name} queue_id: {queue.id}.")
        return redirect('queue:index')
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
    return redirect('queue:manage_queues')


@login_required
def notify_participant(request, queue_id, participant_id):
    participant = get_object_or_404(Participant, id=participant_id)
    if participant.user is None:
        messages.error(request, "There is no participant for this position.")
        return redirect('queue:dashboard', queue_id)
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
    return redirect('queue:dashboard', queue_id)

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
