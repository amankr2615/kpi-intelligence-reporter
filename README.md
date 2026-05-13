# KPI Intelligence Reporter

This application is an AI-powered strategic business analysis tool that generates Executive Decision Memos based on marketing performance and product sales data.

## Getting Started

To securely connect to the Gemini API while keeping your key hidden from the frontend, this app uses a lightweight Python backend server.

1. **Configure API Key**
   Make sure you have a `.env` file in the root directory with your Gemini API key:
   ```env
   GEMINI_API_KEY="your_secure_api_key_here"
   ```

2. **Run the Secure Application**
   Start the backend server using Python (no complex installations required):
   ```bash
   python3 server.py
   ```
   
   The server will serve your files securely and proxy the AI requests.
   Open your browser and navigate to: **[http://localhost:8000/](http://localhost:8000/)**
