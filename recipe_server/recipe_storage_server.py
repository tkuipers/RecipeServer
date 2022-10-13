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

app = FastAPI()
dbConfig = {'sqlalchemy.url':'postgresql://admin:water123@localhost:5432/recipes', 'sqlalchemy.echo':'True'}
engine = sqlalchemy.engine_from_config(dbConfig)
# Base.metadata.drop_all(engine)
if not sqlalchemy.inspect(engine).has_table("recipe"):
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
print("New Database Created "+ str(database_exists(engine.url)))

database = sessionmaker(bind=engine)()

@app.get("/recipes")
async def all_recipes():
    all_recipes = database.query(Recipe).all()
    min_map = map(lambda recipe: recipe.to_dto(), all_recipes)
    return list(min_map)

@app.get("/recipes/{id}")
async def specific_recipes(id: int):
    exists = database.query(Recipe).get(id)is not None
    if exists:
        recipe = database.query(Recipe).get(id)
        return recipe.to_dto()
    raise HTTPException(status_code=404, detail="Item not found")

@app.post("/recipes/")
async def add_recipe(recipe_url: RecipeUrl):
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
        recipe.ingredients_list = scraper.ingredients()
        recipe.instructions_list = scraper.instructions_list()
        database.flush()
        return RedirectResponse(url=f'/recipes/{recipe.id}')
    else:
        return RedirectResponse(url=f'/recipes/{database.query(Recipe).where(Recipe.url == recipe_url.recipe_url).first().id}')

@app.delete("/recipes/{id}")
async def delete_recipe(id: int):
    exists = database.query(Recipe).get(id)
    if exists:
        database.delete(exists)
        database.flush()
        return RedirectResponse(url=f'/recipes/')
    raise HTTPException(status_code=404, detail="Item not found")

@app.patch("/recipes/{id}")
async def update_recipe(id: int, recipe: RecipeDto):
    exists = database.query(Recipe).get(id)
    if exists:
        recipe.id = id
        exists.update(Recipe.from_dto(recipe))
        database.commit()
        return RedirectResponse(url=f'/recipes/{recipe.id}')
    raise HTTPException(status_code=404, detail="Item not found")
    
    

