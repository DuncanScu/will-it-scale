import os
import unittest
from unittest.mock import patch

from will_it_scale.config import resolve_subscription_id


class ResolveSubscriptionIdTests(unittest.TestCase):
    def test_uses_env_var_when_set(self) -> None:
        with patch.dict(os.environ, {"AZURE_SUBSCRIPTION_ID": "sub-123"}):
            self.assertEqual(resolve_subscription_id(), "sub-123")

    def test_falls_back_to_az_cli(self) -> None:
        with patch.dict(os.environ, {"AZURE_SUBSCRIPTION_ID": ""}):
            with patch("will_it_scale.config.subprocess.run") as run:
                run.return_value.stdout = "sub-from-cli\n"
                self.assertEqual(resolve_subscription_id(), "sub-from-cli")

    def test_raises_when_unavailable(self) -> None:
        with patch.dict(os.environ, {"AZURE_SUBSCRIPTION_ID": ""}):
            with patch("will_it_scale.config.subprocess.run", side_effect=FileNotFoundError):
                with self.assertRaises(RuntimeError):
                    resolve_subscription_id()


if __name__ == "__main__":
    unittest.main()
