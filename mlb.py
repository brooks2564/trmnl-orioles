import requests
from datetime import datetime
import pytz

ORIOLES_TEAM_ID = 110
BASE_URL = "https://statsapi.mlb.com/api/v1"
ET = pytz.timezone("America/New_York")


def get_game_data():
    today = datetime.now(ET).strftime("%Y-%m-%d")
    try:
        url = (
            f"{BASE_URL}/schedule?sportId=1&teamId={ORIOLES_TEAM_ID}"
            f"&date={today}&hydrate=probablePitcher(stats),weather,linescore"
        )
        sched = requests.get(url, timeout=10).json()
    except Exception as e:
        return {"status": "error", "message": str(e)}

    if not sched.get("dates"):
        return {"status": "off_day"}

    games = sched["dates"][0].get("games", [])
    if not games:
        return {"status": "off_day"}

    # Prefer a live game (doubleheaders)
    game = next(
        (g for g in games if g["status"]["abstractGameState"] == "Live"), games[0]
    )
    game_pk = game["gamePk"]

    try:
        live = requests.get(
            f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live",
            timeout=10,
        ).json()
    except Exception as e:
        return {"status": "error", "message": str(e)}

    return _parse(live, game)


def _parse(live, sched_game):
    gd = live.get("gameData", {})
    ld = live.get("liveData", {})

    status = gd.get("status", {})
    abstract = status.get("abstractGameState", "Preview")
    detailed = status.get("detailedState", "Scheduled")

    teams = gd.get("teams", {})
    away, home = teams.get("away", {}), teams.get("home", {})
    away_rec, home_rec = away.get("record", {}), home.get("record", {})

    linescore = ld.get("linescore", {})
    ls_teams = linescore.get("teams", {})

    result = {
        "status": abstract,
        "detailed_status": detailed,
        "away": {
            "abbr": away.get("abbreviation", "???"),
            "city": away.get("locationName", ""),
            "name": away.get("teamName", ""),
            "record": f"{away_rec.get('wins', 0)}-{away_rec.get('losses', 0)}",
        },
        "home": {
            "abbr": home.get("abbreviation", "???"),
            "city": home.get("locationName", ""),
            "name": home.get("teamName", ""),
            "record": f"{home_rec.get('wins', 0)}-{home_rec.get('losses', 0)}",
        },
        "orioles_home": home.get("id") == ORIOLES_TEAM_ID,
        "away_score": ls_teams.get("away", {}).get("runs", 0) or 0,
        "home_score": ls_teams.get("home", {}).get("runs", 0) or 0,
        "inning": linescore.get("currentInning", 1),
        "inning_half": linescore.get("inningHalf", "Top"),
        "outs": linescore.get("outs", 0),
        "linescore_grid": _parse_grid(linescore),
    }

    if abstract == "Preview":
        result.update(_parse_pregame(gd, sched_game))
    elif abstract == "Live":
        result.update(_parse_live(ld, linescore, gd.get("players", {})))
    elif abstract == "Final":
        result.update(_parse_final(ld, linescore, gd))

    return result


def _parse_pregame(gd, sched_game):
    dt_str = gd.get("datetime", {}).get("dateTime", "")
    start_time = ""
    if dt_str:
        try:
            dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            start_time = dt.astimezone(ET).strftime("%-I:%M %p ET")
        except Exception:
            pass

    sched_teams = sched_game.get("teams", {})
    away_pp = sched_teams.get("away", {}).get("probablePitcher", {})
    home_pp = sched_teams.get("home", {}).get("probablePitcher", {})
    weather = gd.get("weather", {})

    weather_parts = []
    if weather.get("temp"):
        weather_parts.append(f"{weather['temp']}°F")
    if weather.get("condition"):
        weather_parts.append(weather["condition"])
    if weather.get("wind"):
        weather_parts.append(f"Wind: {weather['wind']}")

    return {
        "start_time": start_time,
        "away_probable": {
            "name": away_pp.get("fullName", "TBD"),
            "era": _fetch_era(away_pp.get("id")),
        },
        "home_probable": {
            "name": home_pp.get("fullName", "TBD"),
            "era": _fetch_era(home_pp.get("id")),
        },
        "weather": "  ".join(weather_parts),
    }


def _fetch_era(player_id):
    if not player_id:
        return "N/A"
    try:
        url = f"{BASE_URL}/people/{player_id}?hydrate=stats(group=pitching,type=season)"
        data = requests.get(url, timeout=8).json()
        splits = (
            data.get("people", [{}])[0]
            .get("stats", [{}])[0]
            .get("splits", [{}])
        )
        if splits:
            return splits[0].get("stat", {}).get("era", "N/A")
    except Exception:
        pass
    return "N/A"


def _parse_live(ld, linescore, players):
    offense = linescore.get("offense", {})
    defense = linescore.get("defense", {})
    boxscore = ld.get("boxscore", {})
    current_play = ld.get("plays", {}).get("currentPlay", {})
    count = current_play.get("count", {})

    pitcher_info = defense.get("pitcher", {})
    pitcher_id = pitcher_info.get("id")
    batter_info = offense.get("batter", {})
    batter_id = batter_info.get("id")

    pitcher_box = _box_player(boxscore, pitcher_id)
    batter_box = _box_player(boxscore, batter_id)

    pitcher_pitching = pitcher_box.get("stats", {}).get("pitching", {})
    batter_hitting = batter_box.get("seasonStats", {}).get("hitting", {})
    pitcher_season = pitcher_box.get("seasonStats", {}).get("pitching", {})

    matchup = current_play.get("matchup", {})
    bvp = matchup.get("batterVsPitcher", {})

    bat_order = batter_info.get("batOrder", "")
    lineup_pos = str(int(bat_order) // 100) if bat_order else ""

    # Last pitch
    last_pitch = {}
    for event in reversed(current_play.get("playEvents", [])):
        if event.get("isPitch"):
            details = event.get("details", {})
            pd = event.get("pitchData", {})
            last_pitch = {
                "type": details.get("type", {}).get("description", ""),
                "description": details.get("description", ""),
                "speed": (
                    round(pd["startSpeed"]) if pd.get("startSpeed") else None
                ),
            }
            break

    # Last completed play description
    last_play = ""
    for play in reversed(ld.get("plays", {}).get("allPlays", [])):
        if play.get("about", {}).get("isComplete"):
            last_play = play.get("result", {}).get("description", "")
            break

    return {
        "pitcher": {
            "name": pitcher_info.get("fullName", ""),
            "era": pitcher_season.get("era", "N/A"),
            "pitch_count": pitcher_pitching.get("numberOfPitches", 0),
            "strikes": pitcher_pitching.get("strikes", 0),
        },
        "batter": {
            "name": batter_info.get("fullName", ""),
            "lineup_pos": lineup_pos,
            "avg": batter_hitting.get("avg", ".---"),
            "hr": batter_hitting.get("homeRuns", 0),
            "rbi": batter_hitting.get("rbi", 0),
            "bvp_h": bvp.get("hits", 0),
            "bvp_ab": bvp.get("atBats", 0),
            "bvp_hr": bvp.get("homeRuns", 0),
            "bvp_k": bvp.get("strikeOuts", 0),
        },
        "bases": {
            "first": offense.get("first", {}).get("fullName") if offense.get("first") else None,
            "second": offense.get("second", {}).get("fullName") if offense.get("second") else None,
            "third": offense.get("third", {}).get("fullName") if offense.get("third") else None,
        },
        "balls": count.get("balls", 0),
        "strikes": count.get("strikes", 0),
        "last_pitch": last_pitch,
        "last_play": last_play,
    }


def _parse_final(ld, linescore, gd):
    decisions = ld.get("decisions", {})
    players = gd.get("players", {})
    boxscore = ld.get("boxscore", {})

    def fmt(d):
        if not d:
            return None
        pid = d.get("id")
        box = _box_player(boxscore, pid)
        season = box.get("seasonStats", {}).get("pitching", {})
        return {
            "name": d.get("fullName", ""),
            "record": f"{season.get('wins', 0)}-{season.get('losses', 0)}",
            "era": season.get("era", "N/A"),
            "saves": season.get("saves", 0),
        }

    game_info = gd.get("gameInfo", {})
    dur = game_info.get("gameDurationMinutes", 0)
    att = game_info.get("attendance", "")

    return {
        "winner": fmt(decisions.get("winner")),
        "loser": fmt(decisions.get("loser")),
        "save": fmt(decisions.get("save")),
        "duration": f"{dur // 60}:{dur % 60:02d}" if dur else "",
        "attendance": f"{att:,}" if isinstance(att, int) and att else str(att),
    }


def _parse_grid(linescore):
    innings = linescore.get("innings", [])
    ls_teams = linescore.get("teams", {})

    def inning_runs(side):
        return [
            ("" if inn.get(side, {}).get("runs") is None else str(inn[side]["runs"]))
            for inn in innings
        ]

    away_inn = inning_runs("away")
    home_inn = inning_runs("home")

    while len(away_inn) < 9:
        away_inn.append("")
    while len(home_inn) < 9:
        home_inn.append("")

    return {
        "away": {
            "innings": away_inn[:9],
            "r": ls_teams.get("away", {}).get("runs", 0) or 0,
            "h": ls_teams.get("away", {}).get("hits", 0) or 0,
            "e": ls_teams.get("away", {}).get("errors", 0) or 0,
            "lob": ls_teams.get("away", {}).get("leftOnBase", ""),
        },
        "home": {
            "innings": home_inn[:9],
            "r": ls_teams.get("home", {}).get("runs", 0) or 0,
            "h": ls_teams.get("home", {}).get("hits", 0) or 0,
            "e": ls_teams.get("home", {}).get("errors", 0) or 0,
            "lob": ls_teams.get("home", {}).get("leftOnBase", ""),
        },
    }


def _box_player(boxscore, player_id):
    if not player_id:
        return {}
    key = f"ID{player_id}"
    for side in ("away", "home"):
        p = boxscore.get("teams", {}).get(side, {}).get("players", {}).get(key)
        if p:
            return p
    return {}
