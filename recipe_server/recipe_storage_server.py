import os
from sqlite3 import register_adapter
from fastapi import FastAPI, HTTPException
import orjson
from recipe_scrapers import scrape_me
import json
import sqlalchemy
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy_utils import database_exists,create_database
from recipe_server.recipe import Base, Recipe, RecipeDto, RecipeUrl
from starlette.responses import RedirectResponse
from datetime import datetime, timedelta

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

app = FastAPI()
dbConfig = {'sqlalchemy.url':'postgresql://admin:water123@localhost:5432/recipes', 'sqlalchemy.echo':'True'}
engine = sqlalchemy.engine_from_config(dbConfig)
# Base.metadata.drop_all(engine)
if not sqlalchemy.inspect(engine).has_table("recipe"):
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
print("New Database Created "+ str(database_exists(engine.url)))

database = sessionmaker(bind=engine)()

# to get a string like this run:
# openssl rand -hex 32
SECRET_KEY = os.environ['API_KEY'] or "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


fake_users_db = {
    "tk": {
        "username": "tk",
        "full_name": "John Doe",
        "email": "johndoe@example.com",
        "hashed_password": os.getenv('HASHED_PASSWORD') or "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW",
        "disabled": False,
    }
}


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: str | None = None


class User(BaseModel):
    username: str
    email: str | None = None
    full_name: str | None = None
    disabled: bool | None = None


class UserInDB(User):
    hashed_password: str


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def get_user(db, username: str):
    if username in db:
        user_dict = db[username]
        return UserInDB(**user_dict)


def authenticate_user(fake_db, username: str, password: str):
    print(username)
    print(password)
    user = get_user(fake_db, username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(404)
        token_data = TokenData(username=username)
    except JWTError:
        raise HTTPException(405)
    print(token_data.username)
    user = get_user(fake_users_db, username=token_data.username)
    if user is None:
        raise HTTPException(406)
    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(fake_users_db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/users/me/", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    return current_user

@app.get("/recipes")
async def all_recipes(current_user: User = Depends(get_current_active_user)):
    all_recipes = database.query(Recipe).all()
    min_map = map(lambda recipe: recipe.to_dto(), all_recipes)
    return list(min_map)

@app.get("/recipes/{id}")
async def specific_recipes(id: int, current_user: User = Depends(get_current_active_user)):
    exists = database.query(Recipe).get(id)is not None
    if exists:
        recipe = database.query(Recipe).get(id)
        return recipe.to_dto()
    raise HTTPException(status_code=404, detail="Item not found")

@app.post("/recipes/", response_class=RedirectResponse, status_code=308)
async def add_recipe(recipe_url: RecipeUrl, current_user: User = Depends(get_current_active_user)):
    exists = database.query(Recipe).filter(Recipe.url == recipe_url.recipe_url).first() is not None
    if not exists:
        recipe = Recipe()
        database.add(recipe)
        scraper = scrape_me(recipe_url.recipe_url, wild_mode=True)
        recipe.url = recipe_url.recipe_url
        recipe.title = scraper.title()
        recipe.total_time = scraper.total_time()
        recipe.image_url = scraper.image()
        recipe.host = scraper.host()
        recipe.yields = scraper.yields()
        recipe.notes = ""
        recipe.rating = 0
        recipe.ingredients_list = scraper.ingredients()
        recipe.instructions_list = scraper.instructions_list()
        database.flush()
        return f'/recipes/{recipe.id}'
    else:
        return f'/recipes/{database.query(Recipe).where(Recipe.url == recipe_url.recipe_url).first().id}'

@app.delete("/recipes/{id}")
async def delete_recipe(id: int, current_user: User = Depends(get_current_active_user)):
    exists = database.query(Recipe).get(id)
    if exists:
        database.delete(exists)
        database.flush()
        return
    raise HTTPException(status_code=404, detail="Item not found")

@app.patch("/recipes/{id}")
async def update_recipe(id: int, recipe: RecipeDto, current_user: User = Depends(get_current_active_user)):
    exists = database.query(Recipe).get(id)
    if exists:
        recipe.id = id
        exists.update(Recipe.from_dto(recipe))
        database.commit()
        return
    raise HTTPException(status_code=404, detail="Item not found")

@app.get("/status")
async def server_status():
    return {"status": "ready"}
    

