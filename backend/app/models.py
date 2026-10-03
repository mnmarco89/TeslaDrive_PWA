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
