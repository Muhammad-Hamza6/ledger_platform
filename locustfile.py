# locustfile.py

import uuid

from locust import HttpUser, between, task


class LedgerUser(HttpUser):
    wait_time = between(0.5, 2)

    def on_start(self):
        """Runs once per simulated user at the start — register, log in,
        create an account, so each virtual user has real credentials
        and a real account to transfer from."""
        email = f"loadtest_{uuid.uuid4()}@example.com"
        password = "LoadTest123!"

        self.client.post(
            "/api/v1/auth/register/",
            json={
                "email": email,
                "password": password,
                "password_confirm": password,
            },
        )

        response = self.client.post(
            "/api/v1/auth/token/",
            json={
                "email": email,
                "password": password,
            },
        )
        print(f"TOKEN RESPONSE [{response.status_code}]: {response.text}")
        self.token = response.json()["access"]
        self.headers = {"Authorization": f"Bearer {self.token}"}

        account_response = self.client.post(
            "/api/v1/accounts/",
            json={"name": "wallet", "currency": "USD"},
            headers=self.headers,
        )
        account_response1 = self.client.post(
            "/api/v1/accounts/",
            json={"name": "saving", "currency": "USD"},
            headers=self.headers,
        )
        self.account_id = account_response.json()["id"]
        self.account_id1 = account_response1.json()["id"]

    @task(3)
    def check_balance(self):
        self.client.get(
            f"/api/v1/accounts/{self.account_id}/balance/",
            headers=self.headers,
        )

    @task(2)
    def view_transactions(self):
        self.client.get(
            f"/api/v1/accounts/{self.account_id}/transactions/",
            headers=self.headers,
        )

    @task(1)
    def attempt_transfer(self):
        """Will mostly fail with insufficient funds (new accounts start
        at zero) — that's fine and actually useful: it exercises the
        full locking/balance-check code path under load, not just the
        happy path."""
        self.client.post(
            "/api/v1/transactions/",
            json={
                "to_account": self.account_id1,
                "amount": "10.00",
                "idempotency_key": str(uuid.uuid4()),
            },
            headers=self.headers,
        )
