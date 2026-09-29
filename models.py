# models.py
from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey
from database import Base

class PropertyDB(Base):
    __tablename__ = "properties"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    price = Column(Float)
    city = Column(String)


class BookingDB(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False, index=True)
    guest_name = Column(String, nullable=False)
    check_in = Column(Date, nullable=False)
    check_out = Column(Date, nullable=False)