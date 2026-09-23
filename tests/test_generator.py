import unittest

from jev_ops.generator import FIELDNAMES, generate_flights


class TestGenerator(unittest.TestCase):
    def test_deterministic_given_same_seed(self):
        a = generate_flights(40, seed=42)
        b = generate_flights(40, seed=42)
        self.assertEqual(a, b)

    def test_different_seed_differs(self):
        a = generate_flights(40, seed=42)
        b = generate_flights(40, seed=7)
        self.assertNotEqual(a, b)

    def test_column_set(self):
        rows = generate_flights(10, seed=1)
        for row in rows:
            self.assertEqual(set(row.keys()), set(FIELDNAMES))

    def test_scenario_mix_present(self):
        rows = generate_flights(200, seed=42)
        has_weather = any(r["weather_remarks"] for r in rows)
        has_maintenance = any(r["maintenance_remarks"] for r in rows)
        has_crew_timeout = any(int(r["crew_minutes_remaining"]) < 45 for r in rows)
        has_normal = any(
            not r["weather_remarks"]
            and not r["maintenance_remarks"]
            and int(r["crew_minutes_remaining"]) >= 45
            for r in rows
        )
        self.assertTrue(has_weather)
        self.assertTrue(has_maintenance)
        self.assertTrue(has_crew_timeout)
        self.assertTrue(has_normal)

    def test_count_respected(self):
        rows = generate_flights(17, seed=5)
        self.assertEqual(len(rows), 17)


if __name__ == "__main__":
    unittest.main()
