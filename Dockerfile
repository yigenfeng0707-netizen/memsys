FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py config.py llm.py store.py pipeline.py extract.py ./
RUN mkdir -p data

EXPOSE 7860
ENV MEMSYS_PORT=7860

CMD ["sh", "-c", "python -m uvicorn server:app --host 0.0.0.0 --port ${MEMSYS_PORT}"]
