from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import datetime, timezone
from app.models import Tournament, TournamentPlayer, Player, SetScore, TournamentStanding, Match
from app.schemas import TournamentCreate, TournamentResponse, TournamentDetailsResponse, MatchResponse, MatchResult
from sqlalchemy.orm import selectinload, aliased
from app.database import get_db
from sqlalchemy import delete, update
from typing import List
import random
from collections import defaultdict
from math import ceil, log2
from app.elo import calculate_elo

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
            Match.id,
            Match.tournament_id,
            Match.player1_id,
            Match.player2_id,
            Player1.name.label("player1_name"),
            Player2.name.label("player2_name"),
            Match.player1_score,
            Match.player2_score,
            Match.winner_id,
            Match.round,
            Match.stage,
        )
        .outerjoin(Player1, Match.player1_id == Player1.id)
        .outerjoin(Player2, Match.player2_id == Player2.id)
        .where(Match.tournament_id == tournament_id)
    )
    result = await db.execute(match_query)
    matches = result.all()

    match_ids = [m.id for m in matches]
    score_results = await db.execute(
        select(SetScore).where(SetScore.match_id.in_(match_ids))
    )
    set_scores_by_match = {}
    for s in score_results.scalars().all():
        set_scores_by_match.setdefault(s.match_id, []).append([s.player1_score, s.player2_score])

    group_matches, knockout_matches, individual_matches = [], [], []
    group_matrix = { "players": [], "results": {} }
    group_player_set = set()

    for match in matches:
        match_obj = MatchResponse(
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
                db.add(Match(
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
    group_rankings = {}

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

        num_players = len(players_advancing)
        ko_size = 2 ** ceil(log2(num_players))
        num_byes = ko_size - num_players

        print(f"🔢 [KO Only] {num_players} players advancing → KO size: {ko_size}, byes: {num_byes}")

        seeded = players_advancing[:num_byes]
        rest = players_advancing[num_byes:]
        random.shuffle(rest)

        for pid in seeded:
            db.add(Match(
                tournament_id=tournament.id,
                player1_id=pid,
                player2_id=None,
                winner_id=pid,
                player1_score=1,
                player2_score=0,
                round=f"Round of {ko_size}",
                stage="knockout"
            ))

        for i in range(0, len(rest), 2):
            p1 = rest[i]
            p2 = rest[i + 1] if i + 1 < len(rest) else None
            if p2 is None:
                db.add(Match(
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
                db.add(Match(
                    tournament_id=tournament.id,
                    player1_id=p1,
                    player2_id=p2,
                    round=f"Round of {ko_size}",
                    stage="knockout"
                ))

        await db.commit()
        return  # ✅ Return early to avoid running group-based logic below

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
            select(Match)
            .where(Match.tournament_id == tournament.id)
            .where(Match.stage == "group")
        )
        group_matches = result.scalars().all()

        # 🧠 Reuse group ranking logic here
        player_stats = defaultdict(lambda: {
            "wins": 0,
            "set_wins": 0,
            "set_losses": 0,
            "points_won": 0,
            "points_lost": 0,
        })

                # First, fetch set scores for all group matches
        match_ids = [m.id for m in group_matches]
        set_score_result = await db.execute(
            select(SetScore).where(SetScore.match_id.in_(match_ids))
        )
        set_scores_by_match = defaultdict(list)
        for s in set_score_result.scalars().all():
            set_scores_by_match[s.match_id].append([s.player1_score, s.player2_score])

        # Now process matches and compute stats
        for m in group_matches:
            if m.winner_id is None:
                continue
            p1, p2 = m.player1_id, m.player2_id
            if m.winner_id == p1:
                player_stats[p1]["wins"] += 1
            else:
                player_stats[p2]["wins"] += 1

            set_scores = set_scores_by_match.get(m.id, [])
            for s in set_scores:
                player_stats[p1]["set_wins"] += int(s[0] > s[1])
                player_stats[p1]["set_losses"] += int(s[0] < s[1])
                player_stats[p2]["set_wins"] += int(s[1] > s[0])
                player_stats[p2]["set_losses"] += int(s[1] < s[0])
                player_stats[p1]["points_won"] += s[0]
                player_stats[p1]["points_lost"] += s[1]
                player_stats[p2]["points_won"] += s[1]
                player_stats[p2]["points_lost"] += s[0]

        # Use point differential: points won - points lost
        def sort_key(pid):
            stats = player_stats[pid]
            return (
                -stats["wins"],                             # 1. Wins
                -(stats["set_wins"] - stats["set_losses"]), # 2. Set difference
                -(stats["points_won"] - stats["points_lost"]) # 3. Point difference ✅ fixed
            )

        for group_num, pids in group_map.items():
            ranked = sorted(pids, key=sort_key)
            group_rankings[group_num] = ranked

        for group_num in sorted(group_rankings.keys()):
            ranked = group_rankings[group_num]
            top_n = ranked[:tournament.players_advance_per_group]
            players_advancing.extend(top_n)

    num_players = len(players_advancing)
    ko_size = 2 ** ceil(log2(num_players))
    num_byes = ko_size - num_players

    print(f"🔢 {num_players} players advancing → KO size: {ko_size}, byes: {num_byes}")

    advance_count = tournament.players_advance_per_group

    # Collect ranked players from each group into buckets by rank
    rank_buckets = defaultdict(list)

    for group_num, ranked in group_rankings.items():
        for i in range(min(advance_count, len(ranked))):
            rank_buckets[i].append(ranked[i])  # i = 0 means 1st place, etc.

    # Create final list by merging sorted buckets
    players_advancing = []
    for i in range(advance_count):
        tier = sorted(rank_buckets[i], key=sort_key)
        players_advancing.extend(tier)

    seeded = players_advancing[:num_byes]
    rest = players_advancing[num_byes:]
    random.shuffle(rest)

    matches = []

    # Give free pass to top players
    for pid in seeded:
        db.add(Match(
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
            db.add(Match(
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
            db.add(Match(
                tournament_id=tournament.id,
                player1_id=p1,
                player2_id=p2,
                round=f"Round of {ko_size}",
                stage="knockout"
            ))

    await db.commit()

async def advance_knockout_rounds(tournament_id: int, db: AsyncSession):
    tournament = await db.get(Tournament, tournament_id)

    # ✅ Already finalized?
    existing = await db.execute(
        select(TournamentStanding).where(TournamentStanding.tournament_id == tournament_id)
    )
    if existing.scalars().first():
        print("🏁 Tournament is already complete.")
        return

    # 🏓 Fetch all KO matches
    result = await db.execute(
        select(
            Match.id,
            Match.player1_id,
            Match.player2_id,
            Match.winner_id,
            Match.round,
            Match.stage
        ).where(
            Match.tournament_id == tournament_id,
            Match.stage == "knockout"
        ).order_by(Match.round)
    )
    matches = result.all()

    if not matches:
        return

    # 📦 Group by round
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
            return int(name.split()[-1])
        except:
            return -1

    round_names = sorted(rounds.keys(), key=round_sort_key, reverse=True)

    if not round_names:
        return

    current_round_name = round_names[-1]
    current_round_matches = rounds[current_round_name]
    if len(round_names) > 1:
        last_round_name = round_names[-2]
        last_round_matches = rounds[last_round_name]
    else:
        last_round_name = None
        last_round_matches = []

    # ✅ Wait if incomplete
    if any(m.winner_id is None for m in last_round_matches):
        return

    # 🎖️ Try 3rd place creation
    if current_round_name == "Round of 4":
        completed = [m for m in last_round_matches if m.winner_id is not None]

        if len(completed) == 2:
            semi_losers = [
                m.player1_id if m.winner_id != m.player1_id else m.player2_id
                for m in completed
            ]
            if any(pid is None for pid in semi_losers):
                print("⚠️ Skipping 3rd place match: missing semifinal loser.")
            else:
                existing_3rd_match = await db.execute(
                    select(Match).where(
                        Match.tournament_id == tournament_id,
                        Match.round == "3rd Place Match"
                    )
                )
                if not existing_3rd_match.scalars().first():
                    db.add(Match(
                        tournament_id=tournament_id,
                        player1_id=semi_losers[0],
                        player2_id=semi_losers[1],
                        round="3rd Place Match",
                        stage="knockout"
                    ))
                    await db.commit()
                    print("🎖️ 3rd Place Match created")
        elif len(completed) == 1:
            semi = completed[0]
            if semi.winner_id:
                third_place_id = semi.player1_id if semi.winner_id != semi.player1_id else semi.player2_id
                if third_place_id:
                    db.add(TournamentStanding(
                        tournament_id=tournament_id,
                        player_id=third_place_id,
                        position=3
                    ))
                    await db.commit()
                    print(f"🥉 Assigned 3rd place to Player {third_place_id}")

    # 🎯 Final round? Save standings
    winners = [m.winner_id for m in current_round_matches if m.winner_id]

    if len(winners) == 1 and current_round_name == "Final":
        final_match = current_round_matches[0]
        first = winners[0]
        second = final_match.player1_id if final_match.winner_id != final_match.player1_id else final_match.player2_id

        # 3rd/4th logic
        third_place_result = await db.execute(
            select(
                Match.player1_id,
                Match.player2_id,
                Match.winner_id
            ).where(
                Match.tournament_id == tournament_id,
                Match.round == "3rd Place Match"
            )
        )
        third_match = third_place_result.first()

        third = None
        fourth = None

        if third_match:
            if third_match.winner_id is None:
                print("⏳ Waiting for 3rd place match to finish before saving final standings.")
                return
            third = third_match.winner_id
            fourth = (
                third_match.player1_id if third_match.winner_id != third_match.player1_id
                else third_match.player2_id
            )
        else:
            semi_with_two_players = next(
                (m for m in last_round_matches if m.player1_id is not None and m.player2_id is not None), None
            )
            if semi_with_two_players and semi_with_two_players.winner_id:
                third = (
                    semi_with_two_players.player1_id if semi_with_two_players.winner_id != semi_with_two_players.player1_id
                    else semi_with_two_players.player2_id
                )
                print(f"🥉 Auto-assigned 3rd place to semi-final loser: Player {third}")

        db.add_all([
            TournamentStanding(tournament_id=tournament_id, player_id=first, position=1),
            TournamentStanding(tournament_id=tournament_id, player_id=second, position=2)
        ])
        if third:
            db.add(TournamentStanding(tournament_id=tournament_id, player_id=third, position=3))
        if fourth:
            db.add(TournamentStanding(tournament_id=tournament_id, player_id=fourth, position=4))

        await db.commit()
        print(f"✅ Final standings saved: 1st={first}, 2nd={second}, 3rd={third}, 4th={fourth}")
        return

    # 🔁 Advance to next round
    next_round_size = len(winners)
    if next_round_size < 2:
        print("⚠️ Not enough winners to create next round.")
        return

    next_round_name = "Final" if next_round_size == 2 else f"Round of {next_round_size}"

    existing_next_round = await db.execute(
        select(Match).where(
            Match.tournament_id == tournament_id,
            Match.round == next_round_name,
            Match.stage == "knockout"
        )
    )
    if existing_next_round.scalars().first():
        print(f"⚠️ {next_round_name} already exists. Skipping.")
        return

    for i in range(0, len(winners), 2):
        p1 = winners[i]
        p2 = winners[i + 1] if i + 1 < len(winners) else None

        match = Match(
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
    print(f"✅ Created {next_round_name} with {len(winners)} players")

@router.post("/matches/{match_id}/result")
async def submit_tournament_match_result(
    match_id: int,
    result: MatchResult,
    db: AsyncSession = Depends(get_db)
):
    # Select tournament_id, stage, round without triggering lazy load
    match_query = await db.execute(
        select(
            Match.id,
            Match.tournament_id,
            Match.stage,
            Match.round,
            Match.player1_id,
            Match.player2_id
        ).where(Match.id == match_id)
    )
    match_info = match_query.first()

    if not match_info:
        raise HTTPException(status_code=404, detail="Match not found")

    tournament_id = match_info.tournament_id

    # Update match scores and winner
    await db.execute(
        update(Match)
        .where(Match.id == match_id)
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
        delete(SetScore).where(SetScore.match_id == match_id)
    )

    # Add new set scores
    for s in result.sets:
        db.add(SetScore(
            match_id=match_id,
            set_number=s.set_number,
            player1_score=s.player1_score,
            player2_score=s.player2_score
        ))

    await db.commit()

        # 🧠 Update Elo ratings and store in global Match table
    stmt = select(Player).where(Player.id.in_([result.player1_id, result.player2_id]))
    players = (await db.execute(stmt)).scalars().all()

    if len(players) < 2:
        raise HTTPException(status_code=400, detail="Both players must exist.")

    player1, player2 = players if players[0].id == result.player1_id else players[::-1]

    if result.winner_id not in [player1.id, player2.id]:
        raise HTTPException(status_code=400, detail="Winner must be one of the players.")

    # ✅ Determine outcome
    outcome1 = 1 if result.winner_id == player1.id else 0
    outcome2 = 1 - outcome1

    # ✅ Calculate new ratings
    new_rating1 = int(calculate_elo(player1.rating, player2.rating, outcome1, player1.matches or 0))
    new_rating2 = int(calculate_elo(player2.rating, player1.rating, outcome2, player2.matches or 0))

    # ✅ Update player stats
    player1.rating = new_rating1
    player2.rating = new_rating2
    player1.matches = (player1.matches or 0) + 1
    player2.matches = (player2.matches or 0) + 1

    await db.commit()


    # Check if all group matches are done and KO hasn't started
    group_match_result = await db.execute(
        select(Match)
        .where(Match.tournament_id == tournament_id)
        .where(Match.stage == "group")
    )
    group_matches = group_match_result.scalars().all()
    all_group_complete = all(m.winner_id is not None for m in group_matches)
    print("Checking if group matches are complete and knockout can start...")
    print("Group matches found:", len(group_matches))
    print("Matches with results:", sum(m.winner_id is not None for m in group_matches))

    # Check if knockout matches already exist
    knockout_result = await db.execute(
        select(Match)
        .where(Match.tournament_id == tournament_id)
        .where(Match.stage == "knockout")
    )
    knockout_exists = len(knockout_result.scalars().all()) > 0

    if all_group_complete and not knockout_exists:
        tournament = await db.get(Tournament, tournament_id)
        print("✅ All group matches complete. Generating KO bracket.")
        await generate_knockout_stage_matches(tournament, db)

    await advance_knockout_rounds(tournament_id, db)

    return {"message": "Tournament match result recorded"}

@router.post("/{tournament_id}/reset")
async def reset_tournament(tournament_id: int, db: AsyncSession = Depends(get_db)):
    # Check tournament exists
    tournament = await db.get(Tournament, tournament_id)
    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")

    print(f"♻️ Resetting tournament ID: {tournament_id}")

    # Delete all set scores
    await db.execute(
        delete(SetScore).where(
            SetScore.match_id.in_(
                select(Match.id).where(Match.tournament_id == tournament_id)
            )
        )
    )

    # Delete all tournament matches
    await db.execute(
        delete(Match).where(Match.tournament_id == tournament_id)
    )

    # Delete all final standings
    await db.execute(
        delete(TournamentStanding).where(TournamentStanding.tournament_id == tournament_id)
    )

    # Re-generate matches using existing group settings
    if tournament.num_groups > 0:
        await generate_group_stage_matches(tournament.id, db)
    else:
        await generate_knockout_stage_matches(tournament, db)

    await db.commit()
    return {"message": f"Tournament {tournament_id} reset and matches regenerated"}

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

@router.delete("/{tournament_id}")
async def delete_tournament(tournament_id: int, db: AsyncSession = Depends(get_db), admin=True):
    from sqlalchemy import delete

    # Get tournament
    result = await db.execute(select(Tournament).where(Tournament.id == tournament_id))
    tournament = result.scalar_one_or_none()
    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")

    # Step 1: Get all matches for this tournament
    matches_result = await db.execute(select(Match).where(Match.tournament_id == tournament_id))
    matches = matches_result.scalars().all()

    match_ids = [match.id for match in matches]
    
    # Step 2: Delete set scores first (if any)
    if match_ids:
        await db.execute(delete(SetScore).where(SetScore.match_id.in_(match_ids)))

    # Step 3: Delete the matches
    await db.execute(delete(Match).where(Match.tournament_id == tournament_id))

    # Step 4: Delete the tournament
    await db.delete(tournament)

    # Commit the changes
    await db.commit()

    return {"message": f"Tournament {tournament_id} and its matches were deleted successfully."}
