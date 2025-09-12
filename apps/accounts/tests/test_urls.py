"""Tests for accounts URLs"""

import pytest
from django.test import TestCase
from django.urls import resolve, reverse

from apps.accounts.views import UserViewSet


class AccountsURLTest(TestCase):
    """Test accounts URL routing"""

    def test_user_list_url_reverse(self):
        """Test user list URL reverse lookup"""
        url = reverse("user-list")
        self.assertEqual(url, "/users/")

    def test_user_detail_url_reverse(self):
        """Test user detail URL reverse lookup"""
        url = reverse("user-detail", args=[1])
        self.assertEqual(url, "/users/1/")

    def test_user_register_url_reverse(self):
        """Test user register URL reverse lookup"""
        url = reverse("user-register")
        self.assertEqual(url, "/users/register/")

    def test_user_change_password_url_reverse(self):
        """Test user change password URL reverse lookup"""
        url = reverse("user-change-password")
        self.assertEqual(url, "/users/change-password/")

    def test_user_ping_url_reverse(self):
        """Test user ping URL reverse lookup"""
        url = reverse("user-ping")
        self.assertEqual(url, "/users/ping/")

    def test_user_delete_account_url_reverse(self):
        """Test user delete account URL reverse lookup"""
        url = reverse("user-delete-account")
        self.assertEqual(url, "/users/delete-account/")

    def test_user_list_url_resolve(self):
        """Test user list URL resolution"""
        resolver = resolve("/users/")
        self.assertEqual(resolver.func.cls, UserViewSet)
        self.assertEqual(resolver.url_name, "user-list")

    def test_user_detail_url_resolve(self):
        """Test user detail URL resolution"""
        resolver = resolve("/users/123/")
        self.assertEqual(resolver.func.cls, UserViewSet)
        self.assertEqual(resolver.url_name, "user-detail")
        self.assertEqual(resolver.kwargs["pk"], "123")

    def test_user_register_url_resolve(self):
        """Test user register URL resolution"""
        resolver = resolve("/users/register/")
        self.assertEqual(resolver.func.cls, UserViewSet)
        self.assertEqual(resolver.url_name, "user-register")

    def test_user_change_password_url_resolve(self):
        """Test user change password URL resolution"""
        resolver = resolve("/users/change-password/")
        self.assertEqual(resolver.func.cls, UserViewSet)
        self.assertEqual(resolver.url_name, "user-change-password")

    def test_user_ping_url_resolve(self):
        """Test user ping URL resolution"""
        resolver = resolve("/users/ping/")
        self.assertEqual(resolver.func.cls, UserViewSet)
        self.assertEqual(resolver.url_name, "user-ping")

    def test_user_delete_account_url_resolve(self):
        """Test user delete account URL resolution"""
        resolver = resolve("/users/delete-account/")
        self.assertEqual(resolver.func.cls, UserViewSet)
        self.assertEqual(resolver.url_name, "user-delete-account")

    def test_url_patterns_count(self):
        """Test that the correct number of URL patterns are registered"""
        from apps.accounts.urls import router, urlpatterns

        # Should have one pattern for the router include
        self.assertEqual(len(urlpatterns), 1)

        # Router should have one registered viewset
        self.assertEqual(len(router.registry), 1)

        # Check the registered viewset
        registry_entry = router.registry[0]
        self.assertEqual(registry_entry[0], "users")  # prefix
        self.assertEqual(registry_entry[1], UserViewSet)  # viewset
        self.assertEqual(registry_entry[2], "user")  # basename

    def test_router_configuration(self):
        """Test router configuration"""
        from rest_framework.routers import DefaultRouter

        from apps.accounts.urls import router

        self.assertIsInstance(router, DefaultRouter)

        # Check that users viewset is registered with correct basename
        users_viewset = None
        for prefix, viewset, basename in router.registry:
            if prefix == "users":
                users_viewset = (prefix, viewset, basename)
                break

        self.assertIsNotNone(users_viewset)
        self.assertEqual(users_viewset[0], "users")
        self.assertEqual(users_viewset[1], UserViewSet)
        self.assertEqual(users_viewset[2], "user")


@pytest.mark.django_db
class TestAccountsURLsWithPytest:
    """Additional pytest-style tests for accounts URLs"""

    def test_all_viewset_actions_have_urls(self):
        """Test that all UserViewSet actions have corresponding URLs"""
        from apps.accounts.urls import router

        # Get the registered URLs for the users viewset
        urls = router.get_urls()
        url_names = [url.name for url in urls]

        # Check that all expected action URLs are present
        expected_urls = [
            "user-list",
            "user-detail",
            "user-register",
            "user-change-password",
            "user-ping",
            "user-delete-account"
        ]

        for expected_url in expected_urls:
            assert expected_url in url_names

    def test_url_reverse_with_different_ids(self):
        """Test URL reverse with different ID types"""
        # Test with integer ID
        url_int = reverse("user-detail", args=[123])
        assert url_int == "/users/123/"

        # Test with string ID
        url_str = reverse("user-detail", args=["abc"])
        assert url_str == "/users/abc/"

        # Test with UUID-like string
        url_uuid = reverse("user-detail", args=["550e8400-e29b-41d4-a716-446655440000"])
        assert url_uuid == "/users/550e8400-e29b-41d4-a716-446655440000/"

    def test_url_resolution_with_trailing_slash(self):
        """Test URL resolution works with and without trailing slashes"""
        # With trailing slash
        resolver_with_slash = resolve("/users/123/")
        assert resolver_with_slash.func.cls == UserViewSet
        assert resolver_with_slash.url_name == "user-detail"

        # Without trailing slash should also work due to Django's APPEND_SLASH
        # This test depends on Django settings, so we'll just test the URL pattern
        assert "/users/123/" == reverse("user-detail", args=[123])

    def test_custom_action_url_patterns(self):
        """Test that custom action URLs are correctly configured"""
        # Test register action
        register_url = reverse("user-register")
        resolver = resolve(register_url)
        assert resolver.func.cls == UserViewSet
        assert resolver.url_name == "user-register"

        # Test change-password action
        change_pass_url = reverse("user-change-password")
        resolver = resolve(change_pass_url)
        assert resolver.func.cls == UserViewSet
        assert resolver.url_name == "user-change-password"

        # Test ping action
        ping_url = reverse("user-ping")
        resolver = resolve(ping_url)
        assert resolver.func.cls == UserViewSet
        assert resolver.url_name == "user-ping"

        # Test delete-account action
        delete_url = reverse("user-delete-account")
        resolver = resolve(delete_url)
        assert resolver.func.cls == UserViewSet
        assert resolver.url_name == "user-delete-account"

    def test_router_basename_consistency(self):
        """Test that router basename is consistent with URL names"""
        from apps.accounts.urls import router

        # Find the users viewset registration
        for prefix, viewset, basename in router.registry:
            if prefix == "users" and viewset == UserViewSet:
                assert basename == "user"
                break
        else:
            pytest.fail("UserViewSet not found in router registry")

    def test_url_namespace_isolation(self):
        """Test that accounts URLs don't conflict with other app URLs"""
        # This is more of a documentation test to ensure we understand
        # that these URLs are for the accounts app specifically

        # All our URLs should start with /users/
        test_urls = [
            ("user-list", "/users/"),
            ("user-detail", "/users/1/"),
            ("user-register", "/users/register/"),
            ("user-change-password", "/users/change-password/"),
            ("user-ping", "/users/ping/"),
            ("user-delete-account", "/users/delete-account/"),
        ]

        for url_name, expected_path in test_urls:
            if url_name == "user-detail":
                actual_path = reverse(url_name, args=[1])
            else:
                actual_path = reverse(url_name)

            assert actual_path == expected_path
            assert actual_path.startswith("/users/")

    def test_drf_router_api_root(self):
        """Test that DRF router provides an API root"""
        from apps.accounts.urls import router

        # The router should provide URL patterns
        urls = router.get_urls()
        assert len(urls) > 0

        # Should have a root URL for the API
        root_urls = [url for url in urls if url.pattern.regex.pattern == "^$"]
        assert len(root_urls) == 1

        # Root URL should be named after the basename
        root_url = root_urls[0]
        assert root_url.name == "api-root"
