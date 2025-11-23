import os
import re
import sys
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from argparse import ArgumentParser
from colorama import init, Fore, Style

# ====== Colrama init ======
init(autoreset=True)

# ========== Default settings ==========
DEFAULT_SOURCE = "https://mavecloud.s3mts.ru/storage/feeds/38058.xml"
DEST_DIR = "downloads"
ONLY_NEW = True
# ============================================


# ========== Color functions ==========
def green(text): return Fore.GREEN + text + Style.RESET_ALL
def red(text): return Fore.RED + text + Style.RESET_ALL
def yellow(text): return Fore.YELLOW + text + Style.RESET_ALL
def blue(text): return Fore.BLUE + text + Style.RESET_ALL
def cyan(text): return Fore.CYAN + text + Style.RESET_ALL
# =====================================



def safe_filename(name: str) -> str:
    """УSanitize filenames"""
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    name = re.sub(r'\s+', " ", name).strip()
    return name


def load_xml(source):
    """Fetching RSS from URL or local file"""
    if source.startswith("http://") or source.startswith("https://"):
        r = requests.get(source, timeout=10)
        r.raise_for_status()
        return ET.fromstring(r.content)
    else:
        return ET.parse(source).getroot()


def parse_date(date_str):
    """Data parser"""
    try:
        dt = datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %Z")
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return None


def progress_bar(downloaded, total):
    """Progress bar handler"""
    percent = downloaded / total * 100 if total else 0
    bar_len = 30
    filled = int(bar_len * (downloaded / total)) if total else 0
    bar = "#" * filled + "-" * (bar_len - filled)
    sys.stdout.write(f"\r[{bar}] {percent:5.1f}%")
    sys.stdout.flush()
# =====================================================


def main():
    # ---------- Command line arguments ----------
    parser = ArgumentParser(description="Podcast RSS downloader.")
    parser.add_argument("--source", default=DEFAULT_SOURCE, help="URL or path to RSS feed")
    parser.add_argument("--season", type=int, help="Filter by season number")
    parser.add_argument("--episode", type=int, help="Filter by episode number")
    parser.add_argument("--force", action="store_true", help="Re-download existing files")
    args = parser.parse_args()

    source = args.source
    season_filter = args.season
    episode_filter = args.episode
    only_new = not args.force

    os.makedirs(DEST_DIR, exist_ok=True)

    # ---------- RSS load ----------
    print(cyan(f"📥 Loading feed: {source}"))
    root = load_xml(source)

    # ---------- Define namespace ----------
    ns = {"itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd"}

    # ---------- Processing elements ----------
    for item in root.findall("./channel/item"):
        enclosure = item.find("enclosure")
        title_el = item.find("title")
        episode_el = item.find("itunes:episode", ns)
        season_el = item.find("itunes:season", ns)
        pub_date_el = item.find("pubDate")

        if enclosure is None:
            continue

        url = enclosure.get("url")
        mime = enclosure.get("type", "")

        if not url or "audio/mpeg" not in mime.lower():
            continue

        # -------- Filters --------
        episode_num = int(episode_el.text) if episode_el is not None and episode_el.text.isdigit() else None
        season_num = int(season_el.text) if season_el is not None and season_el.text.isdigit() else None

        if season_filter and season_filter != season_num:
            continue
        if episode_filter and episode_filter != episode_num:
            continue

        # -------- Headers and date --------
        title = title_el.text if title_el is not None else "episode"
        date_str = parse_date(pub_date_el.text) if pub_date_el is not None else ""

        # -------- Filename compose --------
        parts = []
        if season_num:
            parts.append(f"S{season_num:02d}")
        if episode_num:
            parts.append(f"E{episode_num:02d}")
        if date_str:
            parts.append(f"({date_str})")

        base_name = " ".join(parts) + " " + title
        filename = safe_filename(base_name).strip() + ".mp3"
        filepath = os.path.join(DEST_DIR, filename)

        if only_new and os.path.exists(filepath):
            print(yellow(f"⏭ Already exists: {filename}"))
            continue

        # -------- Download file --------
        print(blue(f"\n🎧 {title}"))
        print(cyan(f"URL: {url}"))

        try:
            with requests.get(url, stream=True, timeout=30) as r:
                r.raise_for_status()
                total = int(r.headers.get("content-length", 0))

                if total:
                    print(green(f"Size: {total/1024/1024:.2f} MB"))
                else:
                    print(yellow(f"Size: Unknown"))  # noqa: F541

                downloaded = 0

                with open(filepath, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total:
                                progress_bar(downloaded, total)

            if total:
                print()

            print(green(f"✔ Saved: {filepath}"))

        except Exception as e:
            print(red(f"✖ Error: {e}"))
        except KeyboardInterrupt:
            print("User interrupted")

