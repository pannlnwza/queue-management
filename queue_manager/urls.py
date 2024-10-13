from django.urls import path
from queue_manager.views import *

app_name = 'queue'
urlpatterns = [
    path('', IndexView.as_view(), name='index'),
    path('create', CreateQView.as_view(), name='create_q'),
    path('queues/', QueueListView.as_view(), name='queues'),
    path('join/', join_queue, name='join'),
]