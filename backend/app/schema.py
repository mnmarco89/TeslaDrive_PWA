"""Use dedicated names to avoid modifying unknown legacy schemas."""
import logging
from sqlalchemy import MetaData, Table, inspect, select, literal, func, text
from .database import Base
from .models import AppMigration, Trip, TripPoint


def initialize_database(engine):
    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        migration = "import_compatible_trips_v21"
        marker = AppMigration.__table__
        if connection.execute(select(marker.c.name).where(marker.c.name == migration)).first():
            return
        inspector = inspect(connection)
        if inspector.has_table("trips"):
            old_columns = {c["name"] for c in inspector.get_columns("trips")}
            needed = set(Trip.__table__.columns.keys()) - {"capacity_source"}
            if needed.issubset(old_columns):
                old = Table("trips", MetaData(), autoload_with=connection)
                dest = Trip.__table__
                columns = list(dest.columns.keys())
                values = [old.c[c] if c in old.c else literal("manual") for c in columns]
                existing = select(dest.c.id).where(dest.c.id == old.c.id).exists()
                connection.execute(dest.insert().from_select(columns, select(*values).where(~existing)))
                if inspector.has_table("trip_points"):
                    point_columns = set(TripPoint.__table__.columns.keys())
                    if point_columns.issubset({c["name"] for c in inspector.get_columns("trip_points")}):
                        source = Table("trip_points", MetaData(), autoload_with=connection)
                        target = TripPoint.__table__
                        exists = select(target.c.id).where(target.c.id == source.c.id).exists()
                        valid_trip = select(dest.c.id).where(dest.c.id == source.c.trip_id).exists()
                        keys = list(target.columns.keys())
                        connection.execute(target.insert().from_select(keys, select(*[source.c[k] for k in keys]).where(~exists, valid_trip)))
                if engine.dialect.name == "postgresql":
                    for name in ("telemetry_trips", "telemetry_trip_points"):
                        connection.execute(text(f"SELECT setval(pg_get_serial_sequence('{name}', 'id'), COALESCE(MAX(id), 1), COUNT(*) > 0) FROM {name}"))
            else:
                logging.getLogger(__name__).warning("Schema trips precedente conservato: nuovi viaggi nelle tabelle telemetry_*")
        connection.execute(marker.insert().values(name=migration))
