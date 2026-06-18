import asyncio
import asyncpg

async def main():
    try:
        conn = await asyncpg.connect(
            host="localhost",
            port=5432,
            user="postgres",
            password="aratek123",
            database="test_manager",
        )

        print("✅ Successfully connected to PostgreSQL!")
        version = await conn.fetchval("SELECT version();")
        print(version)

        await conn.close()

    except Exception as e:
        print("❌ Connection failed:")
        print(type(e).__name__)
        print(e)

asyncio.run(main())