from aiogram.fsm.state import State, StatesGroup
class AdminStates(StatesGroup):
    waiting_price = State()
    waiting_reply = State()
    waiting_question = State()
