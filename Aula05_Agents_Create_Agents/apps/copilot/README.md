# AI Workflow Copilot

A Flask-based application that helps design and manage multi-agent AI systems for customer support.

## Prerequisites

- Python 3.8+
- OpenAI API key

## Installation

1. Clone the repository:
2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows, use: venv\Scripts\activate
```

3. Install required dependencies:
```bash
pip install -r requirements.txt
```

4. Set up your OpenAI API key:
```bash
export OPENAI_API_KEY='your-api-key-here'  # On Windows, use: set OPENAI_API_KEY=your-api-key-here
export API_KEY='test-api-key' # set a shared API key for the application
```

## Running the Application

1. Start the Flask server:
```bash
python app.py
```

The server will start on `http://localhost:3002`

## API Usage

The application exposes a single endpoint at `/chat` that accepts POST requests.

### Example Request:
```bash
curl -X POST http://localhost:3002/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer test-api-key" \
  -d '{
    "messages": [
      {
        "role": "user",
        "content": "Your message here"
      }
    ],
    "workflow_schema": "Your workflow schema here",
    "current_workflow_config": "Your current workflow configuration here"
  }'
```

### Example Response:
```json
{
  "response": "Assistant's response here"
}
```

## Error Handling

The API returns appropriate HTTP status codes:
- 400: Invalid request format or data
- 500: Internal server error

## Development

To run the server in debug mode, ensure `debug=True` is set in `app.py` (already included).

## License

[Add your license information here] 