import os
import sys
import json
import argparse

# Import the search function from the package file
import pandas as pd


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('query', nargs='?', default='')
    parser.add_argument('--csv', default=None)
    parser.add_argument('--images', default=None)
    args = parser.parse_args()

    project_root = os.path.dirname(os.path.abspath(__file__))
    csv_path = args.csv or os.path.join(project_root, 'info.csv')
    # prefer 'Augmenter' but fall back to 'Images' if missing
    default_aug = os.path.join(project_root, 'Augmenter')
    images_root = args.images or default_aug
    if not os.path.isdir(images_root):
        # try case-insensitive match for 'augmenter'
        found = False
        for entry in os.listdir(project_root):
            p = os.path.join(project_root, entry)
            if os.path.isdir(p) and entry.lower() == 'augmenter':
                images_root = p
                found = True
                break
        if not found:
            # fall back to Images folder
            imgs = os.path.join(project_root, 'Images')
            if os.path.isdir(imgs):
                images_root = imgs

    # Ensure MIPT_practice is importable for modules that use bare imports
    mipt_dir = os.path.join(project_root, 'MIPT_practice')
    if os.path.isdir(mipt_dir) and mipt_dir not in sys.path:
        sys.path.insert(0, mipt_dir)

    try:
        from MIPT_practice.find_image import find_unique_images
    except Exception as e:
        # try importing module directly from mipt_dir
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location('find_image', os.path.join(mipt_dir, 'find_image.py'))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            find_unique_images = getattr(mod, 'find_unique_images')
        except Exception:
            print(json.dumps([]))
            return

    # read csv (semicolon separated as used by imageviewer)
    try:
        df = pd.read_csv(csv_path, sep=';', dtype=str, keep_default_na=False)
    except Exception as e:
        print(json.dumps([]))
        return

    # normalize columns to 'image' and 'caption'
    cols = list(df.columns)
    if 'image' not in cols or 'caption' not in cols:
        if len(cols) >= 3:
            df = df.rename(columns={cols[1]: 'image', cols[2]: 'caption'})
        elif len(cols) == 2:
            df = df.rename(columns={cols[0]: 'image', cols[1]: 'caption'})

    query = args.query
    if not query:
        print(json.dumps([]))
        return
    

    try:
        results = find_unique_images(query, df, images_root, ssim_threshold=0.85, top_k=1)
    except Exception:
        print(json.dumps([]))
        return

    if not results:
        print(json.dumps([]))
        return

    # return only paths (or empty list)
    paths = [r['path'] for r in results]
    print(json.dumps(paths, ensure_ascii=False))


if __name__ == '__main__':
    main()
