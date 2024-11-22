import json
import logging
from datetime import timedelta, datetime
from os import close

from django.contrib import messages
from django.contrib.auth import authenticate, login, user_logged_in, \
    user_logged_out, user_login_failed
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.contrib.auth.models import User
from django.dispatch import receiver
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.views import generic, View
from django.views.decorators.http import require_http_methods
from manager.forms import QueueForm, CustomUserCreationForm, EditProfileForm, \
    OpeningHoursForm, ResourceForm
from manager.models import Queue, Resource

from django.views import generic
from django.views.decorators.http import require_http_methods, require_POST
from manager.forms import QueueForm, CustomUserCreationForm, EditProfileForm
from participant.models import Participant, Notification
from manager.models import Queue, UserProfile, QueueLineLength
from manager.utils.queue_handler import QueueHandlerFactory
from manager.utils.category_handler import CategoryHandlerFactory
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger('queue')


class MultiStepFormView(View):
    def get(self, request, step):
        # Get the form depending on the current step
        if step == "1":
            form = QueueForm()
        elif step == "2":
            form = OpeningHoursForm()
        elif step == "3":
            # Retrieve queue data and time/location data to pass category and other info
            queue_data = request.session.get('queue_data', {})

            queue_category = queue_data.get('category',
                                            None)  # Ensure category is passed
            form = ResourceForm(request.POST or None,
                                # Handle POST or empty on GET
                                queue_category={
                                    'category': queue_category})  # Pass queue category dynamically
        else:
            return redirect('manager:your-queue')  # Handle invalid steps

        return render(
            request,
            f'manager/create_queue_steps/step_{step}.html',
            {'form': form, 'step': step}
        )

    def post(self, request, step):
        if step == "1":
            form = QueueForm(request.POST, request.FILES)
            if form.is_valid():
                # Save queue data to session
                request.session['queue_data'] = form.cleaned_data
                return redirect('manager:create_queue_step', step="2")

        elif step == "2":
            form = OpeningHoursForm(request.POST)
            if form.is_valid():
                # Save opening hours and location data to session
                latitude = request.POST.get('latitudeInput')
                longitude = request.POST.get('longitudeInput')

                time_and_location_data = {
                    'open_time': form.cleaned_data['open_time'].strftime(
                        '%H:%M:%S') if form.cleaned_data.get(
                        'open_time') else None,
                    'close_time': form.cleaned_data['close_time'].strftime(
                        '%H:%M:%S') if form.cleaned_data.get(
                        'close_time') else None,
                    'latitude': latitude,
                    'longitude': longitude,
                }

                request.session[
                    'time_and_location_data'] = time_and_location_data

                return redirect('manager:create_queue_step', step="3")

        elif step == "3":
            queue_data = request.session.get('queue_data', {})
            time_and_location_data = request.session.get(
                'time_and_location_data', {})
            queue_data_raw = queue_data.copy()
            queue_data_raw.update(time_and_location_data.copy())
            queue_category = queue_data_raw.get('category',
                                                None)  # Ensure category is present
            form = ResourceForm(request.POST,
                                queue_category={'category': queue_category})

            if form.is_valid():
                try:
                    resource_data = form.cleaned_data
                    queue_category = queue_data_raw['category']
                    handler = CategoryHandlerFactory.get_handler(
                        queue_category)
                    queue_data_raw['created_by'] = request.user
                    queue = handler.create_queue(queue_data_raw)
                    resource_data['queue'] = queue
                    logger.info(f"Resource data: {resource_data}")
                    handler.add_resource(resource_data.copy())
                    messages.success(request,
                                     f"Successfully create queue: {queue.name}")
                    return redirect('manager:your-queue')
                except Exception as e:
                    logger.error(
                        f"Error creating queue or adding resource: {e}")
                    messages.error(request,
                                   f"Error creating queue or adding resource: {e}.")
                    return redirect('manager:create_queue_step', step="3")

        # In case the form is not valid, render the current step
        return render(
            request,
            f'manager/create_queue_steps/step_{step}.html',
            {'form': form, 'step': step}
        )


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

        return redirect(self.success_url)


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


@require_http_methods(["POST"])
@login_required
def notify_participant(request, participant_id):
    participant = get_object_or_404(Participant, id=participant_id)
    queue = participant.queue
    message = request.POST.get('message', '')
    Notification.objects.create(queue=queue, participant=participant,
                                message=message)
    participant.is_notified = True
    participant.save()
    return JsonResponse(
        {'status': 'success', 'message': 'Notification sent successfully!'})


@require_http_methods(["DELETE"])
@login_required
def delete_queue(request, queue_id):
    try:
        queue = Queue.objects.get(pk=queue_id)
    except Queue.DoesNotExist:
        return JsonResponse({'error': 'Queue not found.'}, status=404)

    if request.user != queue.created_by:
        return JsonResponse({'error': 'Unauthorized.'}, status=403)

    try:
        queue.delete()
        return JsonResponse({'success': 'Queue deleted successfully.'},
                            status=200)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["DELETE"])
def delete_participant(request, participant_id):
    participant = get_object_or_404(Participant, id=participant_id)
    logger.info(
        f"Deleting participant {participant_id} from queue {participant.queue.id}")

    if request.user != participant.queue.created_by:
        return JsonResponse({'error': 'Unauthorized.'}, status=403)

    queue = participant.queue
    participant.state = 'removed'
    logger.info(f"Participant {participant_id} is deleted.")

    waiting_participants = Participant.objects.filter(queue=queue,
                                                      state='waiting').order_by(
        'position')
    for idx, p in enumerate(waiting_participants):
        p.position = idx + 1
        p.save()
    return JsonResponse(
        {'message': 'Participant deleted and positions updated.'})


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
        handler = CategoryHandlerFactory.get_handler(
            participant.queue.category)
        participant = handler.get_participant_set(participant.queue.id).get(
            id=participant_id)
        handler.update_participant(participant, data)
        return redirect('manager:participant_list', participant.queue.id)


@require_http_methods(["POST"])
@login_required
def add_participant(request, queue_id):
    name = request.POST.get('name')
    phone = request.POST.get('phone')
    email = request.POST.get('email')
    note = request.POST.get('notes', "")
    special_1 = request.POST.get('special_1')
    special_2 = request.POST.get('special_2')

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
    }
    handler.create_participant(data)
    queue.record_line_length()
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

        if self.request.user != queue.created_by:
            logger.error(
                f"Unauthorized edit attempt on queue {queue.id} by user {self.request.user.id}")
            return JsonResponse({'error': 'Unauthorized.'}, status=403)

        search_query = self.request.GET.get('search', '').strip()
        participant_set = handler.get_participant_set(queue_id)
        if search_query:
            participant_set = participant_set.filter(
                name__icontains=search_query)

        context['waiting_list'] = participant_set.filter(state='waiting')
        context['serving_list'] = participant_set.filter(state='serving')
        context['completed_list'] = participant_set.filter(state='completed')
        context['queue'] = queue
        context['resources'] = queue.resource_set.all()
        context['available_resource'] = queue.get_resources_by_status(
            'available')
        context['busy_resource'] = queue.get_resources_by_status('busy')
        context['unavailable_resource'] = queue.get_resources_by_status(
            'unavailable')

        category_context = handler.add_context_attributes(queue)
        if category_context:
            context.update(category_context)
        return context


@login_required
@require_http_methods(["POST"])
def serve_participant(request, participant_id):
    participant = get_object_or_404(Participant, id=participant_id)
    queue_id = participant.queue.id
    handler = CategoryHandlerFactory.get_handler(participant.queue.category)
    participant_set = handler.get_participant_set(queue_id)
    participant = get_object_or_404(participant_set, id=participant_id)

    try:
        data = json.loads(request.body) if request.body else {}
        resource_id = data.get('resource_id', None)

        if participant.state != 'waiting':
            logger.warning(
                f"Cannot serve participant {participant_id} because they are in state: {participant.state}")
            return JsonResponse({
                'error': f'{participant.name} cannot be served because they are currently in state: {participant.state}.'
            }, status=400)

        handler.assign_to_resource(participant, resource_id=resource_id)
        participant.queue.update_estimated_wait_time_per_turn(
            participant.get_wait_time())
        participant.start_service()
        participant.save()
        logger.info(
            f"Participant {participant_id} started service in queue {participant.queue.id}.")

        waiting_list = Participant.objects.filter(state='waiting').values()
        serving_list = Participant.objects.filter(state='serving').values()

        return JsonResponse({
            'waiting_list': list(waiting_list),
            'serving_list': list(serving_list),
            'success': True
        })

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data.'}, status=400)

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
    participant = handler.get_participant_set(queue.id).filter(
        id=participant_id).first()

    if request.user != queue.created_by:
        logger.error(
            f"Unauthorized edit attempt on queue {queue.id} by user {request.user.id}")
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
        logger.info(
            f"Participant {participant_id} completed service in queue {queue.id}.")

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
        context[
            'time_filter_option_display'] = time_filter_options_display.get(
            time_filter_option, 'All time')
        context['state_filter_option'] = state_filter_option
        context[
            'state_filter_option_display'] = state_filter_options_display.get(
            state_filter_option, 'Any state')
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
            return now - timedelta(
                days=now.weekday())  # monday of the current week
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

        state_filter = self.request.GET.get('state_filter', 'any_state')
        authorized_queues = Queue.objects.filter(created_by=user)

        state_filter_options = {
            'any_state': 'Any state',
            'open': 'Open',
            'closed': 'Closed',
        }

        if state_filter == 'open':
            authorized_queues = authorized_queues.filter(is_closed=False)
        elif state_filter == 'closed':
            authorized_queues = authorized_queues.filter(is_closed=True)

        context['authorized_queues'] = authorized_queues
        context['selected_state_filter'] = state_filter_options.get(
            state_filter)
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

        date_filter = self.request.GET.get('date_filter', 'today')
        date_filter_text = 'today'
        end_date = timezone.now()

        if date_filter == 'today':
            start_date = end_date.replace(hour=0, minute=0, second=0,
                                          microsecond=0)
            date_filter_text = 'today'
        elif date_filter == 'last_7_days':
            start_date = end_date - timedelta(days=7)
            date_filter_text = 'last 7 days'
        elif date_filter == 'last_30_days':
            start_date = end_date - timedelta(days=30)
            date_filter_text = 'last 30 days'
        elif date_filter == 'all_time':
            start_date = None
            date_filter_text = 'all time'
        else:
            start_date = None


        context['queue'] = queue
        context['participant_set'] = participant_set
        context['waitlisted'] = queue.get_number_of_participants_by_date(start_date, end_date)
        context['currently_waiting'] = queue.get_number_waiting_now(start_date, end_date)
        context['currently_serving'] = queue.get_number_serving_now(start_date, end_date)
        context['served'] = queue.get_number_served(start_date, end_date)
        context['served_percentage'] = queue.get_served_percentage(start_date, end_date)
        context['average_wait_time'] = queue.get_average_waiting_time(start_date, end_date)
        context['max_wait_time'] = queue.get_max_waiting_time(start_date, end_date)
        context[
            'average_service_duration'] = queue.get_average_service_duration(start_date, end_date)
        context['max_service_duration'] = queue.get_max_service_duration(start_date, end_date)
        context['peak_line_length'] = queue.get_peak_line_length(start_date, end_date)
        context['avg_line_length'] = queue.get_avg_line_length(start_date, end_date)
        context['dropoff_percentage'] = queue.get_dropoff_percentage(start_date, end_date)
        context['unhandled_percentage'] = queue.get_unhandled_percentage(start_date, end_date)
        context['cancelled_percentage'] = queue.get_cancelled_percentage(start_date, end_date)
        context['removed_percentage'] = queue.get_removed_percentage(start_date, end_date)
        context['guest_percentage'] = queue.get_guest_percentage(start_date, end_date)
        context['staff_percentage'] = queue.get_staff_percentage(start_date, end_date)
        context['date_filter'] = date_filter
        context['date_filter_text'] = date_filter_text
        return context


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
    logger.info(
        f"Deleting resource {resource_id} from queue {resource.queue.id}")

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
                queue.close_time = datetime.strptime(close_time,
                                                     "%H:%M").time()
        except ValueError as e:
            print(f"Error while parsing time: {e}")
            messages.error(request,
                           'Invalid time format. Please use HH:MM format.')
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

            profile, created = UserProfile.objects.get_or_create(user=user)
            if not profile:
                messages.error(request,
                               'Error creating user profile. Please contact support.')

            user = authenticate(username=username, password=raw_passwd)
            if user is not None:
                login(request, user)
                logger.info(f'New user signed up with profile: {username}')
                return redirect('participant:home')
            else:
                logger.error(
                    f'Failed to authenticate user after signup: {username}')
                messages.error(request,
                               'Error during signup process. Please try again.')
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

            profile, created = UserProfile.objects.get_or_create(user=user)

            # Simplify social account image retrieval
            social_accounts = user.socialaccount_set.filter(provider='google')
            if social_accounts.exists():
                extra_data = social_accounts.first().extra_data
                profile_image_url = extra_data.get('picture')
                if profile_image_url:
                    profile.google_picture = profile_image_url
                    profile.save()
                    logger.info(
                        f'Google profile image updated for user: {username}')

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
        return reverse_lazy('manager:edit_profile',
                            kwargs={'queue_id': queue_id})

    def get_object(self, queryset=None):
        profile, created = UserProfile.objects.get_or_create(
            user=self.request.user)
        return profile

    def form_valid(self, form):
        """Handle both User and UserProfile updates"""
        user = self.request.user
        user.username = form.cleaned_data['username']
        user.email = form.cleaned_data['email']
        user.first_name = form.cleaned_data.get('first_name',
                                                user.first_name) or ''
        user.last_name = form.cleaned_data.get('last_name',
                                               user.last_name) or ''
        user.save()

        profile = form.save(commit=False)
        profile.user = user
        profile.phone = form.cleaned_data.get('phone', profile.phone)

        # Handle image removal and upload
        if form.cleaned_data.get('remove_image') == 'true':
            profile.image = 'profile_images/profile.jpg'
            profile.google_picture = None
        elif form.files.get('image'):
            profile.image = form.files['image']
            profile.google_picture = None

        profile.save()
        messages.success(self.request, 'Profile updated successfully.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queue_id = self.kwargs.get('queue_id')
        queue = get_object_or_404(Queue, id=queue_id)
        handler = CategoryHandlerFactory.get_handler(queue.category)
        queue = handler.get_queue_object(queue_id)
        context['queue'] = queue
        context['queue_id'] = queue_id
        context['user'] = self.request.user
        profile = self.get_object()
        context['profile_image_url'] = profile.get_profile_image()
        return context


def get_client_ip(request):
    """Retrieve the client's IP address from the request."""
    return (
        x_forwarded_for.split(',')[0]
        if (x_forwarded_for := request.META.get('HTTP_X_FORWARDED_FOR'))
        else request.META.get('REMOTE_ADDR')
    )


@csrf_exempt
def set_location(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            lat = data.get('lat')
            lon = data.get('lon')
            if lat and lon:
                # Store latitude and longitude in the session
                request.session['user_lat'] = lat
                request.session['user_lon'] = lon
                print(f"Saved to session: Lat = {lat}, Lon = {lon}")
                return JsonResponse({'status': 'success'})
            else:
                return JsonResponse(
                    {'status': 'failed', 'error': 'Invalid data'}, status=400)
        except json.JSONDecodeError:
            return JsonResponse({'status': 'failed', 'error': 'Invalid JSON'},
                                status=400)
    return JsonResponse(
        {'status': 'failed', 'error': 'Only POST method allowed'}, status=400)


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
