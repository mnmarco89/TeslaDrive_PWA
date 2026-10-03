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


class CostRate(Base):
    __tablename__ = "telemetry_cost_rates"
    id = Column(Integer, primary_key=True)
    vin = Column(String, index=True)
    effective_from = Column(DateTime, index=True, nullable=False)
    recorded_at = Column(DateTime, nullable=False)
    electricity = Column(Float, nullable=False)
    diesel = Column(Float)
    diesel_km_l = Column(Float, nullable=False)
    source = Column(String, nullable=False)
    station = Column(String)
    dataset_date = Column(String)


class TripCostSnapshot(Base):
    __tablename__ = "telemetry_trip_cost_snapshots"
    trip_id = Column(Integer, ForeignKey("telemetry_trips.id"), primary_key=True)
    rate_id = Column(Integer, ForeignKey("telemetry_cost_rates.id"))
    diesel = Column(Float)
    diesel_km_l = Column(Float)


class FuelPriceState(Base):
    __tablename__ = "telemetry_fuel_price_state"
    vin = Column(String, primary_key=True)
    last_attempt_at = Column(DateTime)
    last_success_at = Column(DateTime)
    diesel = Column(Float)
    error = Column(String)
    station = Column(String)
    city = Column(String)
    dataset_date = Column(String)
    reported_at = Column(String)


class TripContext(Base):
    __tablename__ = "telemetry_trip_context"
    trip_id = Column(Integer, ForeignKey("telemetry_trips.id"), primary_key=True)
    updated_at = Column(DateTime)
    payload = Column(Text)


class ChargingSession(Base):
    __tablename__ = 'telemetry_charging_sessions'
    id = Column(Integer, primary_key=True)
    vin = Column(String, index=True, nullable=False)
    started_at = Column(DateTime, nullable=False)
    last_sample_at = Column(DateTime, nullable=False)
    ended_at = Column(DateTime)
    status = Column(String, nullable=False, default='active')
    partial = Column(Boolean, nullable=False, default=False)
    start_soc = Column(Float)
    end_soc = Column(Float)
    last_counter_kwh = Column(Float, nullable=False)
    energy_kwh = Column(Float, nullable=False, default=0)


class ChargingIncrement(Base):
    __tablename__ = 'telemetry_charging_increments'
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey('telemetry_charging_sessions.id'), index=True, nullable=False)
    day = Column(String, index=True, nullable=False)
    energy_kwh = Column(Float, nullable=False)
    seconds = Column(Float, nullable=False)
    midnight_estimate = Column(Boolean, nullable=False, default=False)


class VehicleLocation(Base):
    __tablename__ = 'telemetry_vehicle_location'
    vin = Column(String, primary_key=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    recorded_at = Column(DateTime, nullable=False)


class WeatherProviderState(Base):
    __tablename__ = 'telemetry_weather_provider_state'
    name = Column(String, primary_key=True)
    blocked_until = Column(DateTime)


class WeatherProviderCache(Base):
    __tablename__ = 'telemetry_weather_provider_cache'
    key = Column(String, primary_key=True)
    expires_at = Column(DateTime, nullable=False)
    payload = Column(Text, nullable=False)


class TripAmbient(Base):
    __tablename__ = 'telemetry_trip_ambient'
    trip_id = Column(Integer, ForeignKey('telemetry_trips.id'), primary_key=True)
    recorded_at = Column(DateTime, nullable=False)
    temperature_c = Column(Float, nullable=False)


class SavingsBaseline(Base):
    __tablename__ = 'telemetry_savings_baseline'
    vin = Column(String, primary_key=True)
    cutoff_at = Column(DateTime, nullable=False)
    distance_km = Column(Float, nullable=False)
    electricity_price = Column(Float, nullable=False)
    diesel_price = Column(Float, nullable=False)
    electric_kwh_100km = Column(Float, nullable=False)
    diesel_km_l = Column(Float, nullable=False)
