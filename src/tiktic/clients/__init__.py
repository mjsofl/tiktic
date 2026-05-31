"""
Ticket data source clients.

Import order and availability:
- CashorTradeClient is the most important for the $100 goal in v0.1.
- The other two are more stable but generally more expensive.
"""

from .base import TicketClient
from .cashortrade import CashorTradeClient
from .seatgeek import SeatGeekClient
from .ticketmaster import TicketmasterClient

__all__ = [
    "TicketClient",
    "CashorTradeClient",
    "TicketmasterClient",
    "SeatGeekClient",
]
