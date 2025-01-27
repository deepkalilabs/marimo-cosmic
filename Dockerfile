# syntax=docker/dockerfile:1.12
FROM python:3.13-slim AS base

# Copy the entire project
COPY . .


# Install dependencies (including dev extras)
RUN pip install -e ".[dev]"

ENV PORT=2718
EXPOSE $PORT

ENV HOST=0.0.0.0

CMD marimo edit --no-token -p $PORT --host $HOST

# -data entry point
FROM base AS data
RUN pip install --no-cache-dir altair pandas numpy
CMD marimo edit --no-token -p $PORT --host $HOST

# -sql entry point, extends -data
FROM data AS sql
RUN pip install --no-cache-dir marimo[sql]
CMD marimo edit --no-token -p $PORT --host $HOST
