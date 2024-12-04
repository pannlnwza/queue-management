from django.contrib.sessions.models import Session
from django.contrib.auth.models import User
from manager.utils.aws_s3_storage import get_s3_base_url
from django.views import generic
from manager.models import Queue
from django.utils import timezone


class BaseQueueView(generic.ListView):
    """
    Base view for displaying a list of queues filtered by a specific category.
    """
    model = Queue
    template_name = "participant/list_queues.html"
    context_object_name = "queues"
    queue_category = None
    paginate_by = 8

    def get_queryset(self):
        return Queue.objects.filter(category=self.queue_category)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["queue_type"] = self.queue_category.capitalize()
        return context

class RestaurantQueueView(BaseQueueView):
    """
    View for displaying queues categorized as 'restaurant'.
    """
    queue_category = "restaurant"


class GeneralQueueView(BaseQueueView):
    """
    View for displaying queues categorized as 'general'.
    """
    queue_category = "general"


class HospitalQueueView(BaseQueueView):
    """
    View for displaying queues categorized as 'hospital'.
    """
    queue_category = "hospital"


class BankQueueView(BaseQueueView):
    """
    View for displaying queues categorized as 'bank'.
    """
    queue_category = "bank"


class BrowseQueueView(generic.ListView):
    """
    View for browsing all available queues with additional context
    such as active users and default images.
    """

    model = Queue
    template_name = "participant/browse_queue.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_queues'] = Queue.objects.all().count()
        active_sessions = Session.objects.filter(
            expire_date__gte=timezone.now())
        user_ids = [
            session.get_decoded().get('_auth_user_id')
            for session in active_sessions
        ]

        context['active_users'] = User.objects.filter(id__in=user_ids).count()
        context['restaurant'] = get_s3_base_url(
            "default_images/restaurant.jpg")
        context['general'] = get_s3_base_url("default_images/general.jpg")
        context['hospital'] = get_s3_base_url("default_images/hospital.jpg")
        context['bank'] = get_s3_base_url("default_images/bank.jpg")
        context['service_center'] = get_s3_base_url(
            "default_images/service_center.jpg")

        return context
