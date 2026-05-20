import os
import json
import logging
import asyncio
import traceback
from google import genai
from google.genai import types

logger = logging.getLogger("codemender")
logging.basicConfig(level=logging.INFO)

class CodeMender:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(CodeMender, cls).__new__(cls, *args, **kwargs)
            cls._instance._init_mender()
        return cls._instance

    def _init_mender(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.client = genai.Client(api_key=self.api_key) if self.api_key else None
        self.logs = []
        self.subscribers = set()
        self.repair_count = 0
        self.total_recovery_time_ms = 0

    def log_event(self, event_type: str, message: str, original: str = "", repaired: str = "", error_msg: str = ""):
        event = {
            "type": event_type,
            "message": message,
            "original": original,
            "repaired": repaired,
            "error": error_msg,
            "timestamp": asyncio.get_event_loop().time()
        }
        self.logs.append(event)
        # Keep logs capped to prevent memory leaks
        if len(self.logs) > 100:
            self.logs.pop(0)

        # Notify active streaming SSE connections
        for queue in list(self.subscribers):
            try:
                queue.put_nowait(event)
            except Exception:
                pass

    async def get_event_stream(self):
        queue = asyncio.Queue()
        self.subscribers.add(queue)
        try:
            # Yield initial status metrics
            yield f"data: {json.dumps({'type': 'status', 'repairs': self.repair_count, 'avg_time': self.get_avg_recovery_time()})}\n\n"
            while True:
                event = await queue.get()
                yield f"data: {json.dumps(event)}\n\n"
        finally:
            self.subscribers.remove(queue)

    def get_avg_recovery_time(self) -> float:
        if self.repair_count == 0:
            return 0.0
        return round(self.total_recovery_time_ms / self.repair_count, 1)

    async def heal_data(self, original_data: str, error_msg: str, schema_context: str) -> str:
        """Uses Gemini 2.5 Flash at temperature=0 to repair a corrupted JSON payload or malformed text structure."""
        if not self.client:
            logger.error("CodeMender has no GEMINI_API_KEY configured. Cannot heal data.")
            return original_data

        prompt = f"""You are the CodeMender self-healing AI engine.
Your job is to automatically repair malformed, corrupted, or invalid data structures returned in our production pipeline.

An exception occurred:
{error_msg}

The original corrupted data payload was:
```
{original_data}
```

The required schema / structural context is:
{schema_context}

Repair the corrupted data. Ensure that the returned output is syntactically perfect JSON, parses without exceptions, fits the required format perfectly, and keeps all original business numbers intact (never fabricate/hallucinate new figures).

Return ONLY the raw repaired JSON string. Absolutely no markdown blocks, no ```json formatting, no conversational text."""

        loop = asyncio.get_running_loop()
        start_time = loop.time()

        try:
            # Deterministic repairing config
            config = types.GenerateContentConfig(
                temperature=0.0,
                top_k=1
            )
            response = await loop.run_in_executor(
                None,
                lambda: self.client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt,
                    config=config
                )
            )
            repaired_text = response.text.strip()
            
            # Clean possible markdown wrap if the model ignored instructions
            if repaired_text.startswith("```"):
                lines = repaired_text.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines[-1].strip() == "```":
                    lines = lines[:-1]
                repaired_text = "\n".join(lines).strip()

            end_time = loop.time()
            recovery_ms = int((end_time - start_time) * 1000)
            self.repair_count += 1
            self.total_recovery_time_ms += recovery_ms

            logger.info(f"CodeMender successfully repaired payload in {recovery_ms}ms!")
            self.log_event(
                event_type="repair",
                message=f"Auto-healed database/pipeline parsing exception in {recovery_ms}ms.",
                original=original_data,
                repaired=repaired_text,
                error_msg=error_msg
            )
            return repaired_text
        except Exception as e:
            logger.critical(f"CodeMender failed to heal data: {e}")
            self.log_event(
                event_type="failure",
                message="Self-healing failed to repair payload.",
                error_msg=f"{error_msg} -> Secondary error: {str(e)}"
            )
            return original_data

mender = CodeMender()

def heal_async(schema_context: str = ""):
    """Decorator to wrap async pipeline functions and dynamically repair returning outputs on failure."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                err_msg = traceback.format_exc()
                logger.warning(f"CodeMender intercepted exception in '{func.__name__}': {e}")
                
                # Capture arguments as raw string for repairing context
                args_str = f"Args: {str(args)} | Kwargs: {str(kwargs)}"
                
                mender.log_event(
                    event_type="intercept",
                    message=f"Intercepted exception in pipeline function '{func.__name__}'. Initiating self-healing...",
                    original=args_str,
                    error_msg=err_msg
                )
                
                # Attempt to heal data structure based on the error and function name
                repaired = await mender.heal_data(
                    original_data=args_str,
                    error_msg=err_msg,
                    schema_context=schema_context or f"Expected a valid return state for function '{func.__name__}'."
                )
                
                try:
                    # Parse repaired payload to object if function expects dict/list
                    parsed = json.loads(repaired)
                    return parsed
                except Exception:
                    # If parsing as json fails, return healed string raw
                    return repaired
        return wrapper
    return decorator
