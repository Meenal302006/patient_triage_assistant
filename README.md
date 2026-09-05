problem statement number:TRACK_ID=PS01
to run above project use the command:streamlit run app.py
problem statement:Healthcare - Patient Intake Triage Assistant (TRACK_ID=PS01)
Patients arriving at intake describe their situation in incomplete, everyday language - and the cost of routing
them wrongly is measured in outcomes, not minutes.
Build a triage assistant that takes a patient's description in plain language, asks relevant follow-up questions
when information is missing, and checks the case against a small set of triage rules covering common walk-in
complaints - fever, injury, chest pain, breathing difficulty, abdominal pain. It produces a triage note: the
recommended urgency level and department, the specific rule or reasoning behind the recommendation, what
the patient reported versus what the follow-ups established, and what remains unknown. The system must
not diagnose, must cite the rule behind every recommendation, and must escalate uncertain or high-risk
cases to a human rather than guessing.
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
