import asyncio
import logging


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    logging.info("local scheduler placeholder started")
    while True:
        await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())
