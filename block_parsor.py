# Unified API key config
from api_config import get_api_key, ApiService
import os
import cv2
import json
from utils import Doubao, Qwen, GPT, Gemini, encode_image, image_mask

DEFAULT_IMAGE_PATH = "data/input/test1.png"

# Get Doubao API key from unified config
DEFAULT_API_KEY = get_api_key(ApiService.DOUBAO)

# We provide prompts in both Chinese and English.
PROMPT_MERGE = "Return the bounding boxes of the sidebar, main content, header, and navigation in this webpage screenshot. Please only return the corresponding bounding boxes. Note: 1. The areas should not overlap; 2. All text information and other content should be framed inside; 3. Try to keep it compact without leaving a lot of blank space; 4. Output a label and the corresponding bounding box for each line."
# PROMPT_MERGE = "框出网页中的sidebar，main content，header，navigation的位置，请你只返回对应的bounding box，注意：1.各个区域不要重叠；2.所有的文字信息等内容都要框在里面；3.尽量保证紧凑，不留大量空白区域；4.每行输出标签以及对应的bounding box：<bbox>x1 y1 x2 y2</bbox>。"
BBOX_TAG_START = "<bbox>"
BBOX_TAG_END = "</bbox>"

# Additional option: use sequential_component_detection for block parsing.
# PROMPT_LIST = [
#     ("header", "Please output the minimum bounding box of the header. Please output the bounding box in the format of <bbox>x1 y1 x2 y2</bbox>. Avoid the blank space in the header."),
#     ("sidebar", "Please output the minimum bounding box of the sidebar. Please output the bounding box in the format of <bbox>x1 y1 x2 y2</bbox>. Avoid meaningless blank space in the sidebar."),
#     ("navigation", "Please output the minimum bounding box of the navigation. Please output the bounding box in the format of <bbox>x1 y1 x2 y2</bbox>. Avoid the blank space in the navigation."),
#     ("main content", "Please output the minimum bounding box of the main content. Please output the bounding box in the format of <bbox>x1 y1 x2 y2</bbox>. Avoid the blank space in the main content."),
# ]

# PROMPT_LIST = [
#     ("header", "请输出header（页眉）的最小外接框。请按照 <bbox>x1 y1 x2 y2</bbox> 的格式输出边界框。请避免header中的空白区域。"),
#     ("sidebar", "请输出sidebar（侧边栏）的最小外接框。请按照 <bbox>x1 y1 x2 y2</bbox> 的格式输出边界框。请避免sidebar中无意义的空白区域。"),
#     ("navigation", "请输出navigation（导航栏）的最小外接框。请按照 <bbox>x1 y1 x2 y2</bbox> 的格式输出边界框。请避免navigation中的空白区域。"),
#     ("main content", "请输出main content（主内容区）的最小外接框。请按照 <bbox>x1 y1 x2 y2</bbox> 的格式输出边界框。请避免main content中的空白区域。"),
# ]


def resolve_containment(bboxes: dict[str, tuple[int, int, int, int]]) -> dict[str, tuple[int, int, int, int]]:
    """
    Resolves containment issues among bounding boxes.
    If a box is found to be fully contained within another, it is removed.
    This is based on the assumption that major layout components should not contain each other.
    """

    def contains(box_a, box_b):
        """Checks if box_a completely contains box_b."""
        xa1, ya1, xa2, ya2 = box_a
        xb1, yb1, xb2, yb2 = box_b
        return xa1 <= xb1 and ya1 <= yb1 and xa2 >= xb2 and ya2 >= yb2

    names = list(bboxes.keys())
    removed = set()

    for i in range(len(names)):
        for j in range(len(names)):
            if i == j or names[i] in removed or names[j] in removed:
                continue

            name1, box1 = names[i], bboxes[names[i]]
            name2, box2 = names[j], bboxes[names[j]]

            if contains(box1, box2) or contains(box2, box1):
                print(
                    f"Containment found: '{name1}' contains '{name2}'. Removing '{name2}'.")
                removed.add(name2)

    return {name: bbox for name, bbox in bboxes.items() if name not in removed}

# def resolve_overlap(bboxes: dict[str, tuple[int, int, int, int]]) -> dict[str, tuple[int, int, int, int]]:
#     """
#     Resolves overlap issues among bounding boxes.
#     If two boxes overlap, crop the smaller one and keep the larger one.
#     Return the bboxes with the smaller one cropped.
#     """
#     names = list(bboxes.keys())
#     removed = set()

#     for i in range(len(names)):
#         for j in range(len(names)):
#             if i == j or names[i] in removed or names[j] in removed:
#                 continue

#             box1, box2 = bboxes[names[i]], bboxes[names[j]]
#             iou_score = iou(box1, box2)
#             if iou_score > 0:
#                 if box1[2] - box1[0] < box2[2] - box2[0] or (box1[2] - box1[0] == box2[2] - box2[0] and box1[3] - box1[1] < box2[3] - box2[1]):
#                     removed.add(names[i])
#                 else:
#                     removed.add(names[j])

#     return {name: bbox for name, bbox in bboxes.items() if name not in removed}

# def iou(box1, box2):
#     """Calculate Intersection over Union (IoU) between two bounding boxes"""
#     x1, y1, x2, y2 = box1
#     x3, y3, x4, y4 = box2
#     intersection_area = max(0, min(x2, x4) - max(x1, x3)) * max(0, min(y2, y4) - max(y1, y3))
#     box1_area = (x2 - x1) * (y2 - y1)
#     box2_area = (x4 - x3) * (y4 - y3)
#     return intersection_area / (box1_area + box2_area - intersection_area)

# simple version of bbox parsing


def parse_bboxes(bbox_input: str, image_path: str) -> dict[str, tuple[int, int, int, int]]:
    """Parse bounding box string to dictionary of named coordinate tuples"""
    bboxes = {}
    # print("Raw bbox input:", bbox_input) # Debug print

    image = cv2.imread(image_path)
    if image is None:
        print(f"Error: Failed to read image {image_path}")
        return bboxes
    h, w = image.shape[:2]

    try:
        components = bbox_input.strip().split('\n')
        # print("Split components:", components)  # Debug print

        for component in components:
            component = component.strip()
            if not component:
                continue

            if ':' in component:
                name, bbox_str = component.split(':', 1)
            else:
                bbox_str = component
                if 'sidebar' in component.lower():
                    name = 'sidebar'
                elif 'header' in component.lower():
                    name = 'header'
                elif 'navigation' in component.lower():
                    name = 'navigation'
                elif 'main content' in component.lower():
                    name = 'main content'
                else:
                    name = 'unknown'

            name = name.strip().lower()
            bbox_str = bbox_str.strip()

            # print(f"Processing component: {name}, bbox_str: {bbox_str}")  # Debug print

            if BBOX_TAG_START in bbox_str and BBOX_TAG_END in bbox_str:
                start_idx = bbox_str.find(BBOX_TAG_START) + len(BBOX_TAG_START)
                end_idx = bbox_str.find(BBOX_TAG_END)
                coords_str = bbox_str[start_idx:end_idx].strip()

                try:
                    norm_coords = list(map(int, coords_str.split()))
                    if len(norm_coords) == 4:
                        x_min = int(norm_coords[0])
                        y_min = int(norm_coords[1])
                        x_max = int(norm_coords[2])
                        y_max = int(norm_coords[3])
                        bboxes[name] = (x_min, y_min, x_max, y_max)
                        print(f"Successfully parsed {name}: {bboxes[name]}")
                    else:
                        print(
                            f"Invalid number of coordinates for {name}: {norm_coords}")
                except ValueError as e:
                    print(f"Failed to parse coordinates for {name}: {e}")
            else:
                print(f"No bbox tags found in: {bbox_str}")

    except Exception as e:
        print(f"Coordinate parsing failed: {str(e)}")
        import traceback
        traceback.print_exc()

    print("Final parsed bboxes:", bboxes)
    return bboxes


def draw_bboxes(image_path: str, bboxes: dict[str, tuple[int, int, int, int]]) -> str:
    """Draw bounding boxes on image and save with different colors for each component"""
    image = cv2.imread(image_path)
    if image is None:
        print(f"Error: Failed to read image {image_path}")
        return ""

    h, w = image.shape[:2]
    colors = {
        'sidebar': (0, 0, 255),  # Red
        'header': (0, 255, 0),  # Green
        'navigation': (255, 0, 0),  # Blue
        'main content': (255, 255, 0),  # Cyan
        'unknown': (0, 0, 0),  # Black
    }

    for component, norm_bbox in bboxes.items():
        # Convert normalized coordinates to pixel coordinates for drawing
        x_min = int(norm_bbox[0] * w / 1000)
        y_min = int(norm_bbox[1] * h / 1000)
        x_max = int(norm_bbox[2] * w / 1000)
        y_max = int(norm_bbox[3] * h / 1000)

        color = colors.get(component.lower(), (0, 0, 255))
        cv2.rectangle(image, (x_min, y_min), (x_max, y_max), color, 3)

        # Add label
        cv2.putText(image, component, (x_min, y_min - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2)

    # Output directory
    output_dir = "data/tmp"
    os.makedirs(output_dir, exist_ok=True)

    # Get the original filename without path
    original_filename = os.path.basename(image_path)
    output_path = os.path.join(output_dir, os.path.splitext(
        original_filename)[0] + "_with_bboxes.png")

    if cv2.imwrite(output_path, image):
        print(f"Successfully saved annotated image: {output_path}")
        return output_path
    print("Error: Failed to save image")
    return ""


def save_bboxes_to_json(bboxes: dict[str, tuple[int, int, int, int]], image_path: str) -> str:
    """Save bounding boxes information to a JSON file"""
    # Output directory
    output_dir = "data/tmp"
    os.makedirs(output_dir, exist_ok=True)

    original_filename = os.path.basename(image_path)
    json_path = os.path.join(output_dir, os.path.splitext(
        original_filename)[0] + "_bboxes.json")

    bboxes_dict = {k: list(v) for k, v in bboxes.items()}

    try:
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(bboxes_dict, f, indent=4, ensure_ascii=False)
        print(f"Successfully saved bbox information to: {json_path}")
        return json_path
    except Exception as e:
        print(f"Error saving JSON file: {str(e)}")
        return ""

# sequential version of bbox parsing: Using recursive detection with mask
# def sequential_component_detection(image_path: str, api_path: str) -> dict[str, tuple[int, int, int, int]]:
#     """
#     Sequential processing flow: detect each component in turn, mask the image after each detection
#     """
#     bboxes = {}
#     current_image_path = image_path
#     ark_client = Doubao(api_path) # Change your client according to your needs: Qwen(api_path), GPT(api_path), Gemini(api_path)

#     image = cv2.imread(image_path)
#     if image is None:
#         print(f"Error: Failed to read image {image_path}")
#         return bboxes
#     h, w = image.shape[:2]

#     for i, (component_name, prompt) in enumerate(PROMPT_LIST):
#         print(f"\n=== Processing {component_name} (Step {i+1}/{len(PROMPT_LIST)}) ===")

#         base64_image = encode_image(current_image_path)
#         if not base64_image:
#             print(f"Error: Failed to encode image for {component_name}")
#             continue

#         print(f"Sending prompt for {component_name}...")
#         bbox_content = ark_client.ask(prompt, base64_image)
#         print(f"Model response for {component_name}:")
#         print(bbox_content)

#         norm_bbox = parse_single_bbox(bbox_content, component_name)
#         if norm_bbox:
#             bboxes[component_name] = norm_bbox
#             print(f"Successfully detected {component_name}: {norm_bbox}")

#             masked_image = image_mask(current_image_path, norm_bbox)

#             temp_image_path = f"data/temp_{component_name}_masked.png"
#             masked_image.save(temp_image_path)
#             current_image_path = temp_image_path

#             print(f"Created masked image for next step: {temp_image_path}")
#         else:
#             print(f"Failed to detect {component_name}")

#     return bboxes

# def parse_single_bbox(bbox_input: str, component_name: str) -> tuple[int, int, int, int]:
#     """
#     Parses a single component's bbox string and returns normalized coordinates.
#     """
#     print(f"Parsing bbox for {component_name}: {bbox_input}")

#     try:
#         if BBOX_TAG_START in bbox_input and BBOX_TAG_END in bbox_input:
#             start_idx = bbox_input.find(BBOX_TAG_START) + len(BBOX_TAG_START)
#             end_idx = bbox_input.find(BBOX_TAG_END)
#             coords_str = bbox_input[start_idx:end_idx].strip()

#             norm_coords = list(map(int, coords_str.split()))
#             if len(norm_coords) == 4:
#                 return tuple(norm_coords)
#             else:
#                 print(f"Invalid number of coordinates for {component_name}: {norm_coords}")
#         else:
#             print(f"No bbox tags found in response for {component_name}")
#     except Exception as e:
#         print(f"Failed to parse bbox for {component_name}: {e}")

#     return None

# def main_content_processing(bboxes: dict[str, tuple[int, int, int, int]], image_path: str) -> dict[str, tuple[int, int, int, int]]:
#     """devide the main content into several parts"""
#     image = cv2.imread(image_path)
#     if image is None:
#         print(f"Error: Failed to read image {image_path}")
#         return
#     h, w = image.shape[:2]
#     for component, bbox in bboxes.items():
#         bboxes[component] = (
#             int(bbox[0] * w / 1000),
#             int(bbox[1] * h / 1000),
#             int(bbox[2] * w / 1000),
#             int(bbox[3] * h / 1000))


if __name__ == "__main__":
    image_path = DEFAULT_IMAGE_PATH
    api_key = DEFAULT_API_KEY

    print("=== Starting Simple Component Detection ===")
    print(f"Input image: {image_path}")
    print(f"API key: {api_key}")
    # You can switch model by changing the client and API key source
    # For example: Qwen(get_api_key(ApiService.QWEN)), GPT(get_api_key(ApiService.GPT)), Gemini(get_api_key(ApiService.GEMINI))
    client = Doubao(api_key)
    bbox_content = client.ask(PROMPT_MERGE, encode_image(image_path))
    print(f"Model response: {bbox_content}\n")
    bboxes = parse_bboxes(bbox_content, image_path)

    # print("=== Starting Sequential Component Detection ===")
    # print(f"Input image: {image_path}")
    # print(f"API path: {api_path}")
    # bboxes = sequential_component_detection(image_path, api_path)

    bboxes = resolve_containment(bboxes)

    if bboxes:
        print(f"\n=== Detection Complete ===")
        print(f"Found bounding boxes for components: {list(bboxes.keys())}")
        print(f"Total components detected: {len(bboxes)}")

        json_path = save_bboxes_to_json(bboxes, image_path)
        draw_bboxes(image_path, bboxes)

        print(f"\n=== Results ===")
        for component, bbox in bboxes.items():
            print(f"{component}: {bbox}")
    else:
        print("\nNo valid bounding box coordinates found")
        exit(1)
