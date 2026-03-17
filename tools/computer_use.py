"""
JARVIS Computer Use Agent — v2.0
Upgraded with best patterns from UI-TARS-desktop (bytedance/UI-TARS-desktop)

Key improvements over v1:
  - Thought + Action format: model reasons before each action (more reliable)
  - Full UI-TARS action set: drag, press/release, call_user, finished(message)
  - Multi-action per step: model can emit multiple actions in one response
  - Click position marking: red crosshair drawn on screenshot at click coords
  - Retry logic: retries on model call failure + screenshot failure
  - Thought shown in step log for real-time AI reasoning visibility

Author: Rashi AI — Built for Akshay
Inspired by: https://github.com/bytedance/UI-TARS-desktop (Apache 2.0)
"""

import base64
import io
import re
import time
import threading
from typing import Optional, Dict, Any, List, Callable

try:
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.2
    PYAUTOGUI_AVAILABLE = True
except Exception:
    pyautogui = None
    PYAUTOGUI_AVAILABLE = False

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except Exception:
    Image = ImageDraw = ImageFont = None
    PIL_AVAILABLE = False

# Vision models — try in order (Groq)
VISION_MODELS = [
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "meta-llama/llama-4-maverick-17b-128e-instruct",
    "llama-3.2-11b-vision-preview",
]

# ── System Prompt (UI-TARS-inspired Thought+Action format) ─────────────────
SYSTEM_PROMPT = """\
You are JARVIS Computer Use Agent — an AI that controls a real computer to complete tasks.

Screen resolution: {width}x{height}
Step: {step}/{max_steps}

## Output Format
Always respond with this exact structure:
```
Thought: (describe what you see and why you chose this action)
Action: action_type(param=value, ...)
```
You may emit multiple Action lines if needed (they run in order):
```
Thought: ...
Action: click(x=200, y=300)
Action: type(text="hello")
Action: press(key="enter")
```

## Action Space
click(x=INT, y=INT)                               # left-click at pixel coords
double_click(x=INT, y=INT)                        # double-click
right_click(x=INT, y=INT)                         # right-click
drag(x1=INT, y1=INT, x2=INT, y2=INT)             # drag from (x1,y1) to (x2,y2)
type(text="STRING")                               # type text; use \\n for Enter key
press(key="STRING")                               # press one key: enter, tab, escape, backspace, delete, up, down, left, right, home, end, f5, etc.
hotkey(keys="ctrl+c")                             # keyboard shortcut, keys joined with +
scroll(x=INT, y=INT, direction="down", amount=3)  # scroll at position
wait(seconds=INT)                                 # pause (max 5s)
screenshot()                                      # take screenshot without action
finished(message="STRING")                        # task complete — provide a summary
call_user(question="STRING")                      # ask user for help (pauses agent)

## Previous Actions
{history}

## Task
{task}

Study the screenshot carefully, then output your Thought and Action(s):"""


# ── Action parser ──────────────────────────────────────────────────────────

def _parse_thought_and_actions(text: str) -> Dict:
    """
    Parse model response in Thought + Action format.
    Returns {'thought': str, 'actions': [{'type': str, 'params': dict}]}
    """
    # Extract thought
    thought_match = re.search(r'Thought\s*:\s*(.*?)(?=Action\s*:|$)', text, re.IGNORECASE | re.DOTALL)
    thought = thought_match.group(1).strip() if thought_match else ''

    # Extract all Action lines
    action_lines = re.findall(r'Action\s*:\s*(.+)', text, re.IGNORECASE)

    actions = []
    for line in action_lines:
        parsed = _parse_action_call(line.strip())
        if parsed:
            actions.append(parsed)

    return {'thought': thought, 'actions': actions}


def _parse_action_call(text: str) -> Optional[Dict]:
    """
    Parse a single action call like:
      click(x=500, y=300)
      type(text="hello world")
      hotkey(keys="ctrl+c")
      drag(x1=100, y1=200, x2=400, y2=200)
      finished(message="done")
    """
    text = text.strip()
    # Match action_name(...)
    m = re.match(r'^(\w+)\s*\((.*)\)$', text, re.DOTALL)
    if not m:
        # Fallback: bare action name
        bare = re.match(r'^(\w+)$', text)
        if bare:
            return {'type': bare.group(1).lower(), 'params': {}}
        return None

    action_type = m.group(1).lower()
    params_str = m.group(2).strip()

    params = {}
    if params_str:
        # Parse key=value pairs, handling quoted strings and numbers
        for kv in re.finditer(r'(\w+)\s*=\s*("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'|-?\d+\.?\d*)', params_str):
            key = kv.group(1)
            raw = kv.group(2)
            if raw.startswith(('"', "'")):
                # Unescape
                val = raw[1:-1].replace('\\"', '"').replace("\\'", "'").replace('\\n', '\n')
            else:
                try:
                    val = int(raw) if '.' not in raw else float(raw)
                except ValueError:
                    val = raw
            params[key] = val

    return {'type': action_type, 'params': params}


# ── Click position marker (inspired by UI-TARS markClickPosition) ──────────

def _mark_click_on_image(b64: str, x: int, y: int, img_w: int, img_h: int,
                          screen_w: int, screen_h: int) -> str:
    """Draw a red crosshair at the click position on a base64-encoded JPEG."""
    if not PIL_AVAILABLE or not b64:
        return b64
    try:
        buf = io.BytesIO(base64.b64decode(b64))
        img = Image.open(buf).convert('RGB')
        draw = ImageDraw.Draw(img)

        # Scale pixel coords → image coords
        sx = (x / screen_w) * img_w
        sy = (y / screen_h) * img_h
        cx, cy = int(sx), int(sy)
        r = max(12, int(min(img_w, img_h) * 0.02))

        # Red circle + crosshair
        draw.ellipse([cx - r, cy - r, cx + r, cy + r],
                     outline='red', width=3)
        draw.line([cx - r - 6, cy, cx + r + 6, cy], fill='red', width=2)
        draw.line([cx, cy - r - 6, cx, cy + r + 6], fill='red', width=2)
        # Filled center dot
        draw.ellipse([cx - 3, cy - 3, cx + 3, cy + 3], fill='red')

        out = io.BytesIO()
        img.save(out, format='JPEG', quality=75, optimize=True)
        return base64.b64encode(out.getvalue()).decode('utf-8')
    except Exception:
        return b64


# ══════════════════════════════════════════════════════════════════════════════
#  ComputerUseAgent
# ══════════════════════════════════════════════════════════════════════════════

class ComputerUseAgent:
    """
    Agentic loop: screenshot → vision model (Thought+Action) → execute → repeat.
    Inspired by UI-TARS-desktop's GUIAgent loop.
    """

    def __init__(self, groq_client=None):
        self.groq_client = groq_client
        self.running = False
        self.paused_for_user = False
        self.user_response: Optional[str] = None
        self.steps: List[Dict] = []
        self.current_task: Optional[str] = None
        self._stop_event = threading.Event()
        self._user_event = threading.Event()

    # ── Screenshot ───────────────────────────────────────────────────────────
    def take_screenshot(self, max_width: int = 1280) -> Optional[str]:
        """Capture screen, resize, return base64 JPEG."""
        if not PYAUTOGUI_AVAILABLE:
            return None
        for attempt in range(3):
            try:
                img = pyautogui.screenshot()
                iw, ih = img.width, img.height
                if iw > max_width:
                    ratio = max_width / iw
                    img = img.resize((max_width, int(ih * ratio)),
                                     Image.LANCZOS if PIL_AVAILABLE else Image.BILINEAR)
                buf = io.BytesIO()
                img.save(buf, format='JPEG', quality=75, optimize=True)
                return base64.b64encode(buf.getvalue()).decode('utf-8')
            except Exception:
                time.sleep(0.3)
        return None

    def get_screen_size(self):
        if PYAUTOGUI_AVAILABLE:
            try:
                return pyautogui.size()
            except Exception:
                pass
        return (1920, 1080)

    def get_image_size(self, b64: str):
        """Return (width, height) of a base64 image."""
        if not PIL_AVAILABLE or not b64:
            return (1280, 720)
        try:
            buf = io.BytesIO(base64.b64decode(b64))
            img = Image.open(buf)
            return img.size
        except Exception:
            return (1280, 720)

    # ── Vision model call ────────────────────────────────────────────────────
    def think(self, task: str, screenshot_b64: str,
              step: int, max_steps: int, history: List[str]) -> Dict:
        """Call vision model with screenshot → get Thought + Actions."""
        if not self.groq_client:
            return {'error': 'Groq client not available — set GROQ_API_KEY'}

        sw, sh = self.get_screen_size()
        history_text = '\n'.join(history[-8:]) if history else '(none yet)'

        prompt = SYSTEM_PROMPT.format(
            width=sw, height=sh,
            step=step, max_steps=max_steps,
            history=history_text,
            task=task,
        )

        image_msg = {
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{screenshot_b64}"}
        }

        last_err = ''
        for model in VISION_MODELS:
            for attempt in range(2):
                try:
                    resp = self.groq_client.chat.completions.create(
                        model=model,
                        messages=[{
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                image_msg
                            ]
                        }],
                        temperature=0.05,
                        max_tokens=600,
                    )
                    raw = resp.choices[0].message.content.strip()
                    parsed = _parse_thought_and_actions(raw)

                    if not parsed['actions']:
                        # No actions found — try to recover
                        if attempt == 0:
                            time.sleep(0.5)
                            continue
                        return {
                            'error': f'Model returned no valid actions.\nResponse: {raw[:300]}',
                            'raw': raw
                        }

                    return {
                        'thought': parsed['thought'],
                        'actions': parsed['actions'],
                        'raw': raw,
                        'model': model,
                    }
                except Exception as e:
                    last_err = str(e)
                    time.sleep(0.5)
                    continue

        return {'error': f'All vision models failed. Last: {last_err}'}

    # ── Action execution ─────────────────────────────────────────────────────
    def execute_action(self, action_type: str, params: Dict,
                       screenshot_b64: str = '') -> Dict:
        """Execute a single parsed action. Returns result dict."""
        t = action_type.lower()

        try:
            if t == 'click':
                x, y = int(params.get('x', 0)), int(params.get('y', 0))
                pyautogui.click(x, y)
                sw, sh = self.get_screen_size()
                iw, ih = self.get_image_size(screenshot_b64)
                marked = _mark_click_on_image(screenshot_b64, x, y, iw, ih, sw, sh)
                return {'success': True, 'message': f'Clicked ({x}, {y})',
                        'marked_screenshot': marked}

            elif t == 'double_click':
                x, y = int(params.get('x', 0)), int(params.get('y', 0))
                pyautogui.doubleClick(x, y)
                sw, sh = self.get_screen_size()
                iw, ih = self.get_image_size(screenshot_b64)
                marked = _mark_click_on_image(screenshot_b64, x, y, iw, ih, sw, sh)
                return {'success': True, 'message': f'Double-clicked ({x}, {y})',
                        'marked_screenshot': marked}

            elif t == 'right_click':
                x, y = int(params.get('x', 0)), int(params.get('y', 0))
                pyautogui.rightClick(x, y)
                sw, sh = self.get_screen_size()
                iw, ih = self.get_image_size(screenshot_b64)
                marked = _mark_click_on_image(screenshot_b64, x, y, iw, ih, sw, sh)
                return {'success': True, 'message': f'Right-clicked ({x}, {y})',
                        'marked_screenshot': marked}

            elif t == 'drag':
                x1 = int(params.get('x1', 0))
                y1 = int(params.get('y1', 0))
                x2 = int(params.get('x2', 0))
                y2 = int(params.get('y2', 0))
                pyautogui.moveTo(x1, y1, duration=0.3)
                pyautogui.dragTo(x2, y2, duration=0.5, button='left')
                return {'success': True, 'message': f'Dragged ({x1},{y1})→({x2},{y2})'}

            elif t == 'type':
                text = str(params.get('text', ''))
                # Use clipboard paste on Windows for reliability with special chars
                try:
                    import pyperclip
                    # Strip trailing newline for separate enter press
                    ends_with_newline = text.endswith('\n')
                    text_to_paste = text.rstrip('\n')
                    if text_to_paste:
                        pyperclip.copy(text_to_paste)
                        pyautogui.hotkey('ctrl', 'v')
                        time.sleep(0.1)
                    if ends_with_newline:
                        pyautogui.press('enter')
                except Exception:
                    pyautogui.write(text.replace('\n', ''), interval=0.03)
                    if '\n' in text:
                        pyautogui.press('enter')
                return {'success': True, 'message': f'Typed "{text[:60]}"'}

            elif t == 'press':
                key = str(params.get('key', 'enter')).lower()
                pyautogui.press(key)
                return {'success': True, 'message': f'Pressed {key}'}

            elif t == 'hotkey':
                keys_str = str(params.get('keys', 'ctrl+c'))
                keys = [k.strip() for k in re.split(r'[+\s]', keys_str) if k.strip()]
                pyautogui.hotkey(*keys)
                return {'success': True, 'message': f'Hotkey {"+".join(keys)}'}

            elif t == 'scroll':
                x = int(params.get('x', 0)) or None
                y = int(params.get('y', 0)) or None
                direction = str(params.get('direction', 'down')).lower()
                amount = int(params.get('amount', 3))
                clicks = abs(amount) if direction == 'up' else -abs(amount)
                if x and y:
                    pyautogui.scroll(clicks, x=x, y=y)
                else:
                    pyautogui.scroll(clicks)
                return {'success': True, 'message': f'Scrolled {direction} {abs(amount)}'}

            elif t == 'wait':
                secs = min(float(params.get('seconds', 2)), 5.0)
                time.sleep(secs)
                return {'success': True, 'message': f'Waited {secs}s'}

            elif t == 'screenshot':
                return {'success': True, 'message': 'Screenshot taken'}

            elif t == 'finished':
                msg = str(params.get('message', 'Task complete'))
                return {'success': True, 'done': True, 'message': msg}

            elif t == 'call_user':
                question = str(params.get('question', 'I need your help to continue.'))
                return {'success': True, 'call_user': True, 'question': question}

            else:
                return {'success': False, 'error': f'Unknown action: {t}'}

        except Exception as e:
            return {'success': False, 'error': str(e)}

    # ── Control ──────────────────────────────────────────────────────────────
    def stop(self):
        self._stop_event.set()
        self._user_event.set()
        self.running = False

    def provide_user_response(self, response: str):
        """Called from main thread when user responds to call_user()."""
        self.user_response = response
        self.paused_for_user = False
        self._user_event.set()

    # ── Main loop ────────────────────────────────────────────────────────────
    def run(
        self,
        task: str,
        max_steps: int = 25,
        on_step: Optional[Callable] = None,
        on_screenshot: Optional[Callable] = None,
        on_call_user: Optional[Callable] = None,
    ) -> Dict:
        """
        Run the computer use agent loop.

        Callbacks:
          on_step(step_dict)           — after each step
          on_screenshot(b64, step_num) — right after screenshot
          on_call_user(question)       — when model calls call_user()
        """
        self.running = True
        self._stop_event.clear()
        self._user_event.clear()
        self.current_task = task
        self.steps = []
        history: List[str] = []

        if not PYAUTOGUI_AVAILABLE:
            return {
                'success': False,
                'error': (
                    'pyautogui is not available in this environment.\n'
                    'Computer Use requires JARVIS to run locally on your Windows/Mac/Linux machine.\n'
                    'Install JARVIS with JARVIS-Setup.bat, then run it on your own computer.'
                ),
                'steps': []
            }

        for step_num in range(1, max_steps + 1):
            if self._stop_event.is_set():
                return {'success': False, 'stopped': True, 'steps': self.steps}

            # 1. Take screenshot (with retry)
            screenshot_b64 = self.take_screenshot()
            if not screenshot_b64:
                err = 'Screenshot failed after 3 attempts'
                self._emit_step(on_step, {'step': step_num, 'error': err, 'screenshot': ''})
                self.running = False
                return {'success': False, 'error': err, 'steps': self.steps}

            if on_screenshot:
                on_screenshot(screenshot_b64, step_num)

            # 2. Think (with retry built-in)
            think_result = self.think(task, screenshot_b64, step_num, max_steps, history)

            if 'error' in think_result:
                step_info = {
                    'step': step_num, 'error': think_result['error'],
                    'screenshot': screenshot_b64,
                }
                self._emit_step(on_step, step_info)
                self.running = False
                return {'success': False, 'error': think_result['error'], 'steps': self.steps}

            if self._stop_event.is_set():
                return {'success': False, 'stopped': True, 'steps': self.steps}

            thought = think_result.get('thought', '')
            actions = think_result.get('actions', [])

            # 3. Execute each action in this step
            current_screenshot = screenshot_b64
            step_results = []
            done = False
            need_user = False
            user_question = ''

            for action in actions:
                if self._stop_event.is_set():
                    break

                atype = action['type']
                aparams = action['params']

                result = self.execute_action(atype, aparams, current_screenshot)

                # Use marked screenshot if available
                if result.get('marked_screenshot'):
                    current_screenshot = result.pop('marked_screenshot')

                step_results.append({'type': atype, 'params': aparams, 'result': result})

                # Update history
                status = result.get('message') or result.get('error', '')
                history.append(
                    f"Step {step_num} [{atype}({_fmt_params(aparams)})]: {status}"
                )

                if result.get('done'):
                    done = True
                    break
                if result.get('call_user'):
                    need_user = True
                    user_question = result.get('question', 'I need your help.')
                    break

                time.sleep(0.3)

            # Emit step info
            step_info = {
                'step': step_num,
                'thought': thought,
                'actions': step_results,
                'model': think_result.get('model', ''),
                'screenshot': current_screenshot,
            }
            self._emit_step(on_step, step_info)

            # Handle call_user
            if need_user:
                if on_call_user:
                    on_call_user(user_question)
                self.paused_for_user = True
                self._user_event.clear()
                self._user_event.wait(timeout=120)  # wait up to 2 minutes for user
                if self._stop_event.is_set():
                    return {'success': False, 'stopped': True, 'steps': self.steps}
                if self.user_response:
                    history.append(f"User responded: {self.user_response}")
                    self.user_response = None
                continue

            if done:
                msg = step_results[-1]['result'].get('message', 'Task complete') if step_results else 'Done'
                self.running = False
                return {'success': True, 'message': msg, 'steps': self.steps}

            if self._stop_event.is_set():
                return {'success': False, 'stopped': True, 'steps': self.steps}

            time.sleep(0.5)

        self.running = False
        return {
            'success': False,
            'error': f'Reached the {max_steps}-step limit without completing the task.',
            'steps': self.steps
        }

    def _emit_step(self, on_step, step_info):
        self.steps.append(step_info)
        if on_step:
            on_step(step_info)


# ── Helpers ────────────────────────────────────────────────────────────────

def _fmt_params(params: Dict) -> str:
    """Format params dict as readable string for history log."""
    parts = []
    for k, v in params.items():
        val = str(v)
        if len(val) > 40:
            val = val[:37] + '...'
        parts.append(f'{k}={val}')
    return ', '.join(parts)
