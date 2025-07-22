import requests
import json

BASE_URL = "http://127.0.0.1:5000"


def test_health():
    print("Testing /api/health...")
    response = requests.get(f"{BASE_URL}/api/health")
    assert response.status_code == 200, "Health check failed!"
    data = response.json()
    assert data["status"] == "healthy", "Unexpected health status"
    print("Health check OK:", data)


def test_history():
    print("Testing /api/history...")
    params = {"limit": 5, "offset": 0}
    response = requests.get(f"{BASE_URL}/api/history", params=params)
    assert response.status_code == 200, "History endpoint failed!"
    data = response.json()
    assert "history" in data, "Missing 'history' in response"
    print(f"Retrieved {len(data['history'])} entries from history.")


def test_analytics():
    print("Testing /api/analytics...")
    response = requests.get(f"{BASE_URL}/api/analytics")
    assert response.status_code == 200, "Analytics endpoint failed!"
    data = response.json()
    assert "total_requests" in data, "Missing 'total_requests' in analytics"
    print("Analytics data:", json.dumps(data, indent=2))


if __name__ == "__main__":
    try:
        test_health()
        test_history()
        test_analytics()
        print("\nAll tests passed successfully!")
    except AssertionError as ae:
        print("\nTest failed:", ae)
    except Exception as e:
        print("\nUnexpected error occurred:", e)
