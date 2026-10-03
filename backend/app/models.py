from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String

from .database import Base


class UserToken(Base):
    __tablename__ = "user_tokens"

    id = Column(Integer, primary_key=True, index=True)
    access_token = Column(String)
    refresh_token = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)


class UserSettingsDB(Base):
    __tablename__ = "user_settings"

    id = Column(Integer, primary_key=True, index=True)
    electricity = Column(String, default="0.24")
    diesel = Column(String, default="2.19")
    diesel_km_l = Column(String, default="15.5")
    voltage_protection = Column(Integer, default=1)


from sqlalchemy import Boolean, Float, ForeignKey, Text, UniqueConstraint


class TrackingVehicle(Base):
    __tablename__ = "tracking_vehicles"
    vin = Column(String, primary_key=True)
    enabled = Column(Boolean, default=True, nullable=False)
    capacity_kwh = Column(Float, nullable=True)
    last_sample_at = Column(DateTime, nullable=True)
    last_status = Column(String, default="In attesa dei dati Tesla")


class Trip(Base):
    __tablename__ = "telemetry_trips"
    id = Column(Integer, primary_key=True)
    vin = Column(String, index=True, nullable=False)
    started_at = Column(DateTime, index=True, nullable=False)
    ended_at = Column(DateTime)
    last_sample_at = Column(DateTime, nullable=False)
    status = Column(String, default="active", nullable=False)
    partial = Column(Boolean, default=False, nullable=False)
    start_odometer_km = Column(Float)
    end_odometer_km = Column(Float)
    start_battery = Column(Float)
    end_battery = Column(Float)
    capacity_kwh = Column(Float)
    capacity_source = Column(String)
    tariff = Column(Float)
    destination = Column(Text)
    distance_km = Column(Float)
    distance_source = Column(String)
    energy_kwh = Column(Float)
    parked_since = Column(DateTime)


class TripPoint(Base):
    __tablename__ = "telemetry_trip_points"
    __table_args__ = (UniqueConstraint("trip_id", "recorded_at"),)
    id = Column(Integer, primary_key=True)
    trip_id = Column(Integer, ForeignKey("telemetry_trips.id"), index=True, nullable=False)
    recorded_at = Column(DateTime, nullable=False)
    latitude = Column(Float)
    longitude = Column(Float)
    speed_kmh = Column(Float)
    battery = Column(Float)
    odometer_km = Column(Float)


class BatteryCalibration(Base):
    __tablename__ = "telemetry_battery_calibration"
    vin = Column(String, primary_key=True)
    started_at = Column(DateTime)
    last_sample_at = Column(DateTime)
    start_soc = Column(Float)
    start_energy = Column(Float)
    last_soc = Column(Float)
    last_energy = Column(Float)
    nominal_kwh = Column(Float)


class BatteryObservation(Base):
    __tablename__ = "telemetry_battery_observations"
    id = Column(Integer, primary_key=True)
    vin = Column(String, index=True, nullable=False)
    recorded_at = Column(DateTime, nullable=False)
    capacity_kwh = Column(Float, nullable=False)
    soc_delta = Column(Float, nullable=False)


class AppMigration(Base):
    __tablename__ = "telemetry_migrations"
    name = Column(String, primary_key=True)
