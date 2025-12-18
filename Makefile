# Makefile

.PHONY: setup start stop clean deploy-minikube cleanup-minikube k8s-logs k8s-status k8s-access k8s-stop-access \
	deploy-swimming-minikube cleanup-swimming-minikube update-swimming-data swimming-status swimming-logs \
	swimming-start-access swimming-stop-access swimming-access

# Install Poetry and its dependencies
install:
	@echo "Installing Poetry..."
	curl -sSL https://install.python-poetry.org | python -
	@echo "Installing dependencies with Poetry..."
	poetry install


setup:
	cd infrastructure/docker && docker-compose build

start:
	cd infrastructure/docker && docker-compose up -d

stop:
	cd infrastructure/docker && docker-compose down

clean:
	cd infrastructure/docker && docker-compose down --rmi all -v --remove-orphans

# Minikube deployment targets
deploy-minikube:
	@echo "Deploying to Minikube..."
	./scripts/deploy-minikube.sh

cleanup-minikube:
	@echo "Cleaning up Minikube deployment..."
	./scripts/cleanup-minikube.sh

k8s-status:
	@echo "Checking Kubernetes status..."
	kubectl get all -n flask-app

k8s-logs:
	@echo "Flask Backend logs:"
	kubectl logs -f deployment/flask-backend -n flask-app --tail=50 &
	@echo "Streamlit Frontend logs:"
	kubectl logs -f deployment/streamlit-frontend -n flask-app --tail=50

k8s-access:
	@echo "Starting local access to Kubernetes apps..."
	./scripts/start-local-access.sh

k8s-stop-access:
	@echo "Stopping local access to Kubernetes apps..."
	./scripts/stop-local-access.sh

# Swimming App Minikube deployment targets
deploy-swimming-minikube:
	@echo "Deploying Swimming App to Minikube..."
	./scripts/deploy-swimming-minikube.sh

cleanup-swimming-minikube:
	@echo "Cleaning up Swimming App from Minikube..."
	./scripts/cleanup-swimming-minikube.sh

update-swimming-data:
	@echo "Updating Swimming App data (rebuilds image and restarts deployment)..."
	./scripts/update-swimming-data.sh

swimming-status:
	@echo "Checking Swimming App Kubernetes status..."
	@echo "Pods:"
	@kubectl get pods -n swimming-app
	@echo ""
	@echo "Services:"
	@kubectl get services -n swimming-app
	@echo ""
	@echo "Deployment:"
	@kubectl get deployment -n swimming-app

swimming-logs:
	@echo "Viewing Swimming App logs (Ctrl+C to exit)..."
	@kubectl logs -f deployment/swimming-app -n swimming-app --tail=50

swimming-start-access:
	@echo "Starting Swimming App access in detached mode..."
	./scripts/start-swimming-access.sh

swimming-stop-access:
	@echo "Stopping Swimming App access..."
	./scripts/stop-swimming-access.sh

swimming-access:
	@echo "Opening Swimming App in browser (foreground mode)..."
	@minikube service swimming-app-service -n swimming-app
