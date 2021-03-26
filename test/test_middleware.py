import time
import pytest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from fastapi_apollo_middleware.middleware import (
    FastAPIApolloMiddleware,
    startup_apollo_cycle_task,
)


@pytest.fixture(name="test_middleware")
def test_middleware():

    def _test_middleware(**profiler_kwargs):
        app = FastAPI()
        app.add_middleware(
            FastAPIApolloMiddleware,
            apollo_app_id="test-fastapi",
        )

        @app.on_event("startup")
        async def startup():
            await startup_apollo_cycle_task(namespaces=["application"])

        @app.get("/test")
        async def normal_request(request):
            return {"retMsg": "Normal Request test Success!"}

        return app
    return _test_middleware


class TestProfilerMiddleware:
    @pytest.fixture
    def client(self, test_middleware):
        return TestClient(test_middleware())

    def test_apollo(self, client):
        # request
        request_path = "/test"
        client.get(request_path)
