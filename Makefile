##
# Enterprise GenAI Platform — Top-level Makefile
# Target: Red Hat OpenShift AI 3.x
##

.PHONY: help infra-bootstrap deploy verify-all lint test clean

PROJECTS := 01-rag-knowledge-assistant 02-multi-agent-platform 03-llm-finetuning-pipeline 04-document-intelligence 05-observability-guardrails
ENV ?= dev
IMAGE_REGISTRY ?= quay.io/enterprise
IMAGE_TAG ?= $(shell git rev-parse --short HEAD 2>/dev/null || echo "latest")

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

# ─── Infrastructure ───────────────────────────────────────────────────────────

infra-bootstrap: ## Bootstrap all shared infrastructure (namespaces, RHOAI, RBAC)
	@echo "==> Applying namespaces..."
	oc apply -f infrastructure/openshift/namespaces.yaml
	@echo "==> Applying RBAC..."
	oc apply -f infrastructure/openshift/rbac.yaml
	@echo "==> Applying NetworkPolicies..."
	oc apply -f infrastructure/openshift/network-policies.yaml
	@echo "==> Applying ResourceQuotas..."
	oc apply -f infrastructure/openshift/resource-quotas.yaml
	@echo "==> Deploying RHOAI DataScienceCluster..."
	oc apply -f infrastructure/rhoai/datasciencecluster.yaml
	@echo "==> Waiting for RHOAI to become ready..."
	oc wait --for=condition=ready datasciencecluster/default-dsc --timeout=600s || true
	@echo "==> Applying serving runtimes..."
	oc apply -f infrastructure/rhoai/serving-runtimes/
	@echo "Infrastructure bootstrap complete."

# ─── Deployment ───────────────────────────────────────────────────────────────

deploy: ## Deploy a specific project: make deploy PROJECT=01-rag-knowledge-assistant ENV=production
ifndef PROJECT
	$(error PROJECT is required. Usage: make deploy PROJECT=<name> ENV=<env>)
endif
	@echo "==> Deploying $(PROJECT) to $(ENV)..."
	oc apply -k projects/$(PROJECT)/deploy/kustomize/overlays/$(ENV)
	@echo "==> Waiting for rollout..."
	oc rollout status deployment/$(shell echo $(PROJECT) | sed 's/^[0-9]*-//') \
		-n $(shell echo $(PROJECT) | sed 's/^[0-9]*-//') \
		--timeout=300s
	@echo "$(PROJECT) deployed to $(ENV)."

deploy-all: ## Deploy all projects to ENV (default: dev)
	@for project in $(PROJECTS); do \
		echo "==> Deploying $$project to $(ENV)..."; \
		oc apply -k projects/$$project/deploy/kustomize/overlays/$(ENV) || exit 1; \
	done
	@echo "All projects deployed to $(ENV)."

# ─── Images ───────────────────────────────────────────────────────────────────

build: ## Build a project image: make build PROJECT=01-rag-knowledge-assistant
ifndef PROJECT
	$(error PROJECT is required)
endif
	podman build -t $(IMAGE_REGISTRY)/$(shell echo $(PROJECT) | sed 's/^[0-9]*-//'):$(IMAGE_TAG) \
		-f projects/$(PROJECT)/Dockerfile \
		projects/$(PROJECT)/

push: ## Push a project image to Quay
ifndef PROJECT
	$(error PROJECT is required)
endif
	podman push $(IMAGE_REGISTRY)/$(shell echo $(PROJECT) | sed 's/^[0-9]*-//'):$(IMAGE_TAG)

build-all: ## Build all project images
	@for project in $(PROJECTS); do \
		name=$$(echo $$project | sed 's/^[0-9]*-//'); \
		echo "==> Building $$name..."; \
		podman build -t $(IMAGE_REGISTRY)/$$name:$(IMAGE_TAG) \
			-f projects/$$project/Dockerfile projects/$$project/ || exit 1; \
	done

# ─── GitOps ───────────────────────────────────────────────────────────────────

gitops-bootstrap: ## Register all ArgoCD applications
	oc apply -f gitops/applications/genai-platform-apps.yaml
	argocd app sync --selector app.kubernetes.io/part-of=genai-platform

# ─── Verification ─────────────────────────────────────────────────────────────

verify-all: ## Health-check all deployed services
	@echo "==> Verifying RAG Knowledge Assistant..."
	@oc get pods -n rag-knowledge-assistant -l app=rag-knowledge-assistant
	@echo "==> Verifying Multi-Agent Platform..."
	@oc get pods -n multi-agent-platform -l app=multi-agent-platform
	@echo "==> Verifying Document Intelligence..."
	@oc get pods -n document-intelligence -l app=document-intelligence
	@echo "==> Verifying Observability & Guardrails..."
	@oc get pods -n observability-guardrails -l app=observability-guardrails
	@echo "==> RHOAI InferenceServices..."
	@oc get inferenceservice -n rhoai-model-serving

# ─── Development ──────────────────────────────────────────────────────────────

lint: ## Lint all Python code
	@for project in $(PROJECTS); do \
		if [ -f "projects/$$project/requirements.txt" ]; then \
			echo "==> Linting $$project..."; \
			cd projects/$$project && python -m ruff check app/ && cd ../../; \
		fi; \
	done

test: ## Run unit tests for a project: make test PROJECT=01-rag-knowledge-assistant
ifndef PROJECT
	$(error PROJECT is required)
endif
	cd projects/$(PROJECT) && python -m pytest tests/ -v --tb=short

install-dev: ## Install dev dependencies
	pip install ruff pytest pytest-asyncio httpx

clean: ## Remove compiled Python files
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; \
	find . -name "*.pyc" -delete
