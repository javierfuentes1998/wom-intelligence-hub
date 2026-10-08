import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db import Base, get_db
from app.main import app

@pytest.fixture()
def db(tmp_path):
    eng=create_engine(f"sqlite:///{tmp_path/'test.db'}",connect_args={"check_same_thread":False}); Base.metadata.create_all(eng); S=sessionmaker(bind=eng); s=S()
    try: yield s
    finally:s.close()

@pytest.fixture()
def client(db):
    app.dependency_overrides[get_db]=lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()
