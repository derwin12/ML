# grok3api_example.py
from grok3api.client import GrokClient
import json


def main():
    # Initialize the client
    # Optional params: history_msg_count (for conversation memory), always_new_conversation (start fresh each time)
    client = GrokClient(
        history_msg_count=5,  # Keep last 5 messages in history
        always_new_conversation=False  # Reuse conversation from grok.com (if logged in via browser)
    )

    # Optional: Set a system prompt for all responses
    client.history.set_main_system_prompt("You are a music analyst. Respond in concise JSON only.")

    # Send a request to Grok-3
    prompt = """
    Generate a song structure for "Pretty Baby" by Alex Sampson (206 seconds duration).
    Output strict JSON: {"structure": [{"section": "Intro", "start": 0.0, "end": 15.0}, ...]}
    Ensure no gaps/overlaps and full coverage.
    """

    result = client.ask(
        message=prompt,
        modelName="grok-3"  # Default is grok-3; can use "grok-2" if needed
        # Optional: images=["path/to/image.jpg"] for vision tasks (e.g., analyze album art)
    )

    # Print the response
    print("Grok-3 Response:")
    print(result)  # Full result object (includes content, images if any)

    # Extract and parse JSON from response (assuming it's in result.content)
    try:
        structure_data = json.loads(result.content)
        print("\nParsed Structure:")
        print(json.dumps(structure_data, indent=2))
    except json.JSONDecodeError:
        print("\nRaw Content (non-JSON):")
        print(result.content)


if __name__ == "__main__":
    main()