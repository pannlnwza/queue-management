from django.urls import path
from queue_manager.views import *

app_name = 'queue'
urlpatterns = [
    path('', IndexView.as_view(), name='index'),

]