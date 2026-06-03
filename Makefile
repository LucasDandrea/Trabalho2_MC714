PY ?= python

.PHONY: help proto install up down logs build clean

help:
	@echo "Targets disponiveis:"
	@echo "  make install   - instala dependencias Python locais (requirements.txt)"
	@echo "  make proto     - gera os stubs gRPC (node_pb2.py / node_pb2_grpc.py) em src/generated"
	@echo "  make build     - builda as imagens Docker"
	@echo "  make up        - sobe o cluster de 5 nos (docker compose up --build)"
	@echo "  make down      - derruba o cluster"
	@echo "  make logs      - segue os logs de todos os nos"
	@echo "  make clean     - remove stubs gerados e caches"

install:
	$(PY) -m pip install -r requirements.txt

proto:
	$(PY) -m grpc_tools.protoc \
		-I proto \
		--python_out=src/generated \
		--grpc_python_out=src/generated \
		proto/node.proto
	@echo "Stubs gerados em src/generated/"

build:
	docker compose build

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f

clean:
	rm -f src/generated/node_pb2.py src/generated/node_pb2_grpc.py src/generated/node_pb2.pyi
	find . -type d -name __pycache__ -exec rm -rf {} +
