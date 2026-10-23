.PHONY: up-tuned check-tuned pull-model reset help install test seed up down logs clean run-gateway run-user run-agent run-frontend install-frontend run-laya-mac

help:
	@echo "Comandos disponíveis:"
	@echo "  make install          - Instala dependências Python e Node.js"
	@echo "  make install-frontend - Instala dependências do frontend (npm install)"
	@echo "  make run-frontend     - Executa o frontend React localmente (porta 3000)"
	@echo "  make run-laya-mac     - Executa o Laya FP32 nativo no Mac com Apple Silicon GPU (MPS)"
	@echo "  make test             - Executa a suíte de testes de validação da PoC"
	@echo "  make seed             - Reseta e regenera a base de dados com usuários de teste"
	@echo "  make up               - Sobe os serviços com o Laya original (Ollaya)"
	@echo "  make up-tuned         - Sobe também o Laya retreinado (seletor no frontend)"
	@echo "  make check-tuned      - Verifica se o checkpoint do Laya retreinado está instalado"
	@echo "  make pull-model       - Baixa o modelo laya:multilingual no Ollaya (se ainda não existir) e o carrega"
	@echo "  make down             - Derruba os serviços (preserva modelo e banco)"
	@echo "  make reset            - Derruba os serviços E apaga volumes (modelo do Ollaya e banco)"
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

run-laya-mac:
	./scripts/run_native_laya_mac.sh

PYTHON ?= $(shell if [ -f .venv/bin/python ]; then echo .venv/bin/python; else echo python3; fi)
PYTEST ?= $(shell if [ -f .venv/bin/pytest ]; then echo .venv/bin/pytest; else echo pytest; fi)

test:
	$(PYTEST) -v tests/

seed:
	@$(PYTHON) scripts/seed_db.py --target all

up:
	docker compose up --build -d
	@$(MAKE) --no-print-directory pull-model

check-tuned:
	@test -f finetune/models/pix-threats/model.safetensors \
	  && test -f finetune/models/pix-threats/rl_agent_config.json \
	  && echo "OK: checkpoint encontrado em finetune/models/pix-threats" \
	  || (echo "Faltando finetune/models/pix-threats/{model.safetensors,rl_agent_config.json,tokenizer,encoder}. Veja finetune/README.md"; exit 1)

up-tuned: check-tuned
	docker compose up --build -d
	@$(MAKE) --no-print-directory pull-model

# O modelo fica no volume `ollaya_models`, não na imagem. Sem ele toda chamada retorna MODEL_NOT_FOUND
# e o gateway aprova os Pix sem análise.
pull-model:
	@echo "Aguardando o Ollaya..."
	@for i in $$(seq 1 30); do \
	  docker exec pix-ollaya ollaya list >/dev/null 2>&1 && break; sleep 2; \
	done
	@docker exec pix-ollaya ollaya list 2>/dev/null | grep -q "laya:multilingual" \
	  && echo "OK: laya:multilingual já está instalado" \
	  || (echo "Baixando laya:multilingual (~700 MB)..." && docker exec pix-ollaya ollaya pull laya:multilingual)
	@$(PYTHON) scripts/register_native_laya.py

down:
	docker compose down

reset:
	docker compose down -v

logs:
	docker compose logs -f

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -f pix_guard.db test.db
