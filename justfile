set dotenv-load := true

# List all available commands
_default:
    @just --list --unsorted

# ----------------------------------------------------------------------
# DEPENDENCIES
# ----------------------------------------------------------------------

# Bootstrap local development environment
[group('deps')]
@bootstrap:
    just install

# Setup local environnment
[group('deps')]
setup:
    #!/usr/bin/env bash
    [ ! -d .git ] && git init && git add -A
    mv .rename_to_.github .github > /dev/null 2>&1 || true # needed when project was generated from github
    just bootstrap
    just pre-commit install --install-hooks
    just pre-commit autoupdate
    just migrate
    just createsuperuser
    just lint > /dev/null 2>&1 || true
    echo "DEBUG=True" >> .env

# Install dependencies
[group('deps')]
@install:
    uv sync

# Generate requirements.txt file
[group('deps')]
@lock *ARGS:
    uv export --no-emit-project --output-file=requirements.txt --no-dev {{ ARGS }}

# Generate and upgrade dependencies
[group('deps')]
@upgrade:
    uv sync --upgrade

# Clean up local development environment
[group('deps')]
@clean:
    rm -rf .venv
    rm -f .coverage.*
    rm -rf .mypy_cache
    rm -rf .pytest_cache
    rm -rf .ruff_cache

# ----------------------------------------------------------------------
# TESTING/TYPES
# ----------------------------------------------------------------------

# Run the test suite, generate code coverage, and export html report
[group('test')]
@coverage-html: test
    rm -rf htmlcov
    @uv run python -m coverage html --skip-covered --skip-empty

# Run the test suite, generate code coverage, and print report to stdout
[group('test')]
coverage-report: test
    @uv run python -m coverage report

# Run tests using pytest
[group('test')]
@test *ARGS:
    uv run coverage run -m pytest {{ ARGS }}

# Run mypy on project
[group('test')]
@types:
    uv run python -m mypy .

# Run the django deployment checks
[group('test')]
@deploy-checks:
    just dj check --deploy

# Run continuous integration checks
[group('test')]
@runci:
    just types
    just test
    just deploy-checks
    just collectstatic

# ----------------------------------------------------------------------
# DJANGO
# ----------------------------------------------------------------------

# Run a django management command
[group('django')]
@dj *COMMAND:
    uv run -m koruva {{ COMMAND }}

# Run the django development server
[group('django')]
@serve *ARGS:
    just dj migrate
    uv run honcho -f Procfile.dev start {{ ARGS }}

# Kill the django development server in case the process is running in the background
[group('django')]
@kill-server PORT="8000":
    lsof -i :{{ PORT }} -sTCP:LISTEN -t | xargs -t kill

# Open a Django shell using django-extensions shell_plus command
[group('django')]
@shell:
    just dj shell_plus

alias mm := makemigrations

# Generate Django migrations
[group('django')]
@makemigrations *APPS:
    just dj makemigrations {{ APPS }}

# Run Django migrations
[group('django')]
@migrate *ARGS:
    just dj migrate {{ ARGS }}
    just dj migrate --database tasks_db

# Reset the database
[group('django')]
@reset-db:
    just dj reset_db --noinput

alias su := createsuperuser

# Quickly create a superuser with the provided credentials
[group('django')]
createsuperuser EMAIL="admin@localhost" PASSWORD="admin":
    #!/usr/bin/env bash
    set -euo pipefail
    email="{{ EMAIL }}"
    export DJANGO_SUPERUSER_PASSWORD='{{ PASSWORD }}'
    export DJANGO_SUPERUSER_USERNAME="${email%%@*}"
    just dj createsuperuser --noinput --email "{{ EMAIL }}"

# Generate admin code for a django app
[group('django')]
@admin APP:
    just dj admin_generator {{ APP }} | tail -n +2 > koruva/{{ APP }}/admin.py

# Collect static files
[group('django')]
@collectstatic:
    just dj tailwind --skip-checks build
    just dj collectstatic --no-input --skip-checks

# ----------------------------------------------------------------------
# DOCS
# ----------------------------------------------------------------------

# Build documentation using Sphinx
[group('docs')]
@docs-build LOCATION="docs/_build/html":
    uv run --group docs sphinx-build docs {{ LOCATION }}

# Serve documentation locally
[group('docs')]
@docs-serve:
    uv run --group docs sphinx-autobuild docs docs/_build/html --port 8001

# ----------------------------------------------------------------------
# LINTING / FORMATTING
# ----------------------------------------------------------------------

# Run pre-commit
[group('lint')]
@pre-commit *ARGS:
    uvx --with pre-commit-uv pre-commit {{ ARGS }}

# Run all formatters
[group('lint')]
@fmt:
    just --fmt --unstable
    just pre-commit run ruff-format -a > /dev/null 2>&1 || true
    just pre-commit run pyproject-fmt -a > /dev/null 2>&1 || true
    just pre-commit run reorder-python-imports -a  > /dev/null 2>&1 || true
    just pre-commit run djade -a  > /dev/null 2>&1 || true

# Run pre-commit on all files
[group('lint')]
@lint:
    just pre-commit run --all-files

# ----------------------------------------------------------------------
# BUILD UTILITIES
# ----------------------------------------------------------------------

# Generate changelog
[group('build')]
logchanges *ARGS:
    uvx git-cliff --output CHANGELOG.md {{ ARGS }}

# Bump project version and update changelog
[group('build')]
bumpver VERSION:
    #!/usr/bin/env bash
    set -euo pipefail
    uvx bump-my-version bump {{ VERSION }}
    just logchanges
    [ -z "$(git status --porcelain)" ] && { echo "No changes to commit."; git push && git push --tags; exit 0; }
    version="$(uv run bump-my-version show current_version)"
    git add -A
    git commit -m "Generate changelog for version ${version}"
    git tag -f "v${version}"
    git push && git push --tags

# Build a binary distribution of the project using pyapp
[group('build')]
build-bin:
    #!/usr/bin/env bash
    current_version=$(uv run bump-my-version show current_version)
    uv build
    export PYAPP_UV_ENABLED="1"
    export PYAPP_PYTHON_VERSION="3.12"
    export PYAPP_FULL_ISOLATION="1"
    export PYAPP_EXPOSE_METADATA="1"
    export PYAPP_PROJECT_NAME="koruva"
    export PYAPP_PROJECT_VERSION="${current_version}"
    export PYAPP_PROJECT_PATH="${PWD}/dist/koruva-${current_version}-py3-none-any.whl"
    export PYAPP_DISTRIBUTION_EMBED="1"
    export RUST_BACKTRACE="full"
    cargo install pyapp --force --root dist
    mv dist/bin/pyapp "dist/bin/koruva-${current_version}"

# Build linux binary in docker
[group('build')]
build-linux-bin:
    mkdir dist || true
    docker build -t build-bin-container . -f deploy/Dockerfile.binary
    docker run -it -v "${PWD}:/app" -w /app --name final-build build-bin-container uv build && just build-bin
    docker cp final-build:/app/dist .
    docker rm -f final-build

# Build docker image
[group('build')]
build-docker-image:
    #!/usr/bin/env bash
    set -euo pipefail
    export DEBUG="False"
    current_version=$(uv run bump-my-version show current_version)
    image_name="koruva"
    just install
    docker build -t "${image_name}:${current_version}" -f deploy/Dockerfile .
    docker tag "${image_name}:${current_version}" "${image_name}:latest"
    echo "Built docker image ${image_name}:${current_version}"
