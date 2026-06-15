from locust import HttpUser, task, between
import json

class NetworkAPIUser(HttpUser):
    """Giả lập người dùng gửi request đến API network_api."""
    wait_time = between(1, 3)

    @task(3)
    def switch_to_4g(self):
        """Giả lập chuyển sang cấu hình 4G."""
        self.client.post("/api/network", data={"mode": "4g"}, verify=False)

    @task(2)
    def switch_to_3g(self):
        """Giả lập chuyển sang cấu hình 3G."""
        self.client.post("/api/network", data={"mode": "3g"}, verify=False)

    @task(1)
    def reset_network(self):
        """Giả lập reset về cấu hình không giới hạn."""
        self.client.post("/api/network", data={"mode": "reset"}, verify=False)

    @task(4)
    def get_dashboard(self):
        """Giả lập người dùng truy cập trang chủ (được phục vụ bởi Caddy)."""
        self.client.get("/", verify=False)

    def on_start(self):
        """Hành động khi một user bắt đầu."""
        pass
