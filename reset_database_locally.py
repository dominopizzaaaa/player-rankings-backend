import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.database import engine, Base
from app.models import Tournament, TournamentMatch, TournamentPlayer, TournamentSetScore

async def drop_and_recreate_tournament_tables():
    async with engine.begin() as conn:
        print("⚠️ Dropping tournament-related tables...")

        # Temporarily disable FK checks
        await conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))

        # Drop tables
        await conn.execute(text("DROP TABLE IF EXISTS tournament_set_scores"))
        await conn.execute(text("DROP TABLE IF EXISTS tournament_matches"))
        await conn.execute(text("DROP TABLE IF EXISTS tournament_players"))
        await conn.execute(text("DROP TABLE IF EXISTS tournaments"))

        await conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))

        print("✅ Tables dropped.")

        print("🔁 Recreating tables...")
        # Recreate only specific tables
        await conn.run_sync(Base.metadata.create_all, tables=[
            Tournament.__table__,
            TournamentMatch.__table__,
            TournamentPlayer.__table__,
            TournamentSetScore.__table__
        ])
        print("✅ Tables recreated.")

if __name__ == "__main__":
    asyncio.run(drop_and_recreate_tournament_tables())
