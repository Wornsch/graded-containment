ARG PYTHON_VERSION=3.14
ARG NODE_VERSION=24
FROM node:${NODE_VERSION}-trixie-slim AS node-tools

FROM mcr.microsoft.com/devcontainers/python:${PYTHON_VERSION}-trixie AS workspace

ENV PATH="/home/vscode/.local/bin:${PATH}"
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl git openssh-client \
    && rm -rf /var/lib/apt/lists/*

COPY --from=node-tools /usr/local/bin/node /usr/local/bin/node
COPY --from=node-tools /usr/local/lib/node_modules /usr/local/lib/node_modules
ARG NPM_VERSION
RUN ln -sf ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -sf ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && if [ -n "$NPM_VERSION" ]; then npm install --global "npm@$NPM_VERSION"; fi
