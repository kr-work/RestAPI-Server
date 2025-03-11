# New Server For Digital Curling

This is a new server for digital curling. It is a work in progress, but this server can only run one match yet.

## Dependencies

- Python 3.11 (or later)
- Docker
- Docker Compose
- FastAPI
- Uvicorn
- Gunicorn
- Pydantic
- SQLAlchemy

## Setup and Development

1. first you need to install docker and docker-compose, then pull this repository.
1. Create a `.env` file in the root of the project and add the following variables:

    ```bash
    POSTGRES_USER=your_user
    POSTGRES_PASSWORD=your_password
    POSTGRES_DB=your_db
    POSTGRES_HOST=your_host
    POSTGRES_PORT=your_port
    ```

1. Create docker network:

    ```bash
    docker network create dc_network
    ```

1. If you want to run dc-server in production env, run the following command (but this not tested yet):

    ```bash
    docker compose up
    ```

1. If you want to run dc-server in development env, run the following command:

    ```bash
    docker compose -f docker-compose.yml -f docker-compose.dev.yml up
    ```

    or

    ```bash
    docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
    ```

    In development mode, changes in the code will be reflected in the server automatically.

    If you don't want to see the logs, you can run the server in daemon mode with the `-d` flag.

## For developpers

### Generate requirements.txt

```bash
uv pip compile pyproject.toml -o requirements.txt
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## TODOs

- [ ] Add tests
- [ ] Preparation for operation in a production environment
- [ ] Develop a mode for multiple simultaneous matches in Webhook
- [ ] Develop a match mode in RESTAPI
- [ ] Add REST API for GUI, and tumeshogi mode and so on...
