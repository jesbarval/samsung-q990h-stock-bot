import unittest
from unittest.mock import patch, Mock

import monitor


class TestStockDetection(unittest.TestCase):
    def test_out_of_stock_samsung(self):
        self.assertEqual(monitor.detect_stock("Barra Samsung HW-Q990H/XC Producto no disponible. Destacados", False), "out_of_stock")

    def test_stock(self):
        self.assertEqual(monitor.detect_stock("Barra Samsung HW-Q990H/XC Añadir al carrito Destacados", True), "available")

    def test_no_button_not_available(self):
        self.assertEqual(monitor.detect_stock("Samsung HW-Q990H/XC Comprar Destacados", False), "unknown")

    def test_unrelated_model(self):
        self.assertEqual(monitor.detect_stock("Samsung HW-Q990F Comprar", True), "unknown")

    def test_out_of_stock_overrides_button(self):
        self.assertEqual(monitor.detect_stock("Samsung HW-Q990H Producto no disponible Comprar", True), "out_of_stock")

    def test_recommendation_outside_main_not_included(self):
        self.assertEqual(monitor.detect_stock("Samsung HW-Q990H Añadir al carrito Destacados Samsung 990F agotado", True), "available")

    def test_unknown_if_no_cta(self):
        self.assertEqual(monitor.detect_stock("Samsung HW-Q990H precio 700 €", True), "unknown")

    def test_no_notify_when_unknown(self):
        self.assertFalse(monitor.should_notify("out_of_stock", "unknown"))

    def test_notify_only_once(self):
        self.assertTrue(monitor.should_notify("out_of_stock", "available"))
        self.assertTrue(monitor.should_notify("unknown", "available"))
        self.assertFalse(monitor.should_notify("available", "available"))

    @patch("monitor.requests.post")
    @patch.dict("monitor.os.environ", {"TELEGRAM_BOT_TOKEN": "123:TEST", "TELEGRAM_CHAT_ID": "98765"})
    def test_telegram_send(self, post):
        post.return_value = Mock(ok=True)
        post.return_value.json.return_value = {"ok": True}
        monitor.send_telegram("prueba")
        post.assert_called_once()
        self.assertEqual(post.call_args.kwargs["data"]["chat_id"], "98765")
        self.assertEqual(post.call_args.kwargs["data"]["text"], "prueba")

    @patch("monitor.requests.post")
    @patch.dict("monitor.os.environ", {"TELEGRAM_BOT_TOKEN": "123:TEST", "TELEGRAM_CHAT_ID": "98765"})
    def test_failed_telegram_raises(self, post):
        post.return_value = Mock(ok=False, status_code=403)
        with self.assertRaises(RuntimeError):
            monitor.send_telegram("prueba")


if __name__ == "__main__":
    unittest.main()
