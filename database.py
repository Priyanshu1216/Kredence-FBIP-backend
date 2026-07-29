import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

# .env file se secret details (DATABASE_URL) nikalna
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

# Engine: Ye humari main 'Pipe' hai jo database se judti hai
engine = create_engine(DATABASE_URL)

# Session: Database ke andar data bhejne/lane ka rasta
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base: Iska use karke hum aage chalkar apne Tables banayenge
Base = declarative_base()