import logging
from datetime import datetime
import json
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from manager.models import Queue
from django.views import generic
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.decorators.http import require_http_methods
from manager.utils.category_handler import CategoryHandlerFactory
from manager.models import Resource
from participant.models import BankParticipant, HospitalParticipant, Participant
from manager.utils.aws_s3_storage import upload_to_s3

logger = logging.getLogger('queue')


class BaseViewAll(LoginRequiredMixin, generic.TemplateView):
    """
    Base view to display participants in different states (waiting, serving, completed).

    :param state: The state of the participants to filter (e.g., 'waiting', 'serving', 'completed').
    """

    state = None

    def get_context_data(self, **kwargs):
        """
        Retrieves context data for displaying participants in a specified state.
        """
        if self.state is None:
            raise ValueError("Subclasses must define 'state'")
        context = super().get_context_data(**kwargs)
        queue_id = self.kwargs.get('queue_id')
        queue = get_object_or_404(Queue, id=queue_id)

        handler = CategoryHandlerFactory.get_handler(queue.category)
        queue = handler.get_queue_object(queue_id)
        participant_set = handler.get_participant_set(queue_id)
        filtered_list = participant_set.filter(state=self.state)

        context['queue'] = queue
        context[f'{self.state}_list'] = filtered_list
        if queue.category != 'general':
            context['resources'] = queue.resources.all()
        context['available_resource'] = queue.get_resources_by_status(
            'available')

        category_context = handler.add_context_attributes(queue)
        if category_context:
            context.update(category_context)
        return context

    def get_template_names(self):
        """
        Dynamically determines the template name based on queue category and state.

        :return: A list of template names.
        """
        queue_id = self.kwargs.get('queue_id')
        queue = get_object_or_404(Queue, id=queue_id)

        category_path = (
            "manager/view_all/general/"
            if queue.category == "general"
            else "manager/view_all/unique_categories/"
        )
        return [f"{category_path}all_{self.state}.html"]


class ViewAllWaiting(BaseViewAll):
    """
    Displays participants in the 'waiting' state.
    """
    state = 'waiting'


class ViewAllServing(BaseViewAll):
    """
    Displays participants in the 'serving' state.
    """
    state = 'serving'


class ViewAllCompleted(BaseViewAll):
    """
    Displays participants in the 'completed' state.
    """
    state = 'completed'


class YourQueueView(LoginRequiredMixin, generic.TemplateView):
    """
    Displays queues the user has created, with filtering options.
    """
    template_name = 'manager/your_queue.html'

    def get_context_data(self, **kwargs):
        """
        Retrieves context data for displaying the user's authorized queues.
        """
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

        items_per_page = 10
        paginator = Paginator(authorized_queues, items_per_page)
        page = self.request.GET.get('page', 1)

        try:
            queues = paginator.page(page)
        except PageNotAnInteger:
            queues = paginator.page(1)
        except EmptyPage:
            queues = paginator.page(paginator.num_pages)

        context['authorized_queues'] = queues
        context['page_obj'] = queues
        context['selected_state_filter'] = state_filter_options.get(state_filter)
        context['state_filter_options'] = state_filter_options
        return context


class QueueSettingsView(LoginRequiredMixin, generic.TemplateView):
    """
    Displays and manages settings for a specific queue.
    """
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
        print(queue.open_time, queue.close_time)
        category_context = handler.add_resource_attributes(queue)
        if category_context:
            context.update(category_context)
        return context


class CreateQueueView(generic.TemplateView):
    """
    View for creating a new queue with multi-step process.

    This view handles the creation of a new queue, including selecting the queue category, service type, and specialty.
    It supports a step-by-step process, with options for category, service type, and medical specialty (if applicable).
    """

    template_name = 'manager/create_queue.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        step = int(self.request.GET.get('step', 1))
        total_steps = 3
        context.update({
            'step': step,
            'total_steps': total_steps,
            'total_steps_list': range(1, total_steps + 1),
        })
        context['categories'] = Queue.CATEGORY_CHOICES
        context['service_type'] = json.dumps(
            [{'value': code, 'label': label} for code, label in
             BankParticipant.SERVICE_TYPE_CHOICES]
        )
        context['specialty'] = json.dumps(
            [{'value': code, 'label': label} for code, label in
             HospitalParticipant.MEDICAL_FIELD_CHOICES]
        )
        return context


class QueueDisplay(generic.TemplateView):
    """
    View for displaying the current queue's participants, including those currently being served and waiting.

    This view displays the current status of participants in the queue, including the participant being called,
    the next in line, and a list of the first few participants who are waiting.
    """

    template_name = 'manager/queue_display.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queue_id = self.kwargs.get('queue_id')
        queue = get_object_or_404(Queue, id=queue_id)
        context['queue'] = queue

        calling = Participant.objects.filter(queue_id=queue_id, is_notified=True).order_by(
            '-notification__created_at').first()
        calling_number = calling.number if calling else None

        next_in_line = Participant.objects.filter(queue_id=queue_id, state='waiting').exclude(
            is_notified=True).order_by(
            'position').first()
        next_in_line_number = next_in_line.number if next_in_line else "-"
        participants = (
            Participant.objects.filter(queue_id=queue_id, state='waiting')
            .exclude(pk=calling.pk if calling else None)
            .order_by('joined_at')
        )


        context['participants'] = participants[:6]
        context['calling'] = calling_number
        context['next_in_line'] = next_in_line_number
        return context


@login_required
def create_queue(request):
    """
    Create a new queue for a business owner or queue creator.

    :param request: The HTTP request containing the queue data and optional logo file.
    :raises Exception: If an error occurs during queue or resource creation.
    :return: A redirect to the 'your-queue' page with a success or error message.
    """
    data = request.POST.dict()
    category = data.get('category')
    resource_name = data.get('resource_name')
    resource_special = data.get('resource_detail')

    queue_data = {
        'category': category,
        'name': data.get('name'),
        'description': data.get('description'),
        'open_time': data.get("open_time") if data.get(
            "open_time") else None,
        'close_time': data.get("close_time") if data.get(
            "close_time") else None,
        'latitude': data.get('latitude'),
        'longitude': data.get('longitude'),
        'created_by': request.user,
    }

    if 'logo' in request.FILES:
        try:
            logo_file = request.FILES['logo']
            folder = 'queue_logos'
            logo_url = upload_to_s3(logo_file, folder)
            queue_data['logo'] = logo_url
        except Exception as e:
            messages.error(request, f"Error processing the logo file: {e}")
            return redirect('manager:your-queue')

    handler = CategoryHandlerFactory.get_handler(category)
    try:
        queue = handler.create_queue(queue_data)
        if resource_name and resource_special:
            resource_data = {
                'name': resource_name,
                'special': resource_special,
                'queue': queue,
                'status': 'available'
            }
            handler.add_resource(resource_data)
        messages.success(request,
                         f"Queue '{data.get('name')}' created successfully.")
        return redirect('manager:your-queue')
    except Exception as e:
        messages.error(request,
                       f"An error occurred while creating the queue: {str(e)}")
        return redirect('manager:your-queue')


@require_http_methods(["DELETE"])
@login_required
def delete_queue(request, queue_id):
    """
    Delete a queue for a business owner or queue creator.

    :param request: The HTTP request containing the queue ID to delete.
    :param queue_id: The ID of the queue to be deleted.
    :raises Queue.DoesNotExist: If the queue with the provided ID does not exist.
    :raises Unauthorized: If the user does not have permission to delete the queue.
    :return: A JsonResponse with a success or error message.
    """
    try:
        queue = Queue.objects.get(pk=queue_id)
    except Queue.DoesNotExist:
        return JsonResponse({'error': 'Queue not found.'}, status=404)

    if request.user != queue.created_by:
        return JsonResponse({'error': 'Unauthorized.'}, status=403)

    try:
        queue.delete()
        messages.success(request, f"Queue {queue.name} has been deleted.")
        return JsonResponse({'success': 'Queue deleted successfully.'},
                            status=200)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def edit_queue(request, queue_id):
    """
    Edit the settings of a queue for a business owner or queue creator.

    :param request: The HTTP request containing the form data to update the queue.
    :param queue_id: The ID of the queue to be updated.
    :raises Queue.DoesNotExist: If the queue with the provided ID does not exist.
    :raises ValueError: If the provided time format is invalid.
    :return: A redirect response to the queue settings page with success or error messages.
    """
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
        tts_enabled = request.POST.get('tts')

        if 'logo' in request.FILES:
            try:
                logo_file = request.FILES['logo']
                # Upload the file to S3 and store the URL
                folder = 'queue_logos'
                logo_url = upload_to_s3(logo_file, folder)
                queue.logo = logo_url
            except Exception as e:
                logger.error(f"Error uploading logo to S3: {e}")
                messages.error(request, f"Error processing the logo file: {e}")
                return redirect('manager:queue_settings', queue_id=queue_id)

        queue.name = name
        queue.description = description
        queue.latitude = latitude
        queue.longitude = longitude
        print(status)
        queue.is_closed = status is None
        queue.tts_notifications_enabled = True if tts_enabled == 'on' else False

        try:
            # Parse open and close time
            if open_time:
                queue.open_time = datetime.strptime(open_time, "%H:%M").time()
            if close_time:
                queue.close_time = datetime.strptime(close_time,
                                                     "%H:%M").time()
        except ValueError as e:
            logger.error(f"Error parsing time: {e}")
            messages.error(request, 'Invalid time format. Please use HH:MM.')
            return redirect('manager:queue_settings', queue_id=queue_id)
        queue.save()
        messages.success(request, 'Queue settings updated successfully.')
        return redirect('manager:queue_settings', queue_id=queue_id)
