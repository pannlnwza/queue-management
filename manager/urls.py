from django.urls import path


from manager.utils.queue_data import get_unique_queue_category_data, get_general_queue_data
from manager.views import (
    notify_participant, delete_queue, delete_participant, ManageWaitlist, serve_participant,
    complete_participant, \
    edit_participant, ParticipantListView, StatisticsView, YourQueueView, add_participant,
    QueueSettingsView, \
    ResourceSettings, edit_resource, add_resource, delete_resource, WaitingFull, edit_queue,
    EditProfileView,
    CreateQueueView, mark_no_show, ViewAllWaiting, ViewAllServing, ViewAllCompleted,
    serve_participant_no_resource, set_location, create_queue, delete_audio_file)


app_name = 'manager'
urlpatterns = [
    path('delete_participant/<int:participant_id>/', delete_participant, name='delete_participant'),
    path('delete_queue/<int:queue_id>/', delete_queue, name='delete_queue'),
    path('notify/<int:participant_id>/', notify_participant, name='notify_participant'),
    path('manage/<int:queue_id>/', ManageWaitlist.as_view(), name='manage_waitlist'),
    path('serve/<int:participant_id>/', serve_participant, name='serve_participant'),
    path('serve_no_resource/<int:participant_id>/', serve_participant_no_resource, name='serve_participant_no_resource'),
    path('complete/<int:participant_id>/', complete_participant, name='complete_participant'),
    path('unique-category-updates/<int:queue_id>/', get_unique_queue_category_data, name='get_unique_queue_category_data'),
    path('general-updates/<int:queue_id>/', get_general_queue_data, name='get_general_queue_data'),
    path('edit_participant/<int:participant_id>/', edit_participant, name='edit_participant'),
    path('statistics/<int:queue_id>/', StatisticsView.as_view(), name='statistics'),
    path('participants/<int:queue_id>', ParticipantListView.as_view(), name='participant_list'),
    path('queue/', YourQueueView.as_view(), name='your-queue'),
    path('add_participant/<int:queue_id>/', add_participant, name='add_participant'),
    path('settings/<int:queue_id>', QueueSettingsView.as_view(), name='queue_settings'),
    path('settings/<int:queue_id>/resources/', ResourceSettings.as_view(), name='resources'),
    path('edit_resource/<int:resource_id>/', edit_resource, name='edit_resource'),
    path('add_resource/<int:queue_id>/', add_resource, name='add_resource'),
    path('delete_resource/<int:resource_id>/', delete_resource, name='delete_resource'),
    path('waiting_fullscreen/<int:queue_id>', WaitingFull.as_view(), name='waiting_full'),
    path('edit_queue/<int:queue_id>', edit_queue, name='edit_queue'),
    path('edit-profile/<int:queue_id>/', EditProfileView.as_view(), name='edit_profile'),
    path('add_participant/<int:queue_id>/', add_participant, name='add_participant'),
    path('create-queue-step/<str:step>/', CreateQueueView.as_view(), name='create_queue_step'),
    path('create_queue/', create_queue, name='create_queue'),
    path('mark_no_show/<int:participant_id>/', mark_no_show, name='mark_no_show'),
    path('view_all_waiting/<int:queue_id>/', ViewAllWaiting.as_view(), name='view_all_waiting'),
    path('view_all_serving/<int:queue_id>/', ViewAllServing.as_view(), name='view_all_serving'),
    path('view_all_completed/<int:queue_id>/', ViewAllCompleted.as_view(), name='view_all_completed'),
    path('set_location/', set_location, name='set_location'),
    path("delete_audio/<str:filename>/", delete_audio_file, name="delete_audio"),
]
