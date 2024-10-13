import base64
from datetime import timedelta
from unittest.mock import patch

import pytest
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.conf import settings
from django.core.cache import cache
from django.urls import re_path
from django.utils import timezone

from file_listener.consumers import FileTransferConsumer
from file_listener.enums import MessageType
from file_listener.errors import InvalidMessageTypeError, RateLimitExceededError
from file_listener.handlers import FileTransferHandler


@pytest.mark.asyncio
class TestTransferHandlerTestSuite:
    @pytest.fixture(autouse=True)
    async def setup(self):
        self.handler = FileTransferHandler("test.txt", 100)
        yield
        cache.clear()

    async def test_initialize_with_larger_than_max_file_size(self):
        with pytest.raises(ValueError):
            FileTransferHandler("test.txt", settings.FILE_MAX_SIZE + 1)

    async def test_initialize_with_invalid_extension(self):
        with pytest.raises(ValueError):
            FileTransferHandler("test.doc", 100)

    async def test_initizalize_with_unsanitized_file_name(self):
        file = FileTransferHandler("%t$e@s/&t.txt", 100)
        assert file.file_name == "test.txt"

    async def test_intialize_with_sanitized_name(self):
        file = FileTransferHandler("test-some_thing.txt", 100)
        assert file.file_name == "test-some_thing.txt"

    async def test_append_chunk(self):
        chunk = base64.b64encode(b"test data").decode("utf-8")
        await self.handler.append_chunk(chunk)

        assert self.handler.received_size == 9

    async def test_decode_chunk(self):
        chunk = base64.b64encode(b"test data").decode("utf-8")
        decoded_chunk = await self.handler._decode_b64_chunk(chunk)

        assert decoded_chunk == b"test data"

    async def test_is_file_complete_received_size_smalled_than_file_size(self):
        assert not self.handler.is_file_complete()

    async def test_is_file_complete_received_size_equal_to_file_size(self):
        self.handler.received_size = 100
        assert self.handler.is_file_complete()

    @patch("file_listener.handlers.open")
    @patch("file_listener.handlers.os.makedirs")
    async def test_save_file(self, mock_makedirs, mock_open):
        self.handler.content = b"test content"
        await self.handler.save_file()
        mock_makedirs.assert_called_once()
        mock_open.assert_called_once()

    async def test_get_file_extension(self):
        assert self.handler.get_file_extension() == "txt"


class ScopeMiddleWare:
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        scope["client"] = ("127.0.0", 1234)
        return await self.inner(scope, receive, send)


@pytest.mark.asyncio
class TestFileTransferConsumer:
    @pytest.fixture(autouse=True)
    async def setup(self):
        self.save_file_mock = patch("file_listener.consumers.FileTransferHandler.save_file")
        self.save_file_mock.start()

        application = URLRouter(
            [
                re_path(r"^ws/file_transfer/$", ScopeMiddleWare(FileTransferConsumer.as_asgi())),
            ]
        )
        self.consumer = FileTransferConsumer()
        self.consumer.scope = {"client": ("127.0.0.1", 1234)}
        self.communicator = WebsocketCommunicator(application, "/ws/file_transfer/")
        connected, _ = await self.communicator.connect()
        assert connected

        yield

        await self.communicator.disconnect()
        self.save_file_mock.stop()
        cache.clear()

    async def test_dispatch_handler_message_type_meta(self):
        handler = await self.consumer.dispatch_handler(message_type=MessageType.META.value)
        assert handler == self.consumer.handle_file_meta

    async def test_dispatch_handler_message_type_chunk(self):
        handler = await self.consumer.dispatch_handler(message_type=MessageType.CHUNK.value)
        assert handler == self.consumer.handle_file_chunk

    async def test_dispatch_handler_invalid_message_type(self):
        with pytest.raises(InvalidMessageTypeError):
            await self.consumer.dispatch_handler(message_type="invalid")

    async def test_file_meta_handler(self):

        await self.communicator.send_json_to(
            {"type": MessageType.META.value, "file_name": "test.txt", "file_size": 100}
        )

        response = await self.communicator.receive_json_from()

        assert response["type"] == MessageType.META_RECEIVED.value
        assert response["message"] == "Ready to receive file"

    async def test_file_chunk_handler(self):
        # Send file meta first
        await self.communicator.send_json_to(
            {"type": MessageType.META.value, "file_name": "test.txt", "file_size": 10}
        )
        await self.communicator.receive_json_from()

        # Send file chunk
        chunk = base64.b64encode(b"0123456789").decode("utf-8")
        await self.communicator.send_json_to({"type": MessageType.CHUNK.value, "chunk": chunk})

        response = await self.communicator.receive_json_from()

        assert response["type"] == MessageType.FILE_RECEIVED.value
        assert "test.txt received successfully" in response["message"]

    async def test_invalid_message_type(self):
        await self.communicator.send_json_to({"type": "INVALID_TYPE", "data": "some data"})
        response = await self.communicator.receive_json_from()

        assert response["type"] == MessageType.ERROR.value
        assert "Invalid message type" in response["message"]

    async def test_rate_limit_exceeded(self):
        cache.set(
            f"{settings.RATE_LIMIT_KEY_PREFIX}{self.consumer.scope["client"][0]}",
            (settings.RATE_LIMIT_PER_PERIOD + 1, timezone.now()),
        )
        with pytest.raises(RateLimitExceededError):
            await self.consumer.limit_rate()

    async def test_limit_rate_not_exceeded(self):
        await self.consumer.limit_rate()

    async def test_reset_limit_rate_request_count(self):
        key = f"{settings.RATE_LIMIT_KEY_PREFIX}{self.consumer.scope["client"][0]}"
        cache.set(
            key,
            (settings.RATE_LIMIT_PER_PERIOD + 1, timezone.now() - timedelta(seconds=60)),
        )
        await self.consumer.limit_rate()

        cached_count, _ = cache.get(key)
        assert cached_count == 1
