FROM python:3.9-slim

# Install system deps for Playwright
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
      libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
      libxrandr2 libgbm1 libasound2 libpangocairo-1.0-0 \
      libgtk-3-0 ca-certificates wget && \
    rm -rf /var/lib/apt/lists/*

# Python deps
RUN pip install --no-cache-dir \
      playwright paho-mqtt schedule && \
    playwright install --with-deps

# Add launcher & main script
COPY run.sh /run.sh
COPY run.py /run.py
RUN chmod +x /run.sh

CMD [ "/run.sh" ]
