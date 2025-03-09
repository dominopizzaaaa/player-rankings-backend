from fastapi import FastAPI
from . import models, database
from sqlalchemy.orm import Session
from .database import engine

# Initialize the database
models.Base.metadata.create_all(bind=engine)

# Create the FastAPI app
app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Player Rankings API is running!"}
