from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views import generic

from participant.models import Participant, Notification
from manager.models import Queue
from .forms import ReservationForm
from manager.utils.category_handler import CategoryHandlerFactory


class HomePageView(generic.TemplateView):
    template_name = 'participant/get_started.html'


@login_required
def mark_notification_as_read(request, notification_id):
    if request.method == "POST":
        try:
            notification = Notification.objects.get(id=notification_id)
            notification.is_read = True
            notification.save()
            return JsonResponse({"status": "success"})
        except Notification.DoesNotExist:
            return JsonResponse(
                {"status": "error", "message": "Notification not found"}, status=404
            )

    return JsonResponse({"status": "error", "message": "Invalid request"}, status=400)


class BaseQueueView(generic.ListView):
    model = Queue
    template_name = "participant/list_queues.html"
    context_object_name = "queues"
    queue_category = None

    def get_queryset(self):
        return Queue.objects.filter(category=self.queue_category)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["queue_type"] = self.queue_category.capitalize()
        context["queues"] = self.get_queryset()
        return context


class RestaurantQueueView(BaseQueueView):
    queue_category = "restaurant"


class GeneralQueueView(BaseQueueView):
    queue_category = "general"


class HospitalQueueView(BaseQueueView):
    queue_category = "hospital"


class BankQueueView(BaseQueueView):
    queue_category = "bank"


class ServiceCenterQueueView(BaseQueueView):
    queue_category = "service center"


class BrowseQueueView(generic.ListView):
    model = Queue
    template_name = "participant/browse_queue.html"


# @login_required
# def join_queue(request):
#     """Customer joins queue using their ticket code."""
#
#     queue_code = request.POST.get("queue_code")
#     try:
#         participant_slot = Participant.objects.get(queue_code=queue_code)
#         queue = participant_slot.queue
#         if Participant.objects.filter(user=request.user).exists():
#             messages.error(request, "You're already in a queue.")
#             logger.info(
#                 f"User: {request.user} attempted to join queue: {queue.name} when they're already in one."
#             )
#         elif queue.is_closed:
#             messages.error(request, "The queue is closed.")
#             logger.info(
#                 f"User {request.user.username} attempted to join queue {queue.name} that has been closed."
#             )
#         elif participant_slot.user:
#             messages.error(
#                 request,
#                 "Sorry, this slot is already filled by another participant. Are you sure"
#                 " that you have the right code?",
#             )
#             logger.info(
#                 f"User {request.user.username} attempted to join queue {queue.name}, but the participant slot is "
#                 f"already occupied."
#             )
#         else:
#             participant_slot.insert_user(user=request.user)
#             participant_slot.save()
#             messages.success(
#                 request,
#                 f"You have successfully joined the queue with code {queue_code}.",
#             )
#     except Participant.DoesNotExist:
#         messages.error(request, "Invalid queue code. Please try again.")
#         return redirect("participant:index")
#     return redirect("participant:index")


def welcome(request, queue_code):
    queue = get_object_or_404(Queue, code=queue_code)
    return render(request, 'participant/welcome.html', {'queue': queue})


class KioskView(generic.FormView):
    template_name = 'participant/kiosk.html'
    form_class = ReservationForm

    def dispatch(self, request, *args, **kwargs):
        # Retrieve the queue object based on the queue_code from the URL
        self.queue = get_object_or_404(Queue, code=kwargs['queue_code'])
        self.participant_handler = CategoryHandlerFactory.get_handler(self.queue.id)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        # Add the queue object to the context for rendering
        context = super().get_context_data(**kwargs)
        context['queue'] = self.queue
        return context

    def form_valid(self, form):
        # Create a new participant associated with the queue
        form_data = form.cleaned_data.copy()
        form_data['queue'] = self.queue
        participant = self.participant_handler.create_participant(
            form_data,
        )
        participant.save()
        messages.success(self.request, f"You have successfully joined {self.queue.name}.")
        return redirect('participant:home')

    def form_invalid(self, form):
        # Optional: Log or print errors for debugging
        print(form.errors)
        return super().form_invalid(form)
