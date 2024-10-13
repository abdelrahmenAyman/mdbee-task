import base64
from unittest.mock import patch

from channels.testing import WebsocketCommunicator
from django.conf import settings
from django.test import TestCase

from file_listener.consumers import FileTransferConsumer
from file_listener.enums import MessageType
from file_listener.errors import InvalidMessageTypeError
from file_listener.handlers import FileTransferHandler


class FileTransferHandlerTestSuite(TestCase):
    def setUp(self):
        self.handler = FileTransferHandler("test.txt", 100)

    async def test_initialize_with_larger_than_max_file_size(self):
        with self.assertRaises(ValueError):
            FileTransferHandler("test.txt", settings.FILE_MAX_SIZE + 1)

    async def test_initialize_with_invalid_extension(self):
        with self.assertRaises(ValueError):
            FileTransferHandler("test.doc", 100)

    async def test_initizalize_with_unsanitized_file_name(self):
        file = FileTransferHandler("%t$e@s/&t.txt", 100)
        self.assertEqual(file.file_name, "test.txt")

    async def test_intialize_with_sanitized_name(self):
        file = FileTransferHandler("test-some_thing.txt", 100)
        self.assertEqual(file.file_name, "test-some_thing.txt")

    async def test_append_chunk(self):
        chunk = base64.b64encode(b"test data").decode("utf-8")
        await self.handler.append_chunk(chunk)

        self.assertEqual(self.handler.received_size, 9)

    async def test_decode_chunk(self):
        chunk = base64.b64encode(b"test data").decode("utf-8")
        decoded_chunk = await self.handler._decode_b64_chunk(chunk)

        self.assertEqual(decoded_chunk, b"test data")

    async def test_is_file_complete_received_size_smalled_than_file_size(self):
        self.assertFalse(self.handler.is_file_complete())

    async def test_is_file_complete_received_size_equal_to_file_size(self):
        self.handler.received_size = 100
        self.assertTrue(self.handler.is_file_complete())

    @patch("file_listener.handlers.open")
    @patch("file_listener.handlers.os.makedirs")
    async def test_save_file(self, mock_makedirs, mock_open):
        self.handler.content = b"test content"
        await self.handler.save_file()
        mock_makedirs.assert_called_once()
        mock_open.assert_called_once()

    async def test_get_file_extension(self):
        self.assertEqual(self.handler.get_file_extension(), "txt")


class FileTransferConsumerTestSuite(TestCase):
    def setUp(self):
        self.save_file_mock = patch("file_listener.consumers.FileTransferHandler.save_file")
        self.save_file_mock.start()

    def tearDown(self) -> None:
        self.save_file_mock.stop()

    async def test_connection_established(self):
        communicator = WebsocketCommunicator(FileTransferConsumer.as_asgi(), "/ws/file-transfer/")
        connected, _ = await communicator.connect()
        self.assertTrue(connected)
        await communicator.disconnect()

    async def test_dispatch_handler_message_type_meta(self):
        consumer = FileTransferConsumer()
        handler = await consumer.dispatch_handler(message_type=MessageType.META.value)
        self.assertEqual(handler, consumer.handle_file_meta)

    async def test_dispatch_handler_message_type_chunk(self):
        consumer = FileTransferConsumer()
        handler = await consumer.dispatch_handler(message_type=MessageType.CHUNK.value)
        self.assertEqual(handler, consumer.handle_file_chunk)

    async def test_dispatch_handler_invalid_message_type(self):
        consumer = FileTransferConsumer()
        with self.assertRaises(InvalidMessageTypeError):
            await consumer.dispatch_handler(message_type="invalid")

    async def test_file_meta_handler(self):
        communicator = WebsocketCommunicator(FileTransferConsumer.as_asgi(), "/ws/file_transfer/")
        await communicator.connect()

        await communicator.send_json_to({"type": MessageType.META.value, "file_name": "test.txt", "file_size": 100})

        response = await communicator.receive_json_from()
        self.assertEqual(response["type"], MessageType.META_RECEIVED.value)
        self.assertEqual(response["message"], "Ready to receive file")

        await communicator.disconnect()

    async def test_file_chunk_handler(self):
        communicator = WebsocketCommunicator(FileTransferConsumer.as_asgi(), "/ws/file_transfer/")
        await communicator.connect()

        # Send file meta first
        await communicator.send_json_to({"type": MessageType.META.value, "file_name": "test.txt", "file_size": 10})
        await communicator.receive_json_from()

        # Send file chunk
        chunk = base64.b64encode(b"0123456789").decode("utf-8")
        await communicator.send_json_to({"type": MessageType.CHUNK.value, "chunk": chunk})

        response = await communicator.receive_json_from()
        self.assertEqual(response["type"], MessageType.FILE_RECEIVED.value)
        self.assertIn("test.txt received successfully", response["message"])

        await communicator.disconnect()

    async def test_invalid_message_type(self):
        communicator = WebsocketCommunicator(FileTransferConsumer.as_asgi(), "/ws/file_transfer/")
        await communicator.connect()

        await communicator.send_json_to({"type": "INVALID_TYPE", "data": "some data"})

        response = await communicator.receive_json_from()
        self.assertEqual(response["type"], MessageType.ERROR.value)
        self.assertIn("Invalid message type", response["message"])

        await communicator.disconnect()
