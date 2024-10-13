from django.shortcuts import render, redirect
from django.views import generic
from queue_manager.models import *
from django.contrib.auth import login, authenticate
from django.contrib.auth.forms import UserCreationForm
from .forms import QueueForm
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages


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
            # get named fields from the form data
            username = form.cleaned_data.get('username')
            # password input field is named 'password1'
            raw_passwd = form.cleaned_data.get('password1')
            user = authenticate(username=username, password=raw_passwd)
            login(request, user)
        return redirect('queue:index')
        # what if form is not valid?
        # we should display a message in signup.html
    else:
        # create a user form and display it the signup page
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

    def post(self, request, *args, **kwargs):
        """
        Handle form submission for joining a queue.

        Adds the authenticated user to the specified queue based on the provided queue code.

        :param request: The HTTP request object containing the queue code.
        :returns: Renders the index page after processing the request.
        :raises Queue.DoesNotExist: If the queue code does not exist.
        """
        # Handle form submission for joining a queue
        if request.method == "POST":
            queue_code = request.POST.get('queue_code')
            try:
                queue = Queue.objects.get(code=queue_code)
                # Check if the user is already a participant in the queue
                if not queue.participant_set.filter(user=request.user).exists():
                    # Add the user as a participant
                    position = queue.participant_set.count() + 1
                    Participant.objects.create(user=request.user, queue=queue, position=position)
                    # Optionally, update queue's estimated wait time
                    queue.update_estimated_wait_time(average_time_per_participant=5)
                    return self.get(request, *args, **kwargs)  # Re-render the page after joining
                else:
                    # Optionally handle the case where the user is already in the queue
                    pass
            except Queue.DoesNotExist:
                # Optionally handle the case where the queue code is invalid
                pass
        return self.get(request, *args, **kwargs)


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


def join_queue(request):
    """
    Add a user to a queue.

    Processes the joining of a queue based on the provided queue code.

    :param request: The HTTP request object containing the queue code.
    :returns: Redirects to the queue index page after processing.
    :raises Queue.DoesNotExist: If the queue code does not exist.
    """
    if request.method == 'POST':
        code = request.POST.get('queue_code', '').upper()
        try:
            # Get the queue based on the provided code
            queue = Queue.objects.get(code=code)
            # Check if the user is already in the queue
            if not queue.participant_set.filter(user=request.user).exists():
                # Get the position for the new participant (last position + 1)
                last_position = queue.participant_set.count()
                new_position = last_position + 1
                # Add the user as a new participant in the queue
                Participant.objects.create(
                    user=request.user,
                    queue=queue,
                    position=new_position
                )
                # Success message for successfully joining the queue
                messages.success(request,
                                 "You have successfully joined the queue.")
            else:
                # If the user is already in the queue, show an info message
                messages.info(request, "You are already in this queue.")
        except Queue.DoesNotExist:
            # Handle the case where the queue code does not exist
            messages.error(request, "Invalid queue code.")
    # Redirect to the queue index page after processing
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
        # Optionally, you can filter or sort the queues, or return all queues.
        return Queue.objects.all()
