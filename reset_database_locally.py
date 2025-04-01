import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.database import engine, Base, async_session
from app.models import (
    Player,
    Tournament,
    TournamentPlayer,
    TournamentStanding,
    Match,
    SetScore
)

async def drop_and_recreate_all_tables():
    async with engine.begin() as conn:
        print("⚠️ Dropping all tables...")

        await conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        await conn.execute(text("DROP TABLE IF EXISTS set_scores"))
        await conn.execute(text("DROP TABLE IF EXISTS matches"))
        await conn.execute(text("DROP TABLE IF EXISTS tournament_standings"))
        await conn.execute(text("DROP TABLE IF EXISTS tournaments"))
        await conn.execute(text("DROP TABLE IF EXISTS tournament_players"))
        await conn.execute(text("DROP TABLE IF EXISTS players"))
        await conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))

        print("✅ All tables dropped.")
        print("🔁 Recreating all tables...")
        await conn.run_sync(Base.metadata.create_all)
        print("✅ Tables recreated.")

        print("🔢 Resetting AUTO_INCREMENT values...")
        tables = [
            "players", "matches", "set_scores",
            "tournaments", "tournament_players", "tournament_standings"
        ]
        for table in tables:
            await conn.execute(text(f"ALTER TABLE {table} AUTO_INCREMENT = 1"))
        print("✅ AUTO_INCREMENT reset.")

    # 👇 Insert demo players after tables are created
    async with async_session() as session:
        print("👤 Adding demo players...")
        demo_names = ["Alpha", "Bravo", "Charlie", "Delta"]
        for name in demo_names:
            session.add(Player(name=name, rating=1500, matches=0))
        await session.commit()
        print("✅ Demo players inserted.")

        # OPTIONAL: Add a sample tournament
        # from datetime import date
        # tournament = Tournament(name="Test Tournament", date=date.today(), num_groups=2, knockout_size=4, players_advance_per_group=1, num_players=4)
        # session.add(tournament)
        # await session.commit()
        # print("🎯 Sample tournament created.")

if __name__ == "__main__":
    asyncio.run(drop_and_recreate_all_tables())
