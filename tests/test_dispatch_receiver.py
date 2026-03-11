import unittest
import os
import tempfile
from pathlib import Path
from organvm_engine.dispatch.receiver import WebhookReceiver, FormalVerificationError
from organvm_engine.verification.idempotency import DispatchLedger

class TestWebhookReceiver(unittest.TestCase):
    def setUp(self):
        # Create a temporary ledger file
        self.fd, self.path = tempfile.mkstemp()
        self.ledger_path = Path(self.path)
        self.ledger = DispatchLedger(ledger_path=self.ledger_path)
        self.receiver = WebhookReceiver(ledger=self.ledger)

    def tearDown(self):
        os.close(self.fd)
        if self.ledger_path.is_file():
            self.ledger_path.unlink()

    def test_successful_dispatch(self):
        payload = {
            "dispatch_id": "test-uuid-1",
            "event": "theory.published",
            "source": "organvm-i-theoria",
            "target": "organvm-iv-taxis",
            "payload": {
                "artifact_id": "ART-001",
                "title": "On Recursive Roots",
                "source_repo": "radix-recursiva"
            }
        }
        result = self.receiver.receive(payload)
        self.assertEqual(result["status"], "success")
        self.assertTrue(self.ledger.is_consumed("test-uuid-1"))

    def test_contract_failure(self):
        payload = {
            "dispatch_id": "test-uuid-2",
            "event": "theory.published",
            "source": "organvm-i-theoria",
            "target": "organvm-iv-taxis",
            "payload": {
                "artifact_id": "",  # Empty ID should fail contract
                "title": "Invalid Art",
                "source_repo": "repo"
            }
        }
        with self.assertRaises(FormalVerificationError):
            self.receiver.receive(payload)
        self.assertEqual(self.ledger.get_status("test-uuid-2"), "rejected")

    def test_idempotency_duplicate(self):
        payload = {
            "dispatch_id": "test-uuid-3",
            "event": "theory.published",
            "source": "organvm-i-theoria",
            "target": "organvm-iv-taxis",
            "payload": {
                "artifact_id": "ART-003",
                "title": "Double Fire",
                "source_repo": "repo"
            }
        }
        # First send
        self.receiver.receive(payload)
        # Second send (duplicate)
        result = self.receiver.receive(payload)
        self.assertEqual(result["status"], "ignored")
        self.assertEqual(result["reason"], "duplicate")

if __name__ == "__main__":
    unittest.main()
