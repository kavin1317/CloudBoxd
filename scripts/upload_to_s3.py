"""
Upload raw CSVs to S3 data lake.
Run: python scripts/upload_to_s3.py
"""
import boto3
from pathlib import Path
from loguru import logger
from rich.console import Console

console = Console()
BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR  = BASE_DIR / "data" / "raw"
BUCKET   = "cloudboxd-dev-data-lake"

def main():
    console.rule("[bold cyan]Uploading CSVs → S3[/bold cyan]")
    s3 = boto3.client("s3")

    files = sorted(RAW_DIR.glob("*.csv"))
    for f in files:
        key = f"raw/{f.name}"
        s3.upload_file(str(f), BUCKET, key)
        logger.info(f"  ✓ s3://{BUCKET}/{key}")

    console.print(f"\n[bold green]✅ {len(files)} files uploaded to s3://{BUCKET}/raw/[/bold green]")

if __name__ == "__main__":
    main()
