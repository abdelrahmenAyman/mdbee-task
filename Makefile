# Variables
DOCKER_COMPOSE = docker-compose
DOCKER_COMPOSE_FILE = docker-compose.yml
DOCKER_COMPOSE_TEST_FILE = docker-compose.test.yml

# Default target (starts the server)
.PHONY: run
run: migrate  ## Run the Django server and apply migrations automatically
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) up

# Run the Django server in detached mode
.PHONY: run-detached
run-detached: migrate  ## Run the Django server in detached mode and apply migrations automatically
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) up -d

# Run tests
.PHONY: test
test:
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_TEST_FILE) up --abort-on-container-exit

# Apply migrations
.PHONY: migrate
migrate:
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) run web ./manage.py migrate

# Build the Docker image before starting it
.PHONY: build
build:
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) up --build

# Stop all running containers
.PHONY: stop
stop:  ## Stop all running containers
	$(DOCKER_COMPOSE) down

# Remove all containers, networks, and volumes
.PHONY: clean
clean: stop  ## Remove all containers, networks, and volumes
	$(DOCKER_COMPOSE) down -v
