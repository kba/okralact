# Docker tag. Default: '$(DOCKER_TAG)'
DOCKER_TAG = ocrd/okralact

# BEGIN-EVAL makefile-parser --make-help Makefile

help:
	@echo ""
	@echo "  Targets"
	@echo ""
	@echo "    deps-ubuntu            Install Ubuntu dependencies"
	@echo "    deps                   pip3 install -r requirements.txt"
	@echo "    start-worker-train     Start a training worker"
	@echo "    start-worker-eval      Start an evaluation worker"
	@echo "    start-worker-validate  Start validation worker"
	@echo "    start-server           Start redis server"
	@echo "    docker                 Build docker container"
	@echo ""
	@echo "  Variables"
	@echo ""
	@echo "    DOCKER_TAG  Docker tag. Default: '$(DOCKER_TAG)'"

# END-EVAL

# Install Ubuntu dependencies
deps-ubuntu:
	apt-get install -y python3 redis-server

# pip3 install -r requirements.txt
deps:
	pip3 install -r requirements.txt

# Start a training worker
start-worker-train:
	rq worker ocr-tasks

# Start an evaluation worker
start-worker-eval:
	rq worker ocr-evals

# Start validation worker
start-worker-validate:
	rq worker ocr-tasks-valids

# Start redis server
start-server:
	python ocrd.py

# Build docker container
docker:
	docker build -t $(DOCKER_TAG) .
