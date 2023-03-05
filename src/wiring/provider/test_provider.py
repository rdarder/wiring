from typing import TypeAlias, cast, Any
from unittest import TestCase

from wiring.container import Container
from wiring.errors import HelpfulException
from wiring.module import Module
from wiring.provider import Provider
from wiring.provider.errors import (
    MissingProviderMethod,
    ProviderMethodNotCallable,
    ProvidersModuleIsNotAModule,
    CannotProvideBaseModule,
    ProviderMethodMissingReturnTypeAnnotation,
    ProviderMethodReturnTypeMismatch,
    ProviderMethodParameterMissingTypeAnnotation,
    ProviderMethodParameterUnrelatedName,
    ProviderMethodParameterMatchesResourceNameButNotType,
    ProviderMethodParameterInvalidTypeAnnotation,
    ProvidersCannotBeInstantiated,
    InvalidAttributeAnnotationInProvider,
    InvalidPrivateResourceAnnotationInProvider,
    CannotDefinePublicResourceInProvider,
    PrivateResourceCannotOccludeModuleResource,
    InvalidOverridingResourceAnnotationInProvider,
    OverridingResourceIncompatibleType,
    OverridingResourceNameDoesntMatchModuleResource,
    ProviderModuleCantBeChanged,
    InvalidProviderAttributeName,
    ResourceDefinitionCannotReferOtherProvidersResource,
    InvalidModuleResourceAnnotationInProvider,
    CannotDependOnResourceFromAnotherProvider,
    ProvidersDontSupportMultipleInheritance,
    ProviderDeclarationMissingModule,
    BaseProviderProvidesFromADifferentModule,
    ProvidersMustInheritFromProviderClass,
    InvalidProviderAttribute,
    ResourceModuleMismatch,
    UnknownModuleResource,
    UnknownProviderResource,
    ResourceProviderMismatch,
)
from wiring.provider.provider_type import ProviderType
from wiring.resource import (
    ModuleResource,
    Resource,
    PrivateResource,
    OverridingResource,
)
from wiring.utils_for_tests import TestCaseWithOutputFixtures, validate_output


class TestProviderClassBehavior(TestCaseWithOutputFixtures):
    @validate_output
    def test_providers_cannot_be_instantiated(self) -> HelpfulException:
        class SomeModule(Module):
            pass

        class SomeProvider(Provider, module=SomeModule):
            pass

        with self.assertRaises(ProvidersCannotBeInstantiated) as ctx:
            SomeProvider()
        self.assertEqual(ctx.exception.provider, SomeProvider)
        return ctx.exception

    @validate_output
    def test_providers_cannot_be_instantiated_event_if_defining_constructor(
        self,
    ) -> HelpfulException:
        class SomeModule(Module):
            pass

        class SomeProvider(Provider, module=SomeModule):
            def __init__(self) -> None:
                pass

        with self.assertRaises(ProvidersCannotBeInstantiated) as ctx:
            SomeProvider()
        self.assertEqual(ctx.exception.provider, SomeProvider)
        return ctx.exception

    def test_providers_module_cannot_be_manually_set(self) -> None:
        class SomeModule(Module):
            pass

        class AnotherModule(Module):
            pass

        class SomeProvider(Provider, module=SomeModule):
            pass

        with self.assertRaises(ProviderModuleCantBeChanged) as ctx:
            SomeProvider.module = AnotherModule

        self.assertEqual(ctx.exception.provider, SomeProvider)
        self.assertEqual(ctx.exception.assigned_to, AnotherModule)
        self.assertEqual(SomeProvider.module, SomeModule)

    def test_providers_dont_support_multiple_inheritance(self) -> None:
        class SomeBaseClass:
            pass

        class SomeModule(Module):
            pass

        with self.assertRaises(ProvidersDontSupportMultipleInheritance) as ctx:

            class SomeProvider(Provider, SomeBaseClass, module=SomeModule):
                pass

        self.assertEqual(ctx.exception.provider.__name__, "SomeProvider")
        self.assertEqual(ctx.exception.bases, (Provider, SomeBaseClass))

    def test_providers_must_state_which_module_it_provides_for_as_class_argument(
        self,
    ) -> None:
        with self.assertRaises(ProviderDeclarationMissingModule) as ctx:

            class SomeProvider(Provider):
                pass

        self.assertEqual(ctx.exception.provider.__name__, "SomeProvider")

    def test_providers_must_inherit_from_provider_or_subclass(self) -> None:
        class SomeModule(Module):
            pass

        class SomeClass:
            def __init_subclass__(cls, **kwargs: Any) -> None:
                pass

        with self.assertRaises(ProvidersMustInheritFromProviderClass) as ctx:

            class SomeProvider(SomeClass, metaclass=ProviderType, module=SomeModule):
                pass

        self.assertEqual(ctx.exception.provider.__name__, "SomeProvider")
        self.assertEqual(ctx.exception.inherits_from, SomeClass)

    def test_provider_attributes_can_only_be_resources_or_provider_methods(
        self,
    ) -> None:
        class SomeModule(Module):
            pass

        with self.assertRaises(InvalidProviderAttribute) as ctx:

            class SomeProvider(Provider, module=SomeModule):
                a = 10

        self.assertEqual(ctx.exception.provider.__name__, "SomeProvider")
        self.assertEqual(ctx.exception.name, "a")
        self.assertEqual(ctx.exception.value, 10)


class TestProviderCollectingProviderMethods(TestCaseWithOutputFixtures):
    def test_provider_collects_provider_methods(self) -> None:
        class SomeModule(Module):
            a = int

        class SomeProvider(Provider, module=SomeModule):
            def provide_a(self) -> int:
                return 10

        provider_method = SomeProvider[SomeModule.a]  # type: ignore
        self.assertIs(provider_method.provider, SomeProvider)
        self.assertIs(provider_method.method, SomeProvider.provide_a)
        self.assertIs(provider_method.resource, SomeModule.a)

    @validate_output
    def test_missing_provider_method(self) -> HelpfulException:
        class SomeModule(Module):
            a = int

        with self.assertRaises(MissingProviderMethod) as ctx:

            class SomeProvider(Provider, module=SomeModule):
                pass

        self.assertEqual(ctx.exception.provider.__name__, "SomeProvider")
        self.assertEqual(ctx.exception.resource, SomeModule.a)
        return ctx.exception

    @validate_output
    def test_provider_method_not_callable(self) -> HelpfulException:
        class SomeModule(Module):
            a = int

        with self.assertRaises(ProviderMethodNotCallable) as ctx:

            class SomeProvider(Provider, module=SomeModule):
                provide_a = 10

        self.assertEqual(ctx.exception.provider.__name__, "SomeProvider")
        self.assertEqual(ctx.exception.resource, SomeModule.a)
        return ctx.exception

    @validate_output
    def test_provider_method_lookup_unknown_module_resource(self) -> HelpfulException:
        class SomeModule(Module):
            pass

        class SomeProvider(Provider, module=SomeModule):
            pass

        fake_resource = ModuleResource.make_bound(
            t=int, name="fake", module=SomeModule  # pyright: ignore
        )
        with self.assertRaises(UnknownModuleResource) as ctx:
            SomeProvider[fake_resource]

        self.assertEqual(ctx.exception.provider, SomeProvider)
        self.assertEqual(ctx.exception.resource, fake_resource)
        return ctx.exception

    @validate_output
    def test_provider_method_lookup_module_mismatch(self) -> HelpfulException:
        class SomeModule(Module):
            pass

        class SomeProvider(Provider, module=SomeModule):
            a = int

            def provide_a(self) -> int:
                return 10

        class AnotherModule(Module):
            a = int

        with self.assertRaises(ResourceModuleMismatch) as ctx:
            SomeProvider[AnotherModule.a]  # type: ignore

        self.assertEqual(ctx.exception.provider, SomeProvider)
        self.assertEqual(ctx.exception.resource, AnotherModule.a)
        return ctx.exception

    @validate_output
    def test_provider_method_lookup_unknown_provider_resource(self) -> HelpfulException:
        class SomeModule(Module):
            pass

        class SomeProvider(Provider, module=SomeModule):
            pass

        fake_resource = PrivateResource.make_bound(
            t=int, name="fake", provider=SomeProvider  # pyright: ignore
        )
        with self.assertRaises(UnknownProviderResource) as ctx:
            SomeProvider[fake_resource]

        self.assertEqual(ctx.exception.provider, SomeProvider)
        self.assertEqual(ctx.exception.resource, fake_resource)
        return ctx.exception

    @validate_output
    def test_provider_method_lookup_provider_mismatch(self) -> HelpfulException:
        class SomeModule(Module):
            pass

        class SomeProvider(Provider, module=SomeModule):
            a = int

            def provide_a(self) -> int:
                return 10

        class AnotherProvider(Provider, module=SomeModule):
            a = int

            def provide_a(self) -> int:
                return 10

        with self.assertRaises(ResourceProviderMismatch) as ctx:
            SomeProvider[AnotherProvider.a]  # type: ignore

        self.assertEqual(ctx.exception.provider, SomeProvider)
        self.assertEqual(ctx.exception.resource, AnotherProvider.a)
        return ctx.exception

    def test_provider_collects_methods_for_private_provider_resources(self) -> None:
        class SomeModule(Module):
            pass

        class SomeProvider(Provider, module=SomeModule):
            a: TypeAlias = int

            def provide_a(self) -> int:
                return 10

        self.assertIsInstance(SomeProvider.a, PrivateResource)
        methods = list(SomeProvider)
        self.assertEqual(len(methods), 1)
        method = methods[0]
        self.assertEqual(method.provider, SomeProvider)
        self.assertEqual(method.method, SomeProvider.provide_a)
        self.assertEqual(method.resource, SomeProvider.a)
        self.assertEqual(method.dependencies, {})

    @validate_output
    def test_missing_provider_method_for_private_provider_resource(
        self,
    ) -> HelpfulException:
        class SomeModule(Module):
            pass

        with self.assertRaises(MissingProviderMethod) as ctx:

            class SomeProvider(Provider, module=SomeModule):
                a: TypeAlias = int

        self.assertEqual(ctx.exception.provider.__name__, "SomeProvider")
        resource = ctx.exception.resource
        self.assertIsInstance(resource, PrivateResource)
        self.assertEqual(resource.name, "a")
        self.assertEqual(resource.type, int)
        return ctx.exception

    @validate_output
    def test_missing_provider_method_for_overriding_provider_resource(
        self,
    ) -> HelpfulException:
        class BaseClass:
            pass

        class ConcreteClass(BaseClass):
            pass

        class SomeModule(Module):
            a: TypeAlias = BaseClass

        with self.assertRaises(MissingProviderMethod) as ctx:

            class SomeProvider(Provider, module=SomeModule):
                a: TypeAlias = ConcreteClass

        self.assertEqual(ctx.exception.provider.__name__, "SomeProvider")
        resource = ctx.exception.resource
        self.assertIsInstance(resource, OverridingResource)
        self.assertEqual(resource.name, "a")
        self.assertEqual(resource.type, ConcreteClass)
        return ctx.exception

    def test_provider_collects_provider_method_when_overriden_resource_is_present(
        self,
    ) -> None:
        """
        Also, the provider method is bound to the _module_ resource, not the overriden one.
        The container will have to dereference overridden resources instead of trying to
        provide them directly.
        """

        class SomeBaseClass:
            pass

        class SomeConcreteClass(SomeBaseClass):
            pass

        class SomeModule(Module):
            a = Resource(SomeBaseClass)

        class SomeProvider(Provider, module=SomeModule):
            a = Resource(SomeConcreteClass, override=True)

            def provide_a(self) -> SomeConcreteClass:
                return SomeConcreteClass()

        self.assertIsInstance(SomeProvider.a, OverridingResource)
        methods = list(SomeProvider)
        self.assertEqual(len(methods), 1)
        method = methods[0]
        self.assertEqual(method.provider, SomeProvider)
        self.assertEqual(method.method, SomeProvider.provide_a)
        self.assertEqual(method.resource, SomeModule.a)
        self.assertEqual(method.dependencies, {})


class TestProviderModuleAnnotation(TestCaseWithOutputFixtures):
    @validate_output
    def test_invalid_provider_module_annotation(self) -> HelpfulException:
        class SomeClass:
            pass

        with self.assertRaises(ProvidersModuleIsNotAModule) as ctx:

            class SomeProvider(Provider, module=SomeClass):  # pyright: ignore
                pass

        self.assertEqual(ctx.exception.provider.__name__, "SomeProvider")
        self.assertEqual(ctx.exception.invalid_module, SomeClass)
        return ctx.exception

    @validate_output
    def test_invalid_provider_module_annotation_not_even_a_class(
        self,
    ) -> HelpfulException:
        with self.assertRaises(ProvidersModuleIsNotAModule) as ctx:

            class SomeProvider(Provider, module=10):  # pyright: ignore
                pass

        self.assertEqual(ctx.exception.provider.__name__, "SomeProvider")
        self.assertEqual(ctx.exception.invalid_module, 10)
        return ctx.exception

    @validate_output
    def test_cannot_provide_base_module(self) -> HelpfulException:
        with self.assertRaises(CannotProvideBaseModule) as ctx:

            class SomeProvider(Provider, module=Module):
                pass

        self.assertEqual(ctx.exception.provider.__name__, "SomeProvider")
        return ctx.exception

    def test_empty_provider_provides_an_empty_module(self) -> None:
        class SomeModule(Module):
            pass

        class SomeProvider(Provider, module=SomeModule):
            pass

        self.assertEqual(SomeProvider.module, SomeModule)

    def test_provider_cannot_have_module_resource_annotated_attributes(self) -> None:
        class SomeModule(Module):
            pass

        with self.assertRaises(InvalidModuleResourceAnnotationInProvider) as ctx:

            class SomeProvider(Provider, module=SomeModule):
                a: Resource(int)  # type: ignore

        self.assertEqual(ctx.exception.provider.__name__, "SomeProvider")
        self.assertEqual(ctx.exception.name, "a")
        self.assertEqual(ctx.exception.resource.type, int)
        self.assertIsInstance(ctx.exception.resource, ModuleResource)

    def test_provider_method_cannot_depend_on_another_providers_resource(self) -> None:
        class SomeModule(Module):
            a = int

        class SomeProvider(Provider, module=SomeModule):
            b: TypeAlias = int

            def provide_a(self, b: int) -> int:
                return b + 1

            def provide_b(self) -> int:
                return 10

        class AnotherModule(Module):
            c = int

        with self.assertRaises(CannotDependOnResourceFromAnotherProvider) as ctx:

            class AnotherProvider(Provider, module=AnotherModule):
                def provide_c(self, b: SomeProvider.b) -> int:
                    return b + 1

        self.assertEqual(ctx.exception.parameter_resource, SomeProvider.b)
        self.assertEqual(ctx.exception.parameter_name, "b")
        self.assertEqual(ctx.exception.target, AnotherModule.c)


class TestProviderMethodFromSignature(TestCaseWithOutputFixtures):
    @validate_output
    def test_provider_method_must_have_return_type_annotation(self) -> HelpfulException:
        class SomeModule(Module):
            a = int

        with self.assertRaises(ProviderMethodMissingReturnTypeAnnotation) as ctx:

            class SomeProvider(Provider, module=SomeModule):
                def provide_a(self):  # type: ignore
                    return 10

        self.assertEqual(ctx.exception.provider.__name__, "SomeProvider")
        self.assertEqual(ctx.exception.resource, SomeModule.a)
        self.assertEqual(ctx.exception.method.__name__, "provide_a")
        return ctx.exception

    @validate_output
    def test_provider_method_must_have_a_compatible_return_type_annotation(
        self,
    ) -> HelpfulException:
        class SomeModule(Module):
            a = int

        with self.assertRaises(ProviderMethodReturnTypeMismatch) as ctx:

            class SomeProvider(Provider, module=SomeModule):
                def provide_a(self) -> str:
                    return "test"

        self.assertEqual(ctx.exception.provider.__name__, "SomeProvider")
        self.assertEqual(ctx.exception.resource, SomeModule.a)
        self.assertEqual(ctx.exception.method.__name__, "provide_a")
        self.assertEqual(ctx.exception.mismatched_type, str)
        return ctx.exception

    @validate_output
    def test_provider_subclass_must_refine_provider_method_if_refining_overriding_resource(
        self,
    ) -> HelpfulException:
        class SomeClass:
            pass

        class ConcreteClass(SomeClass):
            pass

        class MoreConcreteClass(ConcreteClass):
            pass

        class SomeModule(Module):
            some: TypeAlias = SomeClass

        class SomeProvider(Provider, module=SomeModule):
            some: TypeAlias = ConcreteClass

            def provide_some(self) -> ConcreteClass:
                return ConcreteClass()

        with self.assertRaises(ProviderMethodReturnTypeMismatch) as ctx:

            class AnotherProvider(SomeProvider):
                some: TypeAlias = MoreConcreteClass

        self.assertEqual(ctx.exception.provider.__name__, "AnotherProvider")
        self.assertEqual(ctx.exception.resource.type, MoreConcreteClass)
        self.assertEqual(ctx.exception.mismatched_type, ConcreteClass)
        return ctx.exception

    @validate_output
    def test_provider_subclass_must_refine_provider_method_if_refining_private_resource(
        self,
    ) -> HelpfulException:
        class SomeClass:
            pass

        class ConcreteClass(SomeClass):
            pass

        class SomeModule(Module):
            pass

        class SomeProvider(Provider, module=SomeModule):
            some: TypeAlias = SomeClass

            def provide_some(self) -> SomeClass:
                return SomeClass()

        with self.assertRaises(ProviderMethodReturnTypeMismatch) as ctx:

            class AnotherProvider(SomeProvider):
                some: TypeAlias = ConcreteClass

        self.assertEqual(ctx.exception.provider.__name__, "AnotherProvider")
        self.assertEqual(ctx.exception.resource.type, ConcreteClass)
        self.assertEqual(ctx.exception.mismatched_type, SomeClass)

        return ctx.exception

    def test_provider_method_return_type_can_be_more_specific_type(self) -> None:
        class SomeBaseClass:
            pass

        class SpecificClass(SomeBaseClass):
            pass

        class SomeModule(Module):
            a = SomeBaseClass

        class SomeProvider(Provider, module=SomeModule):
            def provide_a(self) -> SpecificClass:
                return SpecificClass()

        container = Container.empty()
        container.register(SomeModule, SomeProvider)
        container.close_registrations()
        got = container.provide(SomeModule.a)
        self.assertIsInstance(got, SomeBaseClass)
        self.assertIsInstance(got, SpecificClass)

    @validate_output
    def test_provider_method_parameters_must_have_type_annotations(
        self,
    ) -> HelpfulException:
        class SomeModule(Module):
            a = int

        with self.assertRaises(ProviderMethodParameterMissingTypeAnnotation) as ctx:

            class SomeProvider(Provider, module=SomeModule):
                def provide_a(self, b) -> int:  # type: ignore
                    return 10

        self.assertEqual(ctx.exception.provider.__name__, "SomeProvider")
        self.assertEqual(ctx.exception.provides, SomeModule.a)
        self.assertEqual(ctx.exception.method.__name__, "provide_a")
        self.assertEqual(ctx.exception.parameter_name, "b")
        return ctx.exception

    def test_provider_method_parameters_can_refer_to_module_resources(self) -> None:
        class SomeModule(Module):
            a: TypeAlias = int
            b: TypeAlias = int

        class SomeProvider(Provider, module=SomeModule):
            def provide_a(self, b: SomeModule.b) -> int:
                return b + 1

            def provide_b(self) -> int:
                return 10

        provider_method = SomeProvider[SomeModule.a]  # type: ignore
        self.assertEqual(provider_method.dependencies, dict(b=SomeModule.b))

    def test_provider_method_parameters_can_refer_to_own_module_resources_by_name(
        self,
    ) -> None:
        class SomeModule(Module):
            a = int
            b = int

        class SomeProvider(Provider, module=SomeModule):
            def provide_a(self, b: int) -> int:
                return b + 1

            def provide_b(self) -> int:
                return 10

        provider_method = SomeProvider[SomeModule.a]  # type: ignore
        self.assertEqual(provider_method.dependencies, dict(b=SomeModule.b))

    @validate_output
    def test_provider_method_must_either_match_by_resource_or_by_name(
        self,
    ) -> HelpfulException:
        class SomeModule(Module):
            a = int

        with self.assertRaises(ProviderMethodParameterUnrelatedName) as ctx:

            class SomeProvider(Provider, module=SomeModule):
                def provide_a(self, b: int) -> int:
                    return b + 1

        self.assertEqual(ctx.exception.provider.__name__, "SomeProvider")
        self.assertEqual(ctx.exception.provides, SomeModule.a)
        self.assertEqual(ctx.exception.method.__name__, "provide_a")
        self.assertEqual(ctx.exception.parameter_name, "b")
        return ctx.exception

    @validate_output
    def test_provider_method_referring_to_module_resource_must_match_type(
        self,
    ) -> HelpfulException:
        class SomeModule(Module):
            a = int
            b = int

        with self.assertRaises(
            ProviderMethodParameterMatchesResourceNameButNotType
        ) as ctx:

            class SomeProvider(Provider, module=SomeModule):
                def provide_a(self, b: str) -> int:
                    return 10

                def provide_b(self) -> int:
                    return 11

        self.assertEqual(ctx.exception.provider.__name__, "SomeProvider")
        self.assertEqual(ctx.exception.provides, SomeModule.a)
        self.assertEqual(ctx.exception.parameter_name, "b")
        self.assertEqual(ctx.exception.refers_to, SomeModule.b)
        self.assertEqual(ctx.exception.mismatched_type, str)
        return ctx.exception

    def test_provider_method_referring_to_module_resource_can_be_a_superclass(
        self,
    ) -> None:
        class SomeBaseClass:
            pass

        class SomeConcreteClass(SomeBaseClass):
            pass

        class SomeModule(Module):
            a = int
            b = SomeConcreteClass

        class SomeProvider(Provider, module=SomeModule):
            def provide_a(self, b: SomeBaseClass) -> int:
                return 10

            def provide_b(self) -> SomeConcreteClass:
                return SomeConcreteClass()

        provide_a = SomeProvider[SomeModule.a]  # type: ignore
        self.assertEqual(provide_a.dependencies, dict(b=SomeModule.b))

    @validate_output
    def test_provider_method_parameter_annotation_must_be_a_type(
        self,
    ) -> HelpfulException:
        class SomeModule(Module):
            a = int
            b = int

        with self.assertRaises(ProviderMethodParameterInvalidTypeAnnotation) as ctx:

            class SomeProvider(Provider, module=SomeModule):
                def provide_a(self, b: True) -> int:  # type: ignore
                    return 10

                def provide_b(self) -> int:
                    return 11

        self.assertEqual(ctx.exception.provider.__name__, "SomeProvider")
        self.assertEqual(ctx.exception.provides, SomeModule.a)
        self.assertEqual(ctx.exception.method.__name__, "provide_a")
        self.assertEqual(ctx.exception.parameter_name, "b")
        self.assertEqual(ctx.exception.mismatched_type, True)
        return ctx.exception

    @validate_output
    def test_provider_method_for_binding_resource_must_satisfy_more_concrete_type(
        self,
    ) -> HelpfulException:
        class SomeBaseClass:
            pass

        class SomeConcreteClass(SomeBaseClass):
            pass

        class SomeModule(Module):
            a = Resource(SomeBaseClass)

        with self.assertRaises(ProviderMethodReturnTypeMismatch) as ctx:

            class SomeProvider(Provider, module=SomeModule):
                a = Resource(SomeConcreteClass, override=True)

                def provide_a(self) -> SomeBaseClass:
                    # this satisfies the module resource but not the override.
                    return SomeBaseClass()

        self.assertEqual(ctx.exception.resource.type, SomeConcreteClass)
        self.assertEqual(ctx.exception.mismatched_type, SomeBaseClass)
        return ctx.exception


class TestProviderResourcesTypeAliases(TestCase):
    def test_provider_collects_private_resources_from_implicit_type_aliases(
        self,
    ) -> None:
        class SomeModule(Module):
            pass

        class SomeProvider(Provider, module=SomeModule):
            a = int

            def provide_a(self) -> int:
                return 10

        resources = list(SomeProvider.resources)
        self.assertEqual(len(resources), 1)
        resource = cast(PrivateResource[Any], resources[0])
        self.assertIsInstance(resource, PrivateResource)
        self.assertIs(resource, SomeProvider.a)
        self.assertEqual(resource.name, "a")
        self.assertEqual(resource.type, int)
        self.assertEqual(resource.provider, SomeProvider)

    def test_provider_collects_overriding_resources_from_implicit_type_aliases(
        self,
    ) -> None:
        class SomeBaseClass:
            pass

        class SomeConcreteClass(SomeBaseClass):
            pass

        class SomeModule(Module):
            a = SomeBaseClass

        class SomeProvider(Provider, module=SomeModule):
            a = SomeConcreteClass

            def provide_a(self) -> SomeConcreteClass:
                return SomeConcreteClass()

        resources = list(SomeProvider.resources)
        self.assertEqual(len(resources), 1)
        resource = cast(OverridingResource[Any], resources[0])
        self.assertIsInstance(resource, OverridingResource)
        self.assertIs(resource, SomeProvider.a)
        self.assertEqual(resource.name, "a")
        self.assertEqual(resource.type, SomeConcreteClass)
        self.assertEqual(resource.provider, SomeProvider)
        self.assertEqual(resource.overrides, SomeModule.a)

    def test_provider_refuses_overriding_resources_from_type_alias_if_type_not_satisfied(
        self,
    ) -> None:
        class SomeBaseClass:
            pass

        class SomeConcreteClass(SomeBaseClass):
            pass

        class SomeModule(Module):
            a = SomeBaseClass

        with self.assertRaises(OverridingResourceIncompatibleType) as ctx:

            class SomeProvider(Provider, module=SomeModule):
                a = int

                def provide_a(self) -> SomeConcreteClass:
                    return SomeConcreteClass()

        resource = ctx.exception.resource
        self.assertEqual(resource.type, int)
        self.assertEqual(resource.overrides, SomeModule.a)
        self.assertEqual(resource.name, "a")

    def test_provider_collects_resources_from_explicit_type_aliases(self) -> None:
        class SomeModule(Module):
            pass

        class SomeProvider(Provider, module=SomeModule):
            a: TypeAlias = int

            def provide_a(self) -> int:
                return 10

        resources = list(SomeProvider.resources)
        self.assertEqual(len(resources), 1)
        resource = resources[0]
        self.assertIs(resource, SomeProvider.a)
        self.assertEqual(resource.name, "a")
        self.assertEqual(resource.type, int)
        self.assertEqual(resource.provider, SomeProvider)

    def test_provider_refuses_resource_from_type_alias_if_occludes_module_resource(
        self,
    ) -> None:
        class SomeModule(Module):
            a: TypeAlias = int

        with self.assertRaises(PrivateResourceCannotOccludeModuleResource) as ctx:

            class SomeProvider(Provider, module=SomeModule):
                a = Resource(int, private=True)

                def provide_a(self) -> int:
                    return 10

        self.assertEqual(ctx.exception.provider.__name__, "SomeProvider")
        self.assertEqual(ctx.exception.resource.name, "a")
        self.assertEqual(ctx.exception.resource.type, int)


class TestProviderResourcesFromResourceInstances(TestCaseWithOutputFixtures):
    def test_provider_collect_private_resource_instances_and_binds_them(self) -> None:
        class SomeModule(Module):
            pass

        class SomeProvider(Provider, module=SomeModule):
            a = Resource(int, private=True)

            def provide_a(self) -> int:
                return 10

        resources = list(SomeProvider.resources)
        self.assertEqual(len(resources), 1)
        resource = resources[0]
        self.assertIs(resource, SomeProvider.a)
        self.assertEqual(resource.name, "a")
        self.assertEqual(resource.type, int)
        self.assertEqual(resource.provider, SomeProvider)

    def test_provider_collect_overriding_resource_instances_and_binds_them(
        self,
    ) -> None:
        class SomeBaseClass:
            pass

        class SomeConcreteClass(SomeBaseClass):
            pass

        class SomeModule(Module):
            a = Resource(SomeBaseClass)

        class SomeProvider(Provider, module=SomeModule):
            a = Resource(SomeConcreteClass, override=True)

            def provide_a(self) -> SomeConcreteClass:
                return SomeConcreteClass()

        resources = list(SomeProvider.resources)
        self.assertEqual(len(resources), 1)
        resource = cast(OverridingResource[Any], resources[0])
        self.assertIs(resource, SomeProvider.a)
        self.assertEqual(resource.name, "a")
        self.assertEqual(resource.type, SomeConcreteClass)
        self.assertEqual(resource.provider, SomeProvider)
        self.assertEqual(resource.overrides, SomeModule.a)

    def test_provider_fails_on_private_resource_defined_as_another_modules_resource(
        self,
    ) -> None:
        class SomeModule(Module):
            a = Resource(int)

        class AnotherModule(Module):
            pass

        with self.assertRaises(CannotDefinePublicResourceInProvider) as ctx:

            class SomeProvider(Provider, module=AnotherModule):
                b = SomeModule.a

        self.assertEqual(ctx.exception.provider.__name__, "SomeProvider")
        self.assertEqual(ctx.exception.name, "b")
        self.assertEqual(ctx.exception.type, int)

    def test_provider_refuses_definition_of_module_resource_in_it(self) -> None:
        class SomeModule(Module):
            pass

        with self.assertRaises(CannotDefinePublicResourceInProvider) as ctx:

            class SomeProvider(Provider, module=SomeModule):
                a = Resource(int, private=False, override=False)

        self.assertEqual(ctx.exception.provider.__name__, "SomeProvider")
        self.assertEqual(ctx.exception.name, "a")
        self.assertEqual(ctx.exception.type, int)

    def test_provider_refuses_private_resource_if_occludes_module_resource(
        self,
    ) -> None:
        class SomeModule(Module):
            a = Resource(int)

        with self.assertRaises(PrivateResourceCannotOccludeModuleResource) as ctx:

            class SomeProvider(Provider, module=SomeModule):
                a = Resource(int, private=True)

                def provide_a(self) -> int:
                    return 10

        self.assertEqual(ctx.exception.provider.__name__, "SomeProvider")
        self.assertEqual(ctx.exception.resource.name, "a")
        self.assertEqual(ctx.exception.resource.type, int)

    def test_provider_refuses_overriding_resource_if_name_doesnt_match_module_resource(
        self,
    ) -> None:
        class SomeModule(Module):
            pass

        with self.assertRaises(OverridingResourceNameDoesntMatchModuleResource) as ctx:

            class SomeProvider(Provider, module=SomeModule):
                a = Resource(int, override=True)

        self.assertEqual(ctx.exception.name, "a")
        self.assertEqual(ctx.exception.type, int)
        self.assertEqual(ctx.exception.provider.__name__, "SomeProvider")
        self.assertEqual(ctx.exception.module, SomeModule)

    @validate_output
    def test_provider_refuses_resource_declaration_that_uses_another_provider_resource(
        self,
    ) -> HelpfulException:
        class SomeModule(Module):
            pass

        class SomeProvider(Provider, module=SomeModule):
            a = Resource(int, private=True)

            def provide_a(self) -> int:
                return 10

        with self.assertRaises(
            ResourceDefinitionCannotReferOtherProvidersResource
        ) as ctx:

            class AnotherProvider(Provider, module=SomeModule):
                b = SomeProvider.a

        self.assertEqual(ctx.exception.provider.__name__, "AnotherProvider")
        self.assertEqual(ctx.exception.name, "b")
        self.assertEqual(ctx.exception.resource.provider, SomeProvider)
        self.assertEqual(ctx.exception.resource.name, "a")
        return ctx.exception


class TestProviderResourcesFromAnnotations(TestCase):
    def test_provider_fails_on_class_attribute_with_only_type_annotation(self) -> None:
        class SomeModule(Module):
            pass

        with self.assertRaises(InvalidAttributeAnnotationInProvider) as ctx:

            class SomeProvider(Provider, module=SomeModule):
                a: int

        self.assertEqual(ctx.exception.provider.__name__, "SomeProvider")
        self.assertEqual(ctx.exception.name, "a")
        self.assertEqual(ctx.exception.annotation, int)

    def test_provider_fails_on_class_attribute_annotated_with_private_resource_instance(
        self,
    ) -> None:
        class SomeModule(Module):
            pass

        with self.assertRaises(InvalidPrivateResourceAnnotationInProvider) as ctx:

            class SomeProvider(Provider, module=SomeModule):
                a: Resource(int, private=True)  # type: ignore

        self.assertEqual(ctx.exception.provider.__name__, "SomeProvider")
        self.assertEqual(ctx.exception.name, "a")
        self.assertEqual(ctx.exception.resource.type, int)
        self.assertEqual(ctx.exception.resource.is_bound, False)

    def test_provider_fails_on_class_attribute_annotated_with_overriding_resource_instance(
        self,
    ) -> None:
        class SomeBaseClass:
            pass

        class SomeConcreteClass(SomeBaseClass):
            pass

        class SomeModule(Module):
            a = Resource(SomeBaseClass)

        class SomeProvider(Provider, module=SomeModule):
            a = Resource(SomeConcreteClass, override=True)

            def provide_a(self) -> SomeConcreteClass:
                return SomeConcreteClass()

        with self.assertRaises(InvalidOverridingResourceAnnotationInProvider) as ctx:

            class AnotherProvider(Provider, module=SomeModule):
                a: SomeProvider.a  # type: ignore

        self.assertEqual(ctx.exception.provider.__name__, "AnotherProvider")
        self.assertEqual(ctx.exception.name, "a")
        self.assertEqual(ctx.exception.resource.type, SomeConcreteClass)
        self.assertEqual(ctx.exception.resource.is_bound, True)

    def test_provider_fails_on_a_resource_annotated_with_an_external_private_resource(
        self,
    ) -> None:
        class SomeModule(Module):
            pass

        class SomeProvider(Provider, module=SomeModule):
            b = Resource(int, private=True)

            def provide_b(self) -> int:
                return 10

        with self.assertRaises(InvalidPrivateResourceAnnotationInProvider) as ctx:

            class AnotherProvider(Provider, module=SomeModule):
                c: SomeProvider.b  # type: ignore

        self.assertEqual(ctx.exception.provider.__name__, "AnotherProvider")
        self.assertEqual(ctx.exception.name, "c")
        self.assertEqual(ctx.exception.resource.type, int)
        self.assertEqual(ctx.exception.resource.is_bound, True)
        self.assertEqual(ctx.exception.resource.provider, SomeProvider)
        self.assertEqual(ctx.exception.resource.name, "b")


class TestProviderSubclasses(TestCaseWithOutputFixtures):
    def test_a_subclass_of_a_provider_is_also_a_provider_for_the_same_module(
        self,
    ) -> None:
        class SomeModule(Module):
            pass

        class SomeProvider(Provider, module=SomeModule):
            pass

        class AnotherProvider(SomeProvider):
            pass

        self.assertIs(AnotherProvider.module, SomeModule)

    def test_a_provider_subclass_collects_parent_provider_resources(self) -> None:
        class SomeModule(Module):
            pass

        class SomeProvider(Provider, module=SomeModule):
            a: TypeAlias = int

            def provide_a(self) -> int:
                return 10

        class AnotherProvider(SomeProvider):
            pass

        resources = list(AnotherProvider.resources)
        self.assertEqual(len(resources), 1)
        resource = resources[0]
        self.assertEqual(resource.type, int)
        self.assertEqual(resource.name, "a")
        self.assertEqual(resource.module, SomeModule)
        self.assertEqual(resource.provider, AnotherProvider)

    def test_a_provider_subclass_doesnt_mutate_base_provider_resources(self) -> None:
        class SomeModule(Module):
            pass

        class SomeProvider(Provider, module=SomeModule):
            a: TypeAlias = int

            def provide_a(self) -> int:
                return 10

        class AnotherProvider(SomeProvider):
            pass

        resources = list(SomeProvider.resources)
        self.assertEqual(len(resources), 1)
        resource = resources[0]
        self.assertEqual(resource.type, int)
        self.assertEqual(resource.name, "a")
        self.assertEqual(resource.module, SomeModule)
        self.assertEqual(resource.provider, SomeProvider)

    def test_a_provider_subclass_can_add_extra_resources(self) -> None:
        class SomeModule(Module):
            pass

        class SomeProvider(Provider, module=SomeModule):
            a: TypeAlias = int

            def provide_a(self) -> int:
                return 10

        class AnotherProvider(SomeProvider):
            b: TypeAlias = int

            def provide_b(self) -> int:
                return 11

        self.assertEqual(len(list(AnotherProvider.resources)), 2)
        self.assertEqual(len(list(AnotherProvider)), 2)

    def test_provider_attribute_cannot_be_named_module(self) -> None:
        class SomeModule(Module):
            pass

        with self.assertRaises(InvalidProviderAttributeName) as ctx:

            class SomeProvider(Provider, module=SomeModule):
                module: TypeAlias = int

        self.assertEqual(ctx.exception.provider.__name__, "SomeProvider")
        self.assertEqual(ctx.exception.name, "module")
        self.assertEqual(ctx.exception.assigned_to, int)

    def test_provider_attribute_cannot_be_named_resources(self) -> None:
        class SomeModule(Module):
            pass

        with self.assertRaises(InvalidProviderAttributeName) as ctx:

            class SomeProvider(Provider, module=SomeModule):
                resources: TypeAlias = int

        self.assertEqual(ctx.exception.provider.__name__, "SomeProvider")
        self.assertEqual(ctx.exception.name, "resources")
        self.assertEqual(ctx.exception.assigned_to, int)

    def test_provider_subclass_must_provide_for_the_same_module_as_base(self) -> None:
        class SomeModule(Module):
            pass

        class SomeProvider(Provider, module=SomeModule):
            pass

        class AnotherModule(Module):
            pass

        with self.assertRaises(BaseProviderProvidesFromADifferentModule) as ctx:

            class AnotherProvider(SomeProvider, module=AnotherModule):
                pass

        self.assertEqual(ctx.exception.provider.__name__, "AnotherProvider")
        self.assertEqual(ctx.exception.base, SomeProvider)
        self.assertEqual(ctx.exception.module, AnotherModule)
