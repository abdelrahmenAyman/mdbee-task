# Base image with Python 3.12
FROM python:3.12.7

# Expose port 8000 for the Django app
EXPOSE 8000

# Environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV POETRY_VERSION=1.5.1

# Set a working directory
WORKDIR /app

# Install system dependencies and Poetry
RUN apt-get update && apt-get install -y curl && \
    curl -sSL https://install.python-poetry.org | python3 - && \
    ln -s /root/.local/bin/poetry /usr/local/bin/poetry

# Copy Poetry files to install dependencies
COPY pyproject.toml poetry.lock ./

# Install project dependencies using Poetry
RUN poetry config virtualenvs.create false --local && poetry install --no-dev

# Create a non-root user with group
RUN groupadd -r appgroup && useradd -r -g appgroup -u 1000 appuser

# Switch to non-root user
USER appuser

# Copy the project files last to benefit from Docker layer caching
COPY . .

# Run the Django server
CMD ["./manage.py", "runserver", "0.0.0.0:8000"]
