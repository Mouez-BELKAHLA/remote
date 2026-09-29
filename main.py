# main.py
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import date
from models import PropertyDB, BookingDB
from database import engine, SessionLocal, Base
from typing import Optional
from sqlalchemy.exc import IntegrityError
# Creates the "properties" table in Postgres if it doesn't exist yet
Base.metadata.create_all(bind=engine)
CLEANING_FEE = 50.0
app = FastAPI()
class BookingCreate(BaseModel):
    property_id: int
    guest_name: str
    check_in: date
    check_out: date

class Booking(BookingCreate):
    id: int
    nights: Optional[int] = None
    total_price: Optional[float] = None
    model_config = {"from_attributes": True}
# Pydantic model = what the API accepts/returns (unchanged)
class Property(BaseModel):
    id: int
    title: str
    price: float
    city: str

    model_config = {"from_attributes": True} # lets Pydantic read from SQLAlchemy objects


# Dependency: gives each request its own DB session, closes it after
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/properties", response_model=list[Property])
def get_properties(db: Session = Depends(get_db)):
    return db.query(PropertyDB).all()
@app.get("/properties/available", response_model=list[Property])
def get_available_properties(
    check_in: date,
    check_out: date,
    city: Optional[str] = None,
    max_price: Optional[float] = None,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    if check_out <= check_in:
        raise HTTPException(status_code=400, detail="check_out must be after check_in")

    booked = db.query(BookingDB.property_id).filter(
        BookingDB.check_in < check_out,
        BookingDB.check_out > check_in,
    )
    query = db.query(PropertyDB).filter(PropertyDB.id.notin_(booked))

    if city is not None:
        query = query.filter(PropertyDB.city == city)

    if max_price is not None:
        query = query.filter(PropertyDB.price <= max_price)

    return query.offset(skip).limit(limit).all()

@app.get("/properties/{property_id}", response_model=Property)
def get_property(property_id: int, db: Session = Depends(get_db)):
    prop = db.query(PropertyDB).filter(PropertyDB.id == property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    return prop


@app.post("/properties", response_model=Property)
def create_property(property: Property, db: Session = Depends(get_db)):
    existing = db.query(PropertyDB).filter(PropertyDB.id == property.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="ID already exists")
    db_property = PropertyDB(**property.model_dump())
    db.add(db_property)
    db.commit()
    db.refresh(db_property)
    return db_property
@app.put("/bookings/{booking_id}",response_model=Booking)
def update_booking(booking_id:int,updated:BookingCreate,db:Session=Depends(get_db)):
    if updated.check_out <= updated.check_in:
        raise HTTPException(status_code=400,detail="check_out is not after check_in")
    booking=db.query(BookingDB).filter(BookingDB.id==booking_id).first()
    if not booking:
        raise HTTPException(status_code=404,detail="booking not found")
    conflict = db.query(BookingDB).filter(
            BookingDB.property_id == booking.property_id,            
            BookingDB.check_in < updated.check_out,
            BookingDB.check_out > updated.check_in,
            BookingDB.id != booking_id,
        ).first()
    if conflict:
            raise HTTPException(status_code=409, detail="Property already booked for these dates")
    booking.check_in = updated.check_in
    booking.check_out = updated.check_out
    
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Property already booked for these dates")
    db.refresh(booking)
    return booking    

@app.put("/properties/{property_id}", response_model=Property)
def update_property(property_id: int, updated: Property, db: Session = Depends(get_db)):
    prop = db.query(PropertyDB).filter(PropertyDB.id == property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    prop.title = updated.title
    prop.price = updated.price
    prop.city = updated.city
    db.commit()
    db.refresh(prop)
    return prop

@app.delete("/bookings/{id}")
def delete_booking(id:int,db:Session=Depends(get_db)):
    booking=db.query(BookingDB).filter(BookingDB.id==id).first()
    if not booking:
        raise HTTPException(status_code=404,detail="booking not found")
    db.delete(booking)
    db.commit()
    return {"message":"deleted"}
@app.delete("/properties/{property_id}")
def delete_property(property_id: int, db: Session = Depends(get_db)):
    prop = db.query(PropertyDB).filter(PropertyDB.id == property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    db.delete(prop)
    db.commit()
    return {"message": "Deleted"}
@app.post("/bookings", response_model=Booking, status_code=201)
def create_booking(booking: BookingCreate, db: Session = Depends(get_db)):
    # TODO 1: if check_out is not after check_in -> raise HTTPException 400
    if booking.check_out <= booking.check_in:
                raise HTTPException(status_code=400, detail="check_out is not after check_in")
    # TODO 2: if the property doesn't exist -> raise HTTPException 404
    prop = db.query(PropertyDB).filter(PropertyDB.id == booking.property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    # TODO 3: if it overlaps an existing booking for the same property
    conflict = db.query(BookingDB).filter(
        BookingDB.property_id == booking.property_id,
        BookingDB.check_in < booking.check_out,
        BookingDB.check_out > booking.check_in,
    ).first()
    if conflict:
        raise HTTPException(status_code=409, detail="Property already booked for these dates")

    db_booking = BookingDB(**booking.model_dump())
    db.add(db_booking)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Property already booked for these dates")
    db.refresh(db_booking)
    nights = (booking.check_out - booking.check_in).days
    return Booking(
        id=db_booking.id,
        **booking.model_dump(),
        nights=nights,
        total_price=nights * prop.price + CLEANING_FEE,
    )


@app.get("/properties/{property_id}/bookings", response_model=list[Booking])
def get_property_bookings(property_id: int, db: Session = Depends(get_db)):
    return db.query(BookingDB).filter(BookingDB.property_id == property_id).all()