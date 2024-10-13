import base64
import json
import logging
import os

from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings

from file_listener.enums import MessageType

logger = logging.getLogger("django")


class WebSocketMessageHandler:
    def __init__(self, consumer: AsyncWebsocketConsumer):
        self.consumer = consumer

    async def send_error(self, message: str):
        logger.error(f"Sending error message: {message}")
        text_data = {"type": MessageType.ERROR.value, "message": message}
        await self.consumer.send(text_data=json.dumps(text_data))

    async def send_meta_received(self):
        logger.info("File metadata received, ready to accept file.")
        await self.consumer.send(
            text_data=json.dumps(
                {
                    "type": MessageType.META_RECEIVED.value,
                    "message": "Ready to receive file",
                }
            )
        )

    async def send_chunk_received(self):
        logger.info("Chunk received, ready for the next chunk.")
        await self.consumer.send(
            text_data=json.dumps(
                {
                    "type": MessageType.CHUNK_RECEIVED.value,
                    "message": "Ready for next chunk",
                }
            )
        )

    async def send_file_received(self, file_extension: str, file_name: str):
        logger.info(f"File received: {file_name} with extension: {file_extension}")
        await self.consumer.send(
            text_data=json.dumps(
                {
                    "type": MessageType.FILE_RECEIVED.value,
                    "message": f"File {file_name} received successfully and file extension is `{file_extension}`",
                    "extension": file_extension,
                }
            )
        )


class FileTransferHandler:
    def __init__(self, file_name: str, file_size: int):
        self.file_name = file_name
        self.file_size = file_size
        self.received_size = 0
        self.content = b""

        if self.file_size > settings.FILE_MAX_SIZE:
            raise ValueError(f"File size {self.file_size // 1024 // 1024}MB exceeds the maximum allowed size.")
        if (extension := self.get_file_extension()) not in settings.FILE_ALLOWED_EXTENSIONS:
            raise ValueError(f"Invalid file extension: {extension}.")
        self._sanitize_file_name()

    async def append_chunk(self, chunk: str):
        chunk_bytes = await self._decode_b64_chunk(chunk)
        self.content += chunk_bytes
        self.received_size += len(chunk_bytes)

    async def _decode_b64_chunk(self, chunk: str) -> bytes:
        return base64.b64decode(chunk)

    def is_file_complete(self) -> bool:
        return self.received_size >= self.file_size

    async def save_file(self):
        file_path = os.path.join(settings.FILE_SAVE_DIRECTORY, self.file_name)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        logger.info(f"Saving file to {file_path}")
        with open(file_path, "wb") as f:
            f.write(self.content)
        logger.info(f"File saved successfully: {file_path}")

    def get_file_extension(self) -> str:
        extension = os.path.splitext(self.file_name)[1][1:]
        return extension

    def _sanitize_file_name(self):
        self.file_name = "".join(char for char in self.file_name if char.isalnum() or char in [".", "_", "-"])
