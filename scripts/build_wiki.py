import json
from pathlib import Path
from collections import defaultdict
import shutil

ROOT = Path(__file__).resolve().parents[1]

DATA_COMPETITIONS = ROOT / "data" / "competitions"
BIOS_PLAYERS = ROOT / "bios" / "players"
BIOS_COMPETITIONS = ROOT / "bios" / "competitions"
BIOS_LEAGUES = ROOT / "bios" / "leagues"

OUT_COMPETITIONS = ROOT / "competitions"
OUT_PLAYERS = ROOT / "players"
OUT_LEAGUES = ROOT / "leagues"


def read_bio(path: Path) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return ""

def clear_generated_content():
    for folder in [OUT_COMPETITIONS, OUT_PLAYERS, OUT_LEAGUES]:
        folder.mkdir(parents=True, exist_ok=True)

        for file in folder.glob("*.md"):
            if file.name != "index.md":
                file.unlink()

def write_file(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")


def load_competitions():
    competitions = []

    for path in sorted(DATA_COMPETITIONS.glob("*.json")):
        with path.open("r", encoding="utf-8") as f:
            comp = json.load(f)

        required = ["slug", "name", "league", "date", "location", "results"]
        for key in required:
            if key not in comp:
                raise ValueError(f"{path} is missing required key: {key}")

        competitions.append(comp)

    return sorted(competitions, key=lambda c: c["date"])


def md_escape(value):
    return str(value).replace("|", "\\|")


def generate_competition_pages(competitions):
    for comp in competitions:
        slug = comp["slug"]
        bio = read_bio(BIOS_COMPETITIONS / f"{slug}.md")

        rows = []
        for r in sorted(comp["results"], key=lambda x: x["place"]):
            player_slug = r["player_slug"]
            player_name = md_escape(r["player_name"])
            country = md_escape(r.get("country", ""))
            weight = md_escape(r.get("weight", ""))

            rows.append(
                f"| {r['place']} | [{player_name}](../players/{player_slug}.md) | {country} | {weight} |"
            )

        results_table = "\n".join([
            "| Place | Player | Country | Weight |",
            "|---:|---|---|---:|",
            *rows
        ])

        content = f"""---
title: {comp["name"]}
---

# {comp["name"]}

**Date:** {comp["date"]}  
**League:** [{comp["league"]}](../leagues/{comp["league"].lower()}.md)  
**Location:** {comp["location"]}

{bio if bio else "_No competition bio yet._"}

## Results

{results_table}
"""

        write_file(OUT_COMPETITIONS / f"{slug}.md", content)


def generate_league_pages(competitions):
    by_league = defaultdict(list)

    for comp in competitions:
        by_league[comp["league"]].append(comp)

    for league, comps in sorted(by_league.items()):
        league_slug = league.lower()
        bio = read_bio(BIOS_LEAGUES / f"{league_slug}.md")

        rows = []
        for comp in sorted(comps, key=lambda c: c["date"]):
            winner = ""
            if comp["results"]:
                winner_result = sorted(comp["results"], key=lambda x: x["place"])[0]
                winner = f"[{md_escape(winner_result['player_name'])}](../players/{winner_result['player_slug']}.md)"

            rows.append(
                f"| {comp['date']} | [{md_escape(comp['name'])}](../competitions/{comp['slug']}.md) | {md_escape(comp['location'])} | {winner} |"
            )

        table = "\n".join([
            "| Date | Competition | Location | Winner |",
            "|---|---|---|---|",
            *rows
        ])

        content = f"""---
title: {league}
---

# {league}

{bio if bio else "_No league bio yet._"}

## Competitions

{table}
"""

        write_file(OUT_LEAGUES / f"{league_slug}.md", content)


def generate_player_pages(competitions):
    player_results = defaultdict(list)
    player_info = {}

    for comp in competitions:
        for r in comp["results"]:
            slug = r["player_slug"]
            player_info[slug] = {
                "name": r["player_name"],
                "country": r.get("country", "")
            }

            player_results[slug].append({
                "date": comp["date"],
                "competition_slug": comp["slug"],
                "competition_name": comp["name"],
                "league": comp["league"],
                "place": r["place"],
                "weight": r.get("weight", ""),
                "country": r.get("country", "")
            })

    for slug, results in sorted(player_results.items()):
        info = player_info[slug]
        name = info["name"]
        bio = read_bio(BIOS_PLAYERS / f"{slug}.md")

        total = len(results)
        wins = sum(1 for r in results if r["place"] == 1)

        weights = [
            float(r["weight"]) for r in results
            if r["weight"] not in ("", None)
        ]
        avg_weight = round(sum(weights) / len(weights), 2) if weights else ""

        rows = []
        for r in sorted(results, key=lambda x: x["date"]):
            rows.append(
                f"| {r['date']} | [{md_escape(r['competition_name'])}](../competitions/{r['competition_slug']}.md) | {md_escape(r['league'])} | {r['place']} | {md_escape(r['weight'])} |"
            )

        results_table = "\n".join([
            "| Date | Competition | League | Place | Weight |",
            "|---|---|---|---:|---:|",
            *rows
        ])

        content = f"""---
title: {name}
---

# {name}

**Country:** {md_escape(info.get("country", ""))}

{bio if bio else "_No player bio yet._"}

## Career Summary

| Competitions | Wins | Average Weight |
|---:|---:|---:|
| {total} | {wins} | {avg_weight} lbs|

## Results

{results_table}
"""

        write_file(OUT_PLAYERS / f"{slug}.md", content)


def generate_index_pages(competitions):
    leagues = sorted(set(c["league"] for c in competitions))

    league_rows = [
        f"- [{league}](../leagues/{league.lower()}.md)"
        for league in leagues
    ]

    write_file(
        OUT_LEAGUES / "index.md",
        "---\ntitle: Leagues\n---\n\n# Leagues\n\n" + "\n".join(league_rows)
    )

    comp_rows = [
        f"| {c['date']} | [{md_escape(c['name'])}](../competitions/{c['slug']}.md) | {md_escape(c['league'])} | {md_escape(c['location'])} |"
        for c in competitions
    ]

    write_file(
        OUT_COMPETITIONS / "index.md",
        "\n".join([
            "---",
            "title: Competitions",
            "---",
            "",
            "# Competitions",
            "",
            "| Date | Competition | League | Location |",
            "|---|---|---|---|",
            *comp_rows
        ])
    )

    # Basic player index
    players = {}
    for c in competitions:
        for r in c["results"]:
            players[r["player_slug"]] = r["player_name"]

    player_rows = [
        f"- [{name}](../players/{slug}.md)"
        for slug, name in sorted(players.items(), key=lambda x: x[1])
    ]

    write_file(
        OUT_PLAYERS / "index.md",
        "---\ntitle: Players\n---\n\n# Players\n\n" + "\n".join(player_rows)
    )


def main():
    competitions = load_competitions()

    clear_generated_content()
    
    generate_competition_pages(competitions)
    generate_league_pages(competitions)
    generate_player_pages(competitions)
    generate_index_pages(competitions)

    print(f"Built wiki from {len(competitions)} competitions.")


if __name__ == "__main__":
    main()