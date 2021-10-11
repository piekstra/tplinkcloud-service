# API

This project uses your Kasa credentials to make queries to the TP-Link Cloud API

## Prerequisites

### TP-Link Cloud Account

These services are require a TP-Link Cloud account. 

If you are new to TP-Link Kasa products, you can start by creating an account [here](https://www.tplinkcloud.com/register.php). These credentials are used for authentication in the `/api/v1/user/token` workflow.

### Python 3.7+

This project is built and tested with Python 3.7, 3.8, and 3.9. 

Download the latest version of Python [here](https://www.python.org/downloads/).

### Gunicorn

Gunicorn is a Python WSGI HTTP Server for UNIX which will be installed by running `pip install -r requirements.txt` from a terminal running in the [app directory](./app/).

Read more about Gunicorn [here](https://gunicorn.org/).

## Environment

You may need to setup environment variables with proper values in a `.env` file. There is a [`.env.example`](app/configuration/.env.example) provided as an example of what variables to specify, if any.

## Running the API for Development

From the [app](app) folder, you can simply run `gunicorn -k uvicorn.workers.UvicornWorker main:app --reload` to serve the API in development mode.

The app's Swagger page will then be available at http://localhost:8000/docs

### Running as a Docker Container

You can leverage the [`Dockerfile`](Dockerfile) to run the API using the following command which will build the docker container image and run it:

```sh
docker build . -t apiserver

docker run -d \
    -e PORT=80 \
    -p 80:80 \
    apiserver
```

The API will be available at: http://localhost/

This can be useful to leverage the same process as the GitHub Actions Workflow for packaging the Python code.

## Service Discovery

Swagger is available at the `/docs` URL. If running locally, this would be accessed [here](http://localhost:8000/docs), otherwise if run as a docker container, [here](http://localhost/docs).

## Authentication

A consumer must first POST to the `/api/v1/user/token` endpoint with valid TPLinkCloud account credentials as the POST data. An example curl request might look as follows:

```sh
curl -X 'POST' \
    'http://localhost:8000/api/v1/user/token' \
    -H 'accept: application/json' \
    -H 'Content-Type: application/x-www-form-urlencoded' \
    -d 'grant_type=&username=USER%40EMAIL.com&password=PASSWORD'
```

Subsequent API calls require an HTTP header value using the token provided by the output of the `/api/v1/user/token` call. An example curl request with the authentication bearer token provided might look as follows

```sh
curl -X 'GET' \
  'http://localhost:8000/api/v1/power/devices/current?named=X' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer 77eee444-ATMdNs6Qy3woK7FM2MaGMar'
```

### Swagger Authentication

If calling the API through the Swagger documentation page, the consumer must first use the Authorize button at the top right passing the email and password credentials. Once authenticated in Swagger, subsequent calls do not currently require further identity context to be entered manually as they will be provided by the Swagger web client.

## Service Deployment

This service is currently deployed as a Heroku App and should be available [here][heroku-deployment].

> Note that the `$PORT` environment variable indicated in the [`Dockerfile`](Dockerfile) is provided by Heroku per the documentation found [here](https://devcenter.heroku.com/articles/container-registry-and-runtime#get-the-port-from-the-environment-variable). For Heroku, the port is dynamic behind the scenes but for accessing the app's domain, no port specification is needed.


[heroku-deployment]: https://tplinkcloud-service.herokuapp.com/docs
