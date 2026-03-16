"""Compatibility wrapper for system verification tests."""

import unittest

try:
    from ._system_verification_app_context_cases import SystemVerificationAppContextMixin
    from ._system_verification_base import SystemVerificationBase
    from ._system_verification_conversion_cases import SystemVerificationConversionMixin
    from ._system_verification_ctrlpp_cases import SystemVerificationCtrlppMixin
    from ._system_verification_rule_core_cases import SystemVerificationRuleCoreMixin
    from ._system_verification_rule_extended_cases import SystemVerificationRuleExtendedMixin
except ImportError:
    from _system_verification_app_context_cases import SystemVerificationAppContextMixin
    from _system_verification_base import SystemVerificationBase
    from _system_verification_conversion_cases import SystemVerificationConversionMixin
    from _system_verification_ctrlpp_cases import SystemVerificationCtrlppMixin
    from _system_verification_rule_core_cases import SystemVerificationRuleCoreMixin
    from _system_verification_rule_extended_cases import SystemVerificationRuleExtendedMixin


class SystemVerification(
    SystemVerificationRuleCoreMixin,
    SystemVerificationRuleExtendedMixin,
    SystemVerificationAppContextMixin,
    SystemVerificationCtrlppMixin,
    SystemVerificationConversionMixin,
    SystemVerificationBase,
):
    """Aggregated verification suite with preserved public entrypoint."""


if __name__ == "__main__":
    unittest.main()
