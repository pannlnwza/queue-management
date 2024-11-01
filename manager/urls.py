from django.urls import path

from manager.views import CreateQView, ManageQueuesView, EditQueueView, QueueDashboardView, add_participant_slot, \
    notify_participant, delete_queue, delete_participant, ManageWaitlist, serve_participant, complete_participant, \
    edit_participant, ParticipantListView

from participant.utils.data_stream import data_stream
from manager.utils.queue_data import get_restaurant_queue_data

app_name = 'manager'
urlpatterns = [
    path('create', CreateQView.as_view(), name='create_q'),
    path('dashboard/<int:pk>/', QueueDashboardView.as_view(), name='dashboard'),
    path('api/data-stream/', data_stream, name='data_stream'),
    path('api/queue-dashboard-stream/<int:queue_id>/', get_restaurant_queue_data, name='queue_dashboard_stream'),
    path('delete_participant/<int:participant_id>/', delete_participant, name='delete_participant'),
    path('manage/', ManageQueuesView.as_view(), name='manage_queues'),
    path('queue/<int:pk>/edit/', EditQueueView.as_view(), name='edit_queue'),
    path('queue/<int:queue_id>/delete/', delete_queue, name='delete_queue'),
    path('queue/<int:queue_id>/add-participant/', add_participant_slot, name='add_participant_slot'),
    path('notify/<int:participant_id>/', notify_participant, name='notify_participant'),
    path('waitlist/<int:queue_id>/', ManageWaitlist.as_view(), name='manage_waitlist'),
    path('serve/<int:participant_id>/', serve_participant, name='serve_participant'),
    path('complete/<int:participant_id>/', complete_participant, name='complete_participant'),
    path('restaurant-updates/<int:queue_id>/', get_restaurant_queue_data, name='get_restaurant_queue_data'),
    path('edit_participant/<int:participant_id>/', edit_participant, name='edit_participant'),
    path('participants/<int:queue_id>/', ParticipantListView.as_view(), name='participant_list'),
]
