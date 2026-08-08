import os
import argparse
import pandas as pd
import torch
from torch.utils.data import Dataset, DataLoader

try:
    from transformers import M2M100ForConditionalGeneration, M2M100Tokenizer
    from torch.optim import AdamW
    from transformers import get_linear_schedule_with_warmup
except ImportError:
    try:
        from transformers import M2M100ForConditionalGeneration, M2M100Tokenizer
        from torch.optim import AdamW
        get_linear_schedule_with_warmup = None
    except ImportError:
        M2M100ForConditionalGeneration = None
        M2M100Tokenizer = None

class ParallelBilingualDataset(Dataset):
    def __init__(self, csv_path: str, tokenizer, src_lang: str = "mr", tgt_lang: str = "en", max_length: int = 128):
        self.df = pd.read_csv(csv_path)
        self.tokenizer = tokenizer
        self.src_lang = src_lang
        self.tgt_lang = tgt_lang
        self.max_length = max_length

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        row = self.df.iloc[idx]
        src_text = str(row["src"]).strip()
        tgt_text = str(row["tgt"]).strip()

        self.tokenizer.src_lang = self.src_lang
        inputs = self.tokenizer(src_text, max_length=self.max_length, padding="max_length", truncation=True, return_tensors="pt")

        self.tokenizer.src_lang = self.tgt_lang
        targets = self.tokenizer(tgt_text, max_length=self.max_length, padding="max_length", truncation=True, return_tensors="pt")

        labels = targets["input_ids"].squeeze(0)
        labels[labels == self.tokenizer.pad_token_id] = -100

        return {
            "input_ids": inputs["input_ids"].squeeze(0),
            "attention_mask": inputs["attention_mask"].squeeze(0),
            "labels": labels
        }

def train_model(csv_path: str, output_dir: str, epochs: int = 3, lr: float = 5e-5, batch_size: int = 2):
    """Fine-tunes M2M100 / IndicTrans2 seq2seq model on custom bilingual parallel dataset."""
    if M2M100ForConditionalGeneration is None:
        print("[!] PyTorch and Transformers library are required for model fine-tuning.")
        return

    print(f"[*] Loading dataset from {csv_path}...")
    if not os.path.exists(csv_path):
        print(f"[!] Dataset file {csv_path} not found.")
        return

    model_name = "facebook/m2m100_418M"
    print(f"[*] Initializing pre-trained model '{model_name}'...")
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[*] Using compute device: {device}")

    tokenizer = M2M100Tokenizer.from_pretrained(model_name)
    model = M2M100ForConditionalGeneration.from_pretrained(model_name).to(device)

    dataset = ParallelBilingualDataset(csv_path, tokenizer, src_lang="mr", tgt_lang="en")
    dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

    optimizer = AdamW(model.parameters(), lr=lr)
    total_steps = len(dataloader) * epochs
    scheduler = get_linear_schedule_with_warmup(optimizer, num_warmup_steps=0, num_training_steps=total_steps) if get_linear_schedule_with_warmup else None

    print(f"[*] Starting fine-tuning for {epochs} epochs ({total_steps} total steps)...")
    model.train()

    for epoch in range(epochs):
        epoch_loss = 0.0
        for step, batch in enumerate(dataloader):
            optimizer.zero_grad()

            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels = batch["labels"].to(device)

            outputs = model(input_ids=input_ids, attention_mask=attention_mask, labels=labels)
            loss = outputs.loss
            loss.backward()

            optimizer.step()
            if scheduler:
                scheduler.step()

            epoch_loss += loss.item()
            print(f"    Epoch [{epoch+1}/{epochs}] Step [{step+1}/{len(dataloader)}] - Loss: {loss.item():.4f}")

        avg_loss = epoch_loss / max(len(dataloader), 1)
        print(f"[+] Epoch {epoch+1} Complete. Average Loss: {avg_loss:.4f}")

    os.makedirs(output_dir, exist_ok=True)
    print(f"[*] Saving fine-tuned model checkpoint to '{output_dir}'...")
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)
    print(f"[+] Fine-tuning complete! Model checkpoint saved to {output_dir}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fine-tune NMT model on custom bilingual document pairs.")
    parser.add_argument("--csv", type=str, default="data/bilingual_dataset.csv", help="Path to bilingual CSV dataset")
    parser.add_argument("--output", type=str, default="models/indictrans_finetuned", help="Directory to save fine-tuned model")
    parser.add_argument("--epochs", type=int, default=3, help="Number of training epochs")
    parser.add_argument("--lr", type=float, default=5e-5, help="Learning rate")
    args = parser.parse_args()

    train_model(args.csv, args.output, epochs=args.epochs, lr=args.lr)
