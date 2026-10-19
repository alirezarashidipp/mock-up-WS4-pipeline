# Local execution

Install requirements into the existing virtual environment. Run the pipeline manually, then start FastAPI:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m app.main
.\.venv\Scripts\python.exe -m app.review
```

Open http://127.0.0.1:8765/. The first command that runs `app.main` calls OpenAI using the local ignored `.env`. Review makes no model calls. Set paths in `app/main.py`; approved and human-review outputs go beside the results.

For the five-record hand-authored demo, run `python -m app.review --demo` instead. Stop the server with Ctrl+C. Run one worker locally; authentication, cloud hosting, and multi-process storage are outside this PoC.

Python 3.11 is the target. The existing environment is Python 3.14; execution on Python 3.11 is unverified. Tests are not run when the user asks to skip them.
