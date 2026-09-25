import time
from httpx import AsyncClient, HTTPStatusError, Timeout
import asyncio
import sys
import uuid

if __name__ == "__main__":
    import time
    from httpx import AsyncClient, HTTPStatusError
    import asyncio
    import sys
    import uuid

    async def measure_enrollment(url: str, image_path: str, iterations: int = 10000):
        """
        Enroll the same face repeatedly and measure average enrollment time.
        Uses 'id' as query parameter per OpenAPI spec.
        """
        try:
            with open(image_path, 'rb') as f:
                img_data = f.read()
        except Exception as e:
            print(f"Failed to read image: {e}")
            sys.exit(1)

        total_time = 0.0
        success_count = 0
        timeout = Timeout(300.0)  # 5 minutes for everything
        async with AsyncClient(timeout=timeout) as client:
            for i in range(1, iterations + 1):
                unique_id = str(uuid.uuid4())
                start = time.perf_counter()
                files = {'file': ('face.jpg', img_data, 'image/jpeg')}
                data = {'name': unique_id, 'aadhaar': unique_id[:12]}
                url_with_id = f"{url}/enroll?id={unique_id}"
                try:
                    response = await client.post(url_with_id, files=files, data=data)
                    response.raise_for_status()
                except HTTPStatusError as e:
                    print(f"Error at iteration {i}: {e.response.status_code}")
                    print("Response body:", e.response.text)
                    break
                elapsed = time.perf_counter() - start
                total_time += elapsed
                success_count += 1
                if i % 10 == 0:
                    avg = total_time / success_count
                    print(f"[{i} runs] Average enrollment time: {avg:.4f} seconds")
        if success_count > 0:
            overall_avg = total_time / success_count
            print(f"\nFinal average over {success_count} successful enrollments: {overall_avg:.4f} seconds")

    # Usage: python facial_api_test.py <API_URL> <IMAGE_PATH> [ITERATIONS]
    API_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:18081"
    #IMAGE_PATH = sys.argv[2] if len(sys.argv) > 2 else "manish.jpeg"
    IMAGE_PATH = sys.argv[2] if len(sys.argv) > 2 else "/home/manish/Pictures/Women2.png"
    ITERATIONS = int(sys.argv[3]) if len(sys.argv) > 3 else 100000

    asyncio.run(measure_enrollment(API_URL, IMAGE_PATH, ITERATIONS))

