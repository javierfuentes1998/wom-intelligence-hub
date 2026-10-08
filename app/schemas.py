from datetime import date
from pydantic import BaseModel, Field, model_validator

class ExpenseIn(BaseModel):
    concept: str = Field(min_length=2, max_length=160)
    category_id: int
    amount: float = Field(gt=0)
    expense_date: date
    location_id: str | None = None
    room_id: str | None = None
    recurring: bool = False
    periodicity: str | None = None
    recurrence_key: str | None = None
    notes: str | None = None
    @model_validator(mode="after")
    def recurrence_is_coherent(self):
        if self.recurring and (not self.periodicity or not self.recurrence_key):
            raise ValueError("Los gastos recurrentes requieren periodicidad y recurrence_key")
        return self

class ExpenseOut(ExpenseIn):
    id: str
    voided: bool
    model_config = {"from_attributes": True}

class RecurringPlanIn(BaseModel):
    concept: str = Field(min_length=2,max_length=160)
    category_id: int
    amount: float = Field(gt=0)
    location_id: str|None=None
    room_id: str|None=None
    periodicity: str = Field(pattern=r"^(weekly|monthly|quarterly|annual|custom:[1-9][0-9]*:(days|weeks|months|years))$")
    valid_from: date
    valid_to: date|None=None

class LocationIn(BaseModel):
    id: str = Field(pattern="^[A-Z0-9_]+$")
    name: str
    address: str|None=None
    city: str|None=None
    active: bool=True

class RoomIn(BaseModel):
    id: str = Field(pattern="^[A-Z0-9_]+$")
    location_id: str
    name: str
    capacity: int=Field(gt=0)
    experience_type: str|None=None
    active: bool=True

class GameMasterIn(BaseModel):
    id: str
    display_name: str
    external_id: str|None=None
    home_location_id: str|None=None
    start_date: date|None=None
    end_date: date|None=None
    active: bool=True

class ChatIn(BaseModel):
    question: str = Field(min_length=2,max_length=500)
    session_id: str | None = Field(default=None,max_length=80)
    context: dict = Field(default_factory=dict)
