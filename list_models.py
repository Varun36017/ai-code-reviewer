import tomllib
from pathlib import Path

from google import genai


secrets_path = (
    Path(__file__).resolve().parent
    / ".streamlit"
    / "secrets.toml"
)

with secrets_path.open("rb") as file:
    settings = tomllib.load(file)

api_key = settings["GEMINI_API_KEY"]

with genai.Client(api_key=api_key) as client:
    models = list(client.models.list())

print(f"\nTotal models returned: {len(models)}\n")

for model in models:
    model_id = (model.name or "").removeprefix("models/")

    print(f"Model ID: {model_id}")
    print(f"Supported actions: {model.supported_actions}")
    print()