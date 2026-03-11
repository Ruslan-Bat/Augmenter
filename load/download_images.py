#!/usr/bin/env python3
"""
Simple image downloader using icrawler.
Downloads images for a given query (default: "Город Жуковский. Места в Жуковском").
"""

import sys
import os
import shutil
import hashlib
from argparse import ArgumentParser
from pathlib import Path
import tempfile


def make_parser():
    p = ArgumentParser(description="Download images with icrawler")
    p.add_argument("--query", "-q", default="Город Жуковский", help="Search query")
    p.add_argument("--num", "-n", type=int, default=200, help="Number of images to download")
    p.add_argument("--output", "-o", default="images_zhukovsky", help="Output directory")
    return p


def main():
    parser = make_parser()
    args = parser.parse_args()

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        from icrawler.builtin import BingImageCrawler
    except Exception:
        sys.stderr.write("icrawler is not installed. Install with: pip install icrawler\n")
        sys.exit(1)

    # Prepare set of hashes for already-downloaded images
    def file_hash(path: Path):
        h = hashlib.sha256()
        with path.open('rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                h.update(chunk)
        return h.hexdigest()

    seen = set()
    for p in out_dir.iterdir():
        if p.is_file():
            try:
                seen.add(file_hash(p))
            except Exception:
                continue

    # Queries variations to collect more diverse results
    base_query = args.query
    queries = [base_query,
               base_query + " улица",
               base_query + " центр",
               base_query + " парк",
               base_query + " здания",
               base_query + " аэровокзал",
               base_query + " памятник",
               base_query + " улицы",
               base_query + " улицы вечером",
               base_query + " панорама"]

    needed = args.num - len(seen)
    print(f"Need {needed} more unique images (target {args.num}).")

    tmp_dir = Path(tempfile.mkdtemp(prefix="icrawler_tmp_"))

    try:
        # sequential index for naming
        existing_count = len([p for p in out_dir.iterdir() if p.is_file()])
        idx = existing_count + 1

        for q in queries:
            if needed <= 0:
                break
            # download a batch into temporary dir
            batch = max(50, needed * 2)
            print(f"Crawling query=\"{q}\" batch={batch} into temp {tmp_dir}")
            crawler = BingImageCrawler(storage={"root_dir": str(tmp_dir)})
            crawler.crawl(keyword=q, max_num=batch)

            # process downloaded files
            for f in tmp_dir.iterdir():
                if not f.is_file():
                    continue
                try:
                    h = file_hash(f)
                except Exception:
                    f.unlink(missing_ok=True)
                    continue

                if h in seen:
                    f.unlink(missing_ok=True)
                    continue

                # move unique file to output with sequential name
                ext = f.suffix or ".jpg"
                dest = out_dir / f"img_{idx:05d}{ext}"
                try:
                    shutil.move(str(f), str(dest))
                except Exception:
                    try:
                        shutil.copy2(str(f), str(dest))
                        f.unlink(missing_ok=True)
                    except Exception:
                        continue

                seen.add(h)
                idx += 1
                needed -= 1
                if needed <= 0:
                    break

            # clean tmp dir
            for leftover in tmp_dir.iterdir():
                try:
                    if leftover.is_file():
                        leftover.unlink(missing_ok=True)
                    elif leftover.is_dir():
                        shutil.rmtree(leftover, ignore_errors=True)
                except Exception:
                    pass

        print(f"Finished. Collected {len(seen)} unique images into {out_dir}")
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass


if __name__ == '__main__':
    main()
