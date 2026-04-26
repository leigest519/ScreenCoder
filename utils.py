import os
import time
import base64
import io
from PIL import Image, ImageDraw
import cv2
import numpy as np


def _missing_dependency(package_name, install_name=None):
    install_name = install_name or package_name
    raise ModuleNotFoundError(
        f"Missing optional provider dependency '{package_name}'. "
        f"Install it with `pip install {install_name}` before using this provider."
    )


def encode_image(image):
    if type(image) == str:
        try: 
            with open(image, "rb") as image_file:
                encoding = base64.b64encode(image_file.read()).decode('utf-8')
        except Exception as e:
            print(e)
            with open(image, "r", encoding="utf-8") as image_file:
                encoding = base64.b64encode(image_file.read()).decode('utf-8')
        return encoding
    
    else:
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode('utf-8')

def image_mask(image_path: str, bbox_normalized: tuple[int, int, int, int]) -> Image.Image:
    """Creates a mask on the image in the specified normalized bounding box."""
    image = Image.open(image_path)
    masked_image = image.copy()
    
    w, h = image.size
    
    # Convert normalized coordinates to pixel coordinates for drawing
    bbox_pixels = (
        int(bbox_normalized[0] * w / 1000),
        int(bbox_normalized[1] * h / 1000),
        int(bbox_normalized[2] * w / 1000),
        int(bbox_normalized[3] * h / 1000)
    )
    
    draw = ImageDraw.Draw(masked_image)
    draw.rectangle(bbox_pixels, fill=(255, 255, 255))  # Pure white
    
    return masked_image

def projection_analysis(image_path: str, bbox_normalized: tuple[int, int, int, int]) -> dict:
    """
    Performs projection analysis on a specified normalized bounding box area.
    All returned coordinates are also normalized.
    """
    image = cv2.imread(image_path)
    if image is None:
        print(f"Error: Failed to read image {image_path}")
        return {}
    
    h, w = image.shape[:2]
    
    # Convert normalized bbox to pixel coordinates for cropping
    bbox_pixels = (
        int(bbox_normalized[0] * w / 1000),
        int(bbox_normalized[1] * h / 1000),
        int(bbox_normalized[2] * w / 1000),
        int(bbox_normalized[3] * h / 1000)
    )
    
    x1, y1, x2, y2 = bbox_pixels
    roi = image[y1:y2, x1:x2]
    
    if roi.size == 0:
        print(f"Error: Invalid bbox region {bbox_pixels}")
        return {}
    
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    # Perform projection analysis (this part operates on pixels within the ROI)
    horizontal_projection = np.sum(binary, axis=1)
    vertical_projection = np.sum(binary, axis=0)
    
    # Find groups and convert their coordinates back to normalized space
    horizontal_groups = _find_groups_and_normalize(horizontal_projection, 'horizontal', bbox_normalized, w, h)
    vertical_groups = _find_groups_and_normalize(vertical_projection, 'vertical', bbox_normalized, w, h)
    
    return {
        'horizontal_groups': horizontal_groups,
        'vertical_groups': vertical_groups,
        'bbox_normalized': bbox_normalized,
    }

def _find_groups_and_normalize(projection: np.ndarray, direction: str, 
                               bbox_normalized: tuple[int, int, int, int],
                               image_width: int, image_height: int,
                               min_group_size_px: int = 5, threshold_ratio: float = 0.1) -> list:
    """
    Finds contiguous groups from projection data and returns them in normalized coordinates.
    """
    threshold = np.max(projection) * threshold_ratio
    non_zero_indices = np.where(projection > threshold)[0]
    
    if len(non_zero_indices) == 0:
        return []
    
    groups_px = []
    start_px = non_zero_indices[0]
    for i in range(1, len(non_zero_indices)):
        if non_zero_indices[i] > non_zero_indices[i-1] + 1:
            if non_zero_indices[i-1] - start_px >= min_group_size_px:
                groups_px.append((start_px, non_zero_indices[i-1]))
            start_px = non_zero_indices[i]
    if non_zero_indices[-1] - start_px >= min_group_size_px:
        groups_px.append((start_px, non_zero_indices[-1]))
    
    # Convert pixel groups (relative to ROI) to normalized coordinates (relative to full image)
    norm_groups = []
    roi_x1_norm, roi_y1_norm, roi_x2_norm, roi_y2_norm = bbox_normalized
    roi_w_norm = roi_x2_norm - roi_x1_norm
    roi_h_norm = roi_y2_norm - roi_y1_norm

    roi_w_px = int(roi_w_norm * image_width / 1000)
    roi_h_px = int(roi_h_norm * image_height / 1000)

    for start_px, end_px in groups_px:
        if direction == 'horizontal':
            start_norm = roi_y1_norm + int(start_px * roi_h_norm / roi_h_px)
            end_norm = roi_y1_norm + int(end_px * roi_h_norm / roi_h_px)
            norm_groups.append((roi_x1_norm, roi_x2_norm, start_norm, end_norm))
        else: # vertical
            start_norm = roi_x1_norm + int(start_px * roi_w_norm / roi_w_px)
            end_norm = roi_x1_norm + int(end_px * roi_w_norm / roi_w_px)
            norm_groups.append((start_norm, end_norm, roi_y1_norm, roi_y2_norm))
            
    return norm_groups

def visualize_projection_analysis(image_path: str, analysis_result: dict, 
                                 save_path: str = None) -> str:
    """
    Visualizes the results of a completed projection analysis.
    This function takes the analysis result dictionary and draws it on the image.
    """
    if not analysis_result:
        print("Error: Analysis result is empty.")
        return ""
    
    image = cv2.imread(image_path)
    if image is None:
        print(f"Error: Failed to read image for visualization: {image_path}")
        return ""
        
    h, w = image.shape[:2]
    vis_image = image.copy()
    
    bbox_normalized = analysis_result.get('bbox_normalized')
    if not bbox_normalized:
        print("Error: 'bbox_normalized' not found in analysis result.")
        return ""

    # Convert normalized bbox to pixel coordinates for drawing the main ROI
    x1, y1, x2, y2 = (
        int(bbox_normalized[0] * w / 1000),
        int(bbox_normalized[1] * h / 1000),
        int(bbox_normalized[2] * w / 1000),
        int(bbox_normalized[3] * h / 1000)
    )
    cv2.rectangle(vis_image, (x1, y1), (x2, y2), (0, 255, 0), 2) # Green for main ROI
    
    # Draw horizontal groups (Blue)
    for i, group_norm in enumerate(analysis_result.get('horizontal_groups', [])):
        g_x1, g_y1, g_x2, g_y2 = (
            int(group_norm[0] * w / 1000),
            int(group_norm[1] * h / 1000),
            int(group_norm[2] * w / 1000),
            int(group_norm[3] * h / 1000)
        )
        cv2.rectangle(vis_image, (g_x1, g_y1), (g_x2, g_y2), (255, 0, 0), 1)
        cv2.putText(vis_image, f'H{i}', (g_x1, g_y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
        
    # Draw vertical groups (Red)
    for i, group_norm in enumerate(analysis_result.get('vertical_groups', [])):
        g_x1, g_y1, g_x2, g_y2 = (
            int(group_norm[0] * w / 1000),
            int(group_norm[1] * h / 1000),
            int(group_norm[2] * w / 1000),
            int(group_norm[3] * h / 1000)
        )
        cv2.rectangle(vis_image, (g_x1, g_y1), (g_x2, g_y2), (0, 0, 255), 1)
        cv2.putText(vis_image, f'V{i}', (g_x1, g_y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)

    if save_path is None:
        base_name = os.path.splitext(os.path.basename(image_path))[0]
        save_path = f"data/{base_name}_projection_analysis.png"
    
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    
    if cv2.imwrite(save_path, vis_image):
        print(f"Projection analysis visualization saved to: {save_path}")
        return save_path
    else:
        print("Error: Failed to save visualization")
        return ""



class Bot:
    def __init__(self, key_path, patience=3) -> None:
        if os.path.exists(key_path):
            with open(key_path, "r") as f:
                self.key = f.read().replace("\n", "")
        else:
            self.key = key_path
        self.patience = patience
    
    def ask(self):
        raise NotImplementedError
    
    def try_ask(self, question, image_encoding=None, verbose=False):
        for i in range(self.patience):
            try:
                return self.ask(question, image_encoding, verbose)
            except Exception as e:
                print(e, "waiting for 5 seconds")
                time.sleep(5)
        return None

class Doubao(Bot):
    def __init__(self, key_path, patience=3, model="doubao-1.5-thinking-vision-pro-250428") -> None:
        super().__init__(key_path, patience)
        try:
            from volcenginesdkarkruntime import Ark
        except ModuleNotFoundError:
            _missing_dependency("volcenginesdkarkruntime", "volcengine-python-sdk[ark]")
        self.client = Ark(api_key=self.key)
        self.model = model
    
    def ask(self, question, image_encoding=None, verbose=False):

        if image_encoding:
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": question},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_encoding}",
                            },
                        },
                    ],
                }
            ]
        else:
            messages = [{"role": "user", "content": question}]
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=4096,
            temperature=0,
        )
        response = response.choices[0].message.content
        if verbose:
            print("####################################")
            print("question:\n", question)
            print("####################################")
            print("response:\n", response)
            # print("seed used: 42")
            # img = base64.b64decode(image_encoding)
            # img = Image.open(io.BytesIO(img))
            # img.show()
        return response

class Qwen(Bot):
    def __init__(self, key_path, patience=3, model="qwen2.5-vl-32b-instruct") -> None:
        super().__init__(key_path, patience)
        try:
            from openai import OpenAI
        except ModuleNotFoundError:
            _missing_dependency("openai")
        self.client = OpenAI(api_key=self.key, base_url="https://dashscope.aliyuncs.com/compatible-mode/v1")
        self.name = model

    def ask(self, question, image_encoding=None, verbose=False):
        if image_encoding:
            content = {
                "role": "user",
                "content": [
                    {"type": "text", "text": question},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_encoding}"
                        }
                    }
                ]
            }
        else:
            content = {"role": "user", "content": question} 
        
        response = self.client.chat.completions.create(
            model=self.name,
            messages=[content],
            max_tokens=4096,
            temperature=0,
            seed=42,
        )
        response = response.choices[0].message.content
        if verbose:
            print("####################################")
            print("question:\n", question)
            print("####################################")
            print("response:\n", response)
            print("seed used: 42")
        return response

class GPT(Bot):
    def __init__(self, key_path, patience=3, model="gpt-4o") -> None:
        super().__init__(key_path, patience)
        try:
            from openai import OpenAI
        except ModuleNotFoundError:
            _missing_dependency("openai")
        self.client = OpenAI(api_key=self.key)
        self.name="gpt4"
        self.model = model
        
    def ask(self, question, image_encoding=None, verbose=False):
        
        if image_encoding:
            content =    {
            "role": "user",
            "content": [
                {"type": "text", "text": question},
                {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{image_encoding}",
                },
                },
            ],
            }
        else:
            content = {"role": "user", "content": question}
        response = self.client.chat.completions.create(
        model=self.model,
        messages=[
         content
        ],
        max_tokens=4096,
        temperature=0,
        seed=42,
        )
        response = response.choices[0].message.content
        if verbose:
            print("####################################")
            print("question:\n", question)
            print("####################################")
            print("response:\n", response)
            print("seed used: 42")
            # img = base64.b64decode(image_encoding)
            # img = Image.open(io.BytesIO(img))
            # img.show()
        return response

class Gemini(Bot):
    def __init__(self, key_path, patience=3, model="gemini-1.5-flash-latest") -> None:
        super().__init__(key_path, patience)
        try:
            import google.generativeai as genai
        except ModuleNotFoundError:
            _missing_dependency("google.generativeai", "google-generativeai")
        GOOGLE_API_KEY= self.key
        genai.configure(api_key=GOOGLE_API_KEY)
        self.name = "Gemini"
        self.model = model
        self.file_count = 0
        
    def ask(self, question, image_encoding=None, verbose=False):
        model = genai.GenerativeModel(self.model)

        if verbose:
            print(f"##################{self.file_count}##################")
            print("question:\n", question)

        if image_encoding:
            img = base64.b64decode(image_encoding)
            img = Image.open(io.BytesIO(img))
            response = model.generate_content([question, img], request_options={"timeout": 3000}) 
        else:    
            response = model.generate_content(question, request_options={"timeout": 3000})

        if verbose:
            print("####################################")
            print("response:\n", response.text)
            self.file_count += 1

        return response.text
