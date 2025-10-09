FROM mcr.microsoft.com/devcontainers/base:ubuntu

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       software-properties-common \
       curl \
       ca-certificates \
       git \
       build-essential \
       python3.11 \
       python3.11-dev \
       python3.11-venv \
       python3.11-distutils \
       pipx \
    && rm -rf /var/lib/apt/lists/*

RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1
RUN python3 -m ensurepip --upgrade
RUN python3 -m pip install --upgrade pip setuptools wheel

# Install Node.js 20
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get update \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/root/.local/bin:${PATH}"

RUN npm install -g pnpm
RUN pipx ensurepath
RUN pipx install poetry
RUN pipx install pre-commit

RUN corepack enable
