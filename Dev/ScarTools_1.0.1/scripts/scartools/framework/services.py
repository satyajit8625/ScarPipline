"""Callable service registry for UI, batch, and pipeline consumers."""

from __future__ import print_function

from dataclasses import dataclass

from .imports import load_entry_point


@dataclass(frozen=True)
class ServiceDefinition:
    service_id: str
    entry_point: str
    mutates_scene: bool = False
    annotation: str = ""

    def call(self, *args, **kwargs):
        return load_entry_point(self.entry_point)(*args, **kwargs)


class ServiceRegistry:
    def __init__(self):
        self._services = {}

    def register(self, definition):
        if not isinstance(definition, ServiceDefinition):
            raise TypeError("Expected ServiceDefinition.")
        existing = self._services.get(definition.service_id)
        if existing is not None:
            if existing == definition:
                return existing
            raise ValueError("Duplicate ScarTools service: {}".format(definition.service_id))
        self._services[definition.service_id] = definition
        return definition

    def get(self, service_id):
        key = str(service_id)
        service = self._services.get(key)
        if service is None:
            try:
                from ..builtin import register_builtin_services
                register_builtin_services(clear=False)
                service = self._services.get(key)
            except Exception:
                pass
        return service

    def call(self, service_id, *args, **kwargs):
        service = self.get(service_id)
        if service is None:
            raise KeyError("Unknown ScarTools service: {}".format(service_id))
        return service.call(*args, **kwargs)

    def definitions(self):
        return tuple(self._services[key] for key in sorted(self._services))

    def clear(self):
        self._services.clear()


SERVICES = ServiceRegistry()


__all__ = ["SERVICES", "ServiceDefinition", "ServiceRegistry"]
