import logging
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import generic
from django.views.decorators.http import require_http_methods
from manager.models import Resource, Queue
from manager.utils.category_handler import CategoryHandlerFactory

logger = logging.getLogger('queue')


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
def add_resource(request, queue_id):
    """Method to add new resource to queue."""
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
    messages.success(request,
                     f"Resource {request.POST.get('name')} has been added.")
    return redirect('manager:resources', queue_id)


@login_required
@require_http_methods(["POST"])
def edit_resource(request, resource_id):
    """Method to edit existing resource detail in queue."""
    resource = get_object_or_404(Resource, id=resource_id)
    handler = CategoryHandlerFactory.get_handler(resource.queue.category)
    data = {
        'name': request.POST.get('name'),
        'special': request.POST.get('special'),
        'assigned_to': request.POST.get('assigned_to'),
        'status': request.POST.get('status'),
    }
    handler.edit_resource(resource, data)
    messages.success(request,
                     f"Resource {request.POST.get('name')} has been edited.")
    return redirect('manager:resources', resource.queue.id)


@login_required
@require_http_methods(["DELETE"])
def delete_resource(request, resource_id):
    """Method to delete existing resource in queue."""
    resource = get_object_or_404(Resource, id=resource_id)
    logger.info(
        f"Deleting resource {resource_id} from queue {resource.queue.id}")

    if request.user != resource.queue.created_by:
        return JsonResponse({'error': 'Unauthorized.'}, status=403)
    resource.delete()
    logger.info(f"Resource {resource_id} is deleted.")
    messages.success(request,
                     f"Resource {request.POST.get('name')} has been deleted.")
    return JsonResponse({'message': 'Resource deleted successfully.'})
