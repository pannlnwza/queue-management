import logging
from django.shortcuts import render, redirect
from django.views import generic
from queue_manager.models import *
from django.contrib.auth import login, authenticate
from django.contrib.auth.forms import UserCreationForm
from .forms import QueueForm
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

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
            return Queue.objects.filter(participant__user=self.request.user)
        else:
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
            user_participants = Participant.objects.filter(user=self.request.user)
            # Create a dictionary to hold queue positions
            queue_positions = {
                participant.queue.id: participant.position for participant in
                user_participants
            }
            context['queue_positions'] = queue_positions
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
        logger.debug(f'User {request.user.username} attempted to join queue with code: {code}')
        try:
            # Attempt to retrieve the queue based on the provided code
            queue = Queue.objects.get(code=code)
            logger.info(f'Queue found: {queue.name} for user {request.user.username}')
            # Check if the user is already a participant in the queue
            if not queue.participant_set.filter(user=request.user).exists():
                last_position = queue.participant_set.count()
                new_position = last_position + 1
                # Create a new Participant entry
                Participant.objects.create(
                    user=request.user,
                    queue=queue,
                    position=new_position
                )
                messages.success(request, "You have successfully joined the queue.")
                logger.info(f'User {request.user.username} joined queue {queue.name} at position {new_position}.')
            else:
                messages.info(request, "You are already in this queue.")
                logger.warning(f'User {request.user.username} attempted to join queue {queue.name} again.')
        except Queue.DoesNotExist:
            messages.error(request, "Invalid queue code.")
            logger.error(f'User {request.user.username} attempted to join with an invalid queue code: {code}')
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


class QueueDashboardView(generic.DetailView):
    model = Queue
    template_name = 'queue_manager/general_dashboard.html'
    context_object_name = 'queue'


def get_client_ip(request):
    """Retrieve the client's IP address from the request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


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
