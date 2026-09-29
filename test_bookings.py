import random
from fastapi.testclient import TestClient
from main import app
from database import SessionLocal
from models import PropertyDB, BookingDB

client = TestClient(app)

def make_property():
    pid = random.randint(100000, 999999)
    r = client.post("/properties", json={"id": pid, "title": "Test", "price": 100.0, "city": "Tunis"})
    assert r.status_code == 200
    return pid

def cleanup(pid):
    db = SessionLocal()
    db.query(BookingDB).filter(BookingDB.property_id == pid).delete()
    db.query(PropertyDB).filter(PropertyDB.id == pid).delete()
    db.commit()
    db.close()

def test_create_booking():
    pid = make_property()
    try:
        r = client.post("/bookings", json={"property_id": pid, "guest_name": "A",
                                           "check_in": "2030-01-10", "check_out": "2030-01-15"})
        assert r.status_code == 201
        assert r.json()["total_price"] == 5 * 100.0 + 50.0
    finally:
        cleanup(pid)

def test_overlapping_booking_returns_409():
    pid = make_property()
    try:
        client.post("/bookings", json={"property_id": pid, "guest_name": "A",
                                       "check_in": "2030-01-10", "check_out": "2030-01-15"})
        r = client.post("/bookings", json={"property_id": pid, "guest_name": "B",
                                           "check_in": "2030-01-12", "check_out": "2030-01-14"})
        assert r.status_code == 409
    finally:
        cleanup(pid)
def test_update_booking():
    pid = make_property()
    try:
        r = client.post("/bookings", json={"property_id": pid, "guest_name": "A",
                                           "check_in": "2030-02-10", "check_out": "2030-02-15"})
        booking_id = r.json()["id"]
        r = client.put(f"/bookings/{booking_id}", json={"property_id": pid, "guest_name": "A",
                                                        "check_in": "2030-02-11", "check_out": "2030-02-16"})
        assert r.status_code == 200
        assert r.json()["check_in"] == "2030-02-11"
    finally:
        cleanup(pid)

def test_update_booking_conflict_returns_409():
    pid = make_property()
    try:
        r = client.post("/bookings", json={"property_id": pid, "guest_name": "A",
                                           "check_in": "2030-03-01", "check_out": "2030-03-05"})
        first_id = r.json()["id"]
        client.post("/bookings", json={"property_id": pid, "guest_name": "B",
                                       "check_in": "2030-03-10", "check_out": "2030-03-15"})
        r = client.put(f"/bookings/{first_id}", json={"property_id": pid, "guest_name": "A",
                                                      "check_in": "2030-03-12", "check_out": "2030-03-14"})
        assert r.status_code == 409
    finally:
        cleanup(pid)