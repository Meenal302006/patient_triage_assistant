import streamlit as st
import json
import os
import re
from datetime import datetime, timezone
from google import genai


# ============================================================
# PAGE CONFIGURATION
st.set_page_config(
    page_title="Patient Intake Triage Assistant",
    page_icon="🏥",
    layout="wide"
)

st.markdown(
    """
    <style>
    .stApp { background: #f5faf8; }
    [data-testid="stAppViewContainer"] > .main .block-container {
        max-width: 1120px;
        padding: 2rem 2rem 4rem;
    }
    [data-testid="stHeader"] { background: transparent; }
    [data-testid="stMetric"] {
        min-height: 112px;
        padding: 1rem 1.1rem;
        border: 1px solid #d8e9e4;
        border-radius: 12px;
        background: #ffffff;
        box-shadow: 0 8px 20px rgba(20, 43, 53, 0.05);
    }
    [data-testid="stMetricLabel"] p {
        color: #60747b;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.06em;
        text-transform: uppercase;
    }
    [data-testid="stMetricValue"] {
        color: #142b35;
        font-size: 1.35rem;
        line-height: 1.2;
    }
    [data-testid="stProgressBar"] {
        padding: 0.75rem 1rem 0.55rem;
        border: 1px solid #d8e9e4;
        border-radius: 10px;
        background: #ffffff;
    }
    [data-testid="stProgressBar"] > div > div > div {
        background: #087f83;
    }
    .hero {
        padding: 2rem;
        border: 1px solid #d8e9e4;
        border-radius: 16px;
        background: #ffffff;
        box-shadow: 0 12px 30px rgba(20, 43, 53, 0.07);
    }
    .hero .eyebrow {
        color: #087f83;
        font-size: 0.75rem;
        font-weight: 700;
        letter-spacing: 0.12em;
        text-transform: uppercase;
    }
    .hero h1 {
        margin: 0.5rem 0;
        color: #142b35;
        font-family: Georgia, serif;
        font-size: 3rem;
        line-height: 1;
    }
    .hero h1 span { color: #087f83; }
    .hero p { max-width: 650px; color: #60747b; line-height: 1.6; }
        .dashboard-label {
            color: #087f83;
            font-size: 0.75rem;
            font-weight: 700;
            letter-spacing: 0.12em;
            text-transform: uppercase;
        }
        .dashboard-title {
            color: #142b35;
            font-family: Georgia, serif;
            font-size: 2rem;
            margin: 0.2rem 0 1rem;
        }
    [data-testid="stChatMessage"] {
        border: 1px solid #d8e9e4;
        border-radius: 12px;
        background: #ffffff;
    }
    .stButton > button, .stFormSubmitButton > button {
        border: 0;
        border-radius: 8px;
        background: #087f83;
        color: #ffffff;
        font-weight: 700;
    }
    .stButton > button:hover, .stFormSubmitButton > button:hover {
        border: 0;
        background: #07545b;
        color: #ffffff;
    }
    @media (max-width: 640px) {
        [data-testid="stAppViewContainer"] > .main .block-container {
            padding: 1.25rem 1rem 3rem;
        }
        .hero { padding: 1.35rem; }
        .hero h1 { font-size: 2.3rem; }
    }
    </style>
    """,
    unsafe_allow_html=True
)


# ============================================================
# GEMINI CONFIGURATION
# ============================================================

# Store the key in Streamlit secrets or an environment variable.
try:
    configured_key = st.secrets.get("GEMINI_API_KEY", "")
except Exception:
    configured_key = ""

GEMINI_API_KEY = configured_key or os.getenv(
    "GEMINI_API_KEY",
    ""
)

client = (
    genai.Client(api_key=GEMINI_API_KEY)
    if GEMINI_API_KEY
    else None
)

if client is None:

    st.error("Gemini is not configured for this demo.")

    st.info(
        "Add GEMINI_API_KEY to Streamlit secrets or your environment, "
        "then restart the app."
    )

    st.stop()


# ============================================================
# LOAD TRIAGE RULES
# ============================================================

with open("triage_rules.json", "r", encoding="utf-8") as file:
    RULE_DATA = json.load(file)


    def validate_rule_catalogue(rule_data):

        supported = set(rule_data.get("supported_complaints", []))
        rules = rule_data.get("rules", [])

        if not supported:
            raise ValueError("The rule catalogue has no supported complaints.")

        if not isinstance(rules, list) or not rules:
            raise ValueError("The rule catalogue has no rules.")

        rule_ids = [rule.get("id") for rule in rules]

        if any(not rule_id for rule_id in rule_ids):
            raise ValueError("Every triage rule must have an id.")

        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("Triage rule ids must be unique.")

        required_fields = {
            "id",
            "complaint",
            "condition",
            "urgency",
            "department",
            "next_step",
            "human_review"
        }

        for rule in rules:

            missing_fields = required_fields.difference(rule)

            if missing_fields:
                raise ValueError(
                    f"Rule {rule.get('id', '<unknown>')} is missing: "
                    f"{', '.join(sorted(missing_fields))}."
                )

            if rule["complaint"] not in supported:
                raise ValueError(
                    f"Rule {rule['id']} uses an unsupported complaint."
                )


    validate_rule_catalogue(RULE_DATA)

RULES = RULE_DATA["rules"]
SUPPORTED_COMPLAINTS = set(
    RULE_DATA["supported_complaints"]
)
SUPPORTED_COMPLAINTS.add("unknown")
SUPPORTED_COMPLAINTS.add("unsupported")


# ============================================================
# SESSION STATE
# ============================================================

if "messages" not in st.session_state:
    st.session_state.messages = []

if "patient_info" not in st.session_state:
    st.session_state.patient_info = {}

if "follow_up_questions" not in st.session_state:
    st.session_state.follow_up_questions = []

if "triage_result" not in st.session_state:
    st.session_state.triage_result = None

if "waiting_for_answers" not in st.session_state:
    st.session_state.waiting_for_answers = False

if "conversation_complete" not in st.session_state:
    st.session_state.conversation_complete = False

if "clarification_rounds" not in st.session_state:
    st.session_state.clarification_rounds = 0

if "gemini_follow_up_understanding" not in st.session_state:
    st.session_state.gemini_follow_up_understanding = {}

if "decision_history" not in st.session_state:
    st.session_state.decision_history = []


# ============================================================
# HELPER: CLEAN GEMINI JSON
# ============================================================

def clean_json_response(text):

    text = text.strip()

    if text.startswith("```json"):
        text = text[7:]

    elif text.startswith("```"):
        text = text[3:]

    if text.endswith("```"):
        text = text[:-3]

    return text.strip()


def validate_patient_input(value, field_name="message"):

    text = str(value).strip()

    if not text:

        return f"Please enter a {field_name}."

    if len(text) < 2:

        return f"Please provide more detail in the {field_name}."

    if len(text) > 1000:

        return f"The {field_name} is too long. Please keep it under 1,000 characters."

    if not any(character.isalnum() for character in text):

        return f"Please enter meaningful text in the {field_name}."

    return ""


# ============================================================
# HELPER: DEFAULT PATIENT INFORMATION
# ============================================================

def empty_patient_info():

    return {
        "language": "",
        "original_message": "",
        "complaint": "unknown",
        "symptoms": [],
        "duration": "",
        "severity": "",
        "temperature": "",

        # None = unknown
        # True = yes
        # False = no
        "breathing_difficulty": None,
        "chest_pain": None,
        "chest_pain_severe": None,
        "chest_pain_pressure": None,

        "bleeding": None,
        "severe_bleeding": None,

        "confusion": None,
        "fainting": None,
        "loss_of_consciousness": None,

        "sudden_pain": None,

        "inconsistencies": [],

        "other_information": []
    }


# ============================================================
# GEMINI: UNDERSTAND PATIENT MESSAGE
# ============================================================

def infer_complaint_from_text(text):

    normalized = str(text).lower()

    complaint_keywords = [
        (
            "chest_pain",
            [
                "chest pain",
                "chest hurts",
                "chest pressure",
                "chest tightness",
                "heart pain",
                "chest lo noppi",
                "chest pain undi",
                "gunde noppi",
                "gundello noppi",
                "ఛాతి నొప్పి",
                "ఛాతిలో నొప్పి",
                "గుండె నొప్పి"
            ]
        ),
        (
            "breathing_difficulty",
            [
                "can't breathe",
                "cannot breathe",
                "difficulty breathing",
                "breathless",
                "shortness of breath",
                "breathing problem",
                "oopiri teesukovadam kastam",
                "oopiri ibbandi",
                "swasa ibbandi",
                "saans nahi aa rahi",
                "శ్వాస ఇబ్బంది",
                "ఊపిరి తీసుకోవడం కష్టం",
                "ఊపిరి ఆడటం లేదు"
            ]
        ),
        (
            "abdominal_pain",
            [
                "stomach pain",
                "abdominal pain",
                "belly pain",
                "tummy pain",
                "kadupu noppi",
                "pottalo noppi",
                "pet dard",
                "కడుపు నొప్పి",
                "పొట్ట నొప్పి"
            ]
        ),
        (
            "injury",
            [
                "fell",
                "fall",
                "injured",
                "injury",
                "cut",
                "accident",
                "broken bone",
                "gaayam",
                "gayam",
                "padipoyanu",
                "debba tagilindi",
                "గాయం",
                "పడిపోయాను",
                "దెబ్బ"
            ]
        ),
        (
            "fever",
            [
                "fever",
                "temperature",
                "jwar",
                "jwaram",
                "bukhar",
                "bukhaar",
                "జ్వరం",
                "జ్వరము"
            ]
        )
    ]

    for complaint, keywords in complaint_keywords:

        if any(keyword in normalized for keyword in keywords):
            return complaint

    return "unknown"


def has_unsupported_complaint(text):

    normalized = str(text).lower()
    unsupported_keywords = [
        "headache", "migraine", "dizziness", "dizzy", "cough", "cold",
        "sore throat", "vomiting", "nausea", "diarrhea", "rash", "itching",
        "burning urine", "urine pain", "headache", "తలనొప్పి", "తల తిరగడం",
        "దగ్గు", "జలుబు", "వాంతులు", "వాంతి", "దద్దుర్లు"
    ]

    return any(keyword in normalized for keyword in unsupported_keywords)


def find_inconsistent_input(text):

    normalized = str(text).lower()
    inconsistencies = []

    breathing_no = re.search(
        r"(no|without|not)\s+(difficulty breathing|breathing difficulty|shortness of breath)",
        normalized
    )
    breathing_positive_text = re.sub(
        r"(no|without|not)\s+(difficulty breathing|breathing difficulty|shortness of breath)",
        "",
        normalized
    )
    breathing_yes = re.search(
        r"(can't|cannot|unable|difficulty breathing|breathing difficulty|shortness of breath|breathless)",
        breathing_positive_text
    )

    if breathing_yes and breathing_no:
        inconsistencies.append(
            "The message gives conflicting information about breathing difficulty."
        )

    chest_pain_no = re.search(
        r"\b(no|without)\s+chest pain\b",
        normalized
    )
    chest_pain_positive_text = re.sub(
        r"\b(no|without)\s+chest pain\b",
        "",
        normalized
    )

    if chest_pain_no and re.search(
        r"\b(chest pain|chest hurts|chest pressure)\b",
        chest_pain_positive_text
    ):
        inconsistencies.append(
            "The message gives conflicting information about chest pain."
        )

    if (
        re.search(r"\b(severe|extreme|unbearable)\b", normalized)
        and re.search(r"\b(mild|minor|slight)\b", normalized)
    ):
        inconsistencies.append(
            "The message gives conflicting information about symptom severity."
        )

    return inconsistencies


def get_unclear_input_questions(patient):

    message = str(
        patient.get(
            "original_message",
            ""
        )
    ).lower()

    if any(
        word in message
        for word in [
            "cough", "cold", "throat", "sneeze",
            "దగ్గు", "జలుబు", "గొంతు", "daggu", "jalubu", "gontu"
        ]
    ):

        return [
            "Are you having any difficulty breathing?",
            "Do you have a measured temperature? If yes, what is it?",
            "How long have you had these symptoms?"
        ]

    if any(
        word in message
        for word in [
            "dizzy", "dizziness", "lightheaded", "giddy",
            "తల తిరుగుతోంది", "తల తిరగడం", "thala thirugutondi"
        ]
    ):

        return [
            "Have you fainted or felt like you might faint?",
            "Are you having chest pain or difficulty breathing?",
            "When did the dizziness start?"
        ]

    if any(
        word in message
        for word in [
            "vomit", "vomiting", "nausea", "throwing up",
            "వాంతులు", "వాంతి", "vantulu", "vanti"
        ]
    ):

        return [
            "Are you having severe stomach pain?",
            "Is there any blood in the vomit?",
            "When did the nausea or vomiting start?"
        ]

    if any(
        word in message
        for word in ["pain", "ache", "hurts", "hurt"]
    ) and not any(
        word in message
        for word in ["headache", "migraine", "head pain"]
    ):

        return [
            "Where exactly is the pain?",
            "How severe is the pain: mild, moderate, or severe?",
            "Did the pain start suddenly?"
        ]

    if any(
        word in message
        for word in ["weak", "tired", "fatigue", "no energy"]
    ):

        return [
            "When did the weakness or tiredness start?",
            "Have you fainted or felt confused?",
            "Do you have fever, chest pain, or difficulty breathing?"
        ]

    if any(
        word in message
        for word in ["rash", "itch", "swelling", "swollen", "skin"]
    ):

        return [
            "Where on your body is the rash, itching, or swelling?",
            "Did it appear suddenly, or is it spreading?",
            "Are you having difficulty breathing or swelling of your face or lips?"
        ]

    if any(
        word in message
        for word in ["headache", "migraine", "head pain"]
    ):

        return [
            "How severe is the headache: mild, moderate, or severe?",
            "Did the headache start suddenly?",
            "Do you have confusion, fainting, weakness, or vision changes?"
        ]

    if any(
        word in message
        for word in ["diarrhea", "loose motion", "loose stool"]
    ):

        return [
            "How many times have you had loose stools today?",
            "Is there any blood in the stool?",
            "Are you having severe stomach pain or feeling faint?"
        ]

    if any(
        word in message
        for word in ["burning urine", "urine pain", "cannot pee", "blood in urine"]
    ):

        return [
            "Do you have a fever or pain in your back or side?",
            "Have you noticed blood in your urine?",
            "When did the urinary symptoms start?"
        ]

    return [
        "What is the main problem bothering you right now, and where do you feel it?",
        "When did it start, and is it getting better, getting worse, or staying the same?",
        "How severe is it right now: mild, moderate, severe, or unbearable?"
    ]

def understand_patient_message(message):

    prompt = f"""
You are a healthcare patient-intake information extraction assistant.

Your ONLY job is to understand what the patient said.

IMPORTANT:

1. Do NOT diagnose.
2. Do NOT recommend treatment.
3. Do NOT decide urgency.
4. The final triage decision is made only by the local rule engine.
    Do not return urgency, care destination, or a treatment decision.
5. Do NOT guess.
6. Extract only information explicitly stated or clearly expressed.
7. Understand simple everyday language.
8. Understand incomplete sentences.
9. Understand spelling mistakes.
10. Understand slang.
11. Understand Telugu, Hindi, Tamil, English and other languages.
12. Understand mixed-language sentences.
13. Return structured information in English.
14. If the patient did NOT provide a piece of information,
    return it as UNKNOWN.
14. UNKNOWN boolean information must be returned as null,
    NOT false.

Supported complaints:

- fever
- injury
- chest_pain
- breathing_difficulty
- abdominal_pain
- unknown

Return ONLY valid JSON.

Use exactly this structure:

{{
    "language": "",
    "complaint": "fever | injury | chest_pain | breathing_difficulty | abdominal_pain | unknown",

    "symptoms": [],

    "duration": "",
    "severity": "",

    "temperature": "",

    "breathing_difficulty": null,
    "chest_pain": null,
    "chest_pain_severe": null,
    "chest_pain_pressure": null,

    "bleeding": null,
    "severe_bleeding": null,

    "confusion": null,
    "fainting": null,
    "loss_of_consciousness": null,

    "sudden_pain": null,

    "other_information": []
}}

IMPORTANT BOOLEAN RULE:

If patient says:

"I can't breathe"
=> breathing_difficulty = true

If patient says:

"I can breathe normally"
=> breathing_difficulty = false

If patient never mentions breathing
=> breathing_difficulty = null

Examples:

Patient:
"My chest hurts badly and I can't breathe."

Return:

{{
    "complaint": "chest_pain",
    "chest_pain": true,
    "chest_pain_severe": true,
    "breathing_difficulty": true
}}

Patient:
"naaku rendu rojula nunchi jwaram undi"

Return:

{{
    "complaint": "fever",
    "duration": "2 days"
}}

Patient:
"fever 2 days"

Return:

{{
    "complaint": "fever",
    "duration": "2 days"
}}

Patient:
"my chest hurts"

Do NOT assume severity.

Return:

{{
    "complaint": "chest_pain",
    "chest_pain": true,
    "chest_pain_severe": null,
    "chest_pain_pressure": null,
    "breathing_difficulty": null
}}

Patient:
"fell down, leg pain and little swelling"

Return:

{{
    "complaint": "injury",
    "symptoms": ["leg pain", "swelling"]
}}

Patient:
"Naaku fever undi, rendu rojula nunchi, temperature 38.5 C"

Return:

{{
    "language": "Telugu-English mixed",
    "complaint": "fever",
    "duration": "2 days",
    "temperature": "38.5 C"
}}

Patient message:

{message}
"""

    try:

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        text = clean_json_response(response.text)

        data = json.loads(text)

        # Start with safe defaults
        result = empty_patient_info()

        # Copy Gemini information
        for key in result:

            if key in data:
                result[key] = data[key]

        complaint = str(
            result.get(
                "complaint",
                "unknown"
            )
        ).strip().lower()

        result["complaint"] = (
            complaint
            if complaint in SUPPORTED_COMPLAINTS
            else "unknown"
        )

        detected_complaint = infer_complaint_from_text(message)

        if detected_complaint != "unknown":

            result["complaint"] = detected_complaint

        elif has_unsupported_complaint(message):

            result["complaint"] = "unsupported"

        elif result["complaint"] == "unknown":

            result["complaint"] = infer_complaint_from_text(
                message
            )

        result["original_message"] = message
        result["inconsistencies"] = find_inconsistent_input(message)
        result["gemini_understanding"] = data

        return result

    except Exception as error:

        result = empty_patient_info()

        result["complaint"] = (
            "unsupported"
            if has_unsupported_complaint(message)
            else infer_complaint_from_text(message)
        )
        result["error"] = str(error)
        result["original_message"] = message
        result["inconsistencies"] = find_inconsistent_input(message)
        result["gemini_understanding"] = {}

        return result


# ============================================================
# PYTHON: DETERMINE EXACTLY WHICH INFORMATION IS MISSING
# ============================================================

def get_required_follow_up_questions(patient):

    complaint = patient.get(
        "complaint",
        "unknown"
    )

    questions = []
    duration = patient.get(
        "duration",
        ""
    )
    temperature = patient.get(
        "temperature",
        ""
    )
    severity = patient.get(
        "severity",
        ""
    )
    symptoms = patient.get(
        "symptoms",
        []
    )
    original_message = str(
        patient.get(
            "original_message",
            ""
        )
    ).strip().lower()

    symptom_focus = (
        str(symptoms[0]).strip()
        if symptoms
        else ""
    )

    if complaint == "chest_pain":

        if "pressure" in original_message or "tight" in original_message:

            symptom_focus = "chest pressure or tightness"

        elif "sharp" in original_message:

            symptom_focus = "sharp chest pain"


    # --------------------------------------------------------
    # UNKNOWN OR INCOMPLETE COMPLAINT
    # --------------------------------------------------------

    if complaint in ["unknown", "unsupported"]:

        return get_unclear_input_questions(patient)


    # --------------------------------------------------------
    # CHEST PAIN
    # --------------------------------------------------------

    if complaint == "chest_pain":

        breathing = patient.get(
            "breathing_difficulty"
        )

        severe = patient.get(
            "chest_pain_severe"
        )

        pressure = patient.get(
            "chest_pain_pressure"
        )

        # We need to know whether breathing difficulty exists
        if breathing is None:

            questions.append(
                "Are you having any difficulty breathing?"
            )

        # We need to know whether chest pain is severe
        # or pressure-like
        if severe is None and pressure is None:

            if symptom_focus == "chest pressure or tightness":

                questions.append(
                    "Is the chest pressure or tightness severe?"
                )

            elif symptom_focus == "sharp chest pain":

                questions.append(
                    "Is the sharp chest pain severe?"
                )

            else:

                questions.append(
                    "Is the chest pain severe or does it feel like pressure?"
                )

        if not duration:

            questions.append(
                f"When did the {symptom_focus or 'chest pain'} start?"
            )


    # --------------------------------------------------------
    # BREATHING DIFFICULTY
    # --------------------------------------------------------

    elif complaint == "breathing_difficulty":

        chest_pain = patient.get(
            "chest_pain"
        )

        if not severity:

            questions.append(
                "How severe is the breathing difficulty you described: "
                "mild, moderate, or severe?"
            )

        if chest_pain is None:

            questions.append(
                "Are you also having chest pain?"
            )

        if not duration:

            questions.append(
                "When did the breathing difficulty start?"
            )


    # --------------------------------------------------------
    # ABDOMINAL PAIN
    # --------------------------------------------------------

    elif complaint == "abdominal_pain":

        sudden = patient.get(
            "sudden_pain"
        )

        if not severity:

            questions.append(
                f"How severe is the {symptom_focus or 'stomach pain'}: "
                "mild, moderate, or severe?"
            )

        if sudden is None:

            questions.append(
                "Did the stomach pain start suddenly?"
            )

        if not duration:

            questions.append(
                f"How long have you had the {symptom_focus or 'stomach pain'}?"
            )


    # --------------------------------------------------------
    # INJURY
    # --------------------------------------------------------

    elif complaint == "injury":

        severe_bleeding = patient.get(
            "severe_bleeding"
        )

        loss_of_consciousness = patient.get(
            "loss_of_consciousness"
        )

        if severe_bleeding is None:

            questions.append(
                "Is there severe or uncontrolled bleeding?"
            )

        if loss_of_consciousness is None:

            questions.append(
                "Did the person lose consciousness after the injury?"
            )

        if not symptoms:

            questions.append(
                "Which part of the body was injured, and what happened?"
            )


    # --------------------------------------------------------
    # FEVER
    # --------------------------------------------------------

    elif complaint == "fever":

        breathing = patient.get(
            "breathing_difficulty"
        )

        if not temperature:

            questions.append(
                "What is your temperature? Please include the number and unit "
                "if you have measured it, for example 38.5 °C or 101.3 °F."
            )

        if breathing is None:

            questions.append(
                "Are you having any difficulty breathing along with the fever?"
            )

        if not duration:

            questions.append(
                "How long have you had the fever?"
            )

    return questions[:3]


# ============================================================
# GEMINI: INTERPRET FOLLOW-UP ANSWERS
# ============================================================

def interpret_follow_up_answers(
    questions,
    answers,
    previous_information
):

    prompt = f"""
You are a healthcare patient-intake information extraction assistant.

The patient has already described their problem.

Now they answered follow-up questions.

Your job is ONLY to extract facts from their answers.

IMPORTANT:

1. Do NOT diagnose.
2. Do NOT recommend treatment.
3. Do NOT make a triage decision. The local rule engine makes the final decision.
4. Do NOT guess.
5. Understand simple language.
6. Understand Telugu, Hindi, English and mixed-language answers.
7. If the answer means YES, use true.
8. If the answer means NO, use false.
9. If the answer is unclear, use null.
10. Do not overwrite known information unless the new answer
    clearly provides different information.

Previous information:

{json.dumps(previous_information, ensure_ascii=False)}

Questions:

{json.dumps(questions, ensure_ascii=False)}

Patient answers:

{json.dumps(answers, ensure_ascii=False)}

Return ONLY valid JSON.

Use exactly:

{{
    "complaint": "fever | injury | chest_pain | breathing_difficulty | abdominal_pain | unknown",
    "severity": "",
    "temperature": "",
    "duration": "",

    "breathing_difficulty": null,
    "chest_pain": null,
    "chest_pain_severe": null,
    "chest_pain_pressure": null,

    "severe_bleeding": null,
    "loss_of_consciousness": null,

    "sudden_pain": null,

    "symptoms": [],
    "other_information": []
}}

Examples:

Question:
"Are you having any difficulty breathing?"

Answer:
"No"

Return:

{{
    "breathing_difficulty": false
}}

Question:
"Are you having any difficulty breathing?"

Answer:
"yes, konchem"

Return:

{{
    "breathing_difficulty": true
}}

Question:
"Is the chest pain severe or does it feel like pressure?"

Answer:
"yes very bad"

Return:

{{
    "chest_pain_severe": true
}}

Question:
"Did the person lose consciousness after the injury?"

Answer:
"No"

Return:

{{
    "loss_of_consciousness": false
}}
"""

    try:

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        text = clean_json_response(response.text)

        return json.loads(text)

    except Exception:

        return {}


# ============================================================
# PYTHON: APPLY CLEAR FOLLOW-UP ANSWERS DIRECTLY
# ============================================================

def apply_direct_follow_up_answers(questions, answers):

    extracted = {}

    for question, answer in answers.items():

        text = str(answer).strip()
        normalized = text.lower()

        if any(
            word in normalized
            for word in ["అవును", "అవునండి", "avunu", "haan", "sí"]
        ):
            normalized += " yes"

        if any(
            word in normalized
            for word in ["కాదు", "లేదు", "kaadu", "ledu", "nahi", "nahin"]
        ):
            normalized += " no"

        if any(
            word in normalized
            for word in ["తీవ్రంగా", "తీవ్రమైన", "teevram", "teevranga", "bahut zyada"]
        ):
            normalized += " severe"

        if any(
            word in normalized
            for word in ["మితంగా", "మోస్తరు", "mitanga", "mostaru"]
        ):
            normalized += " moderate"

        if any(
            word in normalized
            for word in ["తేలికగా", "స్వల్పంగా", "telikaga", "svalpanga"]
        ):
            normalized += " mild"

        question_text = question.lower()

        if not text:
            continue

        if (
            "main problem" in question_text
            or "main symptom" in question_text
            or "bothering you" in question_text
        ):

            complaint = infer_complaint_from_text(text)

            if complaint != "unknown":
                extracted["complaint"] = complaint

            extracted["symptoms"] = [text]

        if "temperature" in question_text:

            extracted["temperature"] = text

        elif "how long" in question_text or "when did" in question_text:

            extracted["duration"] = text

        elif (
            "severity" in question_text
            or "severe" in question_text
            or "how severe" in question_text
        ):

            if any(
                word in normalized
                for word in [
                    "severe",
                    "very bad",
                    "very severe",
                    "extreme",
                    "terrible"
                ]
            ):
                extracted["severity"] = "severe"
                extracted["chest_pain_severe"] = True

            elif "moderate" in normalized:
                extracted["severity"] = "moderate"

            elif "mild" in normalized or "little" in normalized:
                extracted["severity"] = "mild"

        if "difficulty breathing" in question_text:

            if any(
                word in normalized
                for word in ["yes", "y", "cannot", "can't", "unable"]
            ):
                extracted["breathing_difficulty"] = True

            elif any(
                word in normalized
                for word in ["no", "n", "normal", "none"]
            ):
                extracted["breathing_difficulty"] = False

        if "chest pain" in question_text and "also" in question_text:

            if normalized in ["yes", "y"] or normalized.startswith("yes "):
                extracted["chest_pain"] = True

            elif normalized in ["no", "n"] or normalized.startswith("no "):
                extracted["chest_pain"] = False

        if "chest pressure" in question_text or "sharp chest pain" in question_text:

            if any(
                word in normalized
                for word in ["yes", "severe", "very bad", "extreme"]
            ):
                extracted["chest_pain_severe"] = True

        if "uncontrolled bleeding" in question_text:

            if normalized in ["yes", "y"] or normalized.startswith("yes "):
                extracted["severe_bleeding"] = True

            elif normalized in ["no", "n"] or normalized.startswith("no "):
                extracted["severe_bleeding"] = False

        if "lose consciousness" in question_text:

            if normalized in ["yes", "y"] or normalized.startswith("yes "):
                extracted["loss_of_consciousness"] = True

            elif normalized in ["no", "n"] or normalized.startswith("no "):
                extracted["loss_of_consciousness"] = False

        if "start suddenly" in question_text:

            if normalized in ["yes", "y"] or normalized.startswith("yes "):
                extracted["sudden_pain"] = True

            elif normalized in ["no", "n"] or normalized.startswith("no "):
                extracted["sudden_pain"] = False

        if "which part" in question_text:
            extracted["symptoms"] = [text]

    return extracted


# ============================================================
# MERGE INFORMATION
# ============================================================

def merge_patient_information(
    old_information,
    new_information
):

    merged = old_information.copy()

    for key, value in new_information.items():

        # Ignore empty values
        if value in [
            "",
            None,
            [],
            {}
        ]:
            continue

        if key == "complaint":

            value = str(
                value
            ).strip().lower()

            if value not in SUPPORTED_COMPLAINTS:
                continue

            if (
                value == "unknown"
                and merged.get("complaint") != "unknown"
            ):
                continue

        if (
            key in [
                "breathing_difficulty",
                "chest_pain",
                "chest_pain_severe",
                "chest_pain_pressure",
                "severe_bleeding",
                "loss_of_consciousness",
                "sudden_pain"
            ]
            and value in [True, False]
            and merged.get(key) in [True, False]
            and merged[key] != value
        ):
            inconsistencies = merged.setdefault("inconsistencies", [])
            message = (
                f"Conflicting answers were provided for {key.replace('_', ' ')}."
            )
            if message not in inconsistencies:
                inconsistencies.append(message)
            continue

        merged[key] = value

    return merged


# ============================================================
# PYTHON RULE ENGINE
# ============================================================

def _apply_triage_rules(patient):

    complaint = patient.get(
        "complaint",
        "unknown"
    )

    inconsistencies = patient.get("inconsistencies", [])

    if inconsistencies:

        return {
            "urgency": "UNCERTAIN",
            "department": "Human Clinical Assessment",
            "rule_id": "ESC-INCONSISTENT",
            "reasoning": (
                "The answers contain conflicting information, so no automated "
                "triage decision is safe."
            ),
            "next_step": (
                "Please clarify the conflicting information or seek medical assessment."
            ),
            "human_review": True
        }


    # ========================================================
    # UNKNOWN
    # ========================================================

    if complaint == "unsupported":

        return {
            "urgency": "UNKNOWN",
            "department": "Human Clinical Assessment",
            "rule_id": "ESC-UNSUPPORTED",
            "reasoning": (
                "This complaint is recognized, but it is outside the supported "
                "rule catalogue."
            ),
            "next_step": (
                "Do not rely on an automated triage result for this complaint."
            ),
            "human_review": True
        }

    if complaint == "unknown":

        return {
            "urgency": "UNKNOWN",
            "department": "Human Clinical Assessment",
            "rule_id": "ESC-UNKNOWN",
            "reasoning": (
                "The complaint could not be identified confidently "
                "from the information provided."
            ),
            "next_step": (
                "Human clinical assessment is required rather than "
                "making an automated recommendation."
            ),
            "human_review": True
        }


    # ========================================================
    # CHEST PAIN
    # ========================================================

    if complaint == "chest_pain":

        breathing = patient.get(
            "breathing_difficulty"
        )

        severe = patient.get(
            "chest_pain_severe"
        )

        pressure = patient.get(
            "chest_pain_pressure"
        )

        # Rule CP-BD-01
        if breathing is True:

            return {
                "urgency": "HIGH",
                "department": "Emergency",
                "rule_id": "CP-BD-01",
                "reasoning": (
                    "Chest pain with breathing difficulty "
                    "matches the predefined high-risk rule."
                ),
                "next_step": (
                    "Seek immediate human clinical assessment."
                ),
                "human_review": True
            }

        # Rule CP-01
        if severe is True or pressure is True:

            return {
                "urgency": "HIGH",
                "department": "Emergency",
                "rule_id": "CP-01",
                "reasoning": (
                    "Severe or pressure-like chest pain "
                    "matches the predefined high-risk rule."
                ),
                "next_step": (
                    "Seek immediate human clinical assessment."
                ),
                "human_review": True
            }

        # Information is still uncertain
        return {
            "urgency": "UNCERTAIN",
            "department": "Human Clinical Assessment",
            "rule_id": "ESC-CP",
            "reasoning": (
                "The available information does not match "
                "a sufficiently specific chest pain rule."
            ),
            "next_step": (
                "Human clinical assessment is required."
            ),
            "human_review": True
        }


    # ========================================================
    # BREATHING DIFFICULTY
    # ========================================================

    if complaint == "breathing_difficulty":

        severity = str(
            patient.get(
                "severity",
                ""
            )
        ).lower()

        chest_pain = patient.get(
            "chest_pain"
        )

        # Rule BD-01
        if severity in [
            "severe",
            "very severe",
            "extreme"
        ]:

            return {
                "urgency": "HIGH",
                "department": "Emergency",
                "rule_id": "BD-01",
                "reasoning": (
                    "Severe breathing difficulty matches "
                    "the predefined high-risk rule."
                ),
                "next_step": (
                    "Seek immediate human clinical assessment."
                ),
                "human_review": True
            }

        # Rule BD-02
        if chest_pain is True:

            return {
                "urgency": "HIGH",
                "department": "Emergency",
                "rule_id": "BD-02",
                "reasoning": (
                    "Breathing difficulty with chest pain "
                    "matches the predefined high-risk rule."
                ),
                "next_step": (
                    "Seek immediate human clinical assessment."
                ),
                "human_review": True
            }

        return {
            "urgency": "UNCERTAIN",
            "department": "Human Clinical Assessment",
            "rule_id": "ESC-BD",
            "reasoning": (
                "The available information does not match "
                "a sufficiently specific breathing-difficulty rule."
            ),
            "next_step": (
                "Human clinical assessment is required."
            ),
            "human_review": True
        }


    # ========================================================
    # ABDOMINAL PAIN
    # ========================================================

    if complaint == "abdominal_pain":

        severity = str(
            patient.get(
                "severity",
                ""
            )
        ).lower()

        sudden = patient.get(
            "sudden_pain"
        )

        # Rule AP-01
        if (
            severity in [
                "severe",
                "very severe",
                "extreme"
            ]
            or sudden is True
        ):

            return {
                "urgency": "HIGH",
                "department": "Emergency",
                "rule_id": "AP-01",
                "reasoning": (
                    "Severe or sudden abdominal pain "
                    "matches the predefined high-risk rule."
                ),
                "next_step": (
                    "Seek urgent human clinical assessment."
                ),
                "human_review": True
            }

        return {
            "urgency": "UNCERTAIN",
            "department": "Human Clinical Assessment",
            "rule_id": "ESC-AP",
            "reasoning": (
                "The available information does not match "
                "a sufficiently specific abdominal-pain rule."
            ),
            "next_step": (
                "Human clinical assessment is required."
            ),
            "human_review": True
        }


    # ========================================================
    # INJURY
    # ========================================================

    if complaint == "injury":

        severe_bleeding = patient.get(
            "severe_bleeding"
        )

        loss_of_consciousness = patient.get(
            "loss_of_consciousness"
        )

        # Rule INJ-01
        if severe_bleeding is True:

            return {
                "urgency": "HIGH",
                "department": "Emergency",
                "rule_id": "INJ-01",
                "reasoning": (
                    "Severe or uncontrolled bleeding "
                    "matches the predefined high-risk rule."
                ),
                "next_step": (
                    "Seek immediate human clinical assessment."
                ),
                "human_review": True
            }

        # Rule INJ-02
        if loss_of_consciousness is True:

            return {
                "urgency": "HIGH",
                "department": "Emergency",
                "rule_id": "INJ-02",
                "reasoning": (
                    "Loss of consciousness after injury "
                    "matches the predefined high-risk rule."
                ),
                "next_step": (
                    "Seek immediate human clinical assessment."
                ),
                "human_review": True
            }

        return {
            "urgency": "UNCERTAIN",
            "department": "Human Clinical Assessment",
            "rule_id": "ESC-INJ",
            "reasoning": (
                "The available injury information does not "
                "match a sufficiently specific injury rule."
            ),
            "next_step": (
                "Human clinical assessment is required."
            ),
            "human_review": True
        }


    # ========================================================
    # FEVER
    # ========================================================

    if complaint == "fever":

        breathing = patient.get(
            "breathing_difficulty"
        )

        # Rule FEV-01
        if breathing is True:

            return {
                "urgency": "HIGH",
                "department": "Emergency",
                "rule_id": "FEV-01",
                "reasoning": (
                    "Fever accompanied by breathing difficulty "
                    "matches the predefined high-risk rule."
                ),
                "next_step": (
                    "Seek immediate human clinical assessment."
                ),
                "human_review": True
            }

        return {
            "urgency": "UNCERTAIN",
            "department": "Human Clinical Assessment",
            "rule_id": "ESC-FEV",
            "reasoning": "",
            "next_step": (
                "Human clinical assessment is required."
            ),
            "human_review": True
        }


    # ========================================================
    # FALLBACK
    # ========================================================

    return {
        "urgency": "UNCERTAIN",
        "department": "Human Clinical Assessment",
        "rule_id": "ESC-FALLBACK",
        "reasoning": (
            "The information does not match a supported "
            "triage rule."
        ),
        "next_step": (
            "Human clinical assessment is recommended."
        ),
        "human_review": True
    }


def apply_triage_rules(patient):

    result = _apply_triage_rules(patient)
    result["decision_source"] = "Local rule engine"
    result["rules_version"] = RULE_DATA.get("version", "unknown")
    return result


def record_decision(result, patient):

    event = {
        "time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "complaint": patient.get("complaint", "unknown"),
        "urgency": result.get("urgency", "UNKNOWN"),
        "rule_id": result.get("rule_id", "unknown"),
        "rules_version": result.get("rules_version", "unknown")
    }

    if event not in st.session_state.decision_history:
        st.session_state.decision_history.append(event)


# ============================================================
# DISPLAY TRIAGE RESULT
# ============================================================

def show_dashboard():

    patient = st.session_state.patient_info
    result = st.session_state.triage_result
    understanding_status, understanding_note = get_understanding_status(patient)

    known_fields = [
        patient.get("complaint") not in ["", "unknown", None],
        bool(patient.get("symptoms")),
        bool(patient.get("duration")),
        bool(patient.get("severity")),
        bool(patient.get("temperature")),
    ]
    completeness = round(sum(known_fields) / len(known_fields) * 100)

    st.markdown(
        '<div class="dashboard-label">Completed assessment</div>',
        unsafe_allow_html=True
    )
    st.markdown(
        '<div class="dashboard-title">Triage dashboard</div>',
        unsafe_allow_html=True
    )

    st.info(
        f"**Understanding status: {understanding_status}**  "
        f"\n\n{understanding_note} This status does not determine triage."
    )

    summary_columns = st.columns(4)

    with summary_columns[0]:
        st.metric(
            "Complaint",
            patient.get("complaint", "Unknown").replace("_", " ").title()
        )

    with summary_columns[1]:
        st.metric("Priority", result.get("urgency", "Unknown"))

    with summary_columns[2]:
        st.metric("Care destination", result.get("department", "Unknown"))

    with summary_columns[3]:
        st.metric("Information captured", f"{completeness}%")

    st.progress(completeness / 100, text="Patient information captured")


def get_understanding_status(patient):

    if not patient.get("gemini_understanding"):

        return (
            "Unavailable",
            "No structured extraction was returned."
        )

    if patient.get("complaint") in ["unknown", "unsupported"]:

        return (
            "Needs clarification",
            "The message was understood, but it does not map to a supported complaint."
        )

    understood_fields = sum(
        bool(patient.get(field))
        for field in [
            "complaint",
            "symptoms",
            "duration",
            "severity",
            "temperature"
        ]
    )

    if understood_fields >= 3:

        return (
            "Good understanding",
            "The message contains several usable patient details."
        )

    return (
        "Partial understanding",
        "Some details were understood, but important information may be missing."
    )


def get_rule_citation(rule_id):

    if rule_id.startswith("ESC-"):

        escalation_urgency = (
            "UNKNOWN"
            if rule_id in ["ESC-UNKNOWN", "ESC-UNSUPPORTED"]
            else "UNCERTAIN"
        )

        return {
            "id": rule_id,
            "condition": "Safety escalation: the information is incomplete or inconsistent.",
            "urgency": escalation_urgency,
            "department": "Human Clinical Assessment"
        }

    rule = next(
        (item for item in RULES if item.get("id") == rule_id),
        None
    )

    if rule is None:

        return {
            "id": rule_id,
            "condition": "No matching rule citation is available.",
            "urgency": "UNCERTAIN",
            "department": "Human Clinical Assessment"
        }

    return rule


def get_clinical_assessment(result):

    assessments = {
        "CP-BD-01": "Chest pain with breathing difficulty can be serious.",
        "CP-01": "The chest pain described may require urgent assessment.",
        "BD-01": "Severe breathing difficulty can be a medical emergency.",
        "BD-02": "Breathing difficulty with chest pain can be serious.",
        "AP-01": "Sudden or severe abdominal pain needs urgent assessment.",
        "INJ-01": "Severe or uncontrolled bleeding needs urgent assessment.",
        "INJ-02": "Loss of consciousness after an injury needs urgent assessment.",
        "FEV-01": "Fever with breathing difficulty can be serious.",
        "ESC-FEV": "Your fever may be manageable at home if it is mild and no warning symptoms are present.",
        "ESC-CP": "You have reported chest pain, but the available details are incomplete.",
        "ESC-BD": "You have reported breathing difficulty, but its severity is unclear.",
        "ESC-AP": "You have reported abdominal pain, but its severity and onset are unclear.",
        "ESC-INJ": "You have reported an injury, but the available details are incomplete.",
        "ESC-UNKNOWN": "The reported problem could not be identified clearly.",
        "ESC-UNSUPPORTED": "This complaint is recognized but is not covered by the supported rules.",
        "ESC-INCONSISTENT": "The information provided contains conflicting answers."
    }

    return assessments.get(
        result["rule_id"],
        "The available information needs further clinical assessment."
    )


def show_triage_result(result):

    st.divider()

    urgency = result["urgency"]
    citation = get_rule_citation(result["rule_id"])

    if result.get("human_review"):

        st.warning(
            "### Human review required\n"
            "This result must be reviewed by a qualified healthcare professional."
        )

    st.markdown("## Clinical assessment")

    st.write(
        get_clinical_assessment(result)
    )

    if urgency == "HIGH":

        st.error(
            "### Urgent assessment needed"
        )

        actions = {
            "CP-BD-01": "Chest pain with breathing difficulty requires emergency care now.",
            "CP-01": "Severe or pressure-like chest pain requires emergency care now.",
            "BD-01": "Severe breathing difficulty requires emergency care now.",
            "BD-02": "Breathing difficulty with chest pain requires emergency care now.",
            "AP-01": "Sudden or severe abdominal pain requires urgent medical care now.",
            "INJ-01": "Severe or uncontrolled bleeding requires emergency care now.",
            "INJ-02": "Loss of consciousness after an injury requires emergency care now.",
            "FEV-01": "Fever with breathing difficulty requires emergency care now."
        }
        action = actions.get(
            result["rule_id"],
            "Your symptoms may be serious. Seek emergency medical care now."
        )

    elif urgency == "UNCERTAIN":

        st.warning(
            "### Medical assessment recommended"
        )

        actions = {
            "ESC-FEV": (
                "Rest, drink plenty of fluids, check your temperature, and consider a "
                "COVID-19 or flu test. If you can safely take paracetamol, follow the "
                "package directions or ask a pharmacist. Seek medical care if the fever "
                "persists, worsens, or you develop breathing difficulty, confusion, or severe weakness."
            ),
            "ESC-CP": (
                "Rest and avoid strenuous activity. Arrange a medical assessment "
                "today. Seek emergency care if the pain becomes severe, feels like "
                "pressure, spreads, or comes with sweating or breathing difficulty."
            ),
            "ESC-BD": (
                "Sit upright, rest, and avoid exertion. Arrange a medical assessment. "
                "Seek emergency care if breathing becomes severe or you develop chest pain, "
                "blue lips, confusion, or fainting."
            ),
            "ESC-AP": (
                "Rest and drink fluids if you can. Arrange a medical assessment if the pain "
                "continues. Seek urgent care if it becomes severe, sudden, or comes with "
                "repeated vomiting, fainting, or blood."
            ),
            "ESC-INJ": (
                "Rest the injured area. If it is bleeding, apply firm direct pressure; "
                "use a wrapped cold pack for swelling. Arrange medical assessment if pain, "
                "swelling, bleeding, or movement problems worsen."
            )
        }
        action = actions.get(
            result["rule_id"],
            "More information is needed to assess this problem safely."
        )

    elif urgency == "UNKNOWN":

        st.info(
            "### Assessment unavailable"
        )

        action = (
            "The main health problem could not be identified. "
            "Please describe your symptoms clearly before relying on this tool."
            if result["rule_id"] == "ESC-UNKNOWN"
            else "This complaint is outside the supported rules. Please consult a healthcare professional."
        )

    else:

        st.info(
            f"## Triage level: {urgency}"
        )

    st.markdown("### Recommended next step")

    st.success(
        action
    )

    if urgency == "HIGH":

        st.error(
            "If symptoms are severe, rapidly worsening, or life-threatening, "
            "contact local emergency services immediately."
        )

    st.markdown("### Rule explanation")

    if result["rule_id"] == "ESC-UNKNOWN":

        st.write(
            "No supported complaint could be identified, so the rule engine "
            "did not make an automated clinical assessment."
        )

    elif result["rule_id"] == "ESC-UNSUPPORTED":

        st.write(
            "The complaint is recognizable but is not covered by the current "
            "rule catalogue, so no automated triage decision was made."
        )

    elif result["rule_id"] == "ESC-INCONSISTENT":

        st.write(
            "The information contains conflicting answers. The rule engine "
            "paused automated triage until the information is clarified."
        )

    else:

        st.write(
            f"The rule engine matched the condition: \"{citation['condition']}\". "
            f"This produced a {citation['urgency']} priority and the care "
            f"destination is {citation['department']}."
        )

    if result["reasoning"]:

        st.caption(result["reasoning"])

    st.caption(
        f"Care destination: {result['department']}"
    )

    with st.expander("Rule citation", expanded=True):

        st.write("**Decision source:** Local rule engine")
        st.write(f"**Rule catalogue version:** {result.get('rules_version', 'unknown')}")
        st.write(f"**Rule:** {citation['id']}")
        st.write(f"**Condition:** {citation['condition']}")
        st.write(f"**Rule urgency:** {citation['urgency']}")
        st.write(f"**Care destination:** {citation['department']}")
        st.write(
            "**Human review:** Required"
            if result.get("human_review")
            else "**Human review:** Not required"
        )

    if result["human_review"]:

        st.warning(
            "This is guidance from a prototype and not a diagnosis. "
            "Human clinical review is required."
        )


# ============================================================
# DISPLAY PATIENT INFORMATION
# ============================================================

def show_information():

    patient = st.session_state.patient_info

    with st.expander(
        "📋 Information understood by the system",
        expanded=True
    ):

        if patient.get("inconsistencies"):

            st.warning(
                "Some answers conflict. The assessment has been paused until "
                "the information is clarified."
            )

        evidence_columns = st.columns(2)

        with evidence_columns[0]:

            st.markdown("**Patient reported**")
            st.info(
                patient.get(
                    "original_message",
                    "No initial message recorded."
                )
            )

        with evidence_columns[1]:

            st.markdown("**Follow-up established**")

            if st.session_state.gemini_follow_up_understanding:

                st.json(
                    st.session_state.gemini_follow_up_understanding
                )

            else:

                st.caption(
                    "No follow-up answers have been established."
                )

        st.write(
            "**Complaint:**",
            patient.get(
                "complaint",
                "Unknown"
            )
        )

        if patient.get("language"):

            st.write(
                "**Language detected:**",
                patient.get("language")
            )

        if patient.get("symptoms"):

            st.write(
                "**Symptoms:**",
                ", ".join(
                    patient.get(
                        "symptoms",
                        []
                    )
                )
            )

        if patient.get("duration"):

            st.write(
                "**Duration:**",
                patient.get("duration")
            )

        if patient.get("severity"):

            st.write(
                "**Severity:**",
                patient.get("severity")
            )

        if patient.get("temperature"):

            st.write(
                "**Temperature:**",
                patient.get("temperature")
            )

        if patient.get(
            "breathing_difficulty"
        ) is not None:

            st.write(
                "**Breathing difficulty:**",
                "Yes"
                if patient["breathing_difficulty"]
                else "No"
            )

        if patient.get(
            "chest_pain"
        ) is not None:

            st.write(
                "**Chest pain:**",
                "Yes"
                if patient["chest_pain"]
                else "No"
            )

        if patient.get(
            "chest_pain_severe"
        ) is not None:

            st.write(
                "**Chest pain severe:**",
                "Yes"
                if patient["chest_pain_severe"]
                else "No"
            )

        if patient.get(
            "chest_pain_pressure"
        ) is not None:

            st.write(
                "**Chest pain pressure-like:**",
                "Yes"
                if patient["chest_pain_pressure"]
                else "No"
            )

        if patient.get(
            "severe_bleeding"
        ) is not None:

            st.write(
                "**Severe bleeding:**",
                "Yes"
                if patient["severe_bleeding"]
                else "No"
            )

        if patient.get(
            "loss_of_consciousness"
        ) is not None:

            st.write(
                "**Loss of consciousness:**",
                "Yes"
                if patient["loss_of_consciousness"]
                else "No"
            )

        if patient.get(
            "sudden_pain"
        ) is not None:

            st.write(
                "**Sudden pain:**",
                "Yes"
                if patient["sudden_pain"]
                else "No"
            )

    raw_understanding = patient.get(
        "gemini_understanding",
        {}
    )
    follow_up_understanding = st.session_state.gemini_follow_up_understanding

    if raw_understanding or follow_up_understanding:

        with st.expander(
            "🔎 Exactly what Gemini understood",
            expanded=False
        ):

            st.caption(
                "This is Gemini's raw extraction. The final triage decision is "
                "made separately by the local rule engine."
            )

            if raw_understanding:

                st.write("**Initial message extraction**")
                st.json(raw_understanding)

            if follow_up_understanding:

                st.write("**Follow-up answer extraction**")
                st.json(follow_up_understanding)


# ============================================================
# HEADER
# ============================================================

st.markdown(
    """
    <section class="hero">
        <div class="eyebrow">Patient safety workspace</div>
        <h1>Patient Intake<br><span>Triage Assistant</span></h1>
        <p>
            Tell us what is happening in your own words. The assistant asks
            only for the details needed to check predefined safety rules.
        </p>
        <div class="hero-meta">
            <span>Multilingual intake</span>
            <span>Rule-based triage</span>
            <span>Human review first</span>
        </div>
    </section>
    """,
    unsafe_allow_html=True
)

st.caption(
    "Prototype for patient intake support. It does not diagnose or replace "
    "professional medical care."
)

# ============================================================
# CONVERSATION HISTORY
# ============================================================

with st.sidebar:

    st.markdown("## Conversation history")
    st.caption(
        f"{len(st.session_state.messages)} recorded conversation turns"
    )

    if st.session_state.messages:

        for index, message in enumerate(
            st.session_state.messages,
            start=1
        ):

            role = (
                "Patient"
                if message["role"] == "user"
                else "Assistant"
            )

            with st.expander(
                f"{index:02d}  {role}",
                expanded=False
            ):

                st.write(message["content"])

    else:

        st.info("No conversation has started yet.")

    st.divider()
    st.markdown("## Decision audit")
    st.caption("Rule-based decisions from this browser session")

    if st.session_state.decision_history:

        for event in reversed(st.session_state.decision_history):

            st.write(
                f"**{event['urgency']}** - {event['rule_id']}"
            )
            st.caption(
                f"{event['time']} | {event['complaint'].replace('_', ' ').title()} "
                f"| rules {event['rules_version']}"
            )

    else:

        st.info("No rule-based decision has been recorded yet.")


# ============================================================
# CHAT HISTORY
# ============================================================

for message in st.session_state.messages:

    with st.chat_message(
        message["role"]
    ):

        st.write(
            message["content"]
        )


# ============================================================
# FOLLOW-UP QUESTIONS
# ============================================================

if (
    st.session_state.waiting_for_answers
    and st.session_state.follow_up_questions
):

    st.subheader(
        "❓ I need a little more information"
    )

    st.write(
        "Please answer only the questions below. "
        "These details are needed to apply the predefined rules."
    )

    with st.form("follow_up_form"):

        answers = {}

        for index, question in enumerate(
            st.session_state.follow_up_questions
        ):

            answers[question] = st.text_input(
                question,
                key=f"answer_{index}"
            )

        submitted = st.form_submit_button(
            "Continue"
        )


    if submitted:

        answered_questions = {
            question: answer
            for question, answer in answers.items()
            if answer.strip()
        }

        if not answered_questions:

            st.warning(
                "Please answer at least one question."
            )

        elif any(
            validate_patient_input(answer, "answer")
            for answer in answered_questions.values()
        ):

            st.warning(
                "Please provide meaningful answers under 1,000 characters."
            )

        else:

            # Add answers to chat
            for question, answer in answered_questions.items():

                st.session_state.messages.append(
                    {
                        "role": "user",
                        "content": (
                            f"{question}\nAnswer: {answer}"
                        )
                    }
                )


            with st.spinner(
                "🤖 Understanding your answers..."
            ):

                additional_info = (
                    interpret_follow_up_answers(
                        st.session_state.follow_up_questions,
                        answered_questions,
                        st.session_state.patient_info
                    )
                )

            st.session_state.gemini_follow_up_understanding = additional_info.copy()

            direct_info = apply_direct_follow_up_answers(
                st.session_state.follow_up_questions,
                answered_questions
            )

            additional_info = merge_patient_information(
                additional_info,
                direct_info
            )


            # Merge information
            st.session_state.patient_info = (
                merge_patient_information(
                    st.session_state.patient_info,
                    additional_info
                )
            )


            # ------------------------------------------------
            # IMPORTANT:
            # Check again if required information is missing
            # ------------------------------------------------

            if (
                st.session_state.patient_info.get("complaint") in [
                    "unknown",
                    "unsupported"
                ]
                and st.session_state.clarification_rounds >= 1
            ):

                st.session_state.triage_result = apply_triage_rules(
                    st.session_state.patient_info
                )
                record_decision(
                    st.session_state.triage_result,
                    st.session_state.patient_info
                )
                st.session_state.follow_up_questions = []
                st.session_state.waiting_for_answers = False
                st.session_state.conversation_complete = True

                st.rerun()

            remaining_questions = (
                get_required_follow_up_questions(
                    st.session_state.patient_info
                )
            )


            # ------------------------------------------------
            # STILL MISSING INFORMATION
            # ------------------------------------------------

            if remaining_questions:

                st.session_state.follow_up_questions = (
                    remaining_questions
                )

                st.session_state.waiting_for_answers = True

                st.rerun()


            # ------------------------------------------------
            # ENOUGH INFORMATION
            # ------------------------------------------------

            else:

                result = apply_triage_rules(
                    st.session_state.patient_info
                )

                st.session_state.triage_result = result
                record_decision(
                    result,
                    st.session_state.patient_info
                )

                st.session_state.waiting_for_answers = False

                st.session_state.conversation_complete = True

                st.rerun()


# ============================================================
# SHOW RESULT
# ============================================================

if st.session_state.triage_result:

    show_dashboard()

    show_information()

    show_triage_result(
        st.session_state.triage_result
    )


# ============================================================
# MAIN INPUT
# ============================================================

if (
    not st.session_state.waiting_for_answers
    and not st.session_state.conversation_complete
):

    user_input = st.chat_input(
        "Example: my chest hurts and I feel breathless..."
    )

    if user_input:

        input_error = validate_patient_input(user_input)

        if input_error:

            st.warning(input_error)
            st.stop()

        st.session_state.messages.append(
            {
                "role": "user",
                "content": user_input
            }
        )

        with st.chat_message("user"):

            st.write(user_input)


        # ----------------------------------------------------
        # UNDERSTAND PATIENT MESSAGE
        # ----------------------------------------------------

        with st.spinner(
            "🤖 Understanding your message..."
        ):

            patient_info = (
                understand_patient_message(
                    user_input
                )
            )


        st.session_state.patient_info = patient_info
        st.session_state.gemini_follow_up_understanding = {}

        complaint = patient_info.get(
            "complaint",
            "unknown"
        )


        # ----------------------------------------------------
        # UNKNOWN COMPLAINT
        # ----------------------------------------------------

        if complaint == "unknown":

            st.session_state.clarification_rounds = 1

            st.session_state.follow_up_questions = (
                get_required_follow_up_questions(
                    patient_info
                )
            )

            st.session_state.waiting_for_answers = True

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": (
                        "I need a few more details before I can "
                        "apply the triage rules."
                    )
                }
            )

            st.rerun()


        # ----------------------------------------------------
        # PYTHON CHECKS MISSING INFORMATION
        # ----------------------------------------------------

        questions = (
            get_required_follow_up_questions(
                patient_info
            )
        )


        # ----------------------------------------------------
        # MISSING INFORMATION
        # ----------------------------------------------------

        if questions:

            st.session_state.follow_up_questions = questions

            st.session_state.waiting_for_answers = True

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": (
                        "I need a few important details "
                        "before applying the triage rules."
                    )
                }
            )

            st.rerun()


        # ----------------------------------------------------
        # INFORMATION IS SUFFICIENT
        # ----------------------------------------------------

        else:

            result = apply_triage_rules(
                patient_info
            )

            st.session_state.triage_result = result
            record_decision(
                result,
                patient_info
            )

            st.session_state.conversation_complete = True

            st.rerun()


# ============================================================
# NEW PATIENT
# ============================================================

if st.session_state.conversation_complete:

    st.divider()

    if st.button(
        "🔄 Start New Patient"
    ):

        st.session_state.messages = []

        st.session_state.patient_info = {}

        st.session_state.follow_up_questions = []

        st.session_state.triage_result = None

        st.session_state.waiting_for_answers = False

        st.session_state.conversation_complete = False

        st.session_state.clarification_rounds = 0

        st.rerun()


# ============================================================
# DISCLAIMER
# ============================================================

st.divider()

st.caption(
    "⚠️ Hackathon prototype only. This system does not diagnose "
    "medical conditions and does not replace professional clinical "
    "assessment. Triage rules must be clinically reviewed before "
    "real-world use."
)
