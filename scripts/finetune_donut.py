"""Fine-tunes naver-clova-ix/donut-base to read a cropped feature-control-
frame image and emit its canonical "CODE|value|DATUMS" grammar string.

    python donut_finetune.py --epochs 4 --batch-size 8
"""

import argparse
import json
import os
import time

import torch
from PIL import Image
from torch.utils.data import DataLoader, Dataset
from transformers import DonutProcessor, VisionEncoderDecoderModel

TASK_TOKEN = "<fcf>"
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
MODEL_OUT = os.path.join(os.path.dirname(__file__), "..", "models", "donut_finetuned")


class FCFCropDataset(Dataset):
    def __init__(self, split, processor, max_target_len=48):
        crop_dir = os.path.join(DATA_DIR, "fcf_crops", split)
        targets = json.load(open(os.path.join(DATA_DIR, f"fcf_targets_{split}.json")))
        self.items = [(os.path.join(crop_dir, crop_id + ".png"), t["grammar_string"])
                      for crop_id, t in targets.items()]
        self.processor = processor
        self.max_target_len = max_target_len

    def __len__(self):
        return len(self.items)

    def __getitem__(self, idx):
        path, target_str = self.items[idx]
        image = Image.open(path).convert("RGB")
        pixel_values = self.processor(image, return_tensors="pt").pixel_values.squeeze(0)
        labels = self.processor.tokenizer(
            TASK_TOKEN + target_str + self.processor.tokenizer.eos_token,
            add_special_tokens=False,
            max_length=self.max_target_len,
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        ).input_ids.squeeze(0)
        labels[labels == self.processor.tokenizer.pad_token_id] = -100
        return pixel_values, labels


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--lr", type=float, default=3e-5)
    parser.add_argument("--limit-train", type=int, default=0, help="0 means use all")
    args = parser.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"device: {device}")

    processor = DonutProcessor.from_pretrained("naver-clova-ix/donut-base")
    processor.tokenizer.add_special_tokens({"additional_special_tokens": [TASK_TOKEN]})
    model = VisionEncoderDecoderModel.from_pretrained("naver-clova-ix/donut-base")
    model.decoder.resize_token_embeddings(len(processor.tokenizer))
    model.config.decoder_start_token_id = processor.tokenizer.convert_tokens_to_ids(TASK_TOKEN)
    model.config.pad_token_id = processor.tokenizer.pad_token_id
    # small FCF crops, not full A4 scans: shrink the encoder's input resolution for speed
    processor.image_processor.size = {"height": 320, "width": 320}
    model.config.encoder.image_size = [320, 320]
    model.to(device)

    train_ds = FCFCropDataset("train", processor)
    if args.limit_train:
        train_ds.items = train_ds.items[: args.limit_train]
    val_ds = FCFCropDataset("val", processor)
    print(f"train crops: {len(train_ds)}, val crops: {len(val_ds)}")

    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True, num_workers=2)
    val_loader = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False, num_workers=2)

    opt = torch.optim.AdamW(model.parameters(), lr=args.lr)
    t0 = time.time()
    for epoch in range(args.epochs):
        model.train()
        total_loss, n_batches = 0.0, 0
        for pixel_values, labels in train_loader:
            pixel_values, labels = pixel_values.to(device), labels.to(device)
            out = model(pixel_values=pixel_values, labels=labels)
            loss = out.loss
            opt.zero_grad()
            loss.backward()
            opt.step()
            total_loss += loss.item()
            n_batches += 1
        model.eval()
        val_loss, n_val_batches = 0.0, 0
        with torch.no_grad():
            for pixel_values, labels in val_loader:
                pixel_values, labels = pixel_values.to(device), labels.to(device)
                out = model(pixel_values=pixel_values, labels=labels)
                val_loss += out.loss.item()
                n_val_batches += 1
        print(f"epoch {epoch}  train_loss {total_loss / max(1, n_batches):.4f}  "
              f"val_loss {val_loss / max(1, n_val_batches):.4f}  elapsed {time.time() - t0:.1f}s")

    os.makedirs(MODEL_OUT, exist_ok=True)
    model.save_pretrained(MODEL_OUT)
    processor.save_pretrained(MODEL_OUT)
    print(f"saved to {MODEL_OUT}, total time {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
