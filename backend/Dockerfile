FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Minimal runtime deps for the scaffold API + migrations.
RUN pip install --no-cache-dir \
    Flask==3.0.2 \
    python-dotenv==1.0.1 \
    psycopg[binary]==3.2.3 \
    SQLAlchemy==2.0.30 \
    alembic==1.13.1

COPY . /app

EXPOSE 8000

# The compose services provide the command (api vs worker).
