# ai-server API image.
# python:3.13-slim to match your local interpreter -- "works on my machine"
# bugs often hide in version gaps, so don't introduce one voluntarily.
FROM python:3.13-slim

# Never run as root in a container you'll expose to the internet.
RUN useradd --create-home appuser
WORKDIR /app

# Dependencies first, code second: Docker caches layers top-down, so as
# long as requirements.txt is unchanged, rebuilds after a code edit skip
# the slow pip install entirely. This ordering is THE Dockerfile idiom.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Now the code. .dockerignore keeps venv/, eval_runs/, client/ out.
COPY --chown=appuser:appuser . .

USER appuser
EXPOSE 8000

# Migrations run at startup, THEN the server starts. If alembic fails,
# the container exits loudly instead of serving against a stale schema --
# a crash here is a feature (see: silent failures, passim).
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]