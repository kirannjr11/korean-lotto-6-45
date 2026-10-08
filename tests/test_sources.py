import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from lotto.sources import (ARCHIVE_URL, normalize_official, parse_archive,
                           sync_draws)


FIRST = {"ltEpsd": 1, "ltRflYmd": "20021207", "tm1WnNo": 10,
         "tm2WnNo": 23, "tm3WnNo": 29, "tm4WnNo": 33,
         "tm5WnNo": 37, "tm6WnNo": 40, "bnsWnNo": 16}
ARCHIVE = b'export const DATA = [\n{"round":1,"n":[10,23,29,33,37,40],"b":16}\n]\n'


class SourceTests(unittest.TestCase):
    def test_archive_is_parsed_without_executing_javascript(self):
        rows = parse_archive(ARCHIVE.decode() + '\nthrow Error("never execute");', 1)
        self.assertEqual(rows[0]["source"], ARCHIVE_URL)
        self.assertEqual(rows[0]["date"], "2002-12-07")

    def test_missing_archive_round_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_archive(ARCHIVE.decode(), 2)

    def test_official_bonus_collision_is_rejected(self):
        with self.assertRaises(ValueError):
            normalize_official({**FIRST, "bnsWnNo": 10})

    def test_missing_official_fields_give_validation_error(self):
        malformed = dict(FIRST)
        del malformed["tm3WnNo"]
        with self.assertRaisesRegex(ValueError, "required draw fields"):
            normalize_official(malformed)

    def test_malformed_response_cannot_be_marked_verified(self):
        with tempfile.TemporaryDirectory() as directory, patch("lotto.sources._fetch", side_effect=[ARCHIVE, b'{"data": null}']):
            with self.assertRaisesRegex(ValueError, "data object"):
                sync_draws(1, directory, delay_seconds=0)
            self.assertFalse((Path(directory) / "draws.json").exists())

    def test_official_verification_is_attributed_and_cached(self):
        response = json.dumps({"data": {"list": [FIRST]}}).encode()
        with tempfile.TemporaryDirectory() as directory, patch("lotto.sources._fetch", side_effect=[ARCHIVE, response]) as fetch:
            manifest = sync_draws(1, directory, delay_seconds=0)
            self.assertTrue(manifest["all_official_verified"])
            self.assertEqual(fetch.call_count, 2)
            rows = json.loads((Path(directory) / "draws.json").read_text())
            self.assertIn("dhlottery.co.kr", rows[0]["source"])
            with patch("lotto.sources._fetch", return_value=ARCHIVE) as cached_fetch:
                cached_manifest = sync_draws(1, directory, delay_seconds=0)
                self.assertEqual(cached_fetch.call_count, 1)
                self.assertEqual(cached_manifest["official_cached_count"], 1)

    def test_disagreement_does_not_overwrite_existing_data(self):
        response = json.dumps({"data": {"list": [{**FIRST, "bnsWnNo": 17}]}}).encode()
        with tempfile.TemporaryDirectory() as directory, patch("lotto.sources._fetch", side_effect=[ARCHIVE, response]):
            target = Path(directory) / "draws.json"
            target.write_text("existing trusted artifact")
            with self.assertRaisesRegex(ValueError, "disagrees"):
                sync_draws(1, directory, delay_seconds=0)
            self.assertEqual(target.read_text(), "existing trusted artifact")

    def test_network_failure_is_transparent(self):
        with tempfile.TemporaryDirectory() as directory, patch("lotto.sources._fetch", side_effect=[ARCHIVE, urllib.error.URLError("offline")]):
            manifest = sync_draws(1, directory, delay_seconds=0)
            self.assertFalse(manifest["all_official_verified"])
            self.assertEqual(manifest["official_verified_count"], 0)
            self.assertTrue(manifest["warnings"])
            rows = json.loads((Path(directory) / "draws.json").read_text())
            self.assertEqual(rows[0]["source"], ARCHIVE_URL)


if __name__ == "__main__":
    unittest.main()
