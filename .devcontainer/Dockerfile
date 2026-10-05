# -----------------------------------------------------------------------------
# Devcontainer (private setup: no corporate certificates / proxy)
# -----------------------------------------------------------------------------

FROM python:3.12-slim-bookworm AS base

# ---- Builder stage: build the venv ----
FROM base AS builder
WORKDIR /app

COPY src/requirements.txt .
RUN python -m venv .venv \
    && .venv/bin/pip install --no-cache-dir --upgrade pip setuptools \
    && .venv/bin/pip install --no-cache-dir -r requirements.txt

# ---- Devcontainer stage ----
FROM base AS devcontainer

# -- Timezone --
ENV TZ='Europe/Berlin'
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# -- OS packages --
RUN apt-get update \
    && export DEBIAN_FRONTEND=noninteractive \
    && apt-get install --no-install-recommends -y \
       bash git tree locales curl ca-certificates tar gzip \
       ncurses-bin ncurses-term passwd adduser \
    # only generate the locales we need (~100MB saved)
    && sed -i 's/^# *en_US.UTF-8/en_US.UTF-8/' /etc/locale.gen \
    && sed -i 's/^# *de_DE.UTF-8/de_DE.UTF-8/' /etc/locale.gen \
    && locale-gen \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV LC_ALL=en_US.UTF-8
ENV LANG=en_US.UTF-8

WORKDIR /app

# -- Non-root user --
ARG USERNAME=app
ARG USER_UID=1001
ARG USER_GID=$USER_UID
RUN addgroup --gid ${USER_GID} ${USERNAME} \
    && adduser --uid ${USER_UID} --gid ${USER_GID} --disabled-password --gecos "" --home /home/${USERNAME} ${USERNAME} \
    && mkdir -p /workspaces \
    && chown -R ${USERNAME}:${USERNAME} /app /workspaces

# -- venv from builder --
COPY --from=builder --chown=app:app /app /app

ENV PATH="/app/.venv/bin:$PATH"
# live source folder (mounted repo)
ENV PYTHONPATH="/workspaces/app/src"
ENV PYTHONUNBUFFERED=1

USER app
