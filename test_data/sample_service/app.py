from fastapi import FastAPI

app = FastAPI()


@app.get("/orders")
def list_orders() -> list[dict[str, str]]:
    return load_orders_from_database()


def load_orders_from_database() -> list[dict[str, str]]:
    # The investigation should check whether this creates a new connection per request.
    connection = open_database_connection()
    return connection.query("SELECT id, status FROM orders")


def open_database_connection():
    raise NotImplementedError
