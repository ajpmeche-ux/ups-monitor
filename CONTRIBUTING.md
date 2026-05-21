# Contributing

Thank you for considering a contribution to UPS Monitor.

## How to contribute

1. Fork the repository.
2. Create a feature branch:
   ```bash
   git checkout -b feature/your-change
   ```
3. Install dependencies in a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install -r requirements.txt
   ```
4. Run tests:
   ```bash
   python -m pytest -q
   ```
5. Commit your changes and open a pull request.

## Coding style

- Keep the code simple and readable.
- Use type hints where appropriate.
- Avoid committing environment-specific files.
