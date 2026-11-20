"""Runs a Donut model (fine-tuned or the stock pretrained checkpoint) on
one FCF crop and returns its raw generated text."""

from __future__ import annotations

import torch
from PIL import Image


class DonutExtractor:
    def __init__(self, model_dir: str, task_token: str = "<fcf>", device: str | None = None, max_new_tokens: int = 48):
        from transformers import DonutProcessor, VisionEncoderDecoderModel

        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.processor = DonutProcessor.from_pretrained(model_dir)
        self.model = VisionEncoderDecoderModel.from_pretrained(model_dir).to(self.device)
        self.model.eval()
        self.task_token = task_token
        self.max_new_tokens = max_new_tokens

    def read_crop(self, image_path: str, with_confidence: bool = False):
        image = Image.open(image_path).convert("RGB")
        pixel_values = self.processor(image, return_tensors="pt").pixel_values.to(self.device)
        decoder_input_ids = self.processor.tokenizer(
            self.task_token, add_special_tokens=False, return_tensors="pt"
        ).input_ids.to(self.device)
        with torch.no_grad():
            result = self.model.generate(
                pixel_values,
                decoder_input_ids=decoder_input_ids,
                max_length=self.max_new_tokens,
                eos_token_id=self.processor.tokenizer.eos_token_id,
                pad_token_id=self.processor.tokenizer.pad_token_id,
                output_scores=with_confidence,
                return_dict_in_generate=with_confidence,
            )
        if not with_confidence:
            sequences = result
            text = self.processor.tokenizer.batch_decode(sequences, skip_special_tokens=True)[0]
            return text.replace(self.task_token, "").strip()

        sequences = result.sequences
        text = self.processor.tokenizer.batch_decode(sequences, skip_special_tokens=True)[0]
        text = text.replace(self.task_token, "").strip()
        # mean of the generated sequence's own per-token max softmax
        # probability: a cheap, honest proxy for "how sure was the model",
        # not a calibrated probability on its own (see calibrate_abstention_threshold).
        probs = [torch.softmax(step_logits[0], dim=-1).max().item() for step_logits in result.scores]
        confidence = sum(probs) / len(probs) if probs else 0.0
        return text, confidence
