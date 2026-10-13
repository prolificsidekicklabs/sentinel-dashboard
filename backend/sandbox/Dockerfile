# No mutable base-image tag is supplied; build only with an operator-verified image digest.
ARG PYTHON_BASE_IMAGE
FROM ${PYTHON_BASE_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONNOUSERSITE=1 \
    PYTHONPATH=/opt/sentinel \
    PYTHONUNBUFFERED=1

RUN mkdir -p /opt/sentinel/sentinel_core \
    && python -m pip install --no-cache-dir --disable-pip-version-check 'pydantic==2.14.1' \
    && useradd --system --uid 65532 --no-create-home sentinel

COPY src/sentinel_core/__init__.py \
     src/sentinel_core/contracts.py \
     src/sentinel_core/worker.py \
     /opt/sentinel/sentinel_core/

USER 65532:65532
WORKDIR /tmp
CMD ["python", "-m", "sentinel_core.worker"]
