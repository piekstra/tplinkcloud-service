# API

This project uses your Kasa credentials to make queries to the TP-Link Cloud API

## Prerequisites

### Uvicorn

Uvicorn is an HTTP server implementation.

Read more about Uvicorn [here](https://www.uvicorn.org/).

## Environment

You may need to setup environment variables with proper values in a `.env` file. There is a [`.env.example`](app/configuration/.env.example) provided as an example of what variables to specify, if any.

## Running the API for Development

From the [app](app) folder, you can simply run `uvicorn main:app --reload` to serve the API in development mode.

The app's Swagger page will then be available at http://localhost:8000/docs

### Running as a Docker Container

You can leverage the [`Dockerfile`](Dockerfile) to run the API using the following command which will build the docker container image and run it:

```sh
docker build . -t apiserver

docker run -d \
    -p 80:80 \
    apiserver
```

The API will be available at: http://localhost/

This can be useful to leverage the same process as the GitHub Actions Workflow for packaging the Python code.
