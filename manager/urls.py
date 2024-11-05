from django.urls import path

from manager.views import CreateQView, ManageQueuesView, EditQueueView, QueueDashboardView, add_participant_slot, \
    notify_participant, delete_queue, delete_participant, ManageWaitlist, serve_participant, complete_participant, \
    edit_participant, ParticipantListView, StatisticsView, YourQueueView

from participant.utils.data_stream import data_stream
from manager.utils.queue_data import get_restaurant_queue_data, get_general_queue_data

app_name = 'manager'
urlpatterns = [
    path('create', CreateQView.as_view(), name='create_q'),
    path('dashboard/<int:pk>/', QueueDashboardView.as_view(), name='dashboard'),
    path('delete_participant/<int:participant_id>/', delete_participant, name='delete_participant'),
    path('queue/<int:pk>/edit/', EditQueueView.as_view(), name='edit_queue'),
    path('delete_queue/<int:queue_id>/', delete_queue, name='delete_queue'),
    path('queue/<int:queue_id>/add-participant/', add_participant_slot, name='add_participant_slot'),
    path('notify/<int:participant_id>/', notify_participant, name='notify_participant'),
    path('manage/<int:queue_id>/', ManageWaitlist.as_view(), name='manage_waitlist'),
    path('serve/<int:participant_id>/', serve_participant, name='serve_participant'),
    path('complete/<int:participant_id>/', complete_participant, name='complete_participant'),
    path('restaurant-updates/<int:queue_id>/', get_restaurant_queue_data, name='get_restaurant_queue_data'),
    path('general-updates/<int:queue_id>/', get_general_queue_data, name='get_general_queue_data'),
    path('edit_participant/<int:participant_id>/', edit_participant, name='edit_participant'),
    path('statistics/<int:queue_id>/', StatisticsView.as_view(), name='statistics'),
    path('participants/<int:queue_id>', ParticipantListView.as_view(), name='participant_list'),
    path('queue/', YourQueueView.as_view(), name='your-queue'),
]
