set dotenv-load

list:
    @just --list

test:
    poetry run python -m pytest -v .

run *argv:
    poetry run mipc_camera_client {{argv}}

format:
    poetry run black mipc_camera_client/ tests/

build:
    poetry build

clean:
    rm -rf dist/
