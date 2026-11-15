FROM python:3.12.15-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY assistente/ assistente/
COPY convertitore_mcp/ convertitore_mcp/
COPY scadenze_api/ scadenze_api/
# Back-end e front-end solo per eseguire tutta la suite di test nel container.
COPY backend/ backend/
COPY frontend/ frontend/
COPY tests/ tests/
COPY pyproject.toml preferenze.json ./

# Utente non root; /app gli appartiene così pytest può scrivere .pytest_cache.
# /app/note è il punto di montaggio del volume delle note: un volume nuovo ne eredita il proprietario.
RUN useradd --create-home app && mkdir /app/note && chown app:app /app /app/note
USER app

CMD ["python", "-m", "assistente"]
