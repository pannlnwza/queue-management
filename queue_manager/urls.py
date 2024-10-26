from django.urls import path
from queue_manager.views import *

app_name = 'queue'
urlpatterns = [
    path('', IndexView.as_view(), name='index'),
    path('create', CreateQView.as_view(), name='create_q'),
    path('queues/', QueueListView.as_view(), name='queues'),
    path('join/', join_queue, name='join'),
    path('dashboard/<int:pk>/', QueueDashboardView.as_view(), name='dashboard'),
    path('delete/<int:participant_id>/', delete_participant, name='delete'),
    path('manage/', ManageQueuesView.as_view(), name='manage_queues'),
    path('queue/<int:pk>/edit/', EditQueueView.as_view(), name='edit_queue'),
    path('history/', QueueHistoryView.as_view(), name='history'),
    path('leave/<int:participant_id>/', leave_queue, name='leave_queue'),
]

