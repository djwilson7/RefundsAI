FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY apps/api/requirements.txt apps/api/requirements.txt
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r apps/api/requirements.txt

COPY apps/api/src apps/api/src

ENV PYTHONPATH=/app/apps/api/src

EXPOSE 8000
CMD ["python", "-m", "uvicorn", "refunds_ai_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
