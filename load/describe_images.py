#!/usr/bin/env python3
"""
Generate image descriptions using BLIP-2 (Hugging Face transformers).

This script iterates images in the input directory, runs a BLIP-2
image-to-text model and prints/saves the returned captions.

Usage:
  Activate your virtualenv, install requirements and run:

	.venv\\Scripts\\Activate.ps1
	pip install -r requirements.txt
	python describe_images.py --input images_zhukovsky --output descriptions_blip --model "Salesforce/blip2-opt-2.7b"

Notes:
  - Large BLIP-2 models require GPU (CUDA). On CPU they may be very slow or fail.
  - Use `--model` to choose a smaller or different BLIP-2 model if available.
"""

import argparse
from pathlib import Path
from PIL import Image
import torch
from transformers import VisionEncoderDecoderModel, ViTImageProcessor, AutoTokenizer


def make_parser():
	p = argparse.ArgumentParser(description='Generate image captions with BLIP-2')
	p.add_argument('--input', '-i', default='images_zhukovsky', help='Directory with images')
	p.add_argument('--output', '-o', default='descriptions', help='Directory to save descriptions')
	p.add_argument('--model', '-m', default='nlpconnect/vit-gpt2-image-captioning', help='Hugging Face model name')
	p.add_argument('--max-tokens', type=int, default=32, help='Max generated tokens')
	p.add_argument('--device', default=None, help='Device to run on (e.g. cpu or cuda). Auto-detected if omitted')
	return p


def describe_image_with_pipeline(captions_pipe, image_path: Path, max_tokens: int):
	image = Image.open(image_path).convert('RGB')
	result = captions_pipe(image, max_length=max_tokens)
	# pipeline returns a list of dicts with 'caption'
	if isinstance(result, list) and len(result) > 0:
		return result[0].get('caption', '').strip()
	return ''


def main():
	args = make_parser().parse_args()
	input_dir = Path(args.input)
	out_dir = Path(args.output)
	out_dir.mkdir(parents=True, exist_ok=True)

	if not input_dir.exists():
		print('Input directory not found:', input_dir)
		return

	# choose device
	device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

	model_name = args.model
	print(f'Loading model {model_name} on device {device}...')
	model = VisionEncoderDecoderModel.from_pretrained(model_name)
	feature_extractor = ViTImageProcessor.from_pretrained(model_name)
	tokenizer = AutoTokenizer.from_pretrained(model_name)
	model.to(device)

	for img in sorted(input_dir.iterdir()):
		if not img.is_file():
			continue
		print(f'Processing {img.name}...')
		try:
			image = Image.open(img).convert('RGB')
			pixel_values = feature_extractor(images=image, return_tensors='pt').pixel_values.to(device)
			with torch.no_grad():
				output_ids = model.generate(pixel_values, max_length=args.max_tokens, num_beams=4)
			caption = tokenizer.decode(output_ids[0], skip_special_tokens=True).strip()
		except Exception as e:
			print('Failed to describe', img.name, '->', e)
			caption = ''

		print('Caption:', caption)
		(out_dir / (img.stem + '.txt')).write_text(caption, encoding='utf-8')


if __name__ == '__main__':
	main()
