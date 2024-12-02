from django.urls import re_path
from manager.consumers import QueueDisplayConsumer

websocket_urlpatterns = [
    re_path(r'ws/queue/display/(?P<queue_id>\d+)/$', QueueDisplayConsumer.as_asgi()),
]
