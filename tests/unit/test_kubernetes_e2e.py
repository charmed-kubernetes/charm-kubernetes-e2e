import charm
import unittest.mock as mock

def test_determine_arch():
    with mock.patch('kubernetes_e2e.check_output') as mock_check_output:
        mock_check_output.return_value.decode.return_value = "amd64\n"
        assert charm.determine_arch() == "amd64"