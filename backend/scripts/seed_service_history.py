import sys
from datetime import date
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import Base, SessionLocal, engine
from app.models import ServiceRecord

RECORDS = [
    ("HC-2021-001", 2021, "HONDA", "CIVIC", 31800, "2024-01-18", "brakes", "Front brake pads replaced after wear inspection. No ABS faults stored."),
    ("HC-2021-001", 2021, "HONDA", "CIVIC", 44720, "2025-02-11", "electrical", "Intermittent ABS warning reported. Technician found a stored wheel-speed sensor code; connector cleaned and concern not present after road test."),
    ("HC-2021-001", 2021, "HONDA", "CIVIC", 50110, "2025-10-03", "maintenance", "Oil and filter service. Multi-point inspection completed; no brake noise reported."),
    ("HC-2022-002", 2022, "HONDA", "CIVIC", 18400, "2024-05-06", "infotainment", "Customer reported intermittent display reboot. Software version checked and system reset."),
    ("HC-2022-002", 2022, "HONDA", "CIVIC", 27650, "2025-04-14", "tires", "Rotated tires and corrected tire pressures. Slight steering vibration not duplicated."),
    ("HC-2023-003", 2023, "HONDA", "CIVIC", 9900, "2024-08-20", "HVAC", "A/C cooling complaint. Refrigerant level inspected; no leak found."),
    ("HC-2023-003", 2023, "HONDA", "CIVIC", 21300, "2025-07-29", "maintenance", "Scheduled maintenance and cabin filter replacement."),
    ("HC-2020-004", 2020, "HONDA", "CIVIC", 60300, "2025-03-19", "engine", "Rough idle concern. Spark plugs inspected and intake system checked; no active warning light."),
    ("HC-2020-004", 2020, "HONDA", "CIVIC", 67420, "2026-01-07", "battery", "12V battery failed load test and was replaced."),
    ("TR-2021-001", 2021, "TOYOTA", "RAV4", 28600, "2024-03-04", "brakes", "Rear brake pads inspected for noise. No abnormal wear found."),
    ("TR-2021-001", 2021, "TOYOTA", "RAV4", 39210, "2025-01-16", "electrical", "Battery warning complaint. Charging system tested within specification; battery terminals serviced."),
    ("TR-2021-001", 2021, "TOYOTA", "RAV4", 47100, "2025-11-22", "maintenance", "Oil service and tire rotation. No warning lights present."),
    ("TR-2022-002", 2022, "TOYOTA", "RAV4", 19450, "2024-07-09", "HVAC", "Blower fan noise at high speed. Debris removed from cabin air intake."),
    ("TR-2022-002", 2022, "TOYOTA", "RAV4", 32880, "2025-09-18", "brakes", "Customer reported steering wheel shake under braking. Front rotors measured and documented for technician follow-up."),
    ("TR-2023-003", 2023, "TOYOTA", "RAV4", 12100, "2024-10-01", "infotainment", "Phone connectivity concern. Head unit software checked and pairing reset."),
    ("TR-2023-003", 2023, "TOYOTA", "RAV4", 24120, "2025-12-02", "maintenance", "Routine maintenance; filters replaced."),
    ("TR-2020-004", 2020, "TOYOTA", "RAV4", 70800, "2025-06-13", "engine", "Check-engine light with rough running. Diagnostic codes recorded and vehicle referred for further technician diagnosis."),
    ("TR-2020-004", 2020, "TOYOTA", "RAV4", 78150, "2026-02-20", "cooling", "Customer noted temperature gauge above normal. Cooling system pressure test requested; vehicle held for technician inspection."),
]


def main():
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        db.query(ServiceRecord).delete()
        for vehicle_id, year, make, model, mileage, service_date, category, note in RECORDS:
            db.add(ServiceRecord(
                vehicle_id=vehicle_id,
                model_year=year,
                make=make,
                model=model,
                mileage=mileage,
                service_date=date.fromisoformat(service_date),
                category=category,
                technician_note=note,
            ))
        db.commit()
    print(f"Seeded {len(RECORDS)} synthetic dealership service records.")


if __name__ == "__main__":
    main()
