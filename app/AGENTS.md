# Python code

- Keep `main.py` readable from top to bottom: read, rename, clean, prepare, classify, save.
- Preparation code belongs in `data_preparation`; name mappings belong in CSV and prompts and definitions belong in YAML.
- Use Pydantic for the fields sent to the model and the structured response.
- Preserve source files and row IDs. Exclude IDs from model input and redact emails from text.
- Keep essential checks for CSV shape, unique IDs, mapping collisions, and evidence quotes.
- Use short functions and clear early returns; avoid custom exception layers.
