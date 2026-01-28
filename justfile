import './helm.just'

default:
    @just -l


tag VERSION:
    @git tag -s services-api-helm-chart-v{{VERSION}} -m "Release new services-api helm chart v{{VERSION}}"

# Install deployment tool dependencies in .venv
install-deploy-tool:
    @echo "Installing deployment tool dependencies..."
    cd docker/deployment-tool && uv sync --extra dev

# Lint deployment tool with ruff
lint-deploy-tool: format-deploy-tool
    @echo "Linting deployment tool..."
    cd docker/deployment-tool && uvx ruff check src/

# Format deployment tool with ruff
format-deploy-tool:
    @echo "Formatting deployment tool..."
    cd docker/deployment-tool && uvx ruff format src/

# Build deployment tool package
build-deploy-tool:
    @echo "Building deployment tool package..."
    cd docker/deployment-tool && uvx --from build pyproject-build .

# Test deployment tool with pytest
test-deploy-tool:
    @echo "Testing deployment tool..."
    cd docker/deployment-tool && uv run --extra dev pytest -v
