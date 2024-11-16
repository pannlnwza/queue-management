import json
import logging
from datetime import timedelta, datetime
from lib2to3.fixes.fix_input import context
from os import close

from django.contrib import messages
from django.contrib.auth import authenticate, login, user_logged_in, user_logged_out, user_login_failed
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.contrib.auth.models import User
from django.dispatch import receiver
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import generic
from django.views.decorators.http import require_http_methods

from manager.forms import QueueForm
from manager.models import Queue, Resource
from manager.forms import QueueForm, CustomUserCreationForm, EditProfileForm
from participant.models import Participant, Notification
from manager.models import Queue, UserProfile
from manager.utils.queue_handler import QueueHandlerFactory
from manager.models import Queue
from manager.utils.category_handler import CategoryHandlerFactory


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
        handler = CategoryHandlerFactory.get_handler(queue_category)

        queue_data = form.cleaned_data.copy()
        queue_data['created_by'] = self.request.user

        queue = handler.create_queue(queue_data)

        queue.authorized_user.add(self.request.user)

        return redirect(self.success_url)


@login_required
def add_participant_slot(request, queue_id):
    """Staff adds a participant to the queue and generates a queue code."""
    queue = get_object_or_404(Queue, id=queue_id)
    last_position = queue.participant_set.count()
    Participant.objects.create(
        position=last_position + 1,
        queue=queue)
    return redirect('manager:dashboard', queue_id)


@require_http_methods(["POST"])
@login_required
def notify_participant(request, participant_id):
    participant = get_object_or_404(Participant, id=participant_id)
    queue = participant.queue
    message = request.POST.get('message', '')
    Notification.objects.create(queue=queue, participant=participant, message=message)
    participant.is_notified = True
    participant.save()
    return JsonResponse({'status': 'success', 'message': 'Notification sent successfully!'})


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

    queue = participant.queue
    participant.delete()
    logger.info(f"Participant {participant_id} is deleted.")

    waiting_participants = Participant.objects.filter(queue=queue, state='waiting').order_by('position')
    for idx, p in enumerate(waiting_participants):
        p.position = idx + 1
        p.save()
    return JsonResponse({'message': 'Participant deleted and positions updated.'})


@require_http_methods(["POST"])
def edit_participant(request, participant_id):
    participant = get_object_or_404(Participant, id=participant_id)
    if request.method == "POST":
        data = {
            'name': request.POST.get('name'),
            'phone': request.POST.get('phone'),
            'email': request.POST.get('email'),
            'notes': request.POST.get('notes'),
            'resource': request.POST.get('resource'),
            'special_1': request.POST.get('special_1'),
            'special_2': request.POST.get('special_2'),
            'party_size': request.POST.get('party_size'),
            'state': request.POST.get('state')
        }
        handler = CategoryHandlerFactory.get_handler(participant.queue.category)
        participant = handler.get_participant_set(participant.queue.id).get(id=participant_id)
        handler.update_participant(participant, data)
        return redirect('manager:participant_list', participant.queue.id)


@require_http_methods(["POST"])
@login_required
def add_participant(request, queue_id):
    name = request.POST.get('name')
    phone = request.POST.get('phone')
    email = request.POST.get('email')
    note = request.POST.get('note', "")
    special_1 = request.POST.get('special_1')
    special_2 = request.POST.get('special_2')
    party_size = request.POST.get('party_size')

    queue = get_object_or_404(Queue, id=queue_id)
    handler = CategoryHandlerFactory.get_handler(queue.category)
    queue = handler.get_queue_object(queue_id)
    data = {
        'name': name,
        'phone': phone,
        'email': email,
        'note': note,
        'queue': queue,
        'special_1': special_1,
        'special_2': special_2,
        'party_size': party_size
    }
    handler.create_participant(data)
    return redirect('manager:participant_list', queue_id)


class ManageWaitlist(LoginRequiredMixin, generic.TemplateView):
    template_name = 'manager/manage_queue/manage_unique_category.html'

    def get_template_names(self):
        """Return the appropriate template based on the queue category."""
        queue_id = self.kwargs.get('queue_id')
        queue = get_object_or_404(Queue, id=queue_id)
        handler = CategoryHandlerFactory.get_handler(queue.category)
        queue = handler.get_queue_object(queue_id)

        if queue.category == 'general':
            return ['manager/manage_queue/manage_general.html']
        return [self.template_name]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queue_id = self.kwargs.get('queue_id')
        queue = get_object_or_404(Queue, id=queue_id)
        handler = CategoryHandlerFactory.get_handler(queue.category)
        queue = handler.get_queue_object(queue_id)

        if self.request.user not in queue.authorized_user.all():
            logger.error(f"Unauthorized edit attempt on queue {queue.id} by user {self.request.user.id}")
            return JsonResponse({'error': 'Unauthorized.'}, status=403)

        search_query = self.request.GET.get('search', '').strip()
        participant_set = handler.get_participant_set(queue_id)
        if search_query:
            participant_set = participant_set.filter(name__icontains=search_query)

        context['waiting_list'] = participant_set.filter(state='waiting')
        context['serving_list'] = participant_set.filter(state='serving')
        context['completed_list'] = participant_set.filter(state='completed')
        context['queue'] = queue
        context['resources'] = queue.resource_set.all()
        context['available_resource'] = queue.get_resources_by_status('available')
        context['busy_resource'] = queue.get_resources_by_status('busy')
        context['unavailable_resource'] = queue.get_resources_by_status('unavailable')

        category_context = handler.add_context_attributes(queue)
        if category_context:
            context.update(category_context)
        return context


@login_required
def serve_participant(request, participant_id):
    participant = get_object_or_404(Participant, id=participant_id)
    queue_id = participant.queue.id
    handler = CategoryHandlerFactory.get_handler(participant.queue.category)
    participant_set = handler.get_participant_set(queue_id)
    participant = get_object_or_404(participant_set, id=participant_id)

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
    handler = CategoryHandlerFactory.get_handler(queue.category)
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
        handler = CategoryHandlerFactory.get_handler(queue.category)
        queue = handler.get_queue_object(queue_id)

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
        context['participant_state'] = Participant.PARTICIPANT_STATE
        context['resources'] = queue.resources.all()
        context['time_filter_option'] = time_filter_option
        context['time_filter_option_display'] = time_filter_options_display.get(time_filter_option, 'All time')
        context['state_filter_option'] = state_filter_option
        context['state_filter_option_display'] = state_filter_options_display.get(state_filter_option, 'Any state')
        category_context = handler.add_context_attributes(queue)
        if category_context:
            context.update(category_context)
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


class WaitingFull(LoginRequiredMixin, generic.TemplateView):
    template_name = 'manager/manage_queue/waiting_full.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queue_id = self.kwargs.get('queue_id')
        queue = get_object_or_404(Queue, id=queue_id)
        handler = CategoryHandlerFactory.get_handler(queue.category)
        queue = handler.get_queue_object(queue_id)
        context['queue'] = queue

        return context


class YourQueueView(LoginRequiredMixin, generic.TemplateView):
    template_name = 'manager/your_queue.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        authorized_queues = Queue.objects.filter(created_by=user)
        context['authorized_queues'] = authorized_queues
        return context


class StatisticsView(LoginRequiredMixin, generic.TemplateView):
    template_name = 'manager/statistics.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queue_id = self.kwargs.get('queue_id')
        queue = get_object_or_404(Queue, id=queue_id)
        handler = CategoryHandlerFactory.get_handler(queue.category)
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


class QueueSettingsView(LoginRequiredMixin, generic.TemplateView):
    template_name = 'manager/settings/settings.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queue_id = self.kwargs.get('queue_id')
        queue = get_object_or_404(Queue, id=queue_id)
        handler = CategoryHandlerFactory.get_handler(queue.category)
        queue = handler.get_queue_object(queue_id)
        participant_set = handler.get_participant_set(queue_id)
        resources = Resource.objects.filter(queue=queue)
        context['queue'] = queue
        context['resources'] = resources
        context['participant_set'] = participant_set
        category_context = handler.add_resource_attributes(queue)
        if category_context:
            context.update(category_context)
        return context


class ResourceSettings(LoginRequiredMixin, generic.TemplateView):
    template_name = 'manager/settings/resource_settings.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queue_id = self.kwargs.get('queue_id')
        queue = get_object_or_404(Queue, id=queue_id)
        handler = CategoryHandlerFactory.get_handler(queue.category)
        queue = handler.get_queue_object(queue_id)
        resources = Resource.objects.filter(queue=queue)
        participant_set = handler.get_participant_set(queue_id)
        context['participant_set'] = participant_set
        context['resource_status'] = Resource.RESOURCE_STATUS
        context['queue'] = queue
        context['resources'] = resources
        category_context = handler.add_resource_attributes(queue)
        if category_context:
            context.update(category_context)
        return context


@login_required
@require_http_methods(["POST"])
def edit_resource(request, resource_id):
    resource = get_object_or_404(Resource, id=resource_id)
    handler = CategoryHandlerFactory.get_handler(resource.queue.category)
    data = {
        'name': request.POST.get('name'),
        'special': request.POST.get('special'),
        'assigned_to': request.POST.get('assigned_to'),
        'status': request.POST.get('status'),
    }
    handler.edit_resource(resource, data)
    return redirect('manager:resources', resource.queue.id)


@login_required
@require_http_methods(["POST"])
def add_resource(request, queue_id):
    queue = get_object_or_404(Queue, id=queue_id)
    handler = CategoryHandlerFactory.get_handler(queue.category)
    queue = handler.get_queue_object(queue_id)
    data = {
        'name': request.POST.get('name'),
        'special': request.POST.get('special'),
        'status': request.POST.get('status'),
        'queue': queue,
    }
    handler.add_resource(data)
    return redirect('manager:resources', queue_id)


@login_required
@require_http_methods(["DELETE"])
def delete_resource(request, resource_id):
    resource = get_object_or_404(Resource, id=resource_id)
    logger.info(f"Deleting resource {resource_id} from queue {resource.queue.id}")

    if request.user != resource.queue.created_by:
        return JsonResponse({'error': 'Unauthorized.'}, status=403)
    resource.delete()
    logger.info(f"Resource {resource_id} is deleted.")
    return JsonResponse({'message': 'Resource deleted successfully.'})


def edit_queue(request, queue_id):
    queue = get_object_or_404(Queue, id=queue_id)
    handler = CategoryHandlerFactory.get_handler(queue.category)
    queue = handler.get_queue_object(queue_id)
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')
        status = request.POST.get('is_closed')
        latitude = request.POST.get('latitude')
        longitude = request.POST.get('longitude')
        open_time = request.POST.get('open_time')
        close_time = request.POST.get('close_time')
        logo = request.FILES.get('logo', None)

        queue.name = name
        queue.description = description
        queue.latitude = latitude
        queue.longitude = longitude
        queue.is_closed = False if status == 'on' else True
        try:
            if open_time:
                queue.open_time = datetime.strptime(open_time, "%H:%M").time()
            if close_time:
                queue.close_time = datetime.strptime(close_time, "%H:%M").time()
        except ValueError as e:
            print(f"Error while parsing time: {e}")
            messages.error(request, 'Invalid time format. Please use HH:MM format.')
            return redirect('manager:queue_settings', queue_id=queue_id)
        queue.is_closed = False if status == 'on' else True
        if logo:
            queue.logo = logo
        queue.save()
        messages.success(request, 'Queue settings updated successfully.')
        return redirect('manager:queue_settings', queue_id)


def signup(request):
    """
    Register a new user.
    Handles the signup process, creating a new user and profile if the provided data is valid.
    """
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
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
        form = CustomUserCreationForm()

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




class EditProfileView(LoginRequiredMixin, generic.UpdateView):
    model = UserProfile
    template_name = 'manager/edit_profile.html'
    context_object_name = 'profile'
    form_class = EditProfileForm

    def get_success_url(self):
        queue_id = self.kwargs.get('queue_id')
        return reverse_lazy('manager:edit_profile', kwargs={'queue_id': queue_id})

    def get_object(self, queryset=None):
        profile, created = UserProfile.objects.get_or_create(user=self.request.user)
        return profile

    def form_valid(self, form):
        """Handle both User and UserProfile updates"""
        with transaction.atomic():
            user = self.request.user
            user.username = form.cleaned_data['username']
            user.email = form.cleaned_data['email']
            user.first_name = form.cleaned_data.get('first_name', user.first_name) or ''
            user.last_name = form.cleaned_data.get('last_name', user.last_name) or ''
            user.save()

            profile = form.save(commit=False)
            profile.user = user
            if 'phone' in form.cleaned_data:
                profile.phone = form.cleaned_data['phone']
            if 'image' in form.cleaned_data and form.cleaned_data['image']:
                profile.image = form.cleaned_data['image']

            profile.save()
            messages.success(self.request, 'Profile updated successfully.')
            return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queue_id = self.kwargs.get('queue_id')
        context['queue_id'] = queue_id
        context['user'] = self.request.user
        return context


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
