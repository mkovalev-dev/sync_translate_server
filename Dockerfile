FROM python:3.12.0-slim-bullseye as python

FROM python as python-lib-stage
ARG APP_HOME=/app

ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1
# poetry:

ENV POETRY_VIRTUALENVS_CREATE false
ENV POETRY_CACHE_DIR '/var/cache/pypoetry'

WORKDIR ${APP_HOME}

# System deps:
RUN apt-get update && apt-get install --no-install-recommends -y \
  # dependencies for building Python packages
  build-essential \
  # psycopg2 dependencies
  libpq-dev \
  ffmpeg

FROM python-lib-stage as python-deps-stage

RUN pip install --upgrade pip==23.3
RUN pip install poetry

COPY ./pyproject.toml .
COPY ./poetry.lock .

RUN poetry install
RUN pip3 install vosk
#RUN pip install https://github.com/alphacep/vosk-api/releases/download/v0.3.42/vosk-0.3.42-py3-none-linux_aarch64.whl

FROM python-deps-stage as python-copy-stage

COPY . ${APP_HOME}
RUN pip3 install uvicorn googletrans
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]