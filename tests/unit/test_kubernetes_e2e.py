from util import determine_arch
import unittest.mock as mock


def test_determine_arch():
    with mock.patch("subprocess.check_output") as mock_check_output:
        mock_check_output.return_value.decode.return_value = "amd64\n"
        assert determine_arch() == "amd64"
