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
from transformers import (
	VisionEncoderDecoderModel,
	ViTImageProcessor,
	AutoTokenizer,
	Blip2ForConditionalGeneration,
	Blip2Processor,
)
from contextlib import nullcontext


def make_parser():
	p = argparse.ArgumentParser(description='Generate image captions with BLIP-2')
	p.add_argument('--input', '-i', default='images_zhukovsky', help='Directory with images')
	p.add_argument('--output', '-o', default='descriptions', help='Directory to save descriptions')
	# default set to a stronger BLIP-2 model (change if you prefer another)
	p.add_argument('--model', '-m', default='Salesforce/blip2-opt-2.7b', help='Hugging Face model name')
	p.add_argument('--max-tokens', type=int, default=64, help='Max generated tokens')
	# generation parameters
	p.add_argument('--num-beams', type=int, default=4, help='Beam search width')
	p.add_argument('--no-repeat-ngram-size', type=int, default=3, help='No repeat ngram size')
	p.add_argument('--repetition-penalty', type=float, default=1.2, help='Repetition penalty')
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
	device = torch.device(args.device if args.device is not None else ('cuda' if torch.cuda.is_available() else 'cpu'))

	model_name = args.model
	print(f'Loading model {model_name} on device {device}...')
	# Try to load either a VisionEncoderDecoder-style model or BLIP-2
	is_blip2 = False
	# prefer fp16 + device_map when CUDA is available to place model on GPU(s)
	use_device_map = device.type == 'cuda'
	torch_dtype = torch.float16 if use_device_map else None
	try:
		if use_device_map:
			model = VisionEncoderDecoderModel.from_pretrained(model_name, device_map='auto', torch_dtype=torch_dtype)
		else:
			model = VisionEncoderDecoderModel.from_pretrained(model_name)
		feature_extractor = ViTImageProcessor.from_pretrained(model_name)
		tokenizer = AutoTokenizer.from_pretrained(model_name)
	except Exception:
		# fall back to BLIP-2 style model
		if use_device_map:
			model = Blip2ForConditionalGeneration.from_pretrained(model_name, device_map='auto', torch_dtype=torch_dtype)
		else:
			model = Blip2ForConditionalGeneration.from_pretrained(model_name)
		feature_extractor = Blip2Processor.from_pretrained(model_name)
		tokenizer = AutoTokenizer.from_pretrained(model_name, use_fast=False)
		is_blip2 = True

	# If model not already dispatched to devices, move to selected device
	try:
		model.to(device)
	except Exception:
		# some HF sharded models don't support .to() after device_map
		pass

	if device.type == 'cpu' and 'blip2' in model_name.lower():
		print('Warning: BLIP-2 models are large and will be very slow on CPU. Consider using a CUDA GPU or a smaller model.')

	for img in sorted(input_dir.iterdir()):
		if not img.is_file():
			continue
		print(f'Processing {img.name}...')
		try:
			image = Image.open(img).convert('RGB')
			if is_blip2:
				inputs = feature_extractor(images=image, return_tensors='pt')
				pixel_values = inputs['pixel_values']
				# cast to fp16 if model uses it and run on CUDA
				model_dtype = None
				try:
					model_dtype = next(model.parameters()).dtype
				except Exception:
					model_dtype = None
				if device.type == 'cuda' and model_dtype == torch.float16:
					pixel_values = pixel_values.to(device=device, dtype=torch.float16)
				else:
					pixel_values = pixel_values.to(device)
				ctx = torch.cuda.amp.autocast if device.type == 'cuda' else nullcontext
				with ctx():
					with torch.no_grad():
						output_ids = model.generate(
							pixel_values=pixel_values,
							max_length=args.max_tokens,
							num_beams=args.num_beams,
							no_repeat_ngram_size=args.no_repeat_ngram_size,
							repetition_penalty=args.repetition_penalty,
							early_stopping=True,
						)
				caption = tokenizer.decode(output_ids[0], skip_special_tokens=True).strip()
			else:
				pixel_values = feature_extractor(images=image, return_tensors='pt').pixel_values
				model_dtype = None
				try:
					model_dtype = next(model.parameters()).dtype
				except Exception:
					model_dtype = None
				if device.type == 'cuda' and model_dtype == torch.float16:
					pixel_values = pixel_values.to(device=device, dtype=torch.float16)
				else:
					pixel_values = pixel_values.to(device)
				ctx = torch.cuda.amp.autocast if device.type == 'cuda' else nullcontext
				with ctx():
					with torch.no_grad():
						output_ids = model.generate(
							pixel_values,
							max_length=args.max_tokens,
							num_beams=args.num_beams,
							no_repeat_ngram_size=args.no_repeat_ngram_size,
							repetition_penalty=args.repetition_penalty,
							early_stopping=True,
						)
				caption = tokenizer.decode(output_ids[0], skip_special_tokens=True).strip()
		except Exception as e:
			print('Failed to describe', img.name, '->', e)
			caption = ''

		print('Caption:', caption)
		(out_dir / (img.stem + '.txt')).write_text(caption, encoding='utf-8')


if __name__ == '__main__':
	main()
