FROM python:3.12-slim-bookworm AS base
ENV CODE=/code
ENV PYTHONUNBUFFERED=1
RUN apt-get -o Acquire::Retries=3 update && \
    apt-get -o Acquire::Retries=3 install -y --no-install-recommends git libgomp1 && \
    rm -rf /var/lib/apt/lists/*
WORKDIR $CODE
COPY pyproject.toml uv.lock ./
ENV UV_PROJECT_ENVIRONMENT=/usr/local/
RUN --mount=from=ghcr.io/astral-sh/uv,source=/uv,target=/bin/uv \
    uv sync --locked --no-cache --compile-bytecode --no-dev
COPY bsentinel/ bsentinel/
CMD ["python", "-m", "bsentinel.infrastructure.api"]

FROM base AS production
COPY . $CODE
