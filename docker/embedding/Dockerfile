FROM pytorch/pytorch:2.6.0-cuda12.4-cudnn9-runtime

WORKDIR /app

RUN pip install --no-cache-dir \
    fastapi==0.115 \
    uvicorn==0.30 \
    sentence-transformers==3.0

COPY server.py .

EXPOSE 8081

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8081"]
