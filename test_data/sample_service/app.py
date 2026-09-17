from fastapi import FastAPI

app = FastAPI()


@app.get("/orders")
def list_orders() -> list[dict[str, str]]:
    orders = load_orders_from_database()
    return enrich_orders(orders)


def load_orders_from_database() -> list[dict[str, str]]:
    # The investigation should check whether this creates a new connection per request.
    connection = open_database_connection()
    return connection.query("SELECT id, status, customer_id FROM orders")


def enrich_orders(orders: list[dict[str, str]]) -> list[dict[str, str]]:
    enriched_orders: list[dict[str, str]] = []

    for order in orders:
        # This per-order lookup creates an N+1 query pattern.
        customer = load_customer_from_database(order["customer_id"])

        # Comparing every order to every other order is O(n^2) per request.
        related_order_count = sum(
            candidate["customer_id"] == order["customer_id"] for candidate in orders
        )
        enriched_orders.append(
            {
                **order,
                "customer_name": customer["name"],
                "related_order_count": str(related_order_count),
            }
        )

    return enriched_orders


def load_customer_from_database(customer_id: str) -> dict[str, str]:
    connection = open_database_connection()
    return connection.query_one(
        "SELECT id, name FROM customers WHERE id = ?", [customer_id]
    )


def open_database_connection():
    raise NotImplementedError
