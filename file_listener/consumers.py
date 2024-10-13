import json
import logging
from typing import Any

from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from file_listener.enums import MessageType
from file_listener.errors import InvalidMessageTypeError, RateLimitExceededError
from file_listener.handlers import FileTransferHandler, WebSocketMessageHandler

logger = logging.getLogger("django")

Json = dict[str, Any]


class FileTransferConsumer(AsyncWebsocketConsumer):
    def __init__(self):
        super().__init__()
        self.message_handler = WebSocketMessageHandler(self)
        self.message_handlers = {
            MessageType.META.value: self.handle_file_meta,
            MessageType.CHUNK.value: self.handle_file_chunk,
        }

    async def connect(self):
        logger.info("WebSocket connection established.")
        await self.accept()

    async def disconnect(self, code):
        logger.info(f"WebSocket disconnected with code: {code}")

    async def receive(self, text_data):
        try:
            await self.limit_rate()
            text_data_json = json.loads(text_data)
            message_type = text_data_json["type"]
            handler = await self.dispatch_handler(message_type)
            await handler(text_data_json)
        except json.JSONDecodeError:
            logger.error("Invalid JSON format.")
            await self.message_handler.send_error("Invalid JSON format")
        except KeyError as e:
            logger.error(f"Missing key in JSON: {str(e)}")
            await self.message_handler.send_error(f"Missing key in JSON: {str(e)}")
        except InvalidMessageTypeError as e:
            logger.error(str(e))
            await self.message_handler.send_error(str(e))
        except ValueError as e:
            logger.error(f"Value error: {str(e)}")
            await self.message_handler.send_error(f"Value error: {str(e)}")
        except RateLimitExceededError as e:
            logger.error(str(e))
            await self.message_handler.send_error(str(e))
            await self.close(code=1008)
        except Exception as e:
            logger.exception(f"An unexpected error occurred: {str(e)}")
            await self.message_handler.send_error(f"An error occurred: {str(e)}")

    async def limit_rate(self):
        user_ip = self.scope["client"][0]
        key = f"{settings.RATE_LIMIT_KEY_PREFIX}{user_ip}"

        current_time = timezone.now()
        request_count, last_request_time = cache.get(key, (0, current_time))

        if (current_time - last_request_time).total_seconds() > settings.RATE_LIMIT_PERIOD:
            request_count = 0
            last_request_time = current_time

        if request_count >= settings.RATE_LIMIT_PER_PERIOD:
            logger.error(f"Rate limit exceeded for user IP: {user_ip}")
            raise RateLimitExceededError("Rate limit exceeded")

        request_count += 1
        cache.set(key, (request_count, last_request_time), timeout=60)

    async def dispatch_handler(self, message_type: str):
        try:
            return self.message_handlers[message_type]
        except KeyError:
            raise InvalidMessageTypeError(f"Invalid message type: {message_type}")

    async def handle_file_meta(self, data: Json):
        self.file_handler = FileTransferHandler(file_name=data["file_name"], file_size=data["file_size"])
        await self.message_handler.send_meta_received()

    async def handle_file_chunk(self, data: Json):
        await self.file_handler.append_chunk(data["chunk"])
        if self.file_handler.is_file_complete():
            await self.file_handler.save_file()
            file_extension = self.file_handler.get_file_extension()
            await self.message_handler.send_file_received(file_extension, self.file_handler.file_name)
        else:
            await self.message_handler.send_chunk_received()
