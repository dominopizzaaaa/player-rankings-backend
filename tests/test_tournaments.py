import pytest
from httpx import AsyncClient
from datetime import date
from app.main import app
from app.database import async_session
from app.models import Player
from sqlalchemy.ext.asyncio import AsyncSession
from httpx import ASGITransport

test_cases = [
    ("valid_4p_0g", 4, 0, 0, True),
    ("valid_5p_0g", 5, 0, 0, True),
    ("valid_6p_2g_2a", 6, 2, 2, True),
    ("valid_8p_2g_2a", 8, 2, 2, True),
    ("valid_9p_3g_2a", 9, 3, 2, True),
    ("valid_12p_3g_2a", 12, 3, 2, True),
    ("valid_16p_4g_2a", 16, 4, 2, True),
    ("invalid_6p_3g_3a", 6, 3, 3, False),
    ("invalid_8p_2g_5a", 8, 2, 5, False),
    ("invalid_3p_3g_1a", 3, 3, 1, False),
]

async def seed_players(num_players: int):
    async with async_session() as session:
        for i in range(1, num_players + 1):
            session.add(Player(name=f"Player {i}", rating=1500, matches=0))
        await session.commit()

@pytest.mark.asyncio
@pytest.mark.parametrize("test_name,num_players,num_groups,players_advance_per_group,expect_success", test_cases)
async def test_tournament_creation(test_name, num_players, num_groups, players_advance_per_group, expect_success):
    # Seed test players
    await seed_players(num_players)

    payload = {
        "name": f"Tournament {test_name}",
        "date": str(date.today()),
        "num_groups": num_groups,
        "players_per_group_advancing": players_advance_per_group,
        "player_ids": list(range(1, num_players + 1))
    }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/tournaments/", json=payload)

    if expect_success:
        assert response.status_code == 200, response.text
        assert "id" in response.json()
    else:
        assert response.status_code == 400 or response.status_code == 422
