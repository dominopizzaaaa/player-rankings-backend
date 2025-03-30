from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import datetime, timezone
from app.models import Tournament, GroupingMode, TournamentPlayer, TournamentMatch, Player, TournamentSetScore
from app.schemas import TournamentCreate, TournamentResponse, TournamentDetailsResponse, TournamentMatchResponse, TournamentMatchResult
from sqlalchemy.orm import selectinload, aliased
from app.database import get_db
from sqlalchemy import delete, update, or_
from typing import List
import random
from collections import defaultdict
from itertools import permutations

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
        .where(
            TournamentMatch.tournament_id == tournament_id,
            or_(
                TournamentMatch.stage != "knockout",  # Include group/individual matches as-is
                TournamentMatch.round.like("Round of%"),
                TournamentMatch.round == "3rd Place Match"
            )
        )
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
    bracket_by_round = defaultdict(list)
    for match in knockout_matches:
        bracket_by_round[match.round].append(match)

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

async def generate_knockout_stage_matches(tournament: Tournament, db: AsyncSession):
    print("🧠 Starting KO generation for", tournament.id)
    print("Number of groups:", tournament.num_groups)
    print("KO size:", tournament.knockout_size)

    KO_SIZE = tournament.knockout_size
    bracket = [None] * KO_SIZE
    seeded_players = []
    remaining_players = []

    group_assignments = {}  # player_id -> group_number

    if tournament.num_groups == 0:
        # ✅ No groups → seed by Elo rating
        result = await db.execute(
            select(TournamentPlayer.player_id).where(TournamentPlayer.tournament_id == tournament.id)
        )
        player_ids = [r[0] for r in result.all()]

        elo_result = await db.execute(
            select(Player.id, Player.rating).where(Player.id.in_(player_ids))
        )
        ratings = dict(elo_result.all())
        sorted_players = sorted(player_ids, key=lambda pid: -ratings.get(pid, 0))

        if sorted_players:
            bracket[0] = sorted_players[0]
        if len(sorted_players) > 1:
            bracket[-1] = sorted_players[1]

        seeded_ids = set(filter(None, [bracket[0], bracket[-1]]))
        remaining_players = [pid for pid in sorted_players if pid not in seeded_ids]

    else:
        # ✅ Use group stage results
        result = await db.execute(
            select(TournamentPlayer).where(TournamentPlayer.tournament_id == tournament.id)
        )
        players = result.scalars().all()

        group_map = defaultdict(list)
        for p in players:
            group_map[p.group_number].append(p.player_id)
            group_assignments[p.player_id] = p.group_number

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
            seeded_players.append(group_rankings[group_num][0])

        second_place_candidates = [
            group[1] for group in group_rankings.values() if len(group) > 1
        ]
        second_place_candidates.sort(key=lambda pid: -wins[pid])
        while len(seeded_players) < KO_SIZE and second_place_candidates:
            seeded_players.append(second_place_candidates.pop(0))

        if seeded_players:
            bracket[0] = seeded_players[0]
        if len(seeded_players) > 1:
            bracket[-1] = seeded_players[1]

        remaining_players = [
            pid for pid in set(p.player_id for p in players)
            if pid not in set(filter(None, bracket))
        ]

    # 🧩 Avoid first-round group clashes if possible
    def is_valid_bracket(b):
        for i in range(0, KO_SIZE, 2):
            p1 = b[i]
            p2 = b[i + 1] if i + 1 < KO_SIZE else None
            if p1 and p2:
                g1 = group_assignments.get(p1)
                g2 = group_assignments.get(p2)
                if g1 is not None and g2 is not None and g1 == g2:
                    return False
        return True

    # Only if groups exist
    if tournament.num_groups > 0:
        candidates = remaining_players.copy()
        random.shuffle(candidates)
        free_indices = [i for i, val in enumerate(bracket) if val is None]

        # Try all permutations to find a valid one
        for perm in permutations(candidates):
            test_bracket = bracket.copy()
            for idx, val in zip(free_indices, perm):
                test_bracket[idx] = val
            if is_valid_bracket(test_bracket):
                bracket = test_bracket
                break
        else:
            print("⚠️ No valid KO bracket found avoiding group clashes, using fallback.")

    else:
        random.shuffle(remaining_players)
        i = 0
        for pid in remaining_players:
            while i < KO_SIZE and bracket[i] is not None:
                i += 1
            if i < KO_SIZE:
                bracket[i] = pid

    # 🧠 Create matches
    for i in range(0, KO_SIZE, 2):
        p1 = bracket[i]
        p2 = bracket[i + 1] if i + 1 < KO_SIZE else None

        if p1 is None and p2 is None:
            continue
        elif p2 is None:
            db.add(TournamentMatch(
                tournament_id=tournament.id,
                player1_id=p1,
                player2_id=None,
                winner_id=p1,
                player1_score=1,
                player2_score=0,
                round=f"Round of {KO_SIZE}",
                stage="knockout"
            ))
        else:
            db.add(TournamentMatch(
                tournament_id=tournament.id,
                player1_id=p1,
                player2_id=p2,
                round=f"Round of {KO_SIZE}",
                stage="knockout"
            ))

    await db.commit()

async def advance_knockout_rounds(tournament_id: int, db: AsyncSession):
    tournament = await db.get(Tournament, tournament_id)
    if tournament.final_standings:
        print("🏁 Tournament is already complete.")
        return  # Stop if standings already exist

    # 1. Get all knockout matches, ordered by round name
    result = await db.execute(
        select(TournamentMatch)
        .where(TournamentMatch.tournament_id == tournament_id)
        .where(TournamentMatch.stage == "knockout")
        .order_by(TournamentMatch.round)
    )
    matches = result.scalars().all()

    if not matches:
        return  # No knockout matches to process

    # 2. Group matches by round
    from collections import defaultdict
    rounds = defaultdict(list)
    for m in matches:
        rounds[m.round].append(m)

    round_names = sorted(rounds.keys())

    # 3. Get the most recent round (last one with matches)
    last_round_name = round_names[-1]
    last_round_matches = rounds[last_round_name]

    # 4. Check if all matches in that round are completed
    if any(m.winner_id is None for m in last_round_matches):
        return  # Still waiting on results

    # 5. Get winners
    winners = [m.winner_id for m in last_round_matches if m.winner_id]

    if len(winners) == 1:
        tournament = await db.get(Tournament, tournament_id)
        final_match = last_round_matches[0]
        first = winners[0]
        second = final_match.player1_id if final_match.winner_id != final_match.player1_id else final_match.player2_id

        # Determine 3rd/4th if possible
        third, fourth = None, None

        if len(round_names) >= 2 and "Round of 4" in rounds:
            semi_matches = rounds["Round of 4"]
            semi_losers = [
                m.player1_id if m.winner_id != m.player1_id else m.player2_id
                for m in semi_matches
            ]
            # Check if match already exists
            existing_3rd_match = await db.execute(
                select(TournamentMatch).where(
                    TournamentMatch.round == "3rd Place Match",
                    TournamentMatch.tournament_id == tournament_id
                )
            )
            existing = existing_3rd_match.scalars().first()
            if not existing and len(semi_losers) == 2:
                db.add(TournamentMatch(
                    tournament_id=tournament_id,
                    player1_id=semi_losers[0],
                    player2_id=semi_losers[1],
                    round="3rd Place Match",
                    stage="knockout"
                ))
                await db.commit()
                return  # wait for 3rd match result

            # If match exists and has result
            if existing and existing.winner_id:
                third = existing.winner_id
                fourth = existing.player1_id if existing.winner_id != existing.player1_id else existing.player2_id

        # Store final standings
        tournament.final_standings = {
            "1st": first,
            "2nd": second,
            "3rd": third,
            "4th": fourth
        }
        await db.commit()
        print("✅ Final Standings:", tournament.final_standings)
        return
    
    # 6. Seed next round (pair winners in order)
    next_round_name = f"Round of {len(winners)}"

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
