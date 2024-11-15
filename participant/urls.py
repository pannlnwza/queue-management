from django.urls import path, include
from participant.views import mark_notification_as_read, RestaurantQueueView, GeneralQueueView, HospitalQueueView, \
    BankQueueView, ServiceCenterQueueView, BrowseQueueView, welcome, HomePageView, KioskView, QRcodeView, \
    CheckQueueView

from participant.utils.data_stream import data_stream

app_name = 'participant'
urlpatterns = [
    path('', HomePageView.as_view(), name='home'),
    path('queues/', BrowseQueueView.as_view(), name='queues'),
    path('kiosk/<str:queue_code>/', include([
        path('', KioskView.as_view(), name='kiosk'),
        path('qrcode/<int:participant_id>/', QRcodeView.as_view(), name='qrcode'),
    ])),
    path('welcome/<str:queue_code>/', welcome, name='welcome'),
    path('queue_status/<int:pk>/', CheckQueueView.as_view(), name='check_queue'),
    path('api/data-stream/', data_stream, name='data_stream'),
    path('queues/restaurant/', RestaurantQueueView.as_view(), name='restaurant_queues'),
    path('queues/general/', GeneralQueueView.as_view(), name='general_queues'),
    path('queues/hospital/', HospitalQueueView.as_view(), name='hospital_queues'),
    path('queues/bank/', BankQueueView.as_view(), name='bank_queues'),
    path('queues/service_center/', ServiceCenterQueueView.as_view(), name='service_center_queues'),
    path('mark-as-read/<int:notification_id>/', mark_notification_as_read, name='mark_notification_as_read'),
]
