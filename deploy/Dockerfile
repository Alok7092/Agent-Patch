FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY src/ src/
COPY config/ config/
COPY templates/ templates/
COPY static/ static/
RUN mkdir -p data/landscape

EXPOSE 8000

CMD ["uvicorn", "src.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
