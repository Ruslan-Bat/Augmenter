# Image Downloader (icrawler)

This project contains a small script to download images for the query "Город Жуковский" using `icrawler`.

Prerequisites

- Python 3.8+
- Install icrawler:

```bash
pip install icrawler
```

Usage

```bash
python download_images.py --query "Город Жуковский" --num 200 --output images_zhukovsky
```

Options

- `--query` (`-q`): Search query (default: "Город Жуковский")
- `--num` (`-n`): Number of images to download (default: 200)
- `--output` (`-o`): Output directory (default: `images_zhukovsky`)

Notes

- If downloads stop early, try reducing `--num` or re-running.
- Depending on the search engine and network, some images may be duplicates or broken.
- Respect copyright and usage rights of downloaded images.
