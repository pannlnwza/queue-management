import json
import logging
from datetime import timedelta
from django.contrib import messages
from django.contrib.auth import authenticate, login, user_logged_in, user_logged_out, user_login_failed
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.dispatch import receiver
from django.http import Http404, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.views import generic
from django.views.decorators.http import require_http_methods

from manager.forms import QueueForm
from participant.utils.participant_handler import ParticipantHandlerFactory
from participant.models import Participant, Notification
from manager.models import Queue, UserProfile
from manager.utils.queue_handler import QueueHandlerFactory


logger = logging.getLogger('queue')


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
    success_url = reverse_lazy('manager:your-queue')

    def form_valid(self, form):
        """
        Set the creator of the queue to the current user.

        :param form: The form containing the queue data.
        :returns: The response after the form has been successfully validated and saved.
        """
        queue_category = form.cleaned_data['category']
        handler = QueueHandlerFactory.get_handler(queue_category)

        queue_data = form.cleaned_data.copy()
        queue_data['created_by'] = self.request.user

        queue = handler.create_queue(queue_data)

        queue.authorized_user.add(self.request.user)

        return redirect(self.success_url)


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


@require_http_methods(["DELETE"])
@login_required
def delete_queue(request, queue_id):
    try:
        queue = Queue.objects.get(pk=queue_id)
    except Queue.DoesNotExist:
        return JsonResponse({'error': 'Queue not found.'}, status=404)

    if request.user not in queue.authorized_user.all():
        return JsonResponse({'error': 'Unauthorized.'}, status=403)

    try:
        queue.delete()
        return JsonResponse({'success': 'Queue deleted successfully.'}, status=200)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_http_methods(["DELETE"])
def delete_participant(request, participant_id):
    participant = get_object_or_404(Participant, id=participant_id)
    logger.info(f"Deleting participant {participant_id} from queue {participant.queue.id}")

    if request.user not in participant.queue.authorized_user.all():
        return JsonResponse({'error': 'Unauthorized.'}, status=403)

    if participant.state == 'waiting':
        queue = participant.queue
        waiting_participants = Participant.objects.filter(queue=queue, state='waiting').order_by('position')
        participant.delete()
        logger.info(f"Participant {participant_id} is deleted.")

        for idx, p in enumerate(waiting_participants):
            if p.position > participant.position:
                p.position = idx + 1
                p.save()
        return JsonResponse({'message': 'Participant is deleted and positions are updated.'})
    participant.delete()
    return JsonResponse({'message': 'Participant deleted.'})


@require_http_methods(["POST"])
def edit_participant(request, participant_id):
    participant = get_object_or_404(Participant, id=participant_id)
    queue = participant.queue
    if request.user not in queue.authorized_user.all():
        logger.error(f"Unauthorized edit attempt on queue {queue.id} by user {request.user.id}")
        return JsonResponse({'error': 'Unauthorized.'}, status=403)

    handler = ParticipantHandlerFactory.get_handler(queue.category)
    queue = handler.get_queue_object(queue.id)
    participant = handler.get_participant_set(queue.id).get(id=participant_id)

    # Parse the JSON payload
    data = json.loads(request.body)
    handler.update_participant(participant, data)

    logger.info(f"Participant {participant_id} in queue {queue.id} updated successfully.")
    return JsonResponse({
        'status': 'success',
        'message': 'Participant information updated successfully',
    })


class ManageWaitlist(LoginRequiredMixin, generic.TemplateView):
    def get_template_names(self):
        queue_id = self.kwargs.get('queue_id')
        queue = get_object_or_404(Queue, id=queue_id)
        if self.request.user not in queue.authorized_user.all():
            logger.error(f"Unauthorized edit attempt on queue {queue.id} by user {self.request.user.id}")
            return JsonResponse({'error': 'Unauthorized.'}, status=403)

        handler = ParticipantHandlerFactory.get_handler(queue.category)
        return [handler.get_template_name()]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queue_id = self.kwargs.get('queue_id')
        queue = get_object_or_404(Queue, id=queue_id)

        if queue.created_by != self.request.user:
            raise PermissionDenied("You do not have permission to manage this queue.")
        handler = ParticipantHandlerFactory.get_handler(queue.category)
        queue = handler.get_queue_object(queue_id)

        context['waiting_list'] = handler.get_participant_set(queue_id).filter(state='waiting')
        context['serving_list'] = handler.get_participant_set(queue_id).filter(state='serving')
        context['completed_list'] = handler.get_participant_set(queue_id).filter(state='completed')
        context['queue'] = queue
        more_context = handler.add_context_attributes(queue)
        if more_context:
            context.update({key: value for item in handler.add_context_attributes(queue) for key, value in item.items()})
        return context

@login_required
def serve_participant(request, participant_id):
    participant = get_object_or_404(Participant, id=participant_id)
    queue_category = participant.queue.category
    handler = ParticipantHandlerFactory.get_handler(queue_category)

    try:
        if participant.state != 'waiting':
            logger.warning(f"Cannot serve participant {participant_id} because they are in state: {participant.state}")
            return JsonResponse({
                'error': f'{participant.name} cannot be served because they are currently in state: {participant.state}.'
            }, status=400)

        participant.queue.update_estimated_wait_time_per_turn(participant.get_wait_time())
        handler.assign_to_resource(participant)
        participant.start_service()
        participant.save()
        logger.info(f"Participant {participant_id} started service in queue {participant.queue.id}.")

        waiting_list = Participant.objects.filter(state='waiting').values()
        serving_list = Participant.objects.filter(state='serving').values()

        return JsonResponse({
            'waiting_list': list(waiting_list),
            'serving_list': list(serving_list)
        })

    except Exception as e:
        logger.error(f"Error serving participant {participant_id}: {str(e)}")
        return JsonResponse({
            'error': f'Error: {str(e)}'
        }, status=500)


@login_required
def complete_participant(request, participant_id):
    participant = get_object_or_404(Participant, id=participant_id)
    queue = participant.queue
    handler = ParticipantHandlerFactory.get_handler(queue.category)
    participant = handler.get_participant_set(queue.id).filter(id=participant_id).first()

    if request.user not in queue.authorized_user.all():
        logger.error(f"Unauthorized edit attempt on queue {queue.id} by user {request.user.id}")
        return JsonResponse({'error': 'Unauthorized.'}, status=403)

    try:
        if participant.state != 'serving':
            logger.warning(
                f"Cannot complete participant {participant_id} because they are in state: {participant.state}")
            return JsonResponse({
                'error': f'{participant.name} cannot be marked as completed because they are currently in state: {participant.state}.'
            }, status=400)


        handler.complete_service(participant)
        participant.save()
        logger.info(f"Participant {participant_id} completed service in queue {queue.id}.")

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


class ParticipantListView(LoginRequiredMixin, generic.TemplateView):
    template_name = 'manager/participant_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queue_id = self.kwargs.get('queue_id')
        queue = get_object_or_404(Queue, id=queue_id)
        handler = ParticipantHandlerFactory.get_handler(queue.category)

        time_filter_option = self.request.GET.get('time_filter', 'all_time')
        state_filter_option = self.request.GET.get('state_filter', 'any_state')

        time_filter_options_display = {
            'all_time': 'All time',
            'today': 'Today',
            'this_week': 'This week',
            'this_month': 'This month',
            'this_year': 'This year',
        }

        state_filter_options_display = {
            'any_state': 'Any state',
            'waiting': 'Waiting',
            'serving': 'Serving',
            'completed': 'Completed',
        }

        start_date = self.get_start_date(time_filter_option)
        participant_set = handler.get_participant_set(queue_id)

        if start_date:
            participant_set = participant_set.filter(joined_at__gte=start_date)

        if state_filter_option != 'any_state':
            participant_set = participant_set.filter(state=state_filter_option)

        context['queue'] = handler.get_queue_object(queue_id)
        context['participant_set'] = participant_set
        context['time_filter_option'] = time_filter_option
        context['time_filter_option_display'] = time_filter_options_display.get(time_filter_option, 'All time')
        context['state_filter_option'] = state_filter_option
        context['state_filter_option_display'] = state_filter_options_display.get(state_filter_option, 'Any state')
        return context

    def get_start_date(self, time_filter_option):
        """Returns the start date based on the time filter option."""
        now = timezone.now()
        if time_filter_option == 'today':
            return now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif time_filter_option == 'this_week':
            return now - timedelta(days=now.weekday())  # monday of the current week
        elif time_filter_option == 'this_month':
            return now.replace(day=1)
        elif time_filter_option == 'this_year':
            return now.replace(month=1, day=1)
        return None


class YourQueueView(LoginRequiredMixin, generic.TemplateView):
    template_name = 'manager/your_queue.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        authorized_queues = Queue.objects.filter(authorized_user=user)
        context['authorized_queues'] = authorized_queues
        return context


class StatisticsView(LoginRequiredMixin, generic.TemplateView):
    template_name = 'manager/statistics.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queue_id = self.kwargs.get('queue_id')
        queue = get_object_or_404(Queue, id=queue_id)
        handler = ParticipantHandlerFactory.get_handler(queue.category)
        queue = handler.get_queue_object(queue_id)
        participant_set = handler.get_participant_set(queue_id)

        context['queue'] = queue
        context['participant_set'] = participant_set
        return context


def create_or_update_profile(user, profile_image=None):
    """
    Helper function to create or update user profile
    """
    try:
        profile, created = UserProfile.objects.get_or_create(user=user)
        if profile_image:
            profile.image = profile_image
            profile.save()
        return profile

    except Exception as e:
        logger.error(f'Error creating/updating profile for user {user.username}: {str(e)}')
        return None


def signup(request):
    """
    Register a new user.
    Handles the signup process, creating a new user and profile if the provided data is valid.
    """
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            username = form.cleaned_data.get('username')
            raw_passwd = form.cleaned_data.get('password1')

            profile = create_or_update_profile(user)
            if not profile:
                messages.error(request, 'Error creating user profile. Please contact support.')

            user = authenticate(username=username, password=raw_passwd)
            if user is not None:
                login(request, user)
                logger.info(f'New user signed up with profile: {username}')
                return redirect('participant:home')
            else:
                logger.error(f'Failed to authenticate user after signup: {username}')
                messages.error(request, 'Error during signup process. Please try again.')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    logger.error(f'Error signup: {error}')

    else:
        form = UserCreationForm()

    return render(request, 'account/signup.html', {'form': form})


def login_view(request):
    """
    Handle user login and update profile if needed
    """
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)

            if hasattr(user, 'socialaccount_set') and user.socialaccount_set.exists():
                social_account = user.socialaccount_set.first()
                if social_account.provider == 'google':
                    extra_data = social_account.extra_data
                    profile_image_url = extra_data.get('picture')
                    if profile_image_url:
                        profile = create_or_update_profile(user)
                        if profile:
                            profile.google_picture = profile_image_url
                            profile.save()
            else:
                create_or_update_profile(user)

            return redirect('manager:your-queue')
        else:
            messages.error(request, 'Invalid username or password.')

    return render(request, 'account/login.html')


@login_required
def edit_profile(request, queue_id):
    if request.method == 'POST':
        # Get the current user
        user = request.user
        # Update user profile fields from POST data
        user.username = request.POST.get('username')
        user.email = request.POST.get('email')
        user.first_name = request.POST.get('first_name')
        user.last_name = request.POST.get('last_name')

        # Save the changes
        user.save()
        messages.success(request, 'Profile updated successfully!')

        # Redirect with the queue_id
        return redirect('edit_profile', queue_id=queue_id)

    # Render the profile edit page, pass queue_id in the context
    return render(request, 'manager/edit_profile.html', {'queue_id': queue_id})


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