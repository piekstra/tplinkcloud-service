FROM python:3.9

COPY ./app /app

WORKDIR /app

RUN pip install --no-cache-dir --upgrade -r requirements.txt

CMD gunicorn -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT main:app
