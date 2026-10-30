FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY generator/ generator/
COPY model/ model/
COPY api/ api/
COPY docs/ docs/

# Generate data and train model at build time
RUN python -m generator --seed 20261022 --policies 2000 --claims 1000 --out /app/output \
    && python -m model.train

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health').raise_for_status()"

CMD ["uvicorn", "api.serve:app", "--host", "0.0.0.0", "--port", "8000"]

