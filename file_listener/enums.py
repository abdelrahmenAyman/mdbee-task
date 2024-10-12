from enum import Enum


class MessageType(Enum):
    META = "file_meta"
    CHUNK = "file_chunk"
    INVALID = "invalid"
    ERROR = "error"
    META_RECEIVED = "meta_received"
    CHUNK_RECEIVED = "chunk_received"
    FILE_RECEIVED = "file_received"
