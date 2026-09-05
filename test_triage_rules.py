import json
import unittest
from pathlib import Path

from app import apply_direct_follow_up_answers, merge_patient_information


class TriageRuleCatalogueTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        rules_path = Path(__file__).with_name("triage_rules.json")
        with rules_path.open(encoding="utf-8") as rules_file:
            cls.catalogue = json.load(rules_file)

    def test_catalogue_has_supported_complaints(self):
        self.assertTrue(self.catalogue["supported_complaints"])

    def test_rule_ids_are_unique(self):
        rule_ids = [rule["id"] for rule in self.catalogue["rules"]]
        self.assertEqual(len(rule_ids), len(set(rule_ids)))

    def test_rules_have_required_fields(self):
        required_fields = {
            "id",
            "complaint",
            "condition",
            "urgency",
            "department",
            "next_step",
            "human_review",
        }

        for rule in self.catalogue["rules"]:
            self.assertTrue(required_fields.issubset(rule))
            self.assertIn(
                rule["complaint"],
                self.catalogue["supported_complaints"],
            )

    def test_high_priority_rules_require_human_review(self):

        high_priority_rules = [
            rule
            for rule in self.catalogue["rules"]
            if rule["urgency"] == "HIGH"
        ]

        self.assertTrue(high_priority_rules)

        for rule in high_priority_rules:
            self.assertTrue(rule["human_review"])

    def test_rule_ids_use_stable_prefixes(self):

        for rule in self.catalogue["rules"]:
            self.assertRegex(rule["id"], r"^[A-Z]+-[A-Z0-9-]+$")

    def test_negative_chest_pain_severity_answer_is_recorded(self):
        extracted = apply_direct_follow_up_answers(
            [
                "Is the chest pain severe or does it feel like pressure?",
            ],
            {
                "Is the chest pain severe or does it feel like pressure?": "no",
            }
        )

        self.assertFalse(extracted["chest_pain_severe"])
        self.assertFalse(extracted["chest_pain_pressure"])

    def test_direct_answer_wins_over_conflicting_interpretation(self):
        merged = merge_patient_information(
            {
                "chest_pain_severe": False,
                "chest_pain_pressure": False,
            },
            {
                "chest_pain_severe": True,
            },
        )

        self.assertFalse(merged["chest_pain_severe"])


if __name__ == "__main__":
    unittest.main()
