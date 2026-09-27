.PHONY: help install test up down logs clean run-gateway run-user run-agent run-frontend install-frontend

help:
	@echo "Comandos disponíveis:"
	@echo "  make install          - Instala dependências Python e Node.js"
	@echo "  make install-frontend - Instala dependências do frontend (npm install)"
	@echo "  make run-frontend     - Executa o frontend React localmente (porta 3000)"
	@echo "  make test             - Executa a suíte de testes de validação da PoC"
	@echo "  make up               - Sobe todos os 4 serviços via Docker Compose"
	@echo "  make down             - Derruba os serviços do Docker Compose"
	@echo "  make logs             - Exibe os logs dos serviços do Docker Compose"
	@echo "  make clean            - Remove caches e banco de dados local temporário"

install:
	pip install --upgrade pip
	pip install -e libs/common
	pip install -r requirements.txt
	cd services/frontend-service && npm install

install-frontend:
	cd services/frontend-service && npm install

run-frontend:
	cd services/frontend-service && npm run dev

test:
	pytest -v tests/

up:
	docker compose up --build -d

down:
	docker compose down -v

logs:
	docker compose logs -f

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -f pix_guard.db test.db
