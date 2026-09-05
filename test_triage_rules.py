import json
import unittest
from pathlib import Path


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


if __name__ == "__main__":
    unittest.main()
