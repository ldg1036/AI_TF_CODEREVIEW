import unittest

from ._api_autofix_cases import ApiAutofixCasesMixin
from ._api_general_cases import ApiGeneralCasesMixin
from ._api_integration_test_base import ApiIntegrationTestBase
from ._report_quality_cases import ReportQualityCasesMixin


class ApiIntegrationTests(ApiGeneralCasesMixin, ApiAutofixCasesMixin, ApiIntegrationTestBase):
    pass


class ReportQualityTests(ReportQualityCasesMixin, unittest.TestCase):
    pass
