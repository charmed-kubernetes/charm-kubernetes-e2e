import kubernetes_e2e
import unittest.mock as mock


def test_determine_arch():
    with mock.patch('kubernetes_e2e.check_output') as mock_check_output:
        mock_check_output.return_value.decode.return_value = "amd64\n"
        assert kubernetes_e2e.determine_arch() == "amd64"