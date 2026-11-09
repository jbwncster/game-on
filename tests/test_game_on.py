"""Run: python -m unittest discover -s tests -v"""
import os
import tempfile
import unittest
import importlib
import hashlib
import secrets
from datetime import datetime, timedelta

class GameOnIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.password = "test-password-not-for-production"
        salt = secrets.token_bytes(16)
        rounds = 1000
        digest = hashlib.pbkdf2_hmac("sha256", cls.password.encode(), salt, rounds)
        os.environ["APP_SECRET"] = "test-secret-" * 4
        os.environ["STAFF_PASSWORD_HASH"] = f"pbkdf2_sha256${rounds}${salt.hex()}${digest.hex()}"
        os.environ["DATABASE_PATH"] = os.path.join(cls.tmp.name, "test.db")
        os.environ.pop("BLOB_READ_WRITE_TOKEN", None)
        os.environ.pop("VERCEL", None)
        import status_store
        importlib.reload(status_store)
        import app
        importlib.reload(app)
        cls.app = app.app
        cls.app.config["TESTING"] = True

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self.client = self.app.test_client()
        import status_store
        with status_store._local_connection() as db:
            db.execute("DELETE FROM actions")

    def auth(self):
        response = self.client.post("/api/login", json={"password":self.password})
        self.assertEqual(response.status_code, 200)
        return {"Authorization":"Bearer "+response.json["token"]}

    def test_catalog_and_privacy(self):
        board=self.client.get("/api/board")
        self.assertEqual(board.status_code,200)
        self.assertEqual(len(board.json["items"]),28)
        self.assertNotIn("condition_note",board.json["items"][0])

    def test_maintenance_requires_login(self):
        response=self.client.post("/api/staff/item/item-01/maintenance",json={"out_of_service":True,"note":"Check box"})
        self.assertEqual(response.status_code,401)

    def test_maintenance_blocks_new_checkout_and_is_private(self):
        h=self.auth()
        response=self.client.post("/api/staff/item/item-01/maintenance",headers=h,json={"out_of_service":True,"note":"Staff inspection"})
        self.assertEqual(response.status_code,200)
        public=self.client.get("/api/board").json["items"][0]
        self.assertTrue(public["out_of_service"])
        self.assertNotIn("condition_note",public)
        staff=self.client.get("/api/board",headers=h).json["items"][0]
        self.assertEqual(staff["condition_note"],"Staff inspection")
        blocked=self.client.post("/api/item/item-01/toggle",headers=h)
        self.assertEqual(blocked.status_code,409)
        self.client.post("/api/staff/item/item-01/maintenance",headers=h,json={"out_of_service":False,"note":""})
        self.assertEqual(self.client.post("/api/item/item-01/toggle",headers=h).status_code,200)

    def test_three_hour_due_window_and_stats(self):
        h=self.auth()
        self.assertEqual(self.client.post("/api/item/item-01/toggle",headers=h).status_code,200)
        item=self.client.get("/api/board").json["items"][0]
        out=datetime.fromisoformat(item["checked_out_at"])
        due=datetime.fromisoformat(item["due_at"])
        self.assertEqual(due-out,timedelta(hours=3))
        stats=self.client.get("/api/staff/stats",headers=h)
        self.assertEqual(stats.json["total_checkouts"],1)
        self.assertEqual(stats.json["currently_out"],1)


    def test_staff_inventory_statuses_and_counts(self):
        h=self.auth()
        self.client.post("/api/item/item-01/toggle",headers=h)
        self.client.post("/api/staff/item/item-02/maintenance",headers=h,
            json={"out_of_service":True,"note":"Staff review needed"})
        result=self.client.get("/api/staff/stats",headers=h)
        self.assertEqual(result.status_code,200)
        data=result.json
        self.assertEqual(len(data["item_statuses"]),28)
        counts=data["status_counts"]
        self.assertEqual(sum(counts.values()),28)
        self.assertEqual(counts["Available"],26)
        self.assertEqual(counts["Checked out"],1)
        self.assertEqual(counts["Overdue"],0)
        self.assertEqual(counts["Out of service"],1)
        self.assertEqual(data["item_statuses"][0]["status"],"Checked out")
        self.assertEqual(data["item_statuses"][1]["status"],"Out of service")
        self.assertEqual(data["item_statuses"][1]["condition_note"],"Staff review needed")
        self.assertEqual(data["by_item"][1]["status"],"Out of service")
        self.client.post("/api/staff/stats/reset",headers=h,
            json={"confirmation":"CLEAR STATS","password":self.password})
        after=self.client.get("/api/staff/stats",headers=h).json
        self.assertEqual(after["status_counts"],counts)
        self.assertEqual(after["total_checkouts"],0)

    def test_invalid_condition_note(self):
        h=self.auth()
        response=self.client.post("/api/staff/item/item-02/maintenance",headers=h,
                  json={"out_of_service":False,"note":"x"*251})
        self.assertEqual(response.status_code,400)

    def test_qr_and_libguides(self):
        self.assertEqual(self.client.get("/qr").mimetype,"image/svg+xml")
        snippet=self.client.get("/libguides-snippet")
        self.assertIn(b'target="_blank"',snippet.data)

if __name__=="__main__":
    unittest.main()
