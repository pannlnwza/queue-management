import json
import logging
import os
from datetime import timedelta, datetime

from django.contrib import messages
from django.contrib.auth import authenticate, login, user_logged_in, \
    user_logged_out, user_login_failed
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.views import generic, View
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from gtts.tts import gTTS
import base64

from django.views.decorators.http import require_http_methods
from manager.forms import QueueForm, CustomUserCreationForm, EditProfileForm
from participant.models import Participant, Notification, BankParticipant, HospitalParticipant
from manager.models import UserProfile
from django.dispatch import receiver

from manager.models import Resource
from manager.forms import QueueForm, CustomUserCreationForm, EditProfileForm, OpeningHoursForm, ResourceForm
from manager.models import Queue, UserProfile
from manager.utils.category_handler import CategoryHandlerFactory

from django.views.decorators.csrf import csrf_exempt
from manager.utils.send_email import send_html_email
from django.core.files.storage import FileSystemStorage
from django.conf import settings
import traceback
import os

from participant.models import Participant, Notification

logger = logging.getLogger('queue')



class CreateQueueView(generic.TemplateView):
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
            [{'value': code, 'label': label} for code, label in BankParticipant.SERVICE_TYPE_CHOICES]
        )
        context['specialty'] = json.dumps(
            [{'value': code, 'label': label} for code, label in HospitalParticipant.MEDICAL_FIELD_CHOICES]
        )
        return context


def create_queue(request):
    data = request.POST.dict()
    category = data.get('category')
    resource_name = data.get('resource_name')
    resource_special = data.get('resource_detail')

    queue_data = {
        'category': category,
        'name': data.get('name'),
        'description': data.get('description'),
        'open_time': data.get('open_time'),
        'close_time': data.get('close_time'),
        'latitude': data.get('latitude'),
        'longitude': data.get('longitude'),
        'created_by': request.user,
    }

    if 'logo' in request.FILES:
        try:
            logo_file = request.FILES['logo']
            queue_data['logo'] = logo_file.read()
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
        messages.success(request, f"Queue '{data.get('name')}' created successfully.")
        return redirect('manager:your-queue')
    except Exception as e:
        messages.error(request, f"An error occurred while creating the queue: {str(e)}")
        return redirect('manager:your-queue')


@require_http_methods(["POST"])
@login_required
def notify_participant(request, participant_id):
    participant = get_object_or_404(Participant, id=participant_id)
    queue = participant.queue

    try:
        # Parse the JSON body
        body = json.loads(request.body)
        message = body.get("message", "Your queue is here!")
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "Invalid JSON data"}, status=400)

    # Create the notification and mark the participant as notified
    Notification.objects.create(queue=queue, participant=participant, message=message)
    participant.is_notified = True

    audio_url = None
    if queue.tts_notifications_enabled:
        participant_notification_count = Notification.objects.filter(participant=participant).count()
        if participant_notification_count == 1:  # Generate TTS only for the first notification
            try:
                tts = gTTS(text=f"Attention Participant {participant.number}, your turn is now.", lang="en")
                audio_dir = os.path.join(settings.MEDIA_ROOT, "announcements")
                os.makedirs(audio_dir, exist_ok=True)
                audio_filename = f"announcement_{participant.id}.mp3"
                audio_path = os.path.join(audio_dir, audio_filename)
                tts.save(audio_path)

                # Save the file path to the participant
                participant.announcement_audio = audio_filename
                audio_url = f"{settings.MEDIA_URL}announcements/{audio_filename}"
            except Exception as e:
                logger.error(f"Failed to generate TTS announcement for participant {participant.id}: {str(e)}")

    participant.save()

    # Prepare email context
    email_context = {
        "participant": participant,
        "message": message,
        "queue": queue,
    }

    # Attempt to send the email
    email_error = None
    if participant.email:
        try:
            send_html_email(
                subject="Your Queue Notification",
                to_email=participant.email,
                template_name="manager/emails/participant_notification.html",
                context=email_context,
            )
        except Exception as e:
            logger.error(f"Failed to send email to participant {participant.email}: {str(e)}")
            email_error = f"Failed to send email to participant {participant.email}: {str(e)}"

    # Prepare the JSON response
    response = {
        "status": "success",
        "message": "Notification sent successfully!",
        "audio_url": audio_url,  # Return the audio URL for playback
    }
    if email_error:
        response["email_status"] = "error"
        response["email_message"] = email_error

    return JsonResponse(response)


@login_required
def mark_no_show(request, participant_id):
    participant = get_object_or_404(Participant, id=participant_id)

    if participant.state in ['serving', 'cancelled', 'completed']:
        messages.error(request, "Cannot mark this participant as No Show because they are not in the waiting list.")
        return redirect('manager:manage_waitlist', participant.queue.id)
    participant.state = 'no_show'
    participant.is_notified = False
    participant.waited = (timezone.localtime(timezone.now()) - participant.joined_at).total_seconds() / 60

    participant.queue.update_participants_positions()
    participant.save()
    messages.success(request, f"{participant.name} has been marked as No Show.")

    return redirect('manager:manage_waitlist', participant.queue.id)

def serve_participant_no_resource(request, participant_id):
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
        participant.start_service()
        participant.queue.update_participants_positions()
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

@require_http_methods(["DELETE"])
def delete_audio_file(request, filename):
    logger.info(f"Attempting to delete audio file: {filename}")

    audio_path = os.path.join(settings.MEDIA_ROOT, "announcements", filename)
    if os.path.exists(audio_path):
        os.remove(audio_path)
        logger.info(f"Deleted audio file: {audio_path}")
        return JsonResponse({"status": "success", "message": "Audio file deleted successfully."})
    logger.warning(f"Audio file not found: {audio_path}")
    return JsonResponse({"status": "error", "message": "Audio file not found."}, status=404)


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
        messages.success(request, f"Queue {queue.name} has been deleted.")
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
    participant.save()
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
        messages.success(request, "Participant's information has been edited.")
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
    messages.success(request, "Participant has been added.")
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

        context['waiting_list'] = participant_set.filter(state='waiting').order_by('position')[:5]
        context['serving_list'] = participant_set.filter(state='serving').order_by('-service_started_at')[:5]
        context['completed_list'] = participant_set.filter(state='completed').order_by('-service_completed_at')[:5]
        context['queue'] = queue
        context['resources'] = queue.resource_set.all()
        context['busy_resource'] = queue.get_resources_by_status('busy')
        context['unavailable_resource'] = queue.get_resources_by_status(
            'unavailable')

        category_context = handler.add_context_attributes(queue)
        resource_context = handler.add_resource_attributes(queue)
        if category_context:
            context.update(category_context)
        if resource_context:
            context.update(resource_context)
        context['available_resource'] = context['resources'].filter(status='available')
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
        participant.queue.update_estimated_wait_time_per_turn(participant.get_wait_time())
        participant.start_service()
        participant.queue.update_participants_positions()
        participant.save()

        logger.info(f"Participant {participant_id} started service in queue {participant.queue.id}.")

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

def serve_participant_no_resource(request, participant_id):
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
        participant.start_service()
        participant.queue.update_participants_positions()
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

@login_required
def mark_no_show(request, participant_id):
    participant = get_object_or_404(Participant, id=participant_id)

    if participant.state in ['serving', 'cancelled', 'completed']:
        messages.error(request, "Cannot mark this participant as No Show because they are not in the waiting list.")
        return redirect('manager:manage_waitlist', participant.queue.id)
    participant.state = 'no_show'
    participant.is_notified = False
    participant.waited = (timezone.localtime(timezone.now()) - participant.joined_at).total_seconds() / 60

    participant.queue.update_participants_positions()
    participant.save()
    messages.success(request, f"{participant.name} has been marked as No Show.")

    return redirect('manager:manage_waitlist', participant.queue.id)

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

        items_per_page = 10
        paginator = Paginator(participant_set, items_per_page)
        page = self.request.GET.get('page', 1)

        try:
            participants = paginator.page(page)
        except PageNotAnInteger:
            participants = paginator.page(1)
        except EmptyPage:
            participants = paginator.page(paginator.num_pages)



        context['queue'] = handler.get_queue_object(queue_id)
        context['participant_set'] = participants
        context['participant_state'] = Participant.PARTICIPANT_STATE
        context['page_obj'] = participants
        if queue.category != 'general':
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
        participant_set = handler.get_participant_set(queue_id)
        waiting_list = participant_set.filter(state='waiting')
        serving_list = participant_set.filter(state='serving')
        context['queue'] = queue
        context['waiting_list'] = waiting_list
        context['serving_list'] = serving_list
        if queue.category != 'general':
            context['resources'] = queue.resources.all()
        context['available_resource'] = queue.get_resources_by_status('available')
        category_context = handler.add_context_attributes(queue)
        if category_context:
            context.update(category_context)
        return context


class BaseViewAll(LoginRequiredMixin, generic.TemplateView):
    state = None

    def get_context_data(self, **kwargs):
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
        context['available_resource'] = queue.get_resources_by_status('available')

        category_context = handler.add_context_attributes(queue)
        if category_context:
            context.update(category_context)
        return context

    def get_template_names(self):
        """
        Dynamically determine the template name based on queue category and state.
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
    state = 'waiting'


class ViewAllServing(BaseViewAll):
    state = 'serving'


class ViewAllCompleted(BaseViewAll):
    state = 'completed'



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
        context['selected_state_filter'] = state_filter_options.get(state_filter)
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
        context['resource_totals'] = [
            {
                'resource': resource,
                'name': resource.name,
                'total': resource.total(start_date=start_date,
                                        end_date=end_date),
                'served': resource.served(start_date=start_date,
                                          end_date=end_date),
                'dropoff': resource.dropoff(start_date=start_date,
                                            end_date=end_date),
                'completed': resource.completed(start_date=start_date,
                                                end_date=end_date),
                'avg_wait_time': resource.avg_wait_time(start_date=start_date,
                                                        end_date=end_date),
                'avg_serve_time': resource.avg_serve_time(
                    start_date=start_date, end_date=end_date),
            }
            for resource in queue.resource_set.all()
        ]

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
        user = self.request.user
        user.username = form.cleaned_data['username']
        user.email = form.cleaned_data['email']
        user.first_name = form.cleaned_data.get('first_name', user.first_name) or ''
        user.last_name = form.cleaned_data.get('last_name', user.last_name) or ''
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


@login_required
@require_http_methods(["DELETE"])
def delete_participant(request, participant_id):
    participant = get_object_or_404(Participant, id=participant_id)
    logger.info(f"Deleting participant {participant_id} from queue {participant.queue.id}")

    if request.user != participant.queue.created_by:
        return JsonResponse({'error': 'Unauthorized.'}, status=403)

    queue = participant.queue
    participant.state = 'removed'
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
            logger.warning(f"Cannot serve participant {participant_id} because they are in state: {participant.state}")
            return JsonResponse({
                'error': f'{participant.name} cannot be served because they are currently in state: {participant.state}.'
            }, status=400)

        handler.assign_to_resource(participant, resource_id=resource_id)
        participant.queue.update_estimated_wait_time_per_turn(participant.get_wait_time())
        participant.start_service()
        participant.save()
        logger.info(f"Participant {participant_id} started service in queue {participant.queue.id}.")

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
@require_http_methods(["POST"])
def complete_participant(request, participant_id):
    participant = get_object_or_404(Participant, id=participant_id)
    queue = participant.queue
    handler = CategoryHandlerFactory.get_handler(queue.category)
    participant = handler.get_participant_set(queue.id).filter(id=participant_id).first()

    if request.user != queue.created_by:
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
    messages.success(request, f"Resource {request.POST.get('name')} has been edited.")
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
    messages.success(request, f"Resource {request.POST.get('name')} has been added.")
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
    messages.success(request, f"Resource {request.POST.get('name')} has been deleted.")
    return JsonResponse({'message': 'Resource deleted successfully.'})

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
        return JsonResponse({'success': 'Queue deleted successfully.'}, status=200)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
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
        tts_enabled = request.POST.get('tts')

        if 'logo' in request.FILES:
            try:
                logo_file = request.FILES['logo']
                queue.logo = logo_file.read()
            except Exception as e:
                messages.error(request, f"Error processing the logo file: {e}")
                return redirect('manager:your-queue')

        queue.name = name
        queue.description = description
        queue.latitude = latitude
        queue.longitude = longitude
        queue.is_closed = False if status == 'on' else True
        queue.tts_notifications_enabled = True if tts_enabled == 'on' else False

        try:
            # Parse open and close time
            if open_time:
                queue.open_time = datetime.strptime(open_time, "%H:%M").time()
            if close_time:
                queue.close_time = datetime.strptime(close_time, "%H:%M").time()
        except ValueError as e:
            logger.error(f"Error parsing time: {e}")
            messages.error(request, 'Invalid time format. Please use HH:MM.')
            return redirect('manager:queue_settings', queue_id=queue_id)
        queue.is_closed = False if status == 'on' else True
        queue.save()
        messages.success(request, 'Queue settings updated successfully.')
        return redirect('manager:queue_settings', queue_id=queue_id)

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

def get_client_ip(request):
    """Retrieve the client's IP address from the request."""
    return (
        x_forwarded_for.split(',')[0]
        if (x_forwarded_for := request.META.get('HTTP_X_FORWARDED_FOR'))
        else request.META.get('REMOTE_ADDR'))


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
