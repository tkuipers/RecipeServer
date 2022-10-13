from enum import unique
import json
from pydantic import BaseModel
import recipe_scrapers
from sqlalchemy import Column, Integer, PickleType, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.mutable import MutableList
from dataclasses import dataclass, field
@dataclass()
class RecipeDto:
    id: int = None
    url: str = None
    title: str = None
    total_time: str = None
    image_url: str = None
    host: str = None
    yields: str = None
    ingredients_list: list[str] = field(default_factory=list)
    instructions_list: list[str] = field(default_factory=list)

Base = declarative_base()
class Recipe(Base, object):
    __tablename__ = 'recipe'
    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(String(1000), unique=True)
    title = Column(String(1000))
    total_time = Column(String(1000))
    image_url = Column(String(1000))
    host = Column(String(1000))
    yields = Column(String(1000))
    notes = Column(String(5000))
    ingredients_list = Column(MutableList.as_mutable(PickleType))
    instructions_list = Column(MutableList.as_mutable(PickleType))
    

    def to_dto(self) -> RecipeDto:
        return RecipeDto(self.id, self.url, self.title, self.total_time, self.image_url, 
            self.host, self.yields, self.notes, self.ingredients_list, self.instructions_list) 
        
    def update(self, inc):
        self.id = inc.id
        if inc.url is not None:
            self.url = inc.url
        if inc.title is not None:
            self.title = inc.title
        if inc.total_time is not None:
            self.total_time = inc.total_time
        if inc.image_url is not None:
            self.image_url = inc.image_url
        if inc.host is not None:
            self.host = inc.host
        if inc.yields is not None:
            self.yields = inc.yields
        if inc.notes is not None:
            self.notes = inc.notes
        if inc.ingredients_list is not None and len(inc.ingredients_list) is not 0:
            self.ingredients_list = inc.ingredients_list
        if inc.instructions_list is not None and len(inc.instructions_list) is not 0:
            self.instructions_list = inc.instructions_list
    
    @staticmethod
    def from_dto(dto: RecipeDto):
        out = Recipe()
        out.id = dto.id
        out.url = dto.url
        out.title = dto.title
        out.total_time = dto.total_time
        out.image_url = dto.image_url
        out.host = dto.host
        out.yields = dto.yields
        out.notes = dto.notes
        out.ingredients_list = dto.ingredients_list
        out.instructions_list = dto.instructions_list
        return out



class RecipeUrl(BaseModel):
    recipe_url: str


