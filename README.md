# Patient Intake Triage Assistant

A Streamlit prototype for multilingual patient-intake information collection and rule-based safety triage.

## Run locally

1. Install dependencies:

```text
pip install -r requirements.txt
```

2. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`.
3. Add a valid `GEMINI_API_KEY` to the local secrets file.
4. Start the app:

```text
streamlit run app.py
```

## Test

Run the rule catalogue checks with:

```text
python -m unittest test_triage_rules.py
```

## Safety design

- Gemini extracts patient information only.
- Final urgency and care destination come only from the local rule engine.
- Unknown, unsupported, and contradictory inputs do not receive an invented triage result.
- Every result shows the matched rule, condition, catalogue version, and human-review status.
- Telugu, English, and mixed-language input are supported by the extraction prompt and deterministic fallback keywords.

## Prototype limitations

This is not a diagnostic tool and is not approved for clinical use. The rule catalogue requires review and validation by qualified healthcare professionals before deployment. Production use would also require authenticated access, encrypted persistence, audit retention, monitoring, and a formal privacy review.

Never commit `.streamlit/secrets.toml` or expose an API key. If a key was previously shared or committed, rotate it immediately.
