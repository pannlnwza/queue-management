from django.urls import path
from participant.views import mark_notification_as_read, RestaurantQueueView, GeneralQueueView, HospitalQueueView, \
    BankQueueView, BrowseQueueView, welcome, HomePageView, KioskView, QRcodeView, \
    QueueStatusView, sse_queue_status, participant_leave, set_location, set_location_status, QueueStatusPrint

app_name = 'participant'
urlpatterns = [
    path('', HomePageView.as_view(), name='home'),
    path('queues/', BrowseQueueView.as_view(), name='queues'),
    path('welcome/<str:queue_code>/', welcome, name='welcome'),
    path('kiosk/<str:queue_code>/', KioskView.as_view(), name='kiosk'),
    path('qrcode/<str:participant_code>/', QRcodeView.as_view(), name='qrcode'),
    path('status/<str:participant_code>/', QueueStatusView.as_view(), name='queue_status'),
    path('status/<str:participant_code>/leave', participant_leave, name='participant_leave'),
    path('status/<str:participant_code>/sse', sse_queue_status, name='sse_queue_status'),
    path('queues/restaurant/', RestaurantQueueView.as_view(), name='restaurant_queues'),
    path('queues/general/', GeneralQueueView.as_view(), name='general_queues'),
    path('queues/hospital/', HospitalQueueView.as_view(), name='hospital_queues'),
    path('queues/bank/', BankQueueView.as_view(), name='bank_queues'),
    path('mark-as-read/<int:notification_id>/', mark_notification_as_read, name='mark_notification_as_read'),
    path('status_for_printing/<str:participant_code>/', QueueStatusPrint.as_view(), name='status_print'),
    path('set-location/', set_location, name='set_location'),
    path('set-location-status/', set_location_status, name='set_location_status'),
]