#!/usr/bin/env python3
"""usercheck - polite Discord username availability checker (stdlib only, Python 3.8+).

Examples
  python usercheck.py -p ".xe?"              # every 4-char name starting with .xe
  python usercheck.py -p ".xe??1"            # 5-char names: .xe + any char + 1
  python usercheck.py -p "@@@" --delay 3     # all 3-letter names
  python usercheck.py -f names.txt           # names from a file (one per line)

Pattern wildcards:  ?  letter/digit/_ (add --dots to include '.')
                    @  letter a-z          #  digit 0-9
Anything else is literal. Free names are appended to hits.txt (change with -o).
Progress is saved in checked.txt, so re-running resumes where it stopped.
"""
import argparse, itertools, json, re, string, sys, time
import urllib.request, urllib.error

URL = "https://discord.com/api/v9/unique-username/username-attempt-unauthed"
VALID = re.compile(r"^[a-z0-9_.]{2,32}$")


def valid(n):
    return bool(VALID.match(n)) and ".." not in n


def expand(pattern, dots):
    sets = {"?": string.ascii_lowercase + string.digits + "_" + ("." if dots else ""),
            "@": string.ascii_lowercase, "#": string.digits}
    parts = [sets.get(c, c) for c in pattern]
    for combo in itertools.product(*parts):
        yield "".join(combo)


def check(name, timeout=10):
    """Return True (free), False (taken), or raise on error. Handles 429 itself."""
    while True:
        req = urllib.request.Request(
            URL, data=json.dumps({"username": name}).encode(),
            headers={"Content-Type": "application/json", "User-Agent": "usercheck/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return not json.load(r).get("taken", True)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                try:
                    wait = float(json.load(e).get("retry_after", 5))
                except Exception:
                    wait = 5.0
                print(f"  rate limited, waiting {wait:.0f}s...", file=sys.stderr)
                time.sleep(wait + 0.5)
                continue
            if e.code == 400:  # Discord rejected the name itself
                return False
            raise


def load(path):
    try:
        return {l.strip() for l in open(path, encoding="utf-8") if l.strip()}
    except FileNotFoundError:
        return set()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("-p", "--pattern")
    src.add_argument("-f", "--file")
    ap.add_argument("-o", "--out", default="hits.txt")
    ap.add_argument("--done", default="checked.txt", help="resume file")
    ap.add_argument("--delay", type=float, default=2.0, help="seconds between requests (default 2)")
    ap.add_argument("--dots", action="store_true", help="let ? also match '.'")
    ap.add_argument("--max", type=int, default=0, help="stop after N checks")
    a = ap.parse_args()

    names = list(expand(a.pattern, a.dots)) if a.pattern else [l.strip().lower() for l in open(a.file, encoding="utf-8") if l.strip()]
    skipped = [n for n in names if not valid(n)]
    names = [n for n in dict.fromkeys(names) if valid(n)]
    done = load(a.done)
    todo = [n for n in names if n not in done]
    if a.max:
        todo = todo[:a.max]
    print(f"{len(names)} valid names ({len(skipped)} invalid skipped), {len(todo)} to check, ~{len(todo)*a.delay/60:.1f} min")

    hits = 0
    try:
        with open(a.out, "a", encoding="utf-8") as hf, open(a.done, "a", encoding="utf-8") as df:
            for i, n in enumerate(todo, 1):
                try:
                    free = check(n)
                except Exception as e:
                    print(f"[{i}/{len(todo)}] {n}  error: {e}")
                    time.sleep(a.delay)
                    continue
                df.write(n + "\n"); df.flush()
                if free:
                    hits += 1
                    hf.write(n + "\n"); hf.flush()
                print(f"[{i}/{len(todo)}] {n:<34}{'AVAILABLE' if free else 'taken'}")
                time.sleep(a.delay)
    except KeyboardInterrupt:
        print("\nstopped - re-run to resume")
    print(f"done. {hits} available -> {a.out}")


if __name__ == "__main__":
    main()
