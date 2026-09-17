"""Generate a synthetic opening-bell load burst."""

import argparse
import asyncio
from collections import Counter
from time import perf_counter

import httpx


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--customers", type=int, default=250)
    parser.add_argument("--concurrency", type=int, default=40)
    return parser.parse_args()


async def run_load(base_url: str, customers: int, concurrency: int) -> None:
    """Send concurrent advice requests and print a compact result."""

    semaphore = asyncio.Semaphore(concurrency)
    statuses: Counter[int] = Counter()
    latencies: list[float] = []

    async with httpx.AsyncClient(base_url=base_url, timeout=30) as client:

        async def send(customer_number: int) -> None:
            async with semaphore:
                started = perf_counter()
                response = await client.post(
                    f"/api/portfolios/CUST-{customer_number:05d}/advise",
                    json={
                        "concern": (
                            "Will advice complete during the opening bell?"
                        )
                    },
                )
                statuses[response.status_code] += 1
                latencies.append((perf_counter() - started) * 1_000)

        await asyncio.gather(
            *(send(customer_number) for customer_number in range(customers))
        )

    ordered = sorted(latencies)
    p95_index = min(round((len(ordered) - 1) * 0.95), len(ordered) - 1)
    print(f"Requests: {customers}")
    print(f"Statuses: {dict(statuses)}")
    print(f"p95 latency: {ordered[p95_index]:.2f} ms")


def main() -> None:
    """Run the load generator."""

    args = parse_args()
    asyncio.run(
        run_load(
            base_url=args.base_url,
            customers=args.customers,
            concurrency=args.concurrency,
        )
    )


if __name__ == "__main__":
    main()
