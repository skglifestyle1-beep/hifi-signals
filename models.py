from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
import datetime as dt

Base = declarative_base()
engine = create_engine("sqlite:///hifi.db", echo=False)
Session = sessionmaker(bind=engine, expire_on_commit=False)

class Signal(Base):
    __tablename__ = "signals"
    id   = Column(Integer, primary_key=True)
    side = Column(String(4))
    level= Column(Float)
    entry= Column(Float)
    sl   = Column(Float)
    tp   = Column(Float)
    rr   = Column(Float)
    outcome = Column(String(4), default="")  # WIN / LOSS / OPEN
    pips = Column(Float, default=0)
    ts   = Column(DateTime, default=dt.datetime.utcnow)

Base.metadata.create_all(engine)
