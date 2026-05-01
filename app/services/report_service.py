from app.services.transaction_service import TransactionService
from typing import Optional


class ReportService:
    @staticmethod
    def monthly_digest_text(user_id: int, month: Optional[str] = None) -> str:
        summary = TransactionService.monthly_summary(user_id, month)
        return (
            f"FinTrack monthly digest for {summary['month']}\n"
            f"Transactions: {summary['transaction_count']}\n"
            f"Income: P {summary['income']:.2f}\n"
            f"Expenses: P {summary['expenses']:.2f}\n"
            f"Net: P {summary['balance']:.2f}\n"
        )
