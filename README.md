# File Transfer WebSocket Service

This is a Django-based WebSocket service designed to handle file uploads via WebSockets. It supports file chunking for large files, rate limiting to prevent abuse, and Redis integration for caching and real-time communication handling.
## Project Overview
The WebSocket service allows clients to upload files over WebSocket connections. Files are sent in chunks, encoded using Base64, and reconstructed on the server side. The project includes built-in rate limiting to control the number of requests a client can send within a defined time window.
## Dependencies
The project is implemented using django, django-channels for websockets and redis for caching.
- Python 3.12
- django: Application server.
- django-channels: used in implementing websockets.
- redis: Acts as a backend layer for django-channels and is used in rate limiting by caching the number of requests a certain client has made.
- poetry: used for dependency management.
- docker & docker-compose: Containerization
## Setup Instructions
Prerequisites:
Before you begin, ensure you have met the following requirements:
  - Docker & Docker Compose (for containerized deployment)
  - make
### 1. Clone the Repository
```bash
git clone git@github.com:abdelrahmenAyman/mdbee-task.git
cd file_receiver
```
### 2. Create Directory to save files
Create a directory in the root of the project called `uploaded_files` or whatever value the env var `FILE_SAVE_DIRECTORY` is set to. This is required for the project to run but it's there just for demonstration of saving files and to make it easier to access uploaded files while testing.
### 3. Run server
- Migrations are run automatically
- Redis server is started inside a docker container
- Django development server is started inside a docker container
- Server accepts connections on localhost:8000
```bash
make run
```
To run compose in detached mode
```bash
make run-detched
```
### 4. Run tests
Runs tests using pytest inside a docker container test.
```bash
make test
```
### 5. Build images manually
```bash
make build
make build-test
```
### 6. Run Migrations manually
```bash
make migrate
```
## Project Usage
### WebSocket Communication
Clients can connect to the WebSocket service using the following URL:

```
ws://localhost:8000/ws/file-transfer/
```
### Frontend
A simple html file is implemented to make uploading files and testing easier. The html contains javascript
code that connects to the websocket. It should be used as follows:

- Navigate to `localhost:8000/` it will return a simple interface with 2 buttons.
- Click the `Choose File` button to select a file from your local file system.
- Click the `Upload File` button to start sending the file over the websocket to the server.
## File Upload Flow:
1. Send File Metadata: The client first sends the file metadata (e.g., file name, file size):
```js
{
  "type": "file_meta",
  "file_name": "example.pdf",
  "file_size": 1048576
}
```
2. After successfully receiving metadata, the server responds indicating successful reception:
```js
{
    "type": "meta_received",
    "message": "Ready to receive file",
}
```
3. Client sends file data in chunks using Base64 encoding:
```js
{
  "type": "file_chunk",
  "chunk": "<Base64 encoded chunk data>"
}
```
4. After each chunk, if the uploaded file size is equal to the size of the communicated size in the meta,
   it responds indicating that the file upload is complete associated with extension field indicating the uploaded file extension:
```js
{
    "type": file_received,
    "message": f"File {file_name} received successfully and file extension is `{file_extension}`",
    "extension": file_extension,
}
```
if there is still another chunk, responds indicating successful reception of chunk:
```js
{
    "type": MessageType.CHUNK_RECEIVED.value,
    "message": "Ready for next chunk",
}
```
5. Any error that happens (e.g., Invalid type, Invalid Json, Invalid size or extension) the server communicates the error:
```js
{
    "type": "error",
    "message": message
}
```
## Security Measures
### Rate Limiting
Each client is rate-limited based on their IP address. If the client exceeds the number of allowed requests in a given period (controlled by environment variables), the server will close the WebSocket connection with a 1008 Policy Violation close code.
#### Rate Limiting Variables:
- RATE_LIMIT_KEY_PREFIX: prefix for key stored in cache.
- RATE_LIMIT_PERIOD: The time window for rate limiting (default: 60 seconds).
- RATE_LIMIT_PER_PERIOD: The maximum number of requests per client per period (default: 1000).
### Sanitizing file names and extension
This is done through ensuring that the file name doesn't contain any non alphanumeric characteres and that the extension is not an executable or any other unkown extension.
## Environment
Environment variables are passed insde the docker-compose environment section for simplicity and ease of use, normally environment shouldn't be included in the codebase, it should be stored on the server and optimally handled by a cloud based tool.For default values look at docker-compose.yml in the environment section.
### Environment variables
- FILE_MAX_SIZE: integer value indicating maximum size of uploaded files in MB.
- FILE_ALLOWED_EXTENSIONS: list of strings including allowed extensions.
- FILE_SAVE_DIRECTORY: string path to directory to save uploaded files.
- REDIS_URL: Redis URL used in caching to track rate limiting and act as backend layer for django channels.
- RATE_LIMIT_PERIOD: integer number of seconds setting the rate limit window.
- RATE_LIMIT_PER_PERIOD: integer setting the maximum number of allowed messages per window or period.
- DEBUG: bool Django debug setting.
- DJANGO_SECRET_KEY: string secret key for django app.
## Assumptions
- WebSocket-Only File Transfer: The service assumes file uploads are exclusively handled via WebSockets and does not account for HTTP-based uploads.
- Rate Limiting Per IP Address: Rate limiting is based on the client's IP address, assuming clients can be uniquely identified by their IPs.
- File Encoding: The client is responsible for encoding files using Base64 before sending file chunks.
- Value set in `FILE_SAVE_DIRECTORY` env variable needs to be created relative to the base directory before running the application.
- Authentication out of scope.
- Messages are delivered in plain text over the web socket because using `wss` requires using a reverse proxy like Ngnix which is out of scope for this task.
