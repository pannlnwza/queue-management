from django.urls import path

from manager.views import CreateQView, ManageQueuesView, EditQueueView, QueueDashboardView, add_participant_slot, \
    notify_participant, delete_queue, delete_participant

from participant.utils.data_stream import data_stream
from manager.utils.dashboard_stream import queue_dashboard_stream

app_name = 'manager'
urlpatterns = [
    path('create', CreateQView.as_view(), name='create_q'),
    path('dashboard/<int:pk>/', QueueDashboardView.as_view(), name='dashboard'),
    path('api/data-stream/', data_stream, name='data_stream'),
    path('api/queue-dashboard-stream/<int:queue_id>/', queue_dashboard_stream, name='queue_dashboard_stream'),
    path('queue/delete/<int:participant_id>/', delete_participant, name='delete_participant'),
    path('manage/', ManageQueuesView.as_view(), name='manage_queues'),
    path('queue/<int:pk>/edit/', EditQueueView.as_view(), name='edit_queue'),
    path('queue/<int:queue_id>/delete/', delete_queue, name='delete_queue'),
    path('queue/<int:queue_id>/add-participant/', add_participant_slot, name='add_participant_slot'),
    path('notify/<int:participant_id>/', notify_participant, name='notify_participant'),
    path('notify-participant/<int:queue_id>/<int:participant_id>/', notify_participant, name='notify_participant'),
]
