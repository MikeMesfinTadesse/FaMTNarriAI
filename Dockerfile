# ═══════════════════════════════════════════════════════════════
# FaMTNarriAI — Dockerfile (multi-stage build)
#
# WHAT IS DOCKER?
#   Docker packages your app into a container — a self-contained box
#   that runs identically on any computer: Windows, Mac, Linux, cloud.
#
#   "It works on my machine" stops being a problem forever.
#
# MULTI-STAGE BUILD (why we have two FROM statements):
#   Stage 1 "builder" — installs everything, including build tools
#   Stage 2 "final"   — copies only what's needed, no build junk
#   Result: final image is ~40% smaller, faster to download/deploy
#
# HOW TO BUILD AND RUN:
#   docker build -t famtnarriai .
#   docker run -v $(pwd)/output:/app/output famtnarriai --cli --input book.pdf
#   docker run famtnarriai --help
# ═══════════════════════════════════════════════════════════════

# ── Stage 1: Builder ────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
# We copy requirements.txt FIRST — Docker caches this layer.
# If requirements.txt hasn't changed, pip install is skipped on rebuild.
COPY requirements.txt .
RUN pip install --no-cache-dir --user \
    edge-tts \
    pymupdf \
    deep-translator


# ── Stage 2: Final image ────────────────────────────────────────
FROM python:3.11-slim AS final

LABEL maintainer="FaMTNarriAI Team"
LABEL description="FaMTNarriAI — PDF to Audiobook Converter (CLI mode)"
LABEL version="1.4.0"

WORKDIR /app

# Copy installed packages from builder stage only
COPY --from=builder /root/.local /root/.local

# Copy application code (not the whole repo — just what's needed)
COPY core/     ./core/
COPY main.py   .

# Output directory for converted MP3 files
# Mount your local folder here:  -v $(pwd)/output:/app/output
RUN mkdir -p /app/output

# Python environment settings
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PATH=/root/.local/bin:$PATH

# Run as non-root user for security (good practice)
RUN useradd --create-home --shell /bin/bash narrauser
RUN chown -R narrauser:narrauser /app
USER narrauser

# Default: show help. Override with your own args.
ENTRYPOINT ["python", "main.py", "--cli"]
CMD ["--help"]
