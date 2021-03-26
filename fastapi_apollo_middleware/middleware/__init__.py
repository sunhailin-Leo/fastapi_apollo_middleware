import json
import asyncio
import hashlib
from http import HTTPStatus
from asyncio.tasks import Task
from typing import Dict, List, Union

import requests
from starlette.types import ASGIApp
from starlette.requests import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from fastapi_apollo_middleware.middleware.decorator import cached_method
from fastapi_apollo_middleware.middleware.exceptions import GetApolloConfigurationFailure


__all__ = ["FastAPIApolloMiddleware", "startup_apollo_cycle_task"]


class _SimpleApolloClient(object):
    def __init__(
        self,
        app_id: str,
        env: str = "DEV",
        cluster: str = "default",
        config_server_url: str = "http://localhost:8080",
        cycle_time: int = 30,
        request_timeout: int = 6,
    ):
        """
        简化版的 Apollo Client For Python / Simplify Apollo Client For Python

        :param app_id: Apollo 上的项目 AppId / AppId on Apollo Project
        :param env: 环境值，默认是 'DEV' / Apollo Environment Variable, default is "DEV"
        :param cluster: 集群名称，默认是 'default' / Apollo Cluster Name, default is "default"
        :param config_server_url: Apollo Config Server, default is http://localhost:8080
        :param cycle_time: 循环时间 / Cycle time for background task to update config.
            Suggestion:
                In production env, we suggest use longer time to
                get config with cycle background task.

        :param request_timeout: 请求超时时间 / Timeout arguments for request to config server.
        """
        self.app_id = app_id
        self.env = env
        self.cluster = cluster
        self.config_server_url = config_server_url
        self._cycle_time = cycle_time
        self._request_timeout = request_timeout

    @staticmethod
    def _cache_md5(data: str) -> str:
        m = hashlib.md5(data.encode("utf-8"))
        return m.hexdigest()

    def _compare_json_md5(
        self,
        old_json: Union[str, Dict],
        new_json: Union[str, Dict],
    ) -> bool:
        old = self._cache_md5(data=json.dumps(old_json, ensure_ascii=False))
        new = self._cache_md5(data=json.dumps(new_json, ensure_ascii=False))
        return new != old

    def _get_config_by_cache_url(self, namespace: str) -> str:
        # f"/configs/{self.app_id}/{self.cluster}/{namespace}"
        return (
            f"{self.config_server_url}"
            f"/configfiles/json/{self.app_id}"
            f"/{self.cluster}/{namespace}"
        )

    def _update_config(self, namespace: str, config_result: Dict, current_config: Dict):
        cache_result = getattr(self, "_cache_result", None)
        if cache_result is None:
            current_config.update({namespace: config_result})
        else:
            _d = cache_result.get(namespace)
            if _d is not None:
                # Compare json hash with previous version
                if self._compare_json_md5(old_json=_d, new_json=config_result):
                    cache_result.update({namespace: config_result})
            else:
                # TODO 暂时不解决(原因: Apollo 没有配置数据)
                return

    @cached_method
    def _get_config_by_namespace(self, namespaces: List) -> Dict:
        config: Dict = {}
        for namespace in namespaces:
            config_url = self._get_config_by_cache_url(namespace=namespace)
            resp = requests.get(
                url=config_url, params=None, timeout=self._request_timeout,
            )
            if resp.status_code == HTTPStatus.OK:
                try:
                    data = resp.json()
                    self._update_config(
                        namespace=namespace, config_result=data, current_config=config,
                    )
                except Exception:
                    raise GetApolloConfigurationFailure()
            elif resp.status_code in [
                HTTPStatus.NOT_FOUND, HTTPStatus.INTERNAL_SERVER_ERROR
            ]:
                raise GetApolloConfigurationFailure()
            else:
                config.update({namespace: None})
        return config

    def get_value(self):
        return getattr(self, "_cache_result", None)

    async def start_async_task(self, namespaces: List) -> Task:
        r = getattr(self, "_cache_result", None)
        if r is None or len(r) == 0:
            self._get_config_by_namespace(namespaces=namespaces)

        # Use asyncio task to get config with schedule
        loop = asyncio.get_event_loop()
        asyncio.set_event_loop(loop=loop)
        task = asyncio.create_task(self._async_listener(namespaces=namespaces))
        return task

    async def _async_listener(self, namespaces: List) -> None:
        while True:
            await asyncio.sleep(self._cycle_time)
            self._get_config_by_namespace(namespaces=namespaces)


# client
_client: _SimpleApolloClient


class FastAPIApolloMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: ASGIApp,
        *,
        apollo_app_id: str,
        apollo_env: str = "DEV",
        apollo_cluster_name: str = "default",
        apollo_config_server: str = "http://localhost:8080",
        config_cycle_time: int = 30,
        config_request_timeout: int = 6,
    ):
        self._app = app

        # initialize apollo client
        self._apollo_client = _SimpleApolloClient(
            app_id=apollo_app_id,
            env=apollo_env,
            cluster=apollo_cluster_name,
            config_server_url=apollo_config_server,
            cycle_time=config_cycle_time,
            request_timeout=config_request_timeout,
        )
        global _client
        _client = self._apollo_client

        # Super
        super().__init__(app=self._app)

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        # Use request.scope to set data in middleware
        request.scope.setdefault("apollo", self._apollo_client.get_value())
        return await call_next(request)


# It must use in @app.on_event("startup")
async def startup_apollo_cycle_task(namespaces: List) -> Task:
    return await _client.start_async_task(namespaces=namespaces)
