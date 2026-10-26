FROM python:3.12.15-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY assistente/ assistente/
COPY tests/ tests/
COPY pyproject.toml ./

# Utente non root; /app gli appartiene così pytest può scrivere .pytest_cache.
RUN useradd --create-home app && chown app:app /app
USER app

CMD ["python", "-m", "assistente"]
