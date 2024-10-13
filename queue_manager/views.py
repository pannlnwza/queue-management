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

logger = logging.getLogger('queue')


def signup(request):
    """Register a new user."""
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            raw_passwd = form.cleaned_data.get('password1')
            user = authenticate(username=username, password=raw_passwd)
            login(request, user)
            return redirect('queue:index')
    else:
        form = UserCreationForm()
    return render(request, 'registration/signup.html', {'form': form})


class IndexView(generic.ListView):
    template_name = 'queue_manager/index.html'
    context_object_name = 'queue_list'

    def get_queryset(self):
        if self.request.user.is_authenticated:
            return Queue.objects.filter(participant__user=self.request.user)
        else:
            return Queue.objects.none()

    def get_context_data(self, **kwargs):
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
    model = Queue
    form_class = QueueForm
    template_name = 'queue_manager/create_q.html'
    success_url = reverse_lazy('queue:index')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


@login_required
def join_queue(request):
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
    model = Queue
    template_name = 'queue_manager/all_queues.html'
    context_object_name = 'queues'

    def get_queryset(self):
        return Queue.objects.all()
