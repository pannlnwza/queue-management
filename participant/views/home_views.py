from django.http import JsonResponse
from django.views import generic
from manager.models import Queue
from django.views.decorators.csrf import csrf_exempt
import json


class HomePageView(generic.TemplateView):
    """View for displaying home page."""
    template_name = 'participant/get_started.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        featured_queues = Queue.get_top_featured_queues()
        context['featured_queues'] = featured_queues
        location_status = self.request.session.get('location_status', None)
        if location_status == 'blocked':
            context['num_nearby_queues'] = 0
            context[
                'error'] = "Location not provided. Enable location services, and refresh the page to view nearby queues."
        else:
            user_lat = self.request.session.get('user_lat', None)
            user_lon = self.request.session.get('user_lon', None)
            if user_lat and user_lon:
                try:
                    user_lat = float(user_lat)
                    user_lon = float(user_lon)
                    nearby_queues = Queue.get_nearby_queues(user_lat, user_lon)
                    context['nearby_queues'] = nearby_queues
                    context['num_nearby_queues'] = len(
                        nearby_queues) if nearby_queues else 0
                except ValueError:
                    context[
                        'error'] = "Invalid latitude or longitude provided."
            else:
                context['num_nearby_queues'] = 0
                context[
                    'error'] = "Location not provided. Enable location services, and refresh the page to view nearby queues."
        return context


@csrf_exempt
def set_location(request):
    """
    Sets the user's location for determining nearby queues.

    This method accepts a POST request containing latitude and longitude data in JSON format.
    The provided location is saved in the session for future use, enabling the system to show nearby queues based on the user's location.

    :param request: The HTTP request object containing the location data.
    :returns: A JSON response indicating success or failure, along with an error message if applicable.

    :raises JSONDecodeError: If the body of the request contains invalid JSON.
    :raises ValueError: If the latitude or longitude data is missing or invalid.
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            lat = data.get('lat')
            lon = data.get('lon')
            if lat and lon:
                request.session['user_lat'] = lat
                request.session['user_lon'] = lon
                print(f"Saved to session: Lat = {lat}, Lon = {lon}")
                request.session['location_status'] = 'allowed'
                return JsonResponse({'status': 'success'})
            else:
                request.session['location_status'] = 'blocked'
                return JsonResponse(
                    {'status': 'failed', 'error': 'Invalid location data'},
                    status=400
                )
        except json.JSONDecodeError:
            return JsonResponse(
                {'status': 'failed', 'error': 'Invalid JSON format'},
                status=400
            )
    else:
        return JsonResponse(
            {'status': 'failed', 'error': 'Only POST method allowed'},
            status=400
        )


@csrf_exempt
def set_location_status(request):
    """
    Sets the user's location access permission.

    This method accepts a POST request to set the user's location access status.
    Based on the 'status' value ('blocked' or 'allowed'), the user's latitude and longitude are either removed or saved in the session.

    :param request: The HTTP request object containing the status data.
    :returns: A JSON response indicating success or failure, with an optional error message.

    :raises Exception: If an unexpected error occurs while processing the request.
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            status = data.get('status')
            if status == 'blocked':
                request.session.pop('user_lat', None)
                request.session.pop('user_lon', None)
                request.session['location_status'] = 'blocked'
            elif status == 'allowed':
                request.session['location_status'] = 'allowed'
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request method'})
