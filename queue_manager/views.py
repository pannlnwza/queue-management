import logging
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
from django.db.models import Q

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
    template_name = 'queue_manager/index.html'
    context_object_name = 'queue_list'

    def get_queryset(self):
        """
        Get the list of queues for the authenticated user.
        :returns: A queryset of queues the user is participating in, or an empty queryset if not authenticated.
        """
        if self.request.user.is_authenticated:
            return Queue.objects.filter(participant__user=self.request.user,
                                        participant__status_user='active')
        return Queue.objects.none()

    def get_context_data(self, **kwargs):
        """
        Add additional context data to the template.

        :param kwargs: Additional keyword arguments passed to the method.
        :returns: The updated context dictionary with user's queue positions.
        """
        context = super().get_context_data(**kwargs)
        # Get the user's participant objects to include their positions
        if self.request.user.is_authenticated:
            user_participants = Participant.objects.filter(
                user=self.request.user,
                status_user='active'
            )
            queue_positions = {}
            active_queues = set()  # Track active queues for the user

            for participant in user_participants:
                position = Participant.objects.filter(
                    queue=participant.queue,
                    status_user='active',
                    joined_at__lte=participant.joined_at
                ).count()
                queue_positions[participant.queue.id] = position
                active_queues.add(participant.queue.id)  # Store active queue IDs

            context['queue_positions'] = queue_positions
            context['active_queues'] = active_queues
            context['active_participants'] = {participant.queue.id: participant.id for participant in user_participants}
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

    def form_invalid(self, form):
        messages.error(self.request, "You cannot join your own queue.")
        return self.render_to_response(self.get_context_data(form=form))


@login_required
def join_queue(request):
    """
    Add a user to a queue.

    Processes the joining of a queue based on the provided queue code.

    :param request: The HTTP request object containing the queue code.
    :returns: Redirects to the queue index page after processing.
    :raises Queue.DoesNotExist: If the queue code does not exist.
    """

    if request.method == 'POST':
        # Get the queue code from the submitted form and convert it to uppercase
        code = request.POST.get('queue_code', '').upper()
        logger.debug(
            f'User {request.user.username} attempted to join queue with code: {code}')
        try:
            # Attempt to retrieve the queue based on the provided code
            queue = Queue.objects.get(code=code)
            participant = queue.participant_set.filter(user=request.user).first()
            logger.info(
                f'Queue found: {queue.name} for user {request.user.username}')

            # Check queue conditions
            if queue.is_closed:
                messages.error(request, "The queue is closed.")
                logger.info(
                    f'User {request.user.username} attempted to join queue {queue.name} that has been closed.')
                return redirect('queue:index')

            if request.user == queue.created_by:
                messages.error(request, "You cannot join your own queue.")
                logger.warning(f"Queue creator {request.user.username} attempts to join his own queue {queue.name}.")
                return redirect('queue:index')

            # Handle participant cases
            if not participant:
                # New participant - never joined before
                last_position = queue.participant_set.count()
                new_position = last_position + 1
                Participant.objects.create(
                    user=request.user,
                    queue=queue,
                    position=new_position
                )
                messages.success(request, "You have successfully joined the queue.")
                logger.info(
                    f'User {request.user.username} joined queue {queue.name} at position {new_position}.')

            elif participant.status_user in ['canceled', 'completed']:
                # Existing participant with canceled/completed status - update their record
                last_position = queue.participant_set.count()
                new_position = last_position + 1

                participant.position = new_position
                participant.joined_at = timezone.now()
                participant.status_user = 'active'
                participant.save()

                messages.success(request, "You have successfully rejoined the queue.")
                logger.info(f"User {request.user.username} rejoined queue {queue.name} at position {new_position}.")

            else:
                # Active participant trying to join again
                messages.info(request, "You are already in this queue.")
                logger.warning(
                    f'User {request.user.username} attempted to join queue {queue.name} again.')

        except Queue.DoesNotExist:
            messages.error(request, "Invalid queue code.")
            logger.error(
                f'User {request.user.username} attempted to join with an invalid queue code: {code}')
        except Exception as e:
            messages.error(request, "An error occurred while joining the queue. Please try again.")
            logger.error(
                f'Error occurred while user {request.user.username} was joining queue {code}: {str(e)}')

    # Redirect to the index page after processing the request
    return redirect('queue:index')


class QueueListView(generic.ListView):
    """
    List all queues.

    Displays all available queues to the user.

    :param model: The model to use for retrieving the queues.
    :param template_name: The name of the template to render.
    :param context_object_name: The name of the context variable to hold the list of queues.
    """
    model = Queue
    template_name = 'queue_manager/all_queues.html'
    context_object_name = 'queues'

    def get_queryset(self):
        """
        Retrieve all queues.

        :returns: A queryset of all queues available in the system.
        """
        return Queue.objects.all()


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
            messages.error(self.request, "You do not have permission to edit this queue.")
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
                self.object.edit(name=name, description=description, is_closed=is_closed)
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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add count of active participants
        context['active_count'] = self.object.participant_set.filter(
            status_user='active'
        ).count()
        return context

    def get(self, request, *args, **kwargs):
        try:
            queue = get_object_or_404(Queue, pk=kwargs.get('pk'))
        except Http404:
            logger.warning(f'User {request.user.username} attempted '
                           f'to access a non-existent queue with ID {kwargs.get("pk")}.')
            messages.error(request, 'Queue does not exist.')
            return redirect('queue:index')
        if queue.created_by == request.user:
            logger.info(f'User {request.user.username} accessed the '
                        f'dashboard for queue "{queue.name}" with ID {queue.pk}.')
            return super().get(request, *args, **kwargs)
        logger.warning(f'User {request.user.username} attempted to access the dashboard '
                       f'for queue "{queue.name}" (ID: {queue.pk}) without ownership.')
        messages.error(request, 'You are not the owner of this queue.')
        return redirect('queue:index')


class QueueHistoryView(LoginRequiredMixin, generic.ListView):
    template_name = 'queue_manager/queue_history.html'
    context_object_name = 'history_queues'

    def get_queryset(self):
        user = self.request.user
        created_queues = Queue.objects.filter(created_by=user)
        joined_queues = Queue.objects.filter(participant__user=user)

        return created_queues.union(joined_queues).order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        context['created_queues'] = Queue.objects.filter(created_by=user)
        context['joined_queues'] = Queue.objects.filter(
            Q(participant__user=user) & ~Q(participant__status_user='active')
        ).annotate(
            participant_status=models.F('participant__status_user'),
            participant_joined_at=models.F('participant__joined_at')
        ).order_by(
            '-participant__joined_at'
        )

        return context


def get_client_ip(request):
    """Retrieve the client's IP address from the request."""
    return (
        x_forwarded_for.split(',')[0]
        if (x_forwarded_for := request.META.get('HTTP_X_FORWARDED_FOR'))
        else request.META.get('REMOTE_ADDR')
    )


@login_required
def delete_participant(request, participant_id):
    """Delete a participant from a specific queue if the requester is the queue creator or the participant."""
    try:
        # Fetch the participant object by ID
        participant = Participant.objects.get(id=participant_id)
    except Participant.DoesNotExist:
        # Handle the case where the participant does not exist
        messages.error(request, f"Participant with ID {participant_id} does not exist.")
        logger.error(f"Participant with ID {participant_id} does not exist.")
        return redirect('queue:index')

    queue = participant.queue

    # Case 1: The participant is canceling their own participation
    if participant.user == request.user:
        participant.status_user = 'canceled'
        participant.save()
        messages.success(request, "You have successfully left the queue.")
        logger.info(f"User {request.user} canceled participation in queue {queue.id}.")
        return redirect('queue:index')

    # Case 2: Queue creator is managing the queue and marking the participant as completed
    if queue.created_by == request.user:
        try:
            participant.status_user = 'completed'
            participant.save()

            messages.success(request, f"Participant {participant.user.username} marked as 'completed' successfully.")
            logger.info(
                f"Participant {participant.user.username} marked as 'completed' by queue creator {request.user} in queue {queue.id}.")
        except Exception as e:
            messages.error(request, f"Error updating participant status: {e}")
            logger.error(f"Failed to update participant {participant_id} in queue {queue.id} by user {request.user}: {e}")
    else:
        # Unauthorized attempt by a non-creator trying to manage a queue
        messages.error(request, "You are not authorized to manage participants in this queue.")
        logger.warning(
            f"Unauthorized delete attempt by user {request.user} for participant {participant_id} in queue {queue.id}.")

    return redirect('queue:dashboard', pk=queue.id)


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

