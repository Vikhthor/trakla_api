from fastapi import FastAPI, Query, Path, Depends, HTTPException, status
from pydantic import BaseModel, AfterValidator, Field
from enum import Enum
from typing import Annotated, Literal
import random
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from .config import get_settings
from .routers import customer_groups, customers, maintenance_schedules, order_items, organizations, service_requests, users, vendor_groups, work_orders
from .routers import contacts, asset_types, analytics, vendors, technicians

from .db import create_db_and_tables

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield

app = FastAPI(root_path="/api", lifespan=lifespan)

# @app.on_event("startup")
# def on_startup():
#     create_db_and_tables()

settings = get_settings()
allow_cors = settings.allow_cors or ["http://localhost:3000"]
if allow_cors and isinstance(allow_cors, str):
    allow_cors = allow_cors.split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_cors,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(customers.router)
app.include_router(customer_groups.router)
app.include_router(organizations.router)
app.include_router(users.router)
app.include_router(order_items.router)
app.include_router(service_requests.router)
app.include_router(work_orders.router)
app.include_router(maintenance_schedules.router)
app.include_router(vendors.router)
app.include_router(vendor_groups.router)
app.include_router(contacts.router)
app.include_router(technicians.router)
app.include_router(asset_types.router)
app.include_router(analytics.router)


############## Mock Endpoints ##################

# class FilterParams(BaseModel):
#     model_config = {"extra": "forbid"} # optionally restrict the query parameters that you want to receive. Here, if a client tries to send some extra data in the query parameters, they will receive an error response.
#     limit: int = Field(100, gt=0, le=100)
#     offset: int = Field(0, ge=0)
#     order_by: Literal["created_at", "updated_at"] = "created_at"
#     tags: list[str] = []

# class Item(BaseModel):
#     name: str
#     price: float
#     tax: float
#     is_offer: bool | None = None

# class ModelName(str, Enum):
#     alexnet = "alexnet"
#     resnet = "resnet"
#     lenet = "lenet"

# def check_valid_id(id: str):
#     if not id.startswith(("isbn-", "imdb-")):
#         raise ValueError('Invalid ID format, it must start with "isbn-" or "imdb-"')
#     return id

# @app.get("/")
# def read_root():
#     return {"Hello": "World"}


# # @app.get("/items/{item_id}")
# # def read_item(item_id: int, q: str | None = None):
# #     # When you declare other function parameters that are not part of the path parameters in a get operation ( q in this case), they are automatically interpreted as "query" parameters.
# #     return {"item_id": item_id, "q": q}

# @app.get("/items/{item_id}")
# async def read_item(
#     item_id: Annotated[int, Path(title="The ID of the item to get")],
#     q: Annotated[str | None, Query(alias="item-query")] = None,
# ):
#     """
#         Path validation can also be used without Annotated. e.g
#         async def read_items(item_id: int = Path(title="The ID of the item to get"),...)
#     """
#     results = {"item_id": item_id}
#     if q:
#         results.update({"q": q})
#     return results

# # NB: A path parameter is always required as it has to be part of the path. Even if you declared it with None or set a default value, it would not affect anything, it would still be always required.

# # Pass *, as the first parameter of the function. 
# # Python won't do anything with that *, but it will know that all the following parameters should be called as keyword arguments (key-value pairs), also known as kwargs. Even if they don't have a default value.
# # e.g: async def read_items(*, item_id: int = Path(title="The ID of the item to get"), q: str):

# @app.post("/items/")
# async def create_item(item: Item):
#     """
#     FastAPI will recognize that the function parameters that match path parameters should be taken from the path, 
#     and that function parameters that are declared to be Pydantic models should be taken from the request body
#     """
#     item_dict = item.model_dump()
#     if item.tax is not None:
#         price_with_tax = item.price + item.tax
#         item_dict.update({"price_with_tax": price_with_tax})
#     return item_dict

# @app.put("/items/{item_id}")
# async def update_item(item_id: int, item: Item, q: str | None = None):
#     """
#     You can also declare body, path and query parameters, all at the same time.
#     If the parameter is also declared in the path, it will be used as a path parameter.
#     If the parameter is of a singular type (like int, float, str, bool, etc) it will be interpreted as a query parameter.
#     If the parameter is declared to be of the type of a Pydantic model, it will be interpreted as a request body.
#     """
#     result = {"item_id": item_id, **item.model_dump()}
#     if q:
#         result.update({"q": q})
#     return result

# """
# NB: FastAPI will know that the value of q is not required because of the default value = None.
# The str | None is not used by FastAPI to determine that the value is not required, it will know it's not required because it has a default value of = None.
# But adding the type annotations will allow your editor to give you better support and detect errors.
# """

# data = {
#     "isbn-9781529046137": "The Hitchhiker's Guide to the Galaxy",
#     "imdb-tt0371724": "The Hitchhiker's Guide to the Galaxy",
#     "isbn-9781439512982": "Isaac Asimov: The Complete Stories, Vol. 2",
# }

# @app.get("/items/")
# async def read_items(
#     q: Annotated[str | None, Query(max_length=50)] = None,
#     id: Annotated[str | None, AfterValidator(check_valid_id)] = None
# ):
#     """
#     Query validation can also be used without Annotated. e.g
#     async def read_items(q: str | None = Query(default=None, max_length=50)):
#     It enforces that even though q is optional, whenever it is provided, its length doesn't exceed 50 characters.
#     """
#     results = {"items": [{"item_id": "Foo"}, {"item_id": "Bar"}]}
#     if q:
#         results.update({"q": q})
#     elif id:
#         item = data.get(id)
#         results.update({"id": id, "name": item})
#     else:
#         id, item = random.choice(list(data.items()))
#         results.update({"id": id, "name": item})
#     return results

# """
# NB: Here we are using Query() because this is a query parameter. Others like Path(), Body(), Header(), and Cookie(), can also accept the same arguments as Query().
# Other validations include:
# min_length e.g Query(min_length=3, max_length=50)
# pattern (for regex) e.g Query(min_length=3, max_length=50, pattern="^fixedquery$")
# title (will be included in the generated OpenAPI) e.g Query(title="Query string", min_length=3)
# description (will be included in the generated OpenAPI) e.g Query(title="Query string", description="Query string for the items to search in the database that have a good match", min_length=3)
# alias (alias name is what will be used to find the parameter value) e.g Query(alias="item-query")
# deprecated (you want the docs to clearly show it as deprecated) e.g Query(deprecated=True)
# include_in_schema (exclude a query parameter from the generated OpenAPI schema) e.g Query(include_in_schema=False)
# ge (i.e greater than or equal to) e.g Path(title="The ID of the item to get", ge=1)
# gt (i.e greater than) e.g Path(title="The ID of the item to get", gt=0)
# le (i.e less than or equal) e.g Path(title="The ID of the item to get", le=1000)
# lt (i.e less than) e.g Query(gt=0, lt=10.5)

# Query, Path, and others are subclasses of a common Param class.
# All of them share the same parameters for additional validation and metadata.

# When you define a query parameter explicitly with Query you can also declare it to receive a list of values. i.e
# async def read_items(q: Annotated[list[str] | None, Query()] = None):
# ...
# Then, with a URL like:
# http://localhost:8000/items/?q=foo&q=bar
# To declare a query parameter with a type of list, like in the example above, you need to explicitly use Query, otherwise it would be interpreted as a request body as list[str] is treated as a model.
# You can also define a default list of values if none are provided:
# async def read_items(q: Annotated[list[str], Query()] = ["foo", "bar"]):
# or
# async def read_items(q: Annotated[list[str], Query()] = []):
# You can also use list directly instead of list[str]: e.g
# async def read_items(q: Annotated[list, Query()] = []):
# But FastAPI won't check and validate the contents of the list.

# """

# @app.get("/items_2/")
# async def read_items_2(filter_query: Annotated[FilterParams, Query()]): # Use query model
#     return filter_query

# @app.get("/models/{model_name}")
# async def get_model(model_name: ModelName):
#     if model_name is ModelName.alexnet:
#         return {"model_name": model_name, "message": "Deep Learning FTW!"}

#     if model_name.value == "lenet":
#         # You could also access the value "lenet" with ModelName.lenet.value.
#         return {"model_name": model_name, "message": "LeCNN all the images"}

#     return {"model_name": model_name, "message": "Have some residuals"}
#     # NB: model_name will be converted to their corresponding values (strings in this case) before returning them to the client

# @app.get("/files/{file_path:path}")
# async def read_file(file_path: str):
#     """
#         the name of the parameter is file_path, and the last part, :path, tells it that the parameter should match any path
#         e.g /home/johndoe/myfile.txt
#     """
#     return {"file_path": file_path}

# @app.get("/users/{user_id}/items/{item_id}")
# async def read_user_item(
#     user_id: int, item_id: str, q: str | None = None, short: bool = False
# ):
#     """Declare multiple path parameters and query parameters at the same time"""
#     item = {"item_id": item_id, "owner_id": user_id}
#     if q:
#         item.update({"q": q})
#     if not short:
#         item.update(
#             {"description": "This is an amazing item that has a long description"}
#         )
#     return item

# @app.get("/items/{item_id}")
# async def read_user_item(item_id: str, needy: str):
#     """ 
#         When you declare a default value for non-path parameters, then it is not required.
#         If you don't want to add a specific value but just make it optional, set the default as None
#         But when you want to make a query parameter required, you can just not declare any default value
#     """
#     item = {"item_id": item_id, "needy": needy}
#     return item