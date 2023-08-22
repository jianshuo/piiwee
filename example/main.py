import json
import logging
import os
from typing import Annotated, Union

import uvicorn
from fastapi import Body, Depends, FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from models import BaseModel
from peewee import ModelSelect
from starlette.datastructures import QueryParams

logging.basicConfig(level=os.environ.get("LOGLEVEL", "INFO").upper())


class IndentJSONResponse(JSONResponse):
    def render(self, content):
        return json.dumps(content, indent=4, ensure_ascii=False).encode("utf-8")


def get_resources():
    return {sub._meta.name: sub for sub in BaseModel.__subclasses__()}


def get_resource(kind: str):
    if kind in get_resources():
        return get_resources()[kind]
    raise NotImplementedError(f"Resource [{kind}] not supported yet")


def get_instance(kind: str, id: Union[int, str]):
    return get_resource(kind).get_by_id(id)


def with_psf(select: ModelSelect, query: QueryParams, user_id: int):
    page = int(query.get("page", 1))
    size = int(query.get("size", 5))
    if page > 100 or size > 100:
        raise ValueError("page or size must be less than 100")

    return {
        "data": [
            o.to_dict(user_id, only=query.get("fields", "").split(","))
            for o in select.where(query.get("filter"))
            .order_by(query.get("sort"))
            .paginate(page, size)
        ],
        "pagination": {"page": page, "size": size},
    }


Resource = Annotated[type(BaseModel), Depends(get_resource)]
Instance = Annotated[BaseModel, Depends(get_instance)]

app = FastAPI(default_response_class=IndentJSONResponse)


@app.exception_handler(Exception)
async def _(request: Request, exc: Exception):
    return IndentJSONResponse({"error": str(exc), "type": exc.__class__.__name__})


@app.get("/users/me{path:path}")
def _(request: Request, user: int = 0):
    url = str(request.url).replace("/me", f"/{user}")
    return RedirectResponse(url)


@app.get("/{kind}/{id}")
def _(ins: Instance, user: int = 0):
    return ins.to_dict(user)


@app.get("/{kind}")
def _(res: Resource, request: Request, user: int = 0):
    return with_psf(res.select(), request.query_params, user)


@app.get("/{kind}/{id}/{edge}")
def _(ins: Instance, edge: str, request: Request, user: int = 0):
    return with_psf(getattr(ins, edge), request.query_params, user)


@app.post("/{kind}/{id}")
def _(ins: Instance, user: int = 0, props: dict = Body()):
    return ins.from_dict(props, user).save()


@app.delete("/{kind}/{id}")
def _(ins: Instance, user: int = 0):
    return ins.from_dict({"deleted", True}, user).save()


if __name__ == "__main__":
    uvicorn.run(app="main:app", host="0.0.0.0", reload=True)
