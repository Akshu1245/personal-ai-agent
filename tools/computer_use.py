"""
JARVIS Computer Use Agent
Inspired by UI-TARS — See the screen, take action, accomplish tasks.

How it works:
  1. Take a screenshot of the user's screen
  2. Send it to a Groq vision model with the task description
  3. Model responds with a JSON action (click, type, press, scroll, done...)
  4. Execute the action with pyautogui
  5. Repeat until task is done or max_steps reached

Author: Rashi AI — Built for Akshay
"""

import base64
import io
import json
import re
import time
import threading
from typing import Optional, Dict, Any, List, Callable

try:
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.25
    PYAUTOGUI_AVAILABLE = True
except Exception:
    pyautogui = None
    PYAUTOGUI_AVAILABLE = False

try:
    from PIL import Image
    PIL_AVAILABLE = True
except Exception:
    Image = None
    PIL_AVAILABLE = False

VISION_MODELS = [
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "llama-3.2-11b-vision-preview",
]

SYSTEM_PROMPT_TEMPLATE = """You are JARVIS Computer Use Agent — an AI that controls a real computer screen to complete tasks.

Screen resolution: {width}x{height}
Step: {step}/{max_steps}

Previous actions:
{history}

Your job: Look at the screenshot and decide the SINGLE best next action to accomplish the task.

RESPOND WITH ONLY A JSON OBJECT — no explanation, no markdown, just the JSON.

Available actions:
  {{"type": "click", "x": 500, "y": 300, "description": "click the Search button"}}
  {{"type": "double_click", "x": 500, "y": 300, "description": "open the file"}}
  {{"type": "right_click", "x": 500, "y": 300, "description": "open context menu"}}
  {{"type": "type", "text": "hello world", "description": "type the search query"}}
  {{"type": "press", "key": "enter", "description": "confirm input"}}
  {{"type": "hotkey", "keys": ["ctrl", "c"], "description": "copy selected text"}}
  {{"type": "scroll", "x": 500, "y": 400, "direction": "down", "amount": 3, "description": "scroll down"}}
  {{"type": "move", "x": 500, "y": 300, "description": "hover over element"}}
  {{"type": "wait", "seconds": 1, "description": "wait for page to load"}}
  {{"type": "done", "message": "Task completed: opened the file"}}

Task: {task}

Respond with JSON only:"""


class ComputerUseAgent:
    """Agentic loop: screenshot → vision model → action → execute → repeat"""

    def __init__(self, groq_client=None):
        self.groq_client = groq_client
        self.running = False
        self.steps: List[Dict] = []
        self.current_task: Optional[str] = None
        self._stop_event = threading.Event()

    # ── Screenshot ─────────────────────────────────────────────────
    def take_screenshot(self, max_width: int = 1280) -> Optional[str]:
        """Capture screen, resize, return base64-encoded PNG string."""
        if not PYAUTOGUI_AVAILABLE:
            return None
        try:
            img = pyautogui.screenshot()
            if img.width > max_width:
                ratio = max_width / img.width
                new_h = int(img.height * ratio)
                if PIL_AVAILABLE:
                    img = img.resize((max_width, new_h), Image.LANCZOS)
                else:
                    img = img.resize((max_width, new_h))
            buf = io.BytesIO()
            img.save(buf, format='JPEG', quality=75, optimize=True)
            return base64.b64encode(buf.getvalue()).decode('utf-8')
        except Exception:
            return None

    def get_screen_size(self):
        if PYAUTOGUI_AVAILABLE:
            try:
                return pyautogui.size()
            except Exception:
                pass
        return (1920, 1080)

    # ── Action execution ────────────────────────────────────────────
    def execute_action(self, action: Dict) -> Dict:
        """Execute a parsed action dict using pyautogui."""
        t = action.get('type', '').lower()
        try:
            if t == 'click':
                pyautogui.click(int(action['x']), int(action['y']))
                return {'success': True, 'message': f'Clicked ({action["x"]}, {action["y"]})'}

            elif t == 'double_click':
                pyautogui.doubleClick(int(action['x']), int(action['y']))
                return {'success': True, 'message': f'Double-clicked ({action["x"]}, {action["y"]})'}

            elif t == 'right_click':
                pyautogui.rightClick(int(action['x']), int(action['y']))
                return {'success': True, 'message': f'Right-clicked ({action["x"]}, {action["y"]})'}

            elif t == 'type':
                text = str(action.get('text', ''))
                pyautogui.write(text, interval=0.03)
                return {'success': True, 'message': f'Typed "{text[:50]}"'}

            elif t == 'press':
                key = action.get('key', 'enter')
                pyautogui.press(str(key))
                return {'success': True, 'message': f'Pressed {key}'}

            elif t == 'hotkey':
                keys = action.get('keys', [])
                if isinstance(keys, str):
                    keys = [k.strip() for k in keys.split('+')]
                pyautogui.hotkey(*keys)
                return {'success': True, 'message': f'Hotkey {"+".join(keys)}'}

            elif t == 'scroll':
                x = action.get('x')
                y = action.get('y')
                direction = action.get('direction', 'down')
                amount = int(action.get('amount', 3))
                clicks = abs(amount) if direction == 'up' else -abs(amount)
                if x is not None and y is not None:
                    pyautogui.scroll(clicks, x=int(x), y=int(y))
                else:
                    pyautogui.scroll(clicks)
                return {'success': True, 'message': f'Scrolled {direction} {abs(amount)}'}

            elif t == 'move':
                pyautogui.moveTo(int(action['x']), int(action['y']), duration=0.3)
                return {'success': True, 'message': f'Moved to ({action["x"]}, {action["y"]})'}

            elif t == 'wait':
                secs = min(float(action.get('seconds', 1)), 5.0)
                time.sleep(secs)
                return {'success': True, 'message': f'Waited {secs}s'}

            elif t == 'done':
                return {'success': True, 'done': True, 'message': action.get('message', 'Task complete')}

            else:
                return {'success': False, 'error': f'Unknown action type: {t}'}

        except Exception as e:
            return {'success': False, 'error': str(e)}

    # ── Vision model call ────────────────────────────────────────────
    def _parse_action(self, text: str) -> Optional[Dict]:
        """Extract a JSON action object from model response text."""
        for pattern in [r'```json\s*(.*?)```', r'```\s*(.*?)```']:
            m = re.search(pattern, text, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group(1).strip())
                except Exception:
                    pass
        m = re.search(r'\{.*\}', text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
        return None

    def think(self, task: str, screenshot_b64: str, step: int, max_steps: int, history: List[str]) -> Dict:
        """Call vision model with screenshot and get next action."""
        if not self.groq_client:
            return {'error': 'Groq client not available — set your GROQ_API_KEY'}

        w, h = self.get_screen_size()
        history_text = '\n'.join(history[-6:]) if history else '(none yet)'

        prompt = SYSTEM_PROMPT_TEMPLATE.format(
            width=w, height=h,
            step=step, max_steps=max_steps,
            history=history_text,
            task=task,
        )

        image_content = {
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{screenshot_b64}"}
        }

        for model in VISION_MODELS:
            try:
                resp = self.groq_client.chat.completions.create(
                    model=model,
                    messages=[{
                        "role": "user",
                        "content": [{"type": "text", "text": prompt}, image_content]
                    }],
                    temperature=0.1,
                    max_tokens=400,
                )
                raw = resp.choices[0].message.content.strip()
                action = self._parse_action(raw)
                if action:
                    return {'action': action, 'raw': raw, 'model': model}
                return {'error': f'Could not parse JSON from model response:\n{raw[:300]}', 'raw': raw}
            except Exception as e:
                last_err = str(e)
                continue

        return {'error': f'All vision models failed. Last error: {last_err}'}

    # ── Main agent loop ──────────────────────────────────────────────
    def stop(self):
        self._stop_event.set()
        self.running = False

    def run(
        self,
        task: str,
        max_steps: int = 25,
        on_step: Optional[Callable] = None,
        on_screenshot: Optional[Callable] = None,
    ) -> Dict:
        """
        Run the computer use agent loop.

        Args:
            task: Natural language task description
            max_steps: Safety limit on number of steps
            on_step: callback(step_dict) — called after each step
            on_screenshot: callback(b64, step_num) — called right after screenshot
        """
        self.running = True
        self._stop_event.clear()
        self.current_task = task
        self.steps = []
        history: List[str] = []

        if not PYAUTOGUI_AVAILABLE:
            return {
                'success': False,
                'error': (
                    'pyautogui is not available in this environment. '
                    'Computer Use requires JARVIS to run locally on your machine. '
                    'Install JARVIS using JARVIS-Setup.bat and run it on your Windows PC.'
                ),
                'steps': []
            }

        for step_num in range(1, max_steps + 1):
            if self._stop_event.is_set():
                return {'success': False, 'stopped': True, 'steps': self.steps}

            # 1. Screenshot
            screenshot_b64 = self.take_screenshot()
            if not screenshot_b64:
                return {'success': False, 'error': 'Screenshot failed', 'steps': self.steps}

            if on_screenshot:
                on_screenshot(screenshot_b64, step_num)

            # 2. Think
            think_result = self.think(task, screenshot_b64, step_num, max_steps, history)

            if 'error' in think_result:
                step_info = {
                    'step': step_num, 'error': think_result['error'],
                    'screenshot': screenshot_b64
                }
                self.steps.append(step_info)
                if on_step:
                    on_step(step_info)
                self.running = False
                return {'success': False, 'error': think_result['error'], 'steps': self.steps}

            action = think_result['action']
            description = action.get('description', action.get('type', 'action'))

            if self._stop_event.is_set():
                return {'success': False, 'stopped': True, 'steps': self.steps}

            # 3. Execute
            action_result = self.execute_action(action)
            status = action_result.get('message') or action_result.get('error', '')
            history.append(f"Step {step_num} [{action.get('type')}]: {description} → {status}")

            step_info = {
                'step': step_num,
                'action': action,
                'result': action_result,
                'description': description,
                'model': think_result.get('model', ''),
                'screenshot': screenshot_b64,
            }
            self.steps.append(step_info)

            if on_step:
                on_step(step_info)

            # 4. Check completion
            if action.get('type') == 'done' or action_result.get('done'):
                self.running = False
                return {
                    'success': True,
                    'message': action.get('message', 'Task completed'),
                    'steps': self.steps
                }

            time.sleep(0.5)

        self.running = False
        return {
            'success': False,
            'error': f'Reached the {max_steps}-step limit without completing the task.',
            'steps': self.steps
        }
