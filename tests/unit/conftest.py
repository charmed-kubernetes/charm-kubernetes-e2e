import sys
from unittest.mock import MagicMock

charmhelpers = MagicMock()
sys.modules["charmhelpers"] = charmhelpers
sys.modules["charmhelpers.core"] = charmhelpers.core
sys.modules["charmhelpers.core.hookenv"] = charmhelpers.core.hookenv

charms = MagicMock()
sys.modules["charms"] = charms
sys.modules["charms.layer"] = charms.layer
sys.modules["charms.reactive"] = charms.reactive
sys.modules["charms.reactive.helpers"] = charms.reactive.helpers