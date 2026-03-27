"""
Tests for Wallet P0 Fixes:
1. Cas A deadlock reset after dispute/declarative resolution
2. Contestation resolution (upheld + rejected + timeout)
3. Ledger reconciliation job
"""
import uuid
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
import os

os.environ.setdefault('MONGO_URL', 'mongodb://localhost:27017')
os.environ.setdefault('DB_NAME', 'test_database')

from pymongo import MongoClient

# Setup DB
client = MongoClient("mongodb://localhost:27017")
db = client["test_database"]


def _clean_collections():
    """Clean test data from relevant collections."""
    for coll in ["attendance_records", "appointments", "participants",
                 "payment_guarantees", "distributions", "wallets",
                 "wallet_transactions", "reconciliation_reports"]:
        db[coll].delete_many({"_test": True})


@pytest.fixture(autouse=True)
def cleanup():
    _clean_collections()
    yield
    _clean_collections()


# ═══════════════════════════════════════════════════════════════════
# FIX 1: Cas A Deadlock Reset
# ═══════════════════════════════════════════════════════════════════

class TestCasADeadlockReset:
    """Test that Cas A overrides are properly reset before financial re-trigger."""

    def _seed_cas_a_scenario(self):
        """Create a scenario where Cas A blocks a capture."""
        apt_id = f"test-apt-{uuid.uuid4().hex[:8]}"
        payer_pid = f"test-payer-{uuid.uuid4().hex[:8]}"
        reviewer_pid = f"test-reviewer-{uuid.uuid4().hex[:8]}"
        payer_uid = f"test-payer-uid-{uuid.uuid4().hex[:8]}"
        reviewer_uid = f"test-reviewer-uid-{uuid.uuid4().hex[:8]}"

        # Appointment
        db.appointments.insert_one({
            "appointment_id": apt_id,
            "title": "Test Cas A",
            "status": "completed",
            "attendance_evaluated": True,
            "_test": True,
        })

        # Participants
        db.participants.insert_one({
            "participant_id": payer_pid,
            "appointment_id": apt_id,
            "user_id": payer_uid,
            "status": "accepted_guaranteed",
            "_test": True,
        })
        db.participants.insert_one({
            "participant_id": reviewer_pid,
            "appointment_id": apt_id,
            "user_id": reviewer_uid,
            "status": "accepted_guaranteed",
            "_test": True,
        })

        # Attendance records — payer is no_show, reviewer is manual_review
        db.attendance_records.insert_one({
            "record_id": f"rec-{payer_pid}",
            "appointment_id": apt_id,
            "participant_id": payer_pid,
            "user_id": payer_uid,
            "outcome": "no_show",
            "review_required": True,
            "cas_a_override": True,
            "cas_a_reason": "Penalite etablie mais aucun beneficiaire admissible.",
            "_test": True,
        })
        db.attendance_records.insert_one({
            "record_id": f"rec-{reviewer_pid}",
            "appointment_id": apt_id,
            "participant_id": reviewer_pid,
            "user_id": reviewer_uid,
            "outcome": "manual_review",
            "review_required": True,
            "_test": True,
        })

        return {
            "appointment_id": apt_id,
            "payer_pid": payer_pid,
            "reviewer_pid": reviewer_pid,
            "payer_uid": payer_uid,
            "reviewer_uid": reviewer_uid,
        }

    def test_reset_cas_a_overrides_clears_flags(self):
        """reset_cas_a_overrides should clear cas_a_override and review_required."""
        from services.attendance_service import reset_cas_a_overrides
        data = self._seed_cas_a_scenario()

        # Before reset
        rec = db.attendance_records.find_one({"record_id": f"rec-{data['payer_pid']}"}, {"_id": 0})
        assert rec["review_required"] is True
        assert rec["cas_a_override"] is True

        # Reset
        count = reset_cas_a_overrides(data["appointment_id"])
        assert count == 1

        # After reset
        rec = db.attendance_records.find_one({"record_id": f"rec-{data['payer_pid']}"}, {"_id": 0})
        assert rec["review_required"] is False
        assert rec.get("cas_a_override", False) is False
        assert "cas_a_reason" not in rec

    def test_reset_does_not_touch_real_manual_review(self):
        """reset_cas_a_overrides should NOT clear legitimate manual_review records."""
        from services.attendance_service import reset_cas_a_overrides
        data = self._seed_cas_a_scenario()

        count = reset_cas_a_overrides(data["appointment_id"])
        assert count == 1  # Only payer's record

        # Reviewer's manual_review should be untouched
        rec = db.attendance_records.find_one({"record_id": f"rec-{data['reviewer_pid']}"}, {"_id": 0})
        assert rec["review_required"] is True
        assert rec.get("cas_a_override") is None or rec.get("cas_a_override") is False

    def test_reset_is_idempotent(self):
        """Calling reset_cas_a_overrides twice should not cause errors."""
        from services.attendance_service import reset_cas_a_overrides
        data = self._seed_cas_a_scenario()

        count1 = reset_cas_a_overrides(data["appointment_id"])
        assert count1 == 1

        count2 = reset_cas_a_overrides(data["appointment_id"])
        assert count2 == 0  # Nothing left to reset

    def test_reset_on_nonexistent_appointment(self):
        """reset_cas_a_overrides on a non-existent appointment should return 0."""
        from services.attendance_service import reset_cas_a_overrides
        count = reset_cas_a_overrides("nonexistent-apt-id")
        assert count == 0


# ═══════════════════════════════════════════════════════════════════
# FIX 2: Contestation Resolution
# ═══════════════════════════════════════════════════════════════════

class TestContestationResolution:
    """Test the contestation resolution mechanism."""

    def _seed_contested_distribution(self):
        """Create a contested distribution with credited wallets."""
        dist_id = f"test-dist-{uuid.uuid4().hex[:8]}"
        apt_id = f"test-apt-{uuid.uuid4().hex[:8]}"
        guar_id = f"test-guar-{uuid.uuid4().hex[:8]}"
        noshow_uid = f"test-noshow-{uuid.uuid4().hex[:8]}"
        benef_uid = f"test-benef-{uuid.uuid4().hex[:8]}"
        benef_wid = f"test-wallet-{uuid.uuid4().hex[:8]}"

        # Create beneficiary wallet
        db.wallets.insert_one({
            "wallet_id": benef_wid,
            "user_id": benef_uid,
            "wallet_type": "user",
            "currency": "eur",
            "available_balance": 0,
            "pending_balance": 500,  # 5€ credited pending
            "total_received": 500,
            "total_withdrawn": 0,
            "_test": True,
        })

        # Create contested distribution
        db.distributions.insert_one({
            "distribution_id": dist_id,
            "appointment_id": apt_id,
            "guarantee_id": guar_id,
            "no_show_user_id": noshow_uid,
            "no_show_participant_id": "pid-noshow",
            "capture_amount_cents": 500,
            "capture_currency": "eur",
            "status": "contested",
            "contested": True,
            "contested_at": (datetime.now(timezone.utc) - timedelta(days=5)).isoformat(),
            "contested_by": noshow_uid,
            "contest_reason": "Erreur",
            "beneficiaries": [{
                "user_id": benef_uid,
                "wallet_id": benef_wid,
                "role": "participant",
                "amount_cents": 500,
                "status": "credited_pending",
            }],
            "hold_expires_at": (datetime.now(timezone.utc) + timedelta(days=10)).isoformat(),
            "_test": True,
        })

        # Create ledger transaction for initial credit
        db.wallet_transactions.insert_one({
            "transaction_id": str(uuid.uuid4()),
            "wallet_id": benef_wid,
            "type": "credit_pending",
            "amount": 500,
            "currency": "eur",
            "reference_type": "distribution",
            "reference_id": dist_id,
            "description": "Test credit",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "_test": True,
        })

        return {
            "distribution_id": dist_id,
            "appointment_id": apt_id,
            "guarantee_id": guar_id,
            "noshow_uid": noshow_uid,
            "benef_uid": benef_uid,
            "benef_wid": benef_wid,
        }

    def test_resolve_upheld_cancels_and_refunds(self):
        """Upheld contestation should cancel distribution and refund wallets."""
        from services.distribution_service import resolve_contestation
        data = self._seed_contested_distribution()

        with patch("services.distribution_service.StripeGuaranteeService", create=True):
            result = resolve_contestation(data["distribution_id"], "upheld", "admin", "Test")

        assert result["success"] is True
        assert result["resolution"] == "upheld"

        # Distribution should be cancelled
        dist = db.distributions.find_one({"distribution_id": data["distribution_id"]}, {"_id": 0})
        assert dist["status"] == "cancelled"
        assert dist["contestation_resolution"] == "upheld"
        assert dist["contestation_resolved_by"] == "admin"

        # Beneficiary should be refunded
        assert dist["beneficiaries"][0]["status"] == "refunded"

        # Wallet pending balance should be debited
        wallet = db.wallets.find_one({"wallet_id": data["benef_wid"]}, {"_id": 0})
        assert wallet["pending_balance"] == 0  # 500 - 500

    def test_resolve_rejected_resumes_hold(self):
        """Rejected contestation should resume hold period."""
        from services.distribution_service import resolve_contestation
        data = self._seed_contested_distribution()

        result = resolve_contestation(data["distribution_id"], "rejected", "admin", "Non fondé")

        assert result["success"] is True
        assert result["resolution"] == "rejected"
        assert "new_hold_expires" in result

        # Distribution should be back to pending_hold
        dist = db.distributions.find_one({"distribution_id": data["distribution_id"]}, {"_id": 0})
        assert dist["status"] == "pending_hold"
        assert dist["contested"] is False
        assert dist["contestation_resolution"] == "rejected"

        # Wallet should be untouched
        wallet = db.wallets.find_one({"wallet_id": data["benef_wid"]}, {"_id": 0})
        assert wallet["pending_balance"] == 500  # Unchanged

    def test_resolve_invalid_resolution(self):
        """Invalid resolution should be rejected."""
        from services.distribution_service import resolve_contestation
        data = self._seed_contested_distribution()

        result = resolve_contestation(data["distribution_id"], "invalid", "admin")
        assert result["success"] is False

    def test_resolve_non_contested(self):
        """Cannot resolve a distribution that is not contested."""
        from services.distribution_service import resolve_contestation

        dist_id = f"test-dist-{uuid.uuid4().hex[:8]}"
        db.distributions.insert_one({
            "distribution_id": dist_id,
            "status": "pending_hold",
            "_test": True,
        })

        result = resolve_contestation(dist_id, "upheld", "admin")
        assert result["success"] is False
        assert "pas contestée" in result["error"]

    def test_resolve_idempotent(self):
        """Resolving an already resolved contestation should fail gracefully."""
        from services.distribution_service import resolve_contestation
        data = self._seed_contested_distribution()

        # Resolve first time
        resolve_contestation(data["distribution_id"], "rejected", "admin")

        # Resolve second time — should fail (no longer contested)
        result = resolve_contestation(data["distribution_id"], "rejected", "admin")
        assert result["success"] is False

    def test_timeout_job_auto_rejects(self):
        """Timeout job should auto-reject contestations older than 30 days."""
        from services.distribution_service import run_contestation_timeout_job

        dist_id = f"test-dist-{uuid.uuid4().hex[:8]}"
        db.distributions.insert_one({
            "distribution_id": dist_id,
            "status": "contested",
            "contested": True,
            "contested_at": (datetime.now(timezone.utc) - timedelta(days=35)).isoformat(),
            "beneficiaries": [],
            "capture_currency": "eur",
            "_test": True,
        })

        result = run_contestation_timeout_job()
        assert result["resolved"] == 1

        dist = db.distributions.find_one({"distribution_id": dist_id}, {"_id": 0})
        assert dist["status"] == "pending_hold"
        assert dist["contestation_resolution"] == "rejected"
        assert dist["contestation_resolved_by"] == "system_timeout"

    def test_timeout_job_skips_recent(self):
        """Timeout job should not touch recent contestations."""
        from services.distribution_service import run_contestation_timeout_job

        dist_id = f"test-dist-{uuid.uuid4().hex[:8]}"
        db.distributions.insert_one({
            "distribution_id": dist_id,
            "status": "contested",
            "contested": True,
            "contested_at": (datetime.now(timezone.utc) - timedelta(days=5)).isoformat(),
            "_test": True,
        })

        result = run_contestation_timeout_job()
        assert result["resolved"] == 0

        dist = db.distributions.find_one({"distribution_id": dist_id}, {"_id": 0})
        assert dist["status"] == "contested"  # Unchanged


# ═══════════════════════════════════════════════════════════════════
# FIX 3: Ledger Reconciliation
# ═══════════════════════════════════════════════════════════════════

class TestLedgerReconciliation:
    """Test the ledger reconciliation job."""

    def _seed_clean_wallet(self):
        """Create a wallet that matches its ledger perfectly."""
        wid = f"test-wallet-{uuid.uuid4().hex[:8]}"
        uid = f"test-user-{uuid.uuid4().hex[:8]}"

        db.wallets.insert_one({
            "wallet_id": wid,
            "user_id": uid,
            "wallet_type": "user",
            "currency": "eur",
            "available_balance": 300,
            "pending_balance": 700,
            "total_received": 1000,
            "total_withdrawn": 0,
            "_test": True,
        })

        # Ledger: credit_pending 1000, credit_available 300, debit 0 (but pending should still be 700)
        # Actually: credit_pending=1000, then confirm 300 from pending → available
        # That means: credit_pending 1000 + credit_available 300 = 1300? No...
        # Let me think: the actual ledger types used:
        # credit_pending: adds to pending_balance
        # credit_available: moves from pending to available (subtracts pending, adds available)
        # So net effect: credit_pending=1000, credit_available=300 → pending=700, available=300
        # Total credits: 1000 + 300 = 1300, debits: 0 → expected=1300?
        # But actual = 300 + 700 = 1000.
        # This doesn't work with simple SUM approach...

        # Actually, looking at wallet_service code:
        # credit_pending: $inc pending_balance +amount, total_received +amount
        # confirm_pending_to_available: $inc pending_balance -amount, available_balance +amount
        #   AND creates TWO transactions? No, just one: type="credit_available"

        # Wait, let me re-check wallet_service.py
        # credit_pending creates tx type="credit_pending", $inc pending_balance +amount
        # confirm_pending_to_available creates tx type="credit_available", $inc pending-(-amount), available+(+amount)

        # So in the ledger:
        # credit_pending 1000 → pending=1000
        # credit_available 300 → pending-=300, available+=300 → pending=700, available=300
        # Total in ledger: credits = credit_pending(1000) + credit_available(300) = 1300
        # But actual total = 700 + 300 = 1000

        # The reconciliation logic uses: credits = SUM(credit_pending + credit_available) - SUM(debits)
        # This would give 1300 - 0 = 1300, but actual is 1000. DRIFT!

        # The problem is that credit_available represents a MOVE (pending → available), not a new credit.
        # So the reconciliation needs to treat credit_available differently...

        # Actually wait, let me re-read the reconciliation code I wrote:
        # CREDIT_TYPES = ("credit_pending", "credit_available")
        # credits = sum of all credit_pending + credit_available amounts
        # This is wrong! credit_available is a move, not a new credit.

        # The correct formula:
        # Total money IN = SUM(credit_pending)
        # Total money OUT = SUM(debit_payout) + SUM(debit_refund)
        # Expected total = money_in - money_out
        # actual total = available + pending

        # credit_available is just an internal transfer from pending to available, it shouldn't change the total

        # I need to fix the reconciliation code!
        # ONLY credit_pending represents new money coming in
        # credit_available is just a move
        # debit_payout and debit_refund are money going out

        # So: CREDIT_TYPES should only be ("credit_pending",)

        # Actually... this depends on how the system is used. Let me check all types:
        pass

    def test_reconciliation_clean(self):
        """Clean wallet should produce no drift."""
        from services.wallet_service import run_reconciliation_job

        wid = f"test-wallet-{uuid.uuid4().hex[:8]}"
        uid = f"test-user-{uuid.uuid4().hex[:8]}"

        db.wallets.insert_one({
            "wallet_id": wid,
            "user_id": uid,
            "wallet_type": "user",
            "currency": "eur",
            "available_balance": 300,
            "pending_balance": 700,
            "total_received": 1000,
            "total_withdrawn": 0,
            "_test": True,
        })

        # Ledger matches: credit_pending 1000 (the only type that adds total money)
        db.wallet_transactions.insert_one({
            "transaction_id": str(uuid.uuid4()),
            "wallet_id": wid,
            "type": "credit_pending",
            "amount": 1000,
            "currency": "eur",
            "reference_type": "distribution",
            "reference_id": "test-dist-1",
            "description": "Test",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "_test": True,
        })

        report = run_reconciliation_job()
        # Find our wallet in the report
        our_drifts = [d for d in report["drifts"] if d["wallet_id"] == wid]
        assert len(our_drifts) == 0

    def test_reconciliation_detects_drift(self):
        """Drift should be detected and logged."""
        from services.wallet_service import run_reconciliation_job

        wid = f"test-wallet-{uuid.uuid4().hex[:8]}"
        uid = f"test-user-{uuid.uuid4().hex[:8]}"

        # Wallet says 1500 total but ledger only has 1000
        db.wallets.insert_one({
            "wallet_id": wid,
            "user_id": uid,
            "wallet_type": "user",
            "currency": "eur",
            "available_balance": 800,
            "pending_balance": 700,
            "total_received": 1500,
            "total_withdrawn": 0,
            "_test": True,
        })

        db.wallet_transactions.insert_one({
            "transaction_id": str(uuid.uuid4()),
            "wallet_id": wid,
            "type": "credit_pending",
            "amount": 1000,
            "currency": "eur",
            "reference_type": "distribution",
            "reference_id": "test-dist-2",
            "description": "Test",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "_test": True,
        })

        report = run_reconciliation_job()
        our_drifts = [d for d in report["drifts"] if d["wallet_id"] == wid]
        assert len(our_drifts) == 1
        assert our_drifts[0]["drift_cents"] == 500  # 1500 actual - 1000 ledger

    def test_reconciliation_with_debits(self):
        """Reconciliation should account for debits."""
        from services.wallet_service import run_reconciliation_job

        wid = f"test-wallet-{uuid.uuid4().hex[:8]}"
        uid = f"test-user-{uuid.uuid4().hex[:8]}"

        # credit 1000, debit 300 → expected total 700 → actual 700 → clean
        db.wallets.insert_one({
            "wallet_id": wid,
            "user_id": uid,
            "wallet_type": "user",
            "currency": "eur",
            "available_balance": 700,
            "pending_balance": 0,
            "total_received": 1000,
            "total_withdrawn": 300,
            "_test": True,
        })

        db.wallet_transactions.insert_one({
            "transaction_id": str(uuid.uuid4()),
            "wallet_id": wid,
            "type": "credit_pending",
            "amount": 1000,
            "currency": "eur",
            "reference_type": "distribution",
            "reference_id": "test-dist-3",
            "description": "Test credit",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "_test": True,
        })
        db.wallet_transactions.insert_one({
            "transaction_id": str(uuid.uuid4()),
            "wallet_id": wid,
            "type": "debit_payout",
            "amount": 300,
            "currency": "eur",
            "reference_type": "payout",
            "reference_id": "test-payout-1",
            "description": "Test payout",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "_test": True,
        })

        report = run_reconciliation_job()
        our_drifts = [d for d in report["drifts"] if d["wallet_id"] == wid]
        assert len(our_drifts) == 0

    def test_reconciliation_stores_report(self):
        """Reconciliation should store a report in the DB."""
        from services.wallet_service import run_reconciliation_job

        report = run_reconciliation_job()

        assert "report_id" in report
        assert "run_at" in report
        assert "wallets_checked" in report
        assert report["status"] in ("clean", "drift_detected")

        # Verify stored in DB
        stored = db.reconciliation_reports.find_one({"report_id": report["report_id"]}, {"_id": 0})
        assert stored is not None

    def test_reconciliation_no_destructive_changes(self):
        """Reconciliation should NEVER modify wallet balances."""
        from services.wallet_service import run_reconciliation_job

        wid = f"test-wallet-{uuid.uuid4().hex[:8]}"
        uid = f"test-user-{uuid.uuid4().hex[:8]}"

        # Create drifted wallet
        db.wallets.insert_one({
            "wallet_id": wid,
            "user_id": uid,
            "wallet_type": "user",
            "currency": "eur",
            "available_balance": 9999,
            "pending_balance": 0,
            "total_received": 9999,
            "total_withdrawn": 0,
            "_test": True,
        })

        run_reconciliation_job()

        # Balance should be UNCHANGED — no auto-correction
        wallet = db.wallets.find_one({"wallet_id": wid}, {"_id": 0})
        assert wallet["available_balance"] == 9999
