from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import datetime, timezone
from app.models import Tournament, TournamentPlayer, TournamentMatch, Player, TournamentSetScore, TournamentStanding
from app.schemas import TournamentCreate, TournamentResponse, TournamentDetailsResponse, TournamentMatchResponse, TournamentMatchResult
from sqlalchemy.orm import selectinload, aliased
from sqlalchemy.orm.attributes import flag_modified
from app.database import get_db
from sqlalchemy import delete, update, or_
from typing import List
import random
from collections import defaultdict
from math import ceil, log2

router = APIRouter(prefix="/tournaments", tags=["Tournaments"])

@router.post("/", response_model=dict)
async def create_tournament(tournament: TournamentCreate, db: AsyncSession = Depends(get_db), admin=True):
    def next_power_of_two(n: int) -> int:
        power = 1
        while power < n:
            power *= 2
        return power
    
    total_ko_players = tournament.num_groups * tournament.players_per_group_advancing
    computed_ko_size = next_power_of_two(total_ko_players)

    new_tournament = Tournament(
        name=tournament.name,
        date=tournament.date,
        num_groups=tournament.num_groups,
        knockout_size=computed_ko_size,
        players_advance_per_group=tournament.players_per_group_advancing,  # ✅
        created_at=datetime.now(timezone.utc),
        num_players=len(tournament.player_ids)
    )

    db.add(new_tournament)
    await db.flush()

    players = tournament.player_ids[:]

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
                group_number=0  # ✅ Use 0 to mean "no group"
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
            players_advance_per_group=t.players_advance_per_group,
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
        created_at=tournament.created_at,
        player_ids=player_ids
    )

@router.get("/{tournament_id}/details", response_model=TournamentDetailsResponse)
async def get_tournament_details(tournament_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Tournament).where(Tournament.id == tournament_id))
    tournament = result.scalars().first()
    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found.")

    from collections import defaultdict
    Player1 = aliased(Player)
    Player2 = aliased(Player)

    bracket_by_round = defaultdict(list)

    # 🏓 Fetch matches
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
        .outerjoin(Player1, TournamentMatch.player1_id == Player1.id)
        .outerjoin(Player2, TournamentMatch.player2_id == Player2.id)
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

    group_matches, knockout_matches, individual_matches = [], [], []
    group_matrix = { "players": [], "results": {} }
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
            group_matrix["results"][key] = {
                "winner": match.winner_id,
                "score": f"{match.player1_score}-{match.player2_score}",
                "set_scores": " ".join(f"({s[0]}-{s[1]})" for s in match_obj.set_scores)
            }

        elif match.stage == "knockout":
            knockout_matches.append(match_obj)
            round_label = match.round if match.round != "3rd Place Match" else "Round of 2"
            bracket_by_round[round_label].append(match_obj)
        else:
            individual_matches.append(match_obj)

    group_matrix["players"] = sorted(list(group_player_set))

    # 📊 Group ranking logic
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

    # ✅ Load groupings
    result = await db.execute(
        select(Tournament).options(selectinload(Tournament.players)).where(Tournament.id == tournament_id)
    )
    tournament = result.scalars().first()

    players_by_group = defaultdict(list)
    for tp in tournament.players:
        players_by_group[tp.group_number].append(tp.player_id)

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

    # ✅ Final standings from TournamentStanding table
    standings_result = await db.execute(
        select(TournamentStanding).where(TournamentStanding.tournament_id == tournament_id)
    )
    standings_entries = standings_result.scalars().all()
    final_standings = {}
    for s in standings_entries:
        final_standings[f"{s.position}"] = s.player_id

    print("🏁 Final standings in details endpoint:", final_standings)

    return TournamentDetailsResponse(
        id=tournament.id,
        name=tournament.name,
        date=tournament.date,
        num_players=tournament.num_players,
        num_groups=tournament.num_groups,
        knockout_size=tournament.knockout_size,
        created_at=tournament.created_at,
        group_matches=group_matches,
        knockout_matches=knockout_matches,
        individual_matches=individual_matches,
        final_standings=final_standings,
        group_matrix=group_matrix,
        knockout_bracket=dict(bracket_by_round)
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

async def generate_knockout_stage_matches(tournament: Tournament, db):
    print("🧠 Starting KO generation for", tournament.id)

    players_advancing = []

    if tournament.num_groups == 0:
        # ✅ All players go to knockout, seed by Elo
        result = await db.execute(
            select(TournamentPlayer.player_id).where(TournamentPlayer.tournament_id == tournament.id)
        )
        player_ids = [r[0] for r in result.all()]

        elo_result = await db.execute(
            select(Player.id, Player.rating).where(Player.id.in_(player_ids))
        )
        ratings = dict(elo_result.all())
        players_advancing = sorted(player_ids, key=lambda pid: -ratings.get(pid, 0))

    else:
        # ✅ Pick top X from each group
        result = await db.execute(
            select(TournamentPlayer).where(TournamentPlayer.tournament_id == tournament.id)
        )
        players = result.scalars().all()

        group_map = defaultdict(list)
        for p in players:
            group_map[p.group_number].append(p.player_id)

        result = await db.execute(
            select(TournamentMatch)
            .where(TournamentMatch.tournament_id == tournament.id)
            .where(TournamentMatch.stage == "group")
        )
        group_matches = result.scalars().all()

        wins = defaultdict(int)
        for m in group_matches:
            if m.winner_id:
                wins[m.winner_id] += 1

        group_rankings = {}
        for group_num, pids in group_map.items():
            sorted_group = sorted(pids, key=lambda pid: -wins[pid])
            group_rankings[group_num] = sorted_group

        for group_num in sorted(group_rankings.keys()):
            ranked = group_rankings[group_num]
            top_n = ranked[:tournament.players_advance_per_group]
            players_advancing.extend(top_n)

    num_players = len(players_advancing)
    ko_size = 2 ** ceil(log2(num_players))
    num_matches = ko_size // 2
    num_byes = ko_size - num_players

    print(f"🔢 {num_players} players advancing → KO size: {ko_size}, byes: {num_byes}")

    # ✅ Seed top players to get byes
    seeded = players_advancing[:num_byes]
    rest = players_advancing[num_byes:]
    random.shuffle(rest)

    matches = []

    # Give free pass to top players
    for pid in seeded:
        db.add(TournamentMatch(
            tournament_id=tournament.id,
            player1_id=pid,
            player2_id=None,
            winner_id=pid,
            player1_score=1,
            player2_score=0,
            round=f"Round of {ko_size}",
            stage="knockout"
        ))

    # Pair the remaining players
    for i in range(0, len(rest), 2):
        p1 = rest[i]
        p2 = rest[i + 1] if i + 1 < len(rest) else None
        if p2 is None:
            # Odd one out gets a bye
            db.add(TournamentMatch(
                tournament_id=tournament.id,
                player1_id=p1,
                player2_id=None,
                winner_id=p1,
                player1_score=1,
                player2_score=0,
                round=f"Round of {ko_size}",
                stage="knockout"
            ))
        else:
            db.add(TournamentMatch(
                tournament_id=tournament.id,
                player1_id=p1,
                player2_id=p2,
                round=f"Round of {ko_size}",
                stage="knockout"
            ))

    await db.commit()

async def advance_knockout_rounds(tournament_id: int, db: AsyncSession):
    tournament = await db.get(Tournament, tournament_id)

    # ✅ Check if standings already exist in TournamentStanding table
    existing = await db.execute(
        select(TournamentStanding).where(TournamentStanding.tournament_id == tournament_id)
    )
    if existing.scalars().first():
        print("🏁 Tournament is already complete.")
        return

    # 1. Get all knockout matches
    result = await db.execute(
        select(
            TournamentMatch.id,
            TournamentMatch.player1_id,
            TournamentMatch.player2_id,
            TournamentMatch.winner_id,
            TournamentMatch.round,
            TournamentMatch.stage
        ).where(
            TournamentMatch.tournament_id == tournament_id,
            TournamentMatch.stage == "knockout"
        ).order_by(TournamentMatch.round)
    )
    matches = result.all()

    if not matches:
        return  # No knockout matches to process

    # 2. Group matches by round
    rounds = defaultdict(list)
    for m in matches:
        if m.round != "3rd Place Match":
            rounds[m.round].append(m)

    def round_sort_key(name):
        if name == "Final":
            return 1
        if name == "3rd Place Match":
            return 0
        try:
            return int(name.split()[-1])  # e.g., "Round of 16" → 16
        except:
            return -1  # Unknown or malformed round

    round_names = sorted(rounds.keys(), key=round_sort_key, reverse=True)

    last_round_name = round_names[-1] # chnage to [0]
    last_round_matches = rounds[last_round_name]

    # 3. Check if all matches in that round are completed
    if any(m.winner_id is None for m in last_round_matches):
        return  # Still waiting on results

    # ✅ EARLY: If last round was "Round of 4", create 3rd place match now
    if last_round_name == "Round of 4" and len(last_round_matches) == 2:
        semi_losers = [
            m.player1_id if m.winner_id != m.player1_id else m.player2_id
            for m in last_round_matches
        ]
        existing_3rd_match = await db.execute(
            select(TournamentMatch).where(
                TournamentMatch.tournament_id == tournament_id,
                TournamentMatch.round == "3rd Place Match"
            )
        )
        if not existing_3rd_match.scalars().first() and len(semi_losers) == 2:
            db.add(TournamentMatch(
                tournament_id=tournament_id,
                player1_id=semi_losers[0],
                player2_id=semi_losers[1],
                round="3rd Place Match",
                stage="knockout"
            ))
            await db.commit()
            print("🎖️ 3rd Place Match created")

    # 4. Get winners of current round
    winners = [m.winner_id for m in last_round_matches if m.winner_id]

    # 5. If only one winner left, finalize tournament
    if len(winners) == 1:
        final_match = last_round_matches[0]
        first = winners[0]
        second = final_match.player1_id if final_match.winner_id != final_match.player1_id else final_match.player2_id

        # Check if 3rd place match exists and is complete
        third_place_result = await db.execute(
            select(
                TournamentMatch.player1_id,
                TournamentMatch.player2_id,
                TournamentMatch.winner_id
            ).where(
                TournamentMatch.tournament_id == tournament_id,
                TournamentMatch.round == "3rd Place Match"
            )
        )
        third_match = third_place_result.first()

        # Don't finalize yet if 3rd/4th match exists but is not completed
        if third_match and third_match.winner_id is None:
            print("⏳ Waiting for 3rd place match to finish before saving final standings.")
            return

        third = third_match.winner_id if third_match else None
        fourth = (
            third_match.player1_id if third_match and third_match.winner_id != third_match.player1_id
            else third_match.player2_id if third_match else None
        )

        db.add_all([
            TournamentStanding(tournament_id=tournament_id, player_id=first, position=1),
            TournamentStanding(tournament_id=tournament_id, player_id=second, position=2)
        ])
        if third:
            db.add(TournamentStanding(tournament_id=tournament_id, player_id=third, position=3))
        if fourth:
            db.add(TournamentStanding(tournament_id=tournament_id, player_id=fourth, position=4))

        await db.commit()
        print("✅ Final standings saved via TournamentStanding")
        return

    # 6. Seed next round (pair winners in order)
    next_round_size = len(winners)
    next_round_name = "Final" if next_round_size == 2 else f"Round of {next_round_size}"

    # 🔒 Avoid duplicate next round
    existing_next_round = await db.execute(
        select(TournamentMatch).where(
            TournamentMatch.tournament_id == tournament_id,
            TournamentMatch.round == next_round_name,
            TournamentMatch.stage == "knockout"
        )
    )
    existing_next_round_matches = existing_next_round.scalars().all()
    if existing_next_round_matches:
        print(f"⚠️ {next_round_name} already exists. Skipping regeneration.")
        return

    # 7. Create next-round matches
    for i in range(0, len(winners), 2):
        p1 = winners[i]
        p2 = winners[i + 1] if i + 1 < len(winners) else None

        match = TournamentMatch(
            tournament_id=tournament_id,
            player1_id=p1,
            player2_id=p2,
            round=next_round_name,
            stage="knockout",
            winner_id=p1 if p2 is None else None,
            player1_score=1 if p2 is None else None,
            player2_score=0 if p2 is None else None,
        )
        db.add(match)

    await db.commit()

@router.post("/matches/{match_id}/result")
async def submit_tournament_match_result(
    match_id: int,
    result: TournamentMatchResult,
    db: AsyncSession = Depends(get_db)
):
    # Select tournament_id, stage, round without triggering lazy load
    match_query = await db.execute(
        select(
            TournamentMatch.id,
            TournamentMatch.tournament_id,
            TournamentMatch.stage,
            TournamentMatch.round,
            TournamentMatch.player1_id,
            TournamentMatch.player2_id
        ).where(TournamentMatch.id == match_id)
    )
    match_info = match_query.first()

    if not match_info:
        raise HTTPException(status_code=404, detail="Match not found")

    tournament_id = match_info.tournament_id

    # Update match scores and winner
    await db.execute(
        update(TournamentMatch)
        .where(TournamentMatch.id == match_id)
        .values(
            player1_id=result.player1_id,
            player2_id=result.player2_id,
            winner_id=result.winner_id,
            player1_score=result.player1_score,
            player2_score=result.player2_score
        )
    )

    # Delete old set scores
    await db.execute(
        delete(TournamentSetScore).where(TournamentSetScore.match_id == match_id)
    )

    # Add new set scores
    for s in result.sets:
        db.add(TournamentSetScore(
            match_id=match_id,
            set_number=s.set_number,
            player1_score=s.player1_score,
            player2_score=s.player2_score
        ))

    await db.commit()

    # Check if all group matches are done and KO hasn't started
    group_match_result = await db.execute(
        select(TournamentMatch)
        .where(TournamentMatch.tournament_id == tournament_id)
        .where(TournamentMatch.stage == "group")
    )
    group_matches = group_match_result.scalars().all()
    all_group_complete = all(m.winner_id is not None for m in group_matches)
    print("Checking if group matches are complete and knockout can start...")
    print("Group matches found:", len(group_matches))
    print("Matches with results:", sum(m.winner_id is not None for m in group_matches))

    # Check if knockout matches already exist
    knockout_result = await db.execute(
        select(TournamentMatch)
        .where(TournamentMatch.tournament_id == tournament_id)
        .where(TournamentMatch.stage == "knockout")
    )
    knockout_exists = len(knockout_result.scalars().all()) > 0

    if all_group_complete and not knockout_exists:
        tournament = await db.get(Tournament, tournament_id)
        print("✅ All group matches complete. Generating KO bracket.")
        await generate_knockout_stage_matches(tournament, db)

    await advance_knockout_rounds(tournament_id, db)

    return {"message": "Tournament match result recorded"}

@router.post("/{tournament_id}/generate-ko")
async def force_generate_ko(tournament_id: int, db: AsyncSession = Depends(get_db)):
    tournament = await db.get(Tournament, tournament_id)
    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")

    await generate_knockout_stage_matches(tournament, db)
    return {"message": f"KO generated for tournament {tournament_id}"}

@router.post("/{tournament_id}/advance-knockout")
async def trigger_knockout_advancement(tournament_id: int, db: AsyncSession = Depends(get_db)):
    await advance_knockout_rounds(tournament_id, db)
    return {"message": "Knockout advancement executed"}
