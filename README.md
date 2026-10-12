$ git clone https://github.com/Vikhthor/trakla.git
$ uv venv
$ source .venv/bin/activate
$ uv sync

# For dev
$ uv run fastapi dev # OR fastapi dev

# For Prod
$ uv run fastapi run --port 8080 # OR fastapi run --port 8080