from django.urls import path

from queue_manager.services.queue_stream import *
from queue_manager.views import *

app_name = 'queue'
urlpatterns = [
    path('', IndexView.as_view(), name='index'),
    path('create', CreateQView.as_view(), name='create_q'),
    path('queues/', QueueListView.as_view(), name='queues'),
    path('join/', join_queue, name='join'),
    path('dashboard/<int:pk>/', QueueDashboardView.as_view(), name='dashboard'),
    path('api/queue-stream/', queue_stream, name='queue_stream'),
    path('api/queue-dashboard-stream/<int:queue_id>/', queue_dashboard_stream, name='queue_dashboard_stream'),
    path('queue/delete/<int:participant_id>/', delete_participant, name='delete_participant'),
    path('manage/', ManageQueuesView.as_view(), name='manage_queues'),
    path('queue/<int:pk>/edit/', EditQueueView.as_view(), name='edit_queue'),
    path('queue/<int:queue_id>/delete/', delete_queue, name='delete_queue'),
]
