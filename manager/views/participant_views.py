import json
import logging
import os
from datetime import timedelta
from io import BytesIO
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.files.base import ContentFile
from django.http import JsonResponse
from django.shortcuts import redirect, get_object_or_404
from django.utils import timezone
from django.views import generic
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from gtts.tts import gTTS

from django.views.decorators.http import require_http_methods
from manager.models import Queue
from manager.utils.category_handler import CategoryHandlerFactory
from manager.utils.aws_s3_storage import upload_to_s3
from manager.utils.send_email import send_html_email
from django.conf import settings
from participant.models import Participant, Notification
from manager.utils.send_email import send_email_with_qr, generate_participant_qr_code_url

logger = logging.getLogger('queue')


class ManageWaitlist(LoginRequiredMixin, generic.TemplateView):
    """
    View for managing the waitlist of a specific queue category.

    :param template_name: The template used for rendering the manage queue page.

    :return: A context containing the lists of waiting, serving, and completed participants, resources, and
             category-specific attributes.
    """
    template_name = 'manager/manage_queue/manage_unique_category.html'

    def get_template_names(self):
        """
        Returns the appropriate template based on the queue category.

        :return: The template name as a list.
        """
        queue_id = self.kwargs.get('queue_id')
        queue = get_object_or_404(Queue, id=queue_id)
        handler = CategoryHandlerFactory.get_handler(queue.category)
        queue = handler.get_queue_object(queue_id)

        if queue.category == 'general':
            return ['manager/manage_queue/manage_general.html']
        return [self.template_name]

    def get_context_data(self, **kwargs):
        """
        Adds context for managing the waitlist, serving, and completed lists of participants.

        :return: A dictionary containing the context for the manage queue template, including participant lists,
                 resources, and category-specific context attributes.
        """
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

        context['waiting_list'] = participant_set.filter(
            state='waiting').order_by('position')[:5]
        context['serving_list'] = participant_set.filter(
            state='serving').order_by('service_started_at')[:5]
        context['completed_list'] = participant_set.filter(
            state='completed').order_by('-service_completed_at')[:5]
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
        context['available_resource'] = context['resources'].filter(
            status='available')
        return context


class ParticipantListView(LoginRequiredMixin, generic.TemplateView):
    """
    View for listing and filtering participants in a queue.

    :param template_name: The template used for rendering the participant list.

    :return: A context containing the list of participants, filter options, and pagination data.
    """

    template_name = 'manager/participant_list.html'

    def get_context_data(self, **kwargs):
        """
        Adds context for displaying and filtering participants.

        :return: A dictionary containing the context for the participant list template, including the filtered list
                 of participants, time and state filter options, and pagination data.
        """
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
            'last_7': 'Last 7 days',
            'last_30': 'Last 30 days',
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
            participant_set = participant_set.filter(updated_at__gte=start_date)

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
        now = timezone.localtime()
        if time_filter_option == 'today':
            return now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif time_filter_option == 'last_7':
            return now - timedelta(days=7)
        elif time_filter_option == 'last_30':
            return now - timedelta(days=30)
        return None


class WaitingFull(LoginRequiredMixin, generic.TemplateView):
    """
    View for displaying the waiting list when it's full.

    :param template_name: The template used for rendering the waiting list full page.

    :return: A context containing the waiting list, serving list, available resources, and category-specific context.
    """

    template_name = 'manager/manage_queue/waiting_full.html'

    def get_context_data(self, **kwargs):
        """
        Adds context for displaying the waiting list and serving list when the queue is full.

        :return: A dictionary containing the context for the waiting full template, including the lists of waiting
                 and serving participants, resources, and category-specific context attributes.
        """
        context = super().get_context_data(**kwargs)
        queue_id = self.kwargs.get('queue_id')
        queue = get_object_or_404(Queue, id=queue_id)
        handler = CategoryHandlerFactory.get_handler(queue.category)
        queue = handler.get_queue_object(queue_id)
        participant_set = handler.get_participant_set(queue_id)
        waiting_list = participant_set.filter(state='waiting').order_by('position')
        serving_list = participant_set.filter(state='serving').order_by('service_started_at')
        context['queue'] = queue
        context['waiting_list'] = waiting_list
        context['serving_list'] = serving_list
        if queue.category != 'general':
            context['resources'] = queue.resources.all()
        context['available_resource'] = queue.get_resources_by_status(
            'available')
        category_context = handler.add_context_attributes(queue)
        if category_context:
            context.update(category_context)
        return context


@require_http_methods(["POST"])
@login_required
def add_participant(request, queue_id):
    """
    Add a participant to a queue by staff.

    This method processes the data from the form submission, creates a new participant for the specified queue,
    and updates the queue's line length. It also handles errors during the participant creation process.

    :param request: The HTTP request object.
    :param queue_id: The ID of the queue to which the participant is being added.
    :return: Redirects to the participant list page with a success or error message.
    """
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
        'resource': request.POST.get('resource')
    }

    try:
        participant = handler.create_participant(data)
        queue.record_line_length()
        qrcode_url = generate_participant_qr_code_url(participant)
        participant.qrcode_url = qrcode_url
        send_email_with_qr(participant, participant.qrcode_url)
        participant.qrcode_email_sent = True
        participant.save()
        messages.success(request, "Participant has been added.")
        logger.info("Participant added successfully to queue %s", queue_id)
        return redirect('manager:participant_list', queue_id)
    except ValueError as e:
        logger.error("Error adding participant to queue %s: %s", queue_id, e)
        messages.error(request, f"Error adding participant: {e}")
        return redirect('manager:participant_list', queue_id)


@require_http_methods(["POST"])
def edit_participant(request, participant_id):
    """
    Edit an existing participant's details.

    This method processes the data from the form submission to update a participant's information in the specified queue.

    :param request: The HTTP request object.
    :param participant_id: The ID of the participant to be edited.
    :return: Redirects to the participant list page with a success or error message.
    """
    logger.info("Editing participant %s", participant_id)
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

        try:
            participant = handler.get_participant_set(participant.queue.id).get(id=participant_id)
            handler.update_participant(participant, data)
            messages.success(request, "Participant updated successfully.")
            logger.info("Participant %s updated successfully", participant_id)
            return redirect('manager:participant_list', participant.queue.id)
        except ValueError as e:
            logger.error("Error updating participant %s: %s", participant_id, e)
            messages.error(request, f"Error updating participant: {e}")
            return redirect('manager:participant_list', participant.queue.id)


@login_required
@require_http_methods(["DELETE"])
def delete_participant(request, participant_id):
    """
    Delete a participant from the queue and update the positions of remaining participants.

    Ensures the user is authorized to delete the participant and updates the position of all waiting participants.

    :param request: The HTTP request object.
    :param participant_id: The ID of the participant to be deleted.
    :return: A JSON response with a success message and updated participant positions, or an error message if unauthorized.
    """
    participant = get_object_or_404(Participant, id=participant_id)
    logger.info(
        f"Deleting participant {participant_id} from queue {participant.queue.id}")

    if request.user != participant.queue.created_by:
        return JsonResponse({'error': 'Unauthorized.'}, status=403)

    queue = participant.queue
    participant.delete()
    logger.info(f"Participant {participant_id} is deleted.")

    waiting_participants = Participant.objects.filter(queue=queue,
                                                      state='waiting').order_by(
        'position')
    for idx, p in enumerate(waiting_participants):
        p.position = idx + 1
        p.save()
    messages.success(request, f"Participant {participant.name} is deleted.")
    return JsonResponse(
        {'message': 'Participant deleted and positions updated.'})


@login_required
@require_http_methods(["POST"])
def serve_participant(request, participant_id):
    """
    Serve a specific participant in the queue.

    Assigns the participant to a resource if they are in a 'waiting' state and starts their service.
    Updates the queue's estimated wait time and positions of participants.

    :param request: The HTTP request object containing the resource ID.
    :param participant_id: The ID of the participant to be served.
    :return: A JSON response with the updated waiting and serving lists, or an error message if the operation fails.
    """
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


def serve_participant_no_resource(request, participant_id):
    """
    Serve a participant in the queue without assigning a resource.

    Starts the service for the participant if they are in the 'waiting' state,
    updates the queue's estimated wait time, and adjusts the positions of participants.

    :param request: The HTTP request object.
    :param participant_id: The ID of the participant to be served.
    :return: A JSON response with the updated waiting and serving lists, or an error message if the operation fails.
    """
    participant = get_object_or_404(Participant, id=participant_id)
    queue_id = participant.queue.id
    handler = CategoryHandlerFactory.get_handler(participant.queue.category)
    participant_set = handler.get_participant_set(queue_id)
    participant = get_object_or_404(participant_set, id=participant_id)
    try:
        if participant.state != 'waiting':
            logger.warning(
                f"Cannot serve participant {participant_id} because they are in state: {participant.state}")
            return JsonResponse({
                'error': f'{participant.name} cannot be served because they are currently in state: {participant.state}.'
            }, status=400)

        participant.queue.update_estimated_wait_time_per_turn(
            participant.get_wait_time())
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
def mark_no_show(request, participant_id):
    """
    Mark a participant as a 'No Show' if they are in the 'waiting' state.

    The participant's state is updated to 'no_show', their wait time is calculated,
    and their position in the queue is adjusted.

    :param request: The HTTP request object.
    :param participant_id: The ID of the participant to mark as 'No Show'.
    :return: A redirect to the waitlist management page with a success or error message.
    """
    participant = get_object_or_404(Participant, id=participant_id)

    if participant.state in ['serving', 'cancelled', 'completed']:
        messages.error(request,
                       "Cannot mark this participant as No Show because they are not in the waiting list.")
        return redirect('manager:manage_waitlist', participant.queue.id)
    participant.state = 'no_show'
    participant.is_notified = False
    participant.waited = (timezone.localtime(
        timezone.now()) - participant.joined_at).total_seconds() / 60

    participant.queue.update_participants_positions()
    participant.save()
    logger.info(f"{participant.name} has been marked as No Show by {request.user}.")
    messages.success(request,
                     f"{participant.name} has been marked as No Show.")

    return redirect('manager:manage_waitlist', participant.queue.id)


@login_required
@require_http_methods(["POST"])
def complete_participant(request, participant_id):
    """
    Mark a participant as 'completed' after serving is finished.

    If the participant is in the 'serving' state, their status is updated
    to 'completed', and their details are saved.

    :param request: The HTTP request object.
    :param participant_id: The ID of the participant to mark as completed.
    :return: A JSON response with the updated lists of serving and completed participants.
    """
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


@require_http_methods(["POST"])
@login_required
def notify_participant(request, participant_id):
    """
    Notify a participant via email and/or TTS audio, and mark them as notified.

    If enabled, a TTS audio file is generated and uploaded to S3 for the participant's notification.
    An email is also sent to the participant if an email address is provided.

    :param request: The HTTP request object containing the notification message.
    :param participant_id: The ID of the participant to notify.
    :return: A JSON response with the status of the notification and any generated audio URL.
    """
    participant = get_object_or_404(Participant, id=participant_id)
    queue = participant.queue

    try:
        # Parse the JSON body
        body = json.loads(request.body)
        message = body.get("message", "Your queue is here!")
    except json.JSONDecodeError:
        return JsonResponse(
            {"status": "error", "message": "Invalid JSON data"}, status=400)

    # Create the notification and mark the participant as notified
    Notification.objects.create(queue=queue, participant=participant,
                                message=message)
    participant.is_notified = True

    audio_url = None
    if queue.tts_notifications_enabled:
        participant_notification_count = Notification.objects.filter(
            participant=participant).count()
        if participant_notification_count == 1:  # Generate TTS only for the first notification
            try:
                tts = gTTS(
                    text=f"Attention Participant {participant.number}, your turn is now.",
                    lang="en")
                audio_buffer = BytesIO()
                tts.write_to_fp(audio_buffer)
                audio_buffer.seek(0)

                # Create a ContentFile from the buffer
                audio_filename = f"announcement_{participant.id}.mp3"
                audio_file = ContentFile(audio_buffer.read(),
                                         name=audio_filename)

                # Upload to S3
                audio_url = upload_to_s3(audio_file, folder="announcements")

                # Save the S3 URL to the participant
                participant.announcement_audio = audio_url

            except Exception as e:
                logger.error(
                    f"Failed to generate TTS announcement for participant {participant.id}: {str(e)}")

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
            logger.error(
                f"Failed to send email to participant {participant.email}: {str(e)}")
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


@require_http_methods(["DELETE"])
def delete_audio_file(request, filename):
    """
    Delete the specified audio notification file from the server.

    :param request: The HTTP request object.
    :param filename: The name of the audio file to delete.
    :return: A JSON response indicating success or failure.
    """
    logger.info(f"Attempting to delete audio file: {filename}")

    audio_path = os.path.join(settings.MEDIA_ROOT, "announcements", filename)
    if os.path.exists(audio_path):
        os.remove(audio_path)
        logger.info(f"Deleted audio file: {audio_path}")
        return JsonResponse({"status": "success",
                             "message": "Audio file deleted successfully."})
    logger.warning(f"Audio file not found: {audio_path}")
    return JsonResponse(
        {"status": "error", "message": "Audio file not found."}, status=404)
