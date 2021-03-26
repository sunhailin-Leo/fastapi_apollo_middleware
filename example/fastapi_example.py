import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
from starlette.requests import Request

from fastapi_apollo_middleware.middleware import (
    FastAPIApolloMiddleware,
    startup_apollo_cycle_task,
)

# Init server context
app = FastAPI()
app.add_middleware(
    FastAPIApolloMiddleware,
    apollo_app_id="fastapi-test",
    apollo_env="UAT",
    apollo_cluster_name="default",
    apollo_config_server="http://127.0.0.1:8080",
    config_cycle_time=15
)


class RequestItem(BaseModel):
    waybill_id: str = ""


@app.on_event("startup")
async def startup():
    await startup_apollo_cycle_task(namespaces=["application"])


@app.get("/health_check")
async def api_test(request: Request):
    # Use request.scope to get data from middleware
    config = request.scope.get("apollo")
    print(config)
    return {"msg": "ok"}


if __name__ == '__main__':
    uvicorn.run(
        app=app,
        host="0.0.0.0",
        port=12580,
        workers=1,
        reload=False,
        debug=False,
    )
