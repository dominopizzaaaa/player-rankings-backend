from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import datetime, timezone
from app.models import Tournament, GroupingMode, TournamentPlayer, TournamentMatch, Player, TournamentSetScore
from app.schemas import TournamentCreate, TournamentResponse, TournamentDetailsResponse, TournamentMatchResponse, TournamentMatchResult
from sqlalchemy.orm import selectinload, aliased
from app.database import get_db
from sqlalchemy import delete
from typing import List
import random

router = APIRouter(prefix="/tournaments", tags=["Tournaments"])


@router.post("/", response_model=dict)
async def create_tournament(tournament: TournamentCreate, db: AsyncSession = Depends(get_db), admin=True):
    new_tournament = Tournament(
        name=tournament.name,
        date=tournament.date,
        num_groups=tournament.num_groups,
        knockout_size=tournament.knockout_size,
        grouping_mode=tournament.grouping_mode,
        created_at=datetime.now(timezone.utc),
        num_players=len(tournament.player_ids)
    )
    db.add(new_tournament)
    await db.flush()  # Assigns new_tournament.id

    players = tournament.player_ids[:]

    if tournament.grouping_mode == GroupingMode.RANDOM:
        random.shuffle(players)

    group_map = {}
    if tournament.num_groups > 0:
        for i, pid in enumerate(players):
            group_number = i % tournament.num_groups
            db.add(TournamentPlayer(
                tournament_id=new_tournament.id,
                player_id=pid,
                group_number=group_number
            ))
            group_map.setdefault(group_number, []).append(pid)
    else:
        for pid in players:
            db.add(TournamentPlayer(
                tournament_id=new_tournament.id,
                player_id=pid,
                group_number=None
            ))

    await db.flush()
    tournament_id = new_tournament.id

    if tournament.num_groups > 0:
        await generate_group_stage_matches(tournament_id, db)
    else:
        await generate_knockout_stage_matches(new_tournament, db)

    await db.commit()
    return {"message": "Tournament created and matches generated", "tournament_id": tournament_id}


@router.get("/", response_model=List[TournamentResponse])
async def get_all_tournaments(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Tournament)
        .options(selectinload(Tournament.players))
        .order_by(Tournament.date.desc())
    )
    tournaments = result.scalars().all()

    response = []
    for t in tournaments:
        player_ids = [tp.player_id for tp in t.players]
        response.append(TournamentResponse(
            id=t.id,
            name=t.name,
            date=t.date,
            num_players=t.num_players,
            num_groups=t.num_groups,
            knockout_size=t.knockout_size,
            grouping_mode=t.grouping_mode,
            created_at=t.created_at,
            player_ids=player_ids
        ))

    return response

@router.get("/{tournament_id}", response_model=TournamentResponse)
async def get_tournament(tournament_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Tournament).where(Tournament.id == tournament_id))
    tournament = result.scalars().first()
    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found.")
    
    player_ids = [tp.player_id for tp in tournament.players]
    return TournamentResponse(
        id=tournament.id,
        name=tournament.name,
        date=tournament.date,
        num_players=tournament.num_players,
        num_groups=tournament.num_groups,
        knockout_size=tournament.knockout_size,
        grouping_mode=tournament.grouping_mode,
        created_at=tournament.created_at,
        player_ids=player_ids
    )

@router.get("/{tournament_id}/details", response_model=TournamentDetailsResponse)
async def get_tournament_details(tournament_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Tournament).where(Tournament.id == tournament_id))
    tournament = result.scalars().first()
    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found.")

    Player1 = aliased(Player)
    Player2 = aliased(Player)

    match_query = (
        select(
            TournamentMatch.id,
            TournamentMatch.tournament_id,
            TournamentMatch.player1_id,
            TournamentMatch.player2_id,
            Player1.name.label("player1_name"),
            Player2.name.label("player2_name"),
            TournamentMatch.player1_score,
            TournamentMatch.player2_score,
            TournamentMatch.winner_id,
            TournamentMatch.round,
            TournamentMatch.stage,
        )
        .join(Player1, TournamentMatch.player1_id == Player1.id)
        .join(Player2, TournamentMatch.player2_id == Player2.id)
        .where(TournamentMatch.tournament_id == tournament_id)
    )
    result = await db.execute(match_query)
    matches = result.all()

    match_ids = [m.id for m in matches]
    score_results = await db.execute(
        select(TournamentSetScore).where(TournamentSetScore.match_id.in_(match_ids))
    )
    set_scores_by_match = {}
    for s in score_results.scalars().all():
        set_scores_by_match.setdefault(s.match_id, []).append([s.player1_score, s.player2_score])

    group_matches = []
    knockout_matches = []
    individual_matches = []

    group_matrix = {
        "players": [],
        "results": {}
    }
    group_player_set = set()

    for match in matches:
        match_obj = TournamentMatchResponse(
            id=match.id,
            player1_id=match.player1_id,
            player2_id=match.player2_id,
            player1_name=match.player1_name,
            player2_name=match.player2_name,
            player1_score=match.player1_score,
            player2_score=match.player2_score,
            winner_id=match.winner_id,
            round=match.round,
            stage=match.stage,
            set_scores=set_scores_by_match.get(match.id, [])
        )

        if match.stage == "group":
            group_matches.append(match_obj)
            group_player_set.add(match.player1_id)
            group_player_set.add(match.player2_id)

            key = f"{match.player1_id}-{match.player2_id}"
            result = {
                "winner": match.winner_id,
                "score": f"{match.player1_score}-{match.player2_score}",
                "set_scores": " ".join(f"({s[0]}-{s[1]})" for s in match_obj.set_scores)
            }
            group_matrix["results"][key] = result
        elif match.stage == "knockout":
            knockout_matches.append(match_obj)
        else:
            individual_matches.append(match_obj)

    group_matrix["players"] = sorted(list(group_player_set))

    # ➕ Ranking calculation
    from collections import defaultdict

    player_stats = defaultdict(lambda: {
        "wins": 0,
        "losses": 0,
        "set_wins": 0,
        "set_losses": 0,
        "points_won": 0,
        "points_lost": 0,
    })

    for match in group_matches:
        if match.winner_id is None:
            continue

        p1, p2 = match.player1_id, match.player2_id
        if match.winner_id == p1:
            player_stats[p1]["wins"] += 1
            player_stats[p2]["losses"] += 1
        else:
            player_stats[p2]["wins"] += 1
            player_stats[p1]["losses"] += 1

        for s in match.set_scores:
            player_stats[p1]["set_wins"] += int(s[0] > s[1])
            player_stats[p1]["set_losses"] += int(s[0] < s[1])
            player_stats[p2]["set_wins"] += int(s[1] > s[0])
            player_stats[p2]["set_losses"] += int(s[1] < s[0])
            player_stats[p1]["points_won"] += s[0]
            player_stats[p1]["points_lost"] += s[1]
            player_stats[p2]["points_won"] += s[1]
            player_stats[p2]["points_lost"] += s[0]

    # Load group assignments
    result = await db.execute(
        select(TournamentPlayer).where(TournamentPlayer.tournament_id == tournament.id)
    )
    players_by_group = {}
    for tp in result.scalars().all():
        players_by_group.setdefault(tp.group_number, []).append(tp.player_id)

    def sort_key(pid):
        stats = player_stats[pid]
        return (
            -stats["wins"],
            -stats["set_wins"] + stats["set_losses"],
            -stats["points_won"] + stats["points_lost"]
        )

    group_rankings = {}
    for group_num, pids in players_by_group.items():
        ranked = sorted(pids, key=sort_key)

        # Apply head-to-head override for direct ties
        i = 0
        while i < len(ranked) - 1:
            a, b = ranked[i], ranked[i + 1]
            if player_stats[a]["wins"] == player_stats[b]["wins"]:
                h2h = group_matrix["results"].get(f"{a}-{b}") or group_matrix["results"].get(f"{b}-{a}")
                if h2h and h2h["winner"] == b:
                    ranked[i], ranked[i + 1] = ranked[i + 1], ranked[i]
            i += 1

        group_rankings[group_num] = ranked

    group_matrix["rankings"] = group_rankings

    return TournamentDetailsResponse(
        id=tournament.id,
        name=tournament.name,
        date=tournament.date,
        num_players=tournament.num_players,
        num_groups=tournament.num_groups,
        knockout_size=tournament.knockout_size,
        grouping_mode=tournament.grouping_mode,
        created_at=tournament.created_at,
        group_matches=group_matches,
        knockout_matches=knockout_matches,
        individual_matches=individual_matches,
        final_standings=[],
        group_matrix=group_matrix
    )

async def generate_group_stage_matches(tournament_id: int, db: AsyncSession):
    result = await db.execute(
        select(TournamentPlayer)
        .where(TournamentPlayer.tournament_id == tournament_id)
        .order_by(TournamentPlayer.group_number)
    )
    players = result.scalars().all()

    groups = {}
    for player in players:
        groups.setdefault(player.group_number, []).append(player.player_id)

    for group_number, player_ids in groups.items():
        for i in range(len(player_ids)):
            for j in range(i + 1, len(player_ids)):
                db.add(TournamentMatch(
                    tournament_id=tournament_id,
                    player1_id=player_ids[i],
                    player2_id=player_ids[j],
                    round=f"Group {group_number + 1}",
                    stage="group"
                ))
    await db.commit()

async def generate_knockout_stage_matches(tournament: Tournament, db: AsyncSession):
    # 1. Get all players from the tournament
    result = await db.execute(
        select(TournamentPlayer.player_id)
        .where(TournamentPlayer.tournament_id == tournament.id)
    )
    player_ids = [r[0] for r in result.all()]

    # 2. Get Elo ratings
    elo_result = await db.execute(
        select(Player.id, Player.rating).where(Player.id.in_(player_ids))
    )
    ratings = dict(elo_result.all())

    # 3. Sort players by Elo rating descending
    sorted_players = sorted(player_ids, key=lambda pid: -ratings.get(pid, 0))

    # 4. Seed top 2
    top_seed = sorted_players[0] if len(sorted_players) >= 1 else None
    second_seed = sorted_players[1] if len(sorted_players) >= 2 else None
    remaining_players = sorted_players[2:]

    # 5. Determine knockout size
    KO_SIZE = tournament.knockout_size
    bracket = [None] * KO_SIZE

    if top_seed:
        bracket[0] = top_seed
    if second_seed:
        bracket[-1] = second_seed

    import random
    random.shuffle(remaining_players)

    # 6. Fill remaining slots
    i = 1
    for pid in remaining_players:
        while bracket[i] is not None:
            i += 1
        bracket[i] = pid
        i += 1

    # 7. If not enough players, remaining slots are None (free pass)
    matches = []
    for i in range(0, KO_SIZE, 2):
        p1 = bracket[i]
        p2 = bracket[i + 1] if i + 1 < KO_SIZE else None

        if p1 is None and p2 is None:
            continue  # Skip invalid match entirely
        elif p1 is None:
            winner = p2
            loser = None
        elif p2 is None:
            winner = p1
            loser = None
        else:
            # Regular match, no free pass
            db.add(TournamentMatch(
                tournament_id=tournament.id,
                player1_id=p1,
                player2_id=p2,
                round=f"Round of {KO_SIZE}",
                stage="knockout"
            ))
            continue

        # Auto-win case
        match = TournamentMatch(
            tournament_id=tournament.id,
            player1_id=p1 or p2,
            player2_id=None,
            winner_id=winner,
            player1_score=1,
            player2_score=0,
            round=f"Round of {KO_SIZE}",
            stage="knockout"
        )
        db.add(match)


        matches.append(TournamentMatch(
            tournament_id=tournament.id,
            player1_id=p1,
            player2_id=p2,
            round=f"Round of {KO_SIZE}",
            stage="knockout"
        ))

    db.add_all(matches)
    await db.commit()

@router.post("/matches/{match_id}/result")
async def submit_tournament_match_result(
    match_id: int,
    result: TournamentMatchResult,
    db: AsyncSession = Depends(get_db)
):
    db_match = await db.get(TournamentMatch, match_id)
    if not db_match:
        raise HTTPException(status_code=404, detail="Match not found")

    db_match.player1_id = result.player1_id
    db_match.player2_id = result.player2_id
    db_match.winner_id = result.winner_id
    db_match.player1_score = result.player1_score
    db_match.player2_score = result.player2_score

    await db.execute(delete(TournamentSetScore).where(TournamentSetScore.match_id == match_id))

    for s in result.sets:
        db.add(TournamentSetScore(
            match_id=match_id,
            set_number=s.set_number,
            player1_score=s.player1_score,
            player2_score=s.player2_score
        ))

    await db.commit()
    return {"message": "Tournament match result recorded"}
