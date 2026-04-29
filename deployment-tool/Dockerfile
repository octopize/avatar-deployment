FROM python:3.13-slim AS builder
WORKDIR /build
COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN pip install --no-cache-dir hatchling && \
    pip wheel --no-cache-dir --no-deps -w dist .

FROM python:3.13-slim
ARG GIT_SHA
ARG GIT_REF
LABEL org.opencontainers.image.revision="${GIT_SHA}"
LABEL org.opencontainers.image.source="https://github.com/octopize/avatar-deployment"
COPY --from=builder /build/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm /tmp/*.whl
ENTRYPOINT ["octopize-deploy-tool"]
