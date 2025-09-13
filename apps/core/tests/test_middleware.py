"""Comprehensive tests for core middleware functionality."""

import ipaddress
from unittest.mock import Mock, patch

from django.conf import settings
from django.http import HttpResponse, HttpResponseForbidden
from django.test import RequestFactory, TestCase, override_settings

from apps.core.middleware import (
    AdminIPAllowlistMiddleware,
    DemoModeMiddleware,
    SecurityHeadersMiddleware,
)


class SecurityHeadersMiddlewareTestCase(TestCase):
    """Test SecurityHeadersMiddleware functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.middleware = SecurityHeadersMiddleware(
            get_response=lambda r: HttpResponse()
        )

    def test_basic_security_headers_added(self):
        """Test that basic security headers are added to all responses."""
        request = self.factory.get("/")
        response = HttpResponse("Test content")

        processed_response = self.middleware.process_response(request, response)

        # Check basic security headers
        self.assertEqual(
            processed_response["Referrer-Policy"], "strict-origin-when-cross-origin"
        )
        self.assertEqual(processed_response["X-Content-Type-Options"], "nosniff")
        self.assertEqual(processed_response["X-Frame-Options"], "DENY")
        self.assertEqual(processed_response["X-XSS-Protection"], "1; mode=block")

    def test_permissions_policy_header(self):
        """Test Permissions Policy header is set correctly."""
        request = self.factory.get("/")
        response = HttpResponse("Test content")

        processed_response = self.middleware.process_response(request, response)

        permissions_policy = processed_response["Permissions-Policy"]
        expected_policies = [
            "camera=()",
            "microphone=()",
            "geolocation=()",
            "interest-cohort=()",
        ]

        for policy in expected_policies:
            self.assertIn(policy, permissions_policy)

    @override_settings(DEBUG=False)
    def test_production_content_security_policy(self):
        """Test CSP header in production mode."""
        request = self.factory.get("/")
        response = HttpResponse("Test content")

        processed_response = self.middleware.process_response(request, response)

        csp = processed_response["Content-Security-Policy"]

        # Check production CSP directives
        self.assertIn("default-src 'self'", csp)
        self.assertIn(
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net",
            csp,
        )
        self.assertIn("style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net", csp)
        self.assertIn("img-src 'self' data: https:", csp)
        self.assertIn("object-src 'none'", csp)
        self.assertIn("frame-ancestors 'none'", csp)

    @override_settings(DEBUG=True)
    def test_development_content_security_policy(self):
        """Test CSP header in development mode."""
        request = self.factory.get("/")
        response = HttpResponse("Test content")

        processed_response = self.middleware.process_response(request, response)

        csp = processed_response["Content-Security-Policy"]

        # Check development CSP directives (more relaxed)
        self.assertIn("default-src 'self' 'unsafe-inline' 'unsafe-eval'", csp)
        self.assertIn("img-src 'self' data: https: blob:", csp)
        self.assertIn("connect-src 'self' ws: wss:", csp)

    @override_settings(SECURE_SSL_REDIRECT=True, SECURE_HSTS_SECONDS=31536000)
    def test_hsts_header_with_ssl_redirect(self):
        """Test HSTS header when SSL redirect is enabled."""
        request = self.factory.get("/")
        response = HttpResponse("Test content")

        processed_response = self.middleware.process_response(request, response)

        hsts = processed_response["Strict-Transport-Security"]
        self.assertIn("max-age=31536000", hsts)

    @override_settings(
        SECURE_SSL_REDIRECT=True,
        SECURE_HSTS_SECONDS=31536000,
        SECURE_HSTS_INCLUDE_SUBDOMAINS=True,
        SECURE_HSTS_PRELOAD=True,
    )
    def test_hsts_header_with_subdomains_and_preload(self):
        """Test HSTS header with subdomains and preload options."""
        request = self.factory.get("/")
        response = HttpResponse("Test content")

        processed_response = self.middleware.process_response(request, response)

        hsts = processed_response["Strict-Transport-Security"]
        self.assertIn("max-age=31536000", hsts)
        self.assertIn("includeSubDomains", hsts)
        self.assertIn("preload", hsts)

    @override_settings(
        SECURE_SSL_REDIRECT=True,
        SECURE_HSTS_INCLUDE_SUBDOMAINS=False,
        SECURE_HSTS_PRELOAD=False,
    )
    def test_hsts_header_without_subdomains_and_preload(self):
        """Test HSTS header without subdomains and preload options."""
        request = self.factory.get("/")
        response = HttpResponse("Test content")

        processed_response = self.middleware.process_response(request, response)

        hsts = processed_response["Strict-Transport-Security"]
        self.assertNotIn("includeSubDomains", hsts)
        self.assertNotIn("preload", hsts)

    @override_settings(SECURE_SSL_REDIRECT=False)
    def test_no_hsts_header_without_ssl_redirect(self):
        """Test that HSTS header is not added when SSL redirect is disabled."""
        request = self.factory.get("/")
        response = HttpResponse("Test content")

        processed_response = self.middleware.process_response(request, response)

        self.assertNotIn("Strict-Transport-Security", processed_response)

    def test_x_frame_options_not_overridden_if_exists(self):
        """Test that X-Frame-Options is not overridden if already set."""
        request = self.factory.get("/")
        response = HttpResponse("Test content")
        response["X-Frame-Options"] = "SAMEORIGIN"

        processed_response = self.middleware.process_response(request, response)

        # Should not override existing header
        self.assertEqual(processed_response["X-Frame-Options"], "SAMEORIGIN")

    def test_x_frame_options_added_if_missing(self):
        """Test that X-Frame-Options is added if missing."""
        request = self.factory.get("/")
        response = HttpResponse("Test content")

        processed_response = self.middleware.process_response(request, response)

        # Should add default DENY value
        self.assertEqual(processed_response["X-Frame-Options"], "DENY")

    def test_security_headers_with_different_response_types(self):
        """Test security headers are added to different response types."""
        request = self.factory.get("/")

        # Test with different status codes
        for status_code in [200, 201, 404, 500]:
            with self.subTest(status_code=status_code):
                response = HttpResponse("Content", status=status_code)
                processed_response = self.middleware.process_response(request, response)

                # Security headers should be added regardless of status code
                self.assertIn("X-Content-Type-Options", processed_response)
                self.assertIn("Content-Security-Policy", processed_response)


class AdminIPAllowlistMiddlewareTestCase(TestCase):
    """Test AdminIPAllowlistMiddleware functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.middleware = AdminIPAllowlistMiddleware(
            get_response=lambda r: HttpResponse()
        )

    def test_non_admin_url_allowed(self):
        """Test that non-admin URLs are always allowed."""
        request = self.factory.get("/api/users/")
        request.headers = {"x-forwarded-for": "192.168.1.100"}

        result = self.middleware.process_request(request)

        # Should return None (allow request)
        self.assertIsNone(result)

    @override_settings(ADMIN_IP_ALLOWLIST=[])
    def test_admin_url_allowed_when_no_allowlist(self):
        """Test that admin URLs are allowed when no allowlist is configured."""
        request = self.factory.get("/admin/")
        request.headers = {"x-forwarded-for": "192.168.1.100"}

        result = self.middleware.process_request(request)

        # Should return None (allow request)
        self.assertIsNone(result)

    @override_settings(ADMIN_IP_ALLOWLIST=["192.168.1.100"])
    def test_admin_url_allowed_with_matching_ip(self):
        """Test that admin URLs are allowed for IPs in allowlist."""
        request = self.factory.get("/admin/")
        request.headers = {"x-forwarded-for": "192.168.1.100"}

        result = self.middleware.process_request(request)

        # Should return None (allow request)
        self.assertIsNone(result)

    @override_settings(ADMIN_IP_ALLOWLIST=["192.168.1.100"])
    def test_admin_url_forbidden_with_non_matching_ip(self):
        """Test that admin URLs are forbidden for IPs not in allowlist."""
        request = self.factory.get("/admin/")
        request.headers = {"x-forwarded-for": "192.168.1.200"}

        result = self.middleware.process_request(request)

        # Should return HttpResponseForbidden
        self.assertIsInstance(result, HttpResponseForbidden)
        self.assertIn("Access denied", result.content.decode())

    @override_settings(ADMIN_IP_ALLOWLIST=["192.168.1.0/24"])
    def test_admin_url_allowed_with_cidr_notation(self):
        """Test that CIDR notation works in IP allowlist."""
        # Test IP within CIDR range
        request = self.factory.get("/admin/")
        request.headers = {"x-forwarded-for": "192.168.1.150"}

        result = self.middleware.process_request(request)
        self.assertIsNone(result)

        # Test IP outside CIDR range
        request2 = self.factory.get("/admin/")
        request2.headers = {"x-forwarded-for": "192.168.2.150"}

        result2 = self.middleware.process_request(request2)
        self.assertIsInstance(result2, HttpResponseForbidden)

    def test_get_client_ip_from_x_forwarded_for(self):
        """Test client IP extraction from X-Forwarded-For header."""
        request = self.factory.get("/")
        request.headers = {"x-forwarded-for": "192.168.1.100, 10.0.0.1, 172.16.0.1"}

        client_ip = self.middleware._get_client_ip(request)

        # Should return first IP from the chain
        self.assertEqual(client_ip, "192.168.1.100")

    def test_get_client_ip_from_remote_addr(self):
        """Test client IP from REMOTE_ADDR when X-Forwarded-For missing."""
        request = self.factory.get("/")
        request.headers = {}
        request.META = {"REMOTE_ADDR": "127.0.0.1"}

        client_ip = self.middleware._get_client_ip(request)

        self.assertEqual(client_ip, "127.0.0.1")

    def test_get_client_ip_with_whitespace_in_forwarded_for(self):
        """Test client IP extraction handles whitespace in X-Forwarded-For."""
        request = self.factory.get("/")
        request.headers = {"x-forwarded-for": "  192.168.1.100  , 10.0.0.1"}

        client_ip = self.middleware._get_client_ip(request)

        # Should strip whitespace
        self.assertEqual(client_ip, "192.168.1.100")

    def test_ip_in_allowlist_with_single_ips(self):
        """Test IP allowlist checking with single IP addresses."""
        allowed_ips = ["192.168.1.100", "10.0.0.1"]

        # Test matching IP
        self.assertTrue(self.middleware._ip_in_allowlist("192.168.1.100", allowed_ips))
        self.assertTrue(self.middleware._ip_in_allowlist("10.0.0.1", allowed_ips))

        # Test non-matching IP
        self.assertFalse(self.middleware._ip_in_allowlist("192.168.1.200", allowed_ips))

    def test_ip_in_allowlist_with_cidr_notation(self):
        """Test IP allowlist checking with CIDR notation."""
        allowed_ips = ["192.168.1.0/24", "10.0.0.0/8"]

        # Test IPs within CIDR ranges
        self.assertTrue(self.middleware._ip_in_allowlist("192.168.1.50", allowed_ips))
        self.assertTrue(self.middleware._ip_in_allowlist("10.100.200.1", allowed_ips))

        # Test IPs outside CIDR ranges
        self.assertFalse(self.middleware._ip_in_allowlist("192.168.2.50", allowed_ips))
        self.assertFalse(self.middleware._ip_in_allowlist("172.16.0.1", allowed_ips))

    def test_ip_in_allowlist_with_invalid_client_ip(self):
        """Test IP allowlist checking with invalid client IP."""
        allowed_ips = ["192.168.1.100"]

        # Test with invalid IP format
        self.assertFalse(self.middleware._ip_in_allowlist("invalid-ip", allowed_ips))
        self.assertFalse(
            self.middleware._ip_in_allowlist("999.999.999.999", allowed_ips)
        )

    def test_ip_in_allowlist_with_invalid_allowed_ip(self):
        """Test IP allowlist checking with invalid entries in allowlist."""
        allowed_ips = ["192.168.1.100", "invalid-ip", "10.0.0.1"]

        # Should skip invalid entries and check valid ones
        self.assertTrue(self.middleware._ip_in_allowlist("192.168.1.100", allowed_ips))
        self.assertTrue(self.middleware._ip_in_allowlist("10.0.0.1", allowed_ips))
        self.assertFalse(self.middleware._ip_in_allowlist("192.168.1.200", allowed_ips))

    def test_ip_in_allowlist_no_matches_in_list(self):
        """Test IP allowlist checking when no IPs match."""
        allowed_ips = ["192.168.1.100", "10.0.0.1", "172.16.0.0/24"]

        # Test IP that doesn't match any in the list - this should hit line 137
        self.assertFalse(self.middleware._ip_in_allowlist("203.0.113.1", allowed_ips))

        # Test another IP that doesn't match
        self.assertFalse(self.middleware._ip_in_allowlist("8.8.8.8", allowed_ips))

        # Test with empty allowlist - this should also hit line 137
        self.assertFalse(self.middleware._ip_in_allowlist("192.168.1.100", []))

    def test_ip_in_allowlist_all_entries_invalid(self):
        """Test IP allowlist with all invalid entries - should hit line 137."""
        # All entries are invalid, so we go through loop, skip all, return False
        allowed_ips = ["invalid-ip", "999.999.999.999", "not-an-ip"]

        # Valid client IP but all allowlist entries invalid - should hit line 137
        self.assertFalse(self.middleware._ip_in_allowlist("192.168.1.100", allowed_ips))

    def test_ipv6_support(self):
        """Test IPv6 address support in allowlist."""
        allowed_ips = ["2001:db8::1", "2001:db8::/32"]

        # Test exact IPv6 match
        self.assertTrue(self.middleware._ip_in_allowlist("2001:db8::1", allowed_ips))

        # Test IPv6 CIDR match
        self.assertTrue(self.middleware._ip_in_allowlist("2001:db8::abcd", allowed_ips))

        # Test IPv6 non-match
        self.assertFalse(self.middleware._ip_in_allowlist("2001:db9::1", allowed_ips))

    @override_settings(ADMIN_IP_ALLOWLIST=["192.168.1.100"])
    def test_admin_subpaths_protected(self):
        """Test that all admin subpaths are protected."""
        admin_paths = [
            "/admin/",
            "/admin/auth/user/",
            "/admin/auth/user/1/change/",
            "/admin/login/",
        ]

        for path in admin_paths:
            with self.subTest(path=path):
                request = self.factory.get(path)
                request.headers = {
                    "x-forwarded-for": "192.168.1.200"
                }  # Not in allowlist

                result = self.middleware.process_request(request)
                self.assertIsInstance(result, HttpResponseForbidden)


class DemoModeMiddlewareTestCase(TestCase):
    """Test DemoModeMiddleware functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.middleware = DemoModeMiddleware(get_response=lambda r: HttpResponse())

    @override_settings(DEMO_MODE=False)
    def test_no_banner_when_demo_mode_disabled(self):
        """Test that no banner is added when demo mode is disabled."""
        request = self.factory.get("/")
        response = HttpResponse("<html><body>Test content</body></html>")
        response["Content-Type"] = "text/html"

        processed_response = self.middleware.process_response(request, response)

        # Content should be unchanged
        self.assertEqual(
            processed_response.content.decode(),
            "<html><body>Test content</body></html>",
        )

    @override_settings(DEMO_MODE=True)
    def test_banner_added_to_html_response(self):
        """Test that demo banner is added to HTML responses."""
        request = self.factory.get("/")
        response = HttpResponse("<html><body>Test content</body></html>")
        response["Content-Type"] = "text/html"

        processed_response = self.middleware.process_response(request, response)

        content = processed_response.content.decode()

        # Should contain demo banner
        self.assertIn("DEMO MODE", content)
        self.assertIn("demonstration environment", content)
        self.assertIn("position: fixed", content)
        self.assertIn("body { margin-top: 40px !important; }", content)

    @override_settings(DEMO_MODE=True)
    def test_no_banner_for_non_html_response(self):
        """Test that banner is not added to non-HTML responses."""
        request = self.factory.get("/api/data/")
        response = HttpResponse('{"data": "test"}')
        response["Content-Type"] = "application/json"

        processed_response = self.middleware.process_response(request, response)

        # Content should be unchanged
        self.assertEqual(processed_response.content.decode(), '{"data": "test"}')

    @override_settings(DEMO_MODE=True)
    def test_no_banner_for_non_200_response(self):
        """Test that banner is not added to non-200 responses."""
        request = self.factory.get("/")
        response = HttpResponse("<html><body>Not found</body></html>", status=404)
        response["Content-Type"] = "text/html"

        processed_response = self.middleware.process_response(request, response)

        # Content should be unchanged
        self.assertEqual(
            processed_response.content.decode(), "<html><body>Not found</body></html>"
        )

    @override_settings(DEMO_MODE=True)
    def test_banner_positioning_after_body_tag(self):
        """Test that banner is correctly positioned after body tag."""
        request = self.factory.get("/")
        response = HttpResponse(
            "<html><head><title>Test</title></head>"
            '<body class="main">Content</body></html>'
        )
        response["Content-Type"] = "text/html"

        processed_response = self.middleware.process_response(request, response)

        content = processed_response.content.decode()

        # Banner should be inserted after body tag
        body_end = content.find(">", content.find("<body"))
        banner_start = content.find("DEMO MODE")

        self.assertGreater(banner_start, body_end)
        self.assertIn('<body class="main">', content)

    @override_settings(DEMO_MODE=True)
    def test_content_length_updated(self):
        """Test that Content-Length header is updated after adding banner."""
        request = self.factory.get("/")
        original_content = "<html><body>Test content</body></html>"
        response = HttpResponse(original_content)
        response["Content-Type"] = "text/html"

        processed_response = self.middleware.process_response(request, response)

        # Content-Length should be updated
        new_content_length = len(processed_response.content)
        self.assertEqual(int(processed_response["Content-Length"]), new_content_length)
        self.assertGreater(new_content_length, len(original_content.encode()))

    @override_settings(DEMO_MODE=True)
    def test_banner_with_html_without_body_tag(self):
        """Test banner handling when HTML doesn't have body tag."""
        request = self.factory.get("/")
        response = HttpResponse("<html><h1>Simple HTML</h1></html>")
        response["Content-Type"] = "text/html"

        processed_response = self.middleware.process_response(request, response)

        # Content should be unchanged if no body tag found
        self.assertEqual(
            processed_response.content.decode(), "<html><h1>Simple HTML</h1></html>"
        )

    @override_settings(DEMO_MODE=True)
    def test_banner_with_multiple_body_tags(self):
        """Test banner handling with multiple body tags (edge case)."""
        request = self.factory.get("/")
        response = HttpResponse("<html><body>First</body><body>Second</body></html>")
        response["Content-Type"] = "text/html"

        processed_response = self.middleware.process_response(request, response)

        content = processed_response.content.decode()

        # Banner should be added after first body tag
        first_body_end = content.find(">", content.find("<body"))
        banner_start = content.find("DEMO MODE")

        self.assertGreater(banner_start, first_body_end)
        # Should only have one banner
        self.assertEqual(content.count("DEMO MODE"), 1)

    @override_settings(DEMO_MODE=True)
    def test_banner_styling_and_content(self):
        """Test banner styling and content details."""
        request = self.factory.get("/")
        response = HttpResponse("<html><body>Test</body></html>")
        response["Content-Type"] = "text/html"

        processed_response = self.middleware.process_response(request, response)

        content = processed_response.content.decode()

        # Check banner styling
        self.assertIn("position: fixed", content)
        self.assertIn("top: 0", content)
        self.assertIn("background: #ff6b35", content)
        self.assertIn("color: white", content)
        self.assertIn("z-index: 10000", content)

        # Check body margin adjustment
        self.assertIn("body { margin-top: 40px !important; }", content)

        # Check banner emoji and text
        self.assertIn("🚧", content)
        self.assertIn("DEMO MODE", content)

    def test_response_without_content_attribute(self):
        """Test handling of responses without content attribute."""
        request = self.factory.get("/")

        # Mock response without content attribute
        mock_response = Mock(spec=HttpResponse)
        mock_response.status_code = 200
        mock_response.get.return_value = "text/html"
        del mock_response.content  # Remove content attribute

        # Should not raise exception
        with patch.object(settings, "DEMO_MODE", True):
            processed_response = self.middleware.process_response(
                request, mock_response
            )
            self.assertEqual(processed_response, mock_response)


class MiddlewareIntegrationTestCase(TestCase):
    """Test middleware integration and interaction scenarios."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()

    def test_middleware_order_and_interaction(self):
        """Test that multiple middleware work together correctly."""
        # Create a request that goes through multiple middleware
        request = self.factory.get("/admin/")
        request.headers = {"x-forwarded-for": "192.168.1.100"}

        # Initial response
        response = HttpResponse("<html><body>Admin page</body></html>")
        response["Content-Type"] = "text/html"

        # Process through SecurityHeadersMiddleware
        security_middleware = SecurityHeadersMiddleware(get_response=lambda r: response)
        response = security_middleware.process_response(request, response)

        # Process through DemoModeMiddleware
        with override_settings(DEMO_MODE=True):
            demo_middleware = DemoModeMiddleware(get_response=lambda r: response)
            response = demo_middleware.process_response(request, response)

        # Both middleware should have applied their changes
        self.assertIn("X-Content-Type-Options", response)  # Security headers
        self.assertIn("DEMO MODE", response.content.decode())  # Demo banner

    @override_settings(ADMIN_IP_ALLOWLIST=["192.168.1.0/24"])
    def test_admin_access_with_security_headers(self):
        """Test admin access works with security headers applied."""
        request = self.factory.get("/admin/")
        request.headers = {"x-forwarded-for": "192.168.1.100"}  # Allowed IP

        # Process through AdminIPAllowlistMiddleware
        admin_middleware = AdminIPAllowlistMiddleware(
            get_response=lambda r: HttpResponse()
        )
        result = admin_middleware.process_request(request)

        # Should be allowed (None result)
        self.assertIsNone(result)

        # If request proceeds, security headers should be added
        response = HttpResponse("<html><body>Admin</body></html>")
        security_middleware = SecurityHeadersMiddleware(get_response=lambda r: response)
        final_response = security_middleware.process_response(request, response)

        self.assertIn("Content-Security-Policy", final_response)

    @override_settings(ADMIN_IP_ALLOWLIST=["192.168.1.0/24"], DEMO_MODE=True)
    def test_admin_forbidden_response_gets_security_headers(self):
        """Test that forbidden admin responses still get security headers."""
        request = self.factory.get("/admin/")
        request.headers = {"x-forwarded-for": "10.0.0.1"}  # Not allowed IP

        # Process through AdminIPAllowlistMiddleware
        admin_middleware = AdminIPAllowlistMiddleware(
            get_response=lambda r: HttpResponse()
        )
        forbidden_response = admin_middleware.process_request(request)

        # Should be forbidden
        self.assertIsInstance(forbidden_response, HttpResponseForbidden)

        # Security headers should still be applied to forbidden response
        security_middleware = SecurityHeadersMiddleware(
            get_response=lambda r: forbidden_response
        )
        final_response = security_middleware.process_response(
            request, forbidden_response
        )

        self.assertIn("X-Content-Type-Options", final_response)
        self.assertIn("Content-Security-Policy", final_response)

    def test_error_handling_in_middleware_chain(self):
        """Test error handling when middleware encounters issues."""
        request = self.factory.get("/")

        # Test with malformed IP headers
        request.headers = {"x-forwarded-for": "invalid-ip-format"}

        admin_middleware = AdminIPAllowlistMiddleware(
            get_response=lambda r: HttpResponse()
        )

        # Should handle invalid IP gracefully
        result = admin_middleware.process_request(request)
        self.assertIsNone(result)  # Non-admin URL should be allowed regardless

    def test_unicode_content_handling(self):
        """Test middleware handles Unicode content correctly."""
        request = self.factory.get("/")

        # Response with Unicode content
        unicode_content = "<html><body>Test with émojis 🎉</body></html>"
        response = HttpResponse(unicode_content)
        response["Content-Type"] = "text/html"

        # Process through DemoModeMiddleware
        with override_settings(DEMO_MODE=True):
            demo_middleware = DemoModeMiddleware(get_response=lambda r: response)
            processed_response = demo_middleware.process_response(request, response)

        # Should handle Unicode correctly
        content = processed_response.content.decode("utf-8")
        self.assertIn("émojis 🎉", content)
        self.assertIn("DEMO MODE", content)

    @patch("apps.core.middleware.ipaddress.ip_address")
    def test_ip_validation_error_handling(self, mock_ip_address):
        """Test handling of IP validation errors."""
        mock_ip_address.side_effect = ValueError("Invalid IP")

        request = self.factory.get("/admin/")
        request.headers = {"x-forwarded-for": "malformed-ip"}

        admin_middleware = AdminIPAllowlistMiddleware(
            get_response=lambda r: HttpResponse()
        )

        with override_settings(ADMIN_IP_ALLOWLIST=["192.168.1.100"]):
            result = admin_middleware.process_request(request)

            # Should return forbidden response for invalid client IP
            self.assertIsInstance(result, HttpResponseForbidden)

    def test_large_content_handling(self):
        """Test middleware handles large content correctly."""
        request = self.factory.get("/")

        # Create large HTML content
        large_content = "<html><body>" + "x" * 10000 + "</body></html>"
        response = HttpResponse(large_content)
        response["Content-Type"] = "text/html"

        # Process through multiple middleware
        security_middleware = SecurityHeadersMiddleware(get_response=lambda r: response)
        response = security_middleware.process_response(request, response)

        with override_settings(DEMO_MODE=True):
            demo_middleware = DemoModeMiddleware(get_response=lambda r: response)
            response = demo_middleware.process_response(request, response)

        # Content-Length should be updated correctly
        actual_length = len(response.content)
        header_length = int(response["Content-Length"])
        self.assertEqual(actual_length, header_length)
