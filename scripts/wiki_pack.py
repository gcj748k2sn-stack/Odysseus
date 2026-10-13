#!/usr/bin/env python3
"""Build and query local Wikipedia packs (src/wiki_packs.py).

USAGE (from the repo root):

  ./venv/bin/python scripts/wiki_pack.py define edible-fungi-en --lang en --category "Edible fungi" --depth 1 --topic biology --name "Edible fungi"
  ./venv/bin/python scripts/wiki_pack.py define pilze-de --lang de --category "Speisepilzart" --depth 0 --topic biology
  ./venv/bin/python scripts/wiki_pack.py define fungi-project-en --lang en --wikiproject Fungi --topic biology
  ./venv/bin/python scripts/wiki_pack.py list
  ./venv/bin/python scripts/wiki_pack.py plan edible-fungi-en
  ./venv/bin/python scripts/wiki_pack.py build edible-fungi-en [--limit 50]
  ./venv/bin/python scripts/wiki_pack.py query edible-fungi-en "pink oyster mushroom native range"
  ./venv/bin/python scripts/wiki_pack.py delete edible-fungi-en [--forget]

plan   lists the articles (no text downloaded) and writes data/wiki_packs/<id>.plan.json:
       count, count per depth, subcategories just past the depth limit, a sample.
build  downloads plain text for new or changed articles only; rerun to resume or update.
Files live in data/wiki_packs/ (ODYSSEUS_DATA_DIR respected). The app does not read
them yet; nothing here touches app.db.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import wiki_packs as wp  # noqa: E402


def _pack(args):
    packs = wp.load_packs(args.dir)
    if args.id not in packs:
        raise SystemExit(f"no pack {args.id!r} — define it first (known: {', '.join(packs) or 'none'})")
    return packs[args.id]


def cmd_define(args):
    if bool(args.category) == bool(args.wikiproject):
        raise SystemExit("give exactly one of --category or --wikiproject")
    source = ({"type": "category", "name": args.category, "depth": args.depth} if args.category
              else {"type": "wikiproject", "name": args.wikiproject})
    p = wp.define_pack(args.id, args.lang, source, name=args.name, topic=args.topic,
                       exclude_title=args.exclude or (), base=args.dir)
    print(json.dumps(p, indent=1, ensure_ascii=False))


def cmd_list(args):
    packs = wp.load_packs(args.dir)
    if not packs:
        print("no packs defined")
    for p in packs.values():
        src = p["source"]
        where = f"Category:{src['name']} depth {src['depth']}" if src["type"] == "category" else f"WikiProject {src['name']}"
        print(f"{p['id']:22} {p['lang']}  {p['state']:8} articles={p.get('articles')}  {where}  topic={p.get('topic') or '-'}")


def cmd_plan(args):
    r = wp.plan(_pack(args), base=args.dir, sample=args.sample)
    print(f"{r['articles']} articles ({r['listed_titles']} titles listed, {len(r['excluded'])} excluded by pattern)")
    print(f"per depth: {r['by_depth']}")
    print(f"wikitext size: {r['wikitext_bytes'] / 1e6:.1f} MB (markup included; plain text is smaller)")
    if r["subcategories_not_followed"]:
        print(f"subcategories just past the depth limit ({len(r['subcategories_not_followed'])}): "
              + ", ".join(r["subcategories_not_followed"][:40]))
    print("sample: " + "; ".join(r["sample"]))
    print(f"{r['requests']} requests, {r['seconds']} s. Written: {Path(wp.default_dir() if args.dir is None else args.dir) / (args.id + '.plan.json')}")


def cmd_build(args):
    def progress(done, total, spr):
        print(f"  {done}/{total} articles, {spr:.2f} s per request", flush=True)
    r = wp.build(_pack(args), base=args.dir, limit=args.limit, progress=progress)
    print(json.dumps(r, indent=1))


def cmd_query(args):
    hits = wp.query(args.id, args.text, k=args.k, base=args.dir)
    if not hits:
        print("no hits")
    for h in hits:
        print(f"{h['score']:8.2f}  {h['title']}  [{h['heading'] or 'lead'}]  {h['url']}\n          {h['snippet'][:200]}")


def cmd_delete(args):
    removed = wp.delete_pack(args.id, base=args.dir, forget=args.forget)
    print("removed: " + (", ".join(removed) or "nothing"))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dir", help="pack directory (default data/wiki_packs)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("define")
    d.add_argument("id")
    d.add_argument("--lang", required=True)
    d.add_argument("--category")
    d.add_argument("--depth", type=int, default=1)
    d.add_argument("--wikiproject")
    d.add_argument("--name")
    d.add_argument("--topic", default="")
    d.add_argument("--exclude", action="append", help="regex on article titles; repeatable")
    sub.add_parser("list")
    p = sub.add_parser("plan")
    p.add_argument("id")
    p.add_argument("--sample", type=int, default=25)
    b = sub.add_parser("build")
    b.add_argument("id")
    b.add_argument("--limit", type=int, help="fetch at most this many articles (a timing run)")
    q = sub.add_parser("query")
    q.add_argument("id")
    q.add_argument("text")
    q.add_argument("-k", type=int, default=5)
    x = sub.add_parser("delete")
    x.add_argument("id")
    x.add_argument("--forget", action="store_true", help="also remove the definition")
    args = ap.parse_args(argv)
    try:
        _run(args)
    except wp.WikiApiError as exc:
        raise SystemExit(f"Wikipedia API: {exc}. Nothing stored is lost; rerun the same command to resume.")


def _run(args):
    {"define": cmd_define, "list": cmd_list, "plan": cmd_plan, "build": cmd_build,
     "query": cmd_query, "delete": cmd_delete}[args.cmd](args)


if __name__ == "__main__":
    main()
