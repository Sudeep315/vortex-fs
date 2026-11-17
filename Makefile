.PHONY: help install start test benchmark docker-up docker-down clean

help:
	@echo "VortexFS - Event-Driven Real-Time Feature Store"
	@echo "-----------------------------------------------"
	@echo "make install     : Install dependencies in editable mode"
	@echo "make start       : Start API server and interactive Web Dashboard"
	@echo "make test        : Run full automated pytest test suite"
	@echo "make benchmark   : Run throughput and latency benchmarks"
	@echo "make docker-up   : Launch Docker Compose (API + Redis + ClickHouse)"
	@echo "make docker-down : Stop Docker Compose"
	@echo "make clean       : Clean temporary cache files"

install:
	pip install -e .

start:
	python start.py

test:
	pytest -v

benchmark:
	python benchmarks/benchmark_serving.py

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down

clean:
	rm -rf .pytest_cache build dist *.egg-info __pycache__ vortex/**/__pycache__
