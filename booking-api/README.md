# Booking API

A small property-booking REST API built with FastAPI, SQLAlchemy and PostgreSQL.

## Features

- CRUD for properties
- Create, update, delete and list bookings
- Overlap prevention: a property can't be double-booked, and same-day turnover is allowed (one guest checks out the day the next checks in)
- Availability search with `city` and `max_price` filters and pagination (`skip`, `limit`)
- Price calculation on booking creation: `nights * price + flat cleaning fee`
- Automated tests with pytest

## Tech stack

Python 3.12, FastAPI, SQLAlchemy, PostgreSQL (psycopg2), Pydantic v2, pytest, python-dotenv

## Setup

1. Create a PostgreSQL database named `properties_db`.
2. Create a `.env` file in this folder:

```
   DATABASE_URL=postgresql+psycopg2://postgres@localhost:5432/properties_db
```

3. Install dependencies:

```
   pip install fastapi uvicorn sqlalchemy psycopg2-binary python-dotenv pytest httpx
```

4. Add the overlap constraint in Postgres (see "Concurrency" below).
5. Run the server:

```
   uvicorn main:app --reload
```

6. Open `http://127.0.0.1:8000/docs` for the interactive Swagger UI.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/properties` | List all properties |
| POST | `/properties` | Create a property |
| GET | `/properties/available` | Search available properties (`check_in`, `check_out`, optional `city`, `max_price`, `skip`, `limit`) |
| GET | `/properties/{property_id}` | Get one property |
| PUT | `/properties/{property_id}` | Update a property |
| DELETE | `/properties/{property_id}` | Delete a property |
| POST | `/bookings` | Create a booking (returns `nights` and `total_price`) |
| PUT | `/bookings/{booking_id}` | Change a booking's dates |
| DELETE | `/bookings/{id}` | Delete a booking |
| GET | `/properties/{property_id}/bookings` | List bookings for a property |

Error codes: `400` invalid dates, `404` property or booking not found, `409` dates already booked.

## Design decisions

**Overlap logic.** Two stays overlap when `existing.check_in < new.check_out` and `existing.check_out > new.check_in`. The strict comparisons mean a stay ending on the 15th doesn't conflict with one starting on the 15th.

**Concurrency.** Checking for a conflict and then inserting leaves a gap where two simultaneous requests can both pass the check. To close it, PostgreSQL enforces the rule itself with an exclusion constraint, and the API turns the resulting `IntegrityError` into a `409`. Adjust this SQL to match what you ran:

```sql
CREATE EXTENSION IF NOT EXISTS btree_gist;

ALTER TABLE bookings
ADD CONSTRAINT no_overlapping_bookings
EXCLUDE USING gist (
    property_id WITH =,
    daterange(check_in, check_out, '[)') WITH &&
);
```

**Pricing is computed, not stored.** `nights` and `total_price` are calculated when a booking is created and returned in the response. They aren't stored, since they derive from data already in the database, so there's no second copy to go stale. A booking list from `GET` therefore returns them as `null`.

## Assumptions and limitations

- The cleaning fee is a flat 50.0 per booking (`CLEANING_FEE` in `main.py`).
- `PUT /bookings/{id}` only changes the dates. A booking can't be moved to another property, and any `property_id` in the body is ignored.
- `PUT` and `POST` ignore price snapshots. In production I'd store the total at booking time, so later price changes don't rewrite history.
- There's no authentication, and tables are created with `create_all` rather than migrations (Alembic would be the next step).
- Tests run against the real local database. They create their own properties with random IDs and clean up after themselves.

## Running the tests

```
pytest -v
```

Covers creating a booking and its price, overlap rejection (409), updating a booking, and update conflicts (409).

## What I'd improve next

- Alembic migrations, including the exclusion constraint
- A separate test database
- Price snapshot stored on the booking
- Authentication and per-property ownership
- Pagination on the bookings list