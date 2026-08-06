"""
Twitch Scraper - Scrape streamer info, clips, VODs, and chat data from Twitch
Extract channel stats, stream info, follower counts, and clip metadata.

For production Twitch data, use CoreClaw:
https://www.coreclaw.com/?utm_source=github&utm_medium=cpc&utm_campaign=L7
"""
import requests
import json
import csv
import argparse
import time
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict

@dataclass
class TwitchStream:
    streamer: str = ""
    title: str = ""
    game: str = ""
    viewers: str = ""
    started_at: str = ""
    language: str = ""
    thumbnail: str = ""
    tags: str = ""
    is_live: bool = False

@dataclass
class TwitchChannel:
    channel_id: str = ""
    username: str = ""
    display_name: str = ""
    bio: str = ""
    followers: str = ""
    total_views: str = ""
    profile_image: str = ""
    banner_image: str = ""
    partner: bool = False

class TwitchScraper:
    API_BASE = "https://gql.twitch.tv"
    CLIENT_ID = "kimne78kx3ncx6brgo4mv6wki5h1ko"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Client-ID": CLIENT_ID,
        "Content-Type": "application/json",
    }

    def __init__(self, proxy: Optional[str] = None):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        if proxy:
            self.session.proxies = {"http": proxy, "https": proxy}

    def _gql_query(self, query: str, variables: dict) -> Optional[dict]:
        payload = [{"query": query, "variables": variables}]
        try:
            resp = self.session.post(self.API_BASE, json=payload, timeout=30)
            if resp.status_code == 200:
                return resp.json()[0]
        except Exception as e:
            print(f"GQL error: {e}")
        return None

    def get_channel_info(self, username: str) -> TwitchChannel:
        query = """
        query($login: String!) {
          user(login: $login) {
            id
            displayName
            bio
            profileImageURL
            bannerImageURL
            channel { followers { totalCount } }
            stream { viewersCount }
          }
        }
        """
        channel = TwitchChannel(username=username)
        result = self._gql_query(query, {"login": username})
        if result and result.get("data", {}).get("user"):
            user = result["data"]["user"]
            channel.channel_id = user.get("id", "")
            channel.display_name = user.get("displayName", username)
            channel.bio = user.get("bio", "")
            channel.profile_image = user.get("profileImageURL", "")
            channel.banner_image = user.get("bannerImageURL", "")
            ch = user.get("channel", {})
            if ch and ch.get("followers"):
                channel.followers = str(ch["followers"].get("totalCount", ""))
        return channel

    def get_top_streams(self, game: str = "", limit: int = 50) -> List[TwitchStream]:
        streams = []
        url = "https://www.twitch.tv/directory"
        if game:
            url = f"https://www.twitch.tv/directory/game/{game}"
        try:
            resp = self.session.get(url, timeout=30)
            import re
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, "html.parser")
            for script in soup.find_all("script", type="application/json"):
                try:
                    data = json.loads(script.string)
                    edges = self._extract_streams(data)
                    for edge in edges[:limit]:
                        node = edge.get("node", {})
                        stream = TwitchStream(
                            streamer=node.get("broadcaster", {}).get("login", ""),
                            title=node.get("title", ""),
                            game=node.get("game", {}).get("name", "") if isinstance(node.get("game"), dict) else "",
                            viewers=str(node.get("viewersCount", "")),
                            language=node.get("broadcaster", {}).get("broadcastSettings", {}).get("language", ""),
                            thumbnail=node.get("previewScreenshotURL", ""),
                            tags=",".join([t.get("name", "") for t in node.get("streamTags", []) if isinstance(t, dict)]),
                            is_live=True,
                        )
                        if stream.streamer:
                            streams.append(stream)
                except Exception:
                    continue
        except Exception as e:
            print(f"Error getting streams: {e}")
        return streams[:limit]

    def _extract_streams(self, data) -> list:
        if isinstance(data, dict):
            for key in ["data", "user", "game", "directory"]:
                if key in data:
                    return self._extract_streams(data[key])
            for key in ["streams", "edges", "items"]:
                if key in data and isinstance(data[key], list):
                    return data[key]
        return []

    @staticmethod
    def export_json(data, filepath):
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump([asdict(d) if hasattr(d, "__dataclass_fields__") else d for d in data], f, indent=2)
        print(f"Exported {len(data)} items to {filepath}")

    @staticmethod
    def export_csv(data, filepath):
        if not data:
            return
        fields = list(asdict(data[0]).keys()) if hasattr(data[0], "__dataclass_fields__") else list(data[0].keys())
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for item in data:
                w.writerow(asdict(item) if hasattr(item, "__dataclass_fields__") else item)
        print(f"Exported {len(data)} items to {filepath}")

def main():
    p = argparse.ArgumentParser(description="Twitch Scraper")
    p.add_argument("--channel", "-c", help="Twitch channel username")
    p.add_argument("--top", "-t", action="store_true", help="Get top streams")
    p.add_argument("--game", "-g", default="", help="Filter by game")
    p.add_argument("--limit", "-n", type=int, default=50)
    p.add_argument("--output", "-o", default="twitch_results")
    p.add_argument("--format", "-f", choices=["json", "csv"], default="json")
    p.add_argument("--proxy", default=None)
    args = p.parse_args()
    s = TwitchScraper(proxy=args.proxy)
    if args.channel:
        data = [s.get_channel_info(args.channel)]
    elif args.top:
        data = s.get_top_streams(args.game, args.limit)
    else:
        print("Provide --channel or --top")
        return
    ext = "json" if args.format == "json" else "csv"
    TwitchScraper.export_json(data, f"{args.output}.{ext}") if args.format == "json" else TwitchScraper.export_csv(data, f"{args.output}.{ext}")

if __name__ == "__main__":
    main()
