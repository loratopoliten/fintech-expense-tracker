from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class TransactionCreate(BaseModel):
    type: str = Field(pattern="^(income|expense)$")
    amount: float = Field(gt=0)
    category: str = Field(min_length=1, max_length=80)
    description: str = ""
    date: date
    tags: str = ""
    is_recurring: bool = False
    parent_transaction_id: Optional[int] = None


class TransactionOut(TransactionCreate):
    id: int


class BudgetUpsert(BaseModel):
    category: str = Field(min_length=1, max_length=80)
    limit_amt: float = Field(gt=0)
    month: str = Field(pattern=r"^\d{4}-\d{2}$")


class RecurringTransactionCreate(BaseModel):
    type: str = Field(pattern="^(income|expense)$")
    amount: float = Field(gt=0)
    category: str = Field(min_length=1, max_length=80)
    description: str = ""
    tags: str = ""
    frequency: str = Field(default="monthly", pattern="^monthly$")
    next_date: date


class SavingsGoalCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    target_amt: float = Field(gt=0)
    saved_amt: float = Field(default=0, ge=0)
    due_date: Optional[date] = None


class SavingsGoalUpdate(BaseModel):
    saved_amt: float = Field(ge=0)

