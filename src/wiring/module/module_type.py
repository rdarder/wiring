from __future__ import annotations

import inspect
from typing import Any, Optional, TYPE_CHECKING, Iterator

from wiring.module.errors import (
    DefaultProviderIsNotAProvider,
    CannotUseBaseProviderAsDefaultProvider,
    DefaultProviderProvidesToAnotherModule,
    InvalidModuleResourceAnnotationInModule,
    InvalidAttributeAnnotationInModule,
    CannotUseExistingModuleResource,
    ModulesCannotBeInstantiated,
    InvalidPrivateResourceAnnotationInModule,
    InvalidOverridingResourceAnnotationInModule,
)
from wiring.resource import ModuleResource, PrivateResource, OverridingResource

if TYPE_CHECKING:
    from wiring.provider.provider_type import ProviderType


class CannotDefinePrivateResourceInModule(Exception):
    def __init__(self, module: ModuleType, name: str, t: type):
        self.module = module
        self.name = name
        self.type = t


class CannotDefineOverridingResourceInModule(Exception):
    def __init__(self, module: ModuleType, name: str, t: type):
        self.module = module
        self.name = name
        self.type = t


class ModuleType(type):
    _resources_by_name: dict[str, ModuleResource[Any]]
    _resources: set[ModuleResource[Any]]
    _default_provider: Optional[ProviderType]

    def __init__(self, name: str, bases: tuple[type, ...], dct: dict[str, Any]):
        type.__init__(self, name, bases, dct)
        self._resources = set()
        self._resources_by_name = {}
        self._collect_resources(dct, inspect.get_annotations(self))
        self._default_provider = None

    def __call__(self, *args: Any, **kwargs: Any) -> None:
        raise ModulesCannotBeInstantiated(self)

    def _collect_resources(
        self, dct: dict[str, Any], annotations: dict[str, Any]
    ) -> None:
        for name, candidate in dct.items():
            if name.startswith("_"):
                continue
            candidate_type = type(candidate)
            if candidate_type is ModuleResource:
                if candidate.is_bound:
                    raise CannotUseExistingModuleResource(self, name, candidate)
                candidate.bind(name=name, module=self)
                self._add_resource(candidate)
            elif candidate_type is PrivateResource:
                raise CannotDefinePrivateResourceInModule(self, name, candidate.type)
            elif candidate_type is OverridingResource:
                raise CannotDefineOverridingResourceInModule(self, name, candidate.type)
            elif isinstance(candidate, type):
                resource: ModuleResource[Any] = ModuleResource.make_bound(
                    t=candidate, name=name, module=self  # pyright: ignore
                )
                self._add_resource(resource)

        for name, annotation in annotations.items():
            if name.startswith("_") or name in self._resources_by_name:
                continue
            t = type(annotation)
            if t is ModuleResource:
                raise InvalidModuleResourceAnnotationInModule(self, name, annotation)
            elif t is PrivateResource:
                raise InvalidPrivateResourceAnnotationInModule(self, name, annotation)
            elif t is OverridingResource:
                raise InvalidOverridingResourceAnnotationInModule(
                    self, name, annotation
                )
            elif isinstance(annotation, type):
                raise InvalidAttributeAnnotationInModule(self, name, annotation)

    def _add_resource(self, resource: ModuleResource[Any]) -> None:
        self._resources.add(resource)
        self._resources_by_name[resource.name] = resource
        setattr(self, resource.name, resource)

    def __contains__(self, item: str | ModuleResource[Any]) -> bool:
        if type(item) is ModuleResource:
            return item in self._resources
        elif type(item) is str:
            return item in self._resources_by_name
        else:
            raise TypeError()

    def __iter__(self) -> Iterator[ModuleResource[Any]]:
        return iter(self._resources)

    def __getitem__(self, name: str) -> ModuleResource[Any]:
        return self._resources_by_name[name]

    @property
    def default_provider(self) -> Optional[ProviderType]:
        return self._default_provider

    @default_provider.setter
    def default_provider(self, provider: ProviderType) -> None:
        from wiring.provider.provider_type import ProviderType
        from wiring.provider.provider import Provider

        if not isinstance(provider, ProviderType):
            raise DefaultProviderIsNotAProvider(self, provider)
        if provider is Provider:
            raise CannotUseBaseProviderAsDefaultProvider(self)
        if provider.module is not self:
            raise DefaultProviderProvidesToAnotherModule(self, provider)
        self._default_provider = provider
