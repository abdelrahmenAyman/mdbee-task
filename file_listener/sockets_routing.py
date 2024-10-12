from django.urls import re_path

from . import consumers


websocket_urlpatterns = [
    re_path(r"ws/file-transfer/$", consumers.FileTransferConsumer.as_asgi()),
]
