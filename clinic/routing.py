from django.urls import re_path
from clinic.consumers import QueueConsumer, LiveBoardConsumer

websocket_urlpatterns = [
    re_path(r'ws/queue/(?P<clinic_id>[^/]+)/(?P<doctor_id>[^/]+)/$', QueueConsumer.as_asgi()),
    re_path(r'ws/liveboard/(?P<clinic_id>[^/]+)/$', LiveBoardConsumer.as_asgi()),
]
