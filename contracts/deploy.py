# Build the sample contract in this directory using Beaker and output to ./artifacts
from pathlib import Path

from contracts.app import app


def build() -> Path:
    app_spec = app.build()
    output_dir = Path(__file__).parent / "artifacts"
    print(f"Dumping {app_spec.contract.name} to {output_dir}")
    app_spec.export(output_dir)
    return output_dir / "application.json"


if __name__ == "__main__":
    build()