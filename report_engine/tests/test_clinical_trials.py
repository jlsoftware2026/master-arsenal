"""Offline tests for the ClinicalTrials.gov API v2 adapter."""
from datetime import datetime, timezone
import unittest

from report_engine.clinical_trials import ClinicalTrialsGov, _nct_id

NOW = datetime(2026, 11, 17, 16, 0, tzinfo=timezone.utc)
KEY = "listed_equity|exm|usd|example corp|nasdaq"


def study_fixture():
    return {
        "protocolSection": {
            "identificationModule": {
                "nctId": "NCT01234567",
                "briefTitle": "A Phase 3 Study of Example Therapy",
            },
            "statusModule": {
                "overallStatus": "RECRUITING",
                "studyFirstPostDateStruct": {"date": "2024-01-10"},
                "studyLastUpdatePostDateStruct": {"date": "2026-10-30"},
                "primaryCompletionDateStruct": {"date": "2027-06-30", "type": "ESTIMATED"},
            },
            "sponsorCollaboratorsModule": {
                "leadSponsor": {"name": "Example Pharma Inc."},
            },
            "designModule": {
                "studyType": "INTERVENTIONAL",
                "phases": ["PHASE3"],
                "enrollmentInfo": {"count": 450, "type": "ESTIMATED"},
            },
            "outcomesModule": {
                "primaryOutcomes": [
                    {"measure": "Overall response rate", "description": "Defined per protocol",
                     "timeFrame": "24 weeks"}
                ]
            },
            "armsInterventionsModule": {
                "interventions": [{"name": "Example Drug", "type": "DRUG"}]
            },
        },
        "resultsSection": {},
    }


class ClinicalTrialsTests(unittest.TestCase):
    def test_nct_id_validation(self):
        self.assertEqual(_nct_id("nct01234567"), "NCT01234567")
        for value in ("NCT123", "NCT012345678", "01234567", "NCTABCDEFGH"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                _nct_id(value)

    def test_requires_explicit_issuer_trial_attribution(self):
        adapter = ClinicalTrialsGov(fetch_json=lambda *args: study_fixture())
        with self.assertRaisesRegex(ValueError, "attribution_basis"):
            adapter.fetch_study(nct_id="NCT01234567", instrument_key=KEY,
                                attribution_basis="", retrieved_at=NOW)

    def test_fetches_exact_nct_and_preserves_provenance(self):
        seen = {}
        def fake(url, headers, timeout):
            seen.update(url=url, headers=headers, timeout=timeout)
            return study_fixture()
        adapter = ClinicalTrialsGov(fetch_json=fake)
        result = adapter.fetch_study(
            nct_id="NCT01234567", instrument_key=KEY,
            attribution_basis="Issuer 10-K identifies the trial intervention as its lead candidate.",
            retrieved_at=NOW,
        )
        self.assertTrue(seen["url"].endswith("/NCT01234567"))
        self.assertEqual(result["nct_id"], "NCT01234567")
        self.assertEqual(result["issuer_trial_attribution"]["status"],
                         "caller_supplied_not_independently_verified")
        self.assertIn("clinicaltrials.gov/study/NCT01234567", result["source_url"])

    def test_rejects_mismatched_nct_response(self):
        fixture = study_fixture()
        fixture["protocolSection"]["identificationModule"]["nctId"] = "NCT99999999"
        adapter = ClinicalTrialsGov(fetch_json=lambda *args: fixture)
        with self.assertRaisesRegex(ValueError, "different NCT"):
            adapter.fetch_study(nct_id="NCT01234567", instrument_key=KEY,
                                attribution_basis="Documented issuer relationship.",
                                retrieved_at=NOW)

    def test_extracts_phase_status_and_primary_outcome(self):
        adapter = ClinicalTrialsGov(fetch_json=lambda *args: study_fixture())
        result = adapter.fetch_study(nct_id="NCT01234567", instrument_key=KEY,
                                     attribution_basis="Issuer filing reference.",
                                     retrieved_at=NOW)
        self.assertEqual(result["overall_status"], "RECRUITING")
        self.assertEqual(result["phase"], ["PHASE3"])
        dims = {fact["fact_id"].split("-")[-1]: fact for fact in result["facts"]}
        self.assertEqual(dims["status"]["value"], "RECRUITING")
        self.assertIn("Overall response rate", dims["primary_outcomes"]["value"])

    def test_enrollment_target_is_labeled_estimated(self):
        adapter = ClinicalTrialsGov(fetch_json=lambda *args: study_fixture())
        result = adapter.fetch_study(nct_id="NCT01234567", instrument_key=KEY,
                                     attribution_basis="Issuer filing reference.",
                                     retrieved_at=NOW)
        enrollment = next(f for f in result["facts"] if f["fact_id"].endswith("-enrollment"))
        self.assertIn("ESTIMATED", enrollment["label"])
        self.assertEqual(enrollment["value"], "450")

    def test_last_update_is_used_as_observation_date(self):
        adapter = ClinicalTrialsGov(fetch_json=lambda *args: study_fixture())
        result = adapter.fetch_study(nct_id="NCT01234567", instrument_key=KEY,
                                     attribution_basis="Issuer filing reference.",
                                     retrieved_at=NOW)
        status_fact = next(f for f in result["facts"] if f["fact_id"].endswith("-status"))
        self.assertEqual(status_fact["as_of_utc"], "2026-10-30T23:59:59Z")

    def test_missing_results_is_not_misreported_as_positive(self):
        fixture = study_fixture()
        fixture.pop("resultsSection")
        adapter = ClinicalTrialsGov(fetch_json=lambda *args: fixture)
        result = adapter.fetch_study(nct_id="NCT01234567", instrument_key=KEY,
                                     attribution_basis="Issuer filing reference.",
                                     retrieved_at=NOW)
        results_fact = next(f for f in result["facts"] if f["fact_id"].endswith("-results_posted"))
        self.assertFalse(results_fact["value"])

    def test_missing_update_falls_back_to_first_posted_date(self):
        fixture = study_fixture()
        fixture["protocolSection"]["statusModule"].pop("studyLastUpdatePostDateStruct")
        adapter = ClinicalTrialsGov(fetch_json=lambda *args: fixture)
        result = adapter.fetch_study(nct_id="NCT01234567", instrument_key=KEY,
                                     attribution_basis="Issuer filing reference.",
                                     retrieved_at=NOW)
        self.assertEqual(result["facts"][0]["as_of_utc"], "2026-10-30T23:59:59Z") if False else None
        status_fact = next(f for f in result["facts"] if f["fact_id"].endswith("-status"))
        self.assertEqual(status_fact["as_of_utc"], "2024-01-10T23:59:59Z")

    def test_rejects_missing_protocol_section(self):
        adapter = ClinicalTrialsGov(fetch_json=lambda *args: {})
        with self.assertRaisesRegex(ValueError, "protocolSection"):
            adapter.fetch_study(nct_id="NCT01234567", instrument_key=KEY,
                                attribution_basis="Issuer filing reference.",
                                retrieved_at=NOW)


if __name__ == "__main__":
    unittest.main()
