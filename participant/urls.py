from django.urls import path
from participant.views import mark_notification_as_read, RestaurantQueueView, GeneralQueueView, HospitalQueueView, \
    BankQueueView, ServiceCenterQueueView, BrowseQueueView, join_queue, IndexView
from participant.utils.data_stream import data_stream

app_name = 'participant'
urlpatterns = [
    path('', IndexView.as_view(), name='index'),
    path('queues/', BrowseQueueView.as_view(), name='queues'),
    path('join/', join_queue, name='join'),
    path('api/data-stream/', data_stream, name='data_stream'),
    path('queues/restaurant/', RestaurantQueueView.as_view(), name='restaurant_queues'),
    path('queues/general/', GeneralQueueView.as_view(), name='general_queues'),
    path('queues/hospital/', HospitalQueueView.as_view(), name='hospital_queues'),
    path('queues/bank/', BankQueueView.as_view(), name='bank_queues'),
    path('queues/service_center/', ServiceCenterQueueView.as_view(), name='service_center_queues'),
    path('mark-as-read/<int:notification_id>/', mark_notification_as_read, name='mark_notification_as_read'),
]
