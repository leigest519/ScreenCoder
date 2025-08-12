from api_config import get_api_key, ApiService
from utils import encode_image, Doubao, Qwen, GPT, Gemini
from PIL import Image
import bs4
from threading import Thread
import time

# user instruction for each component
user_instruction = {
    "sidebar": "",
    "header": "",
    "navigation": "",
    "main content": ""
}

# We provide prompts in both Chinese and English.
# Chinese prompts for each region
PROMPT_DICT = {
    "sidebar": f"""这是一个container的截图。这是用户给的额外要求：{user_instruction["sidebar"]}请填写一段完整的HTML和tail-wind CSS代码以准确再现给定的容器。请注意所有组块的排版、图标样式、大小、文字信息需要在用户额外条件的基础上与原始截图基本保持一致。以下是供填写的代码：

    <div>
    your code here
    </div>

    只需返回<div>和</div>标签内的代码""",

    "header": f"""这是一个container的截图。这是用户给的额外要求：{user_instruction["header"]}请填写一段完整的HTML和tail-wind CSS代码以准确再现给定的容器。请注意所有组块在boundary box中的相对位置、排版、文字信息、颜色需要在用户额外条件的基础上与原始截图基本保持一致。以下是供填写的代码：

    <div>
    your code here
    </div>

    只需返回<div>和</div>标签内的代码""",

    "navigation": f"""这是一个container的截图。这是用户给的额外要求：{user_instruction["navigation"]}请填写一段完整的HTML和tail-wind CSS代码以准确再现给定的容器。请注意所有组块的在boundary box中的相对位置、文字排版、颜色需要在用户额外条件的基础上与原始截图基本保持一致。请你直接使用原始截图中一致的图标。以下是供填写的代码：

    <div>
    your code here
    </div>

    只需返回<div>和</div>标签内的代码""",

    "main content": f"""这是一个container的截图。这是用户给的额外要求：{user_instruction["main content"]}请填写一段完整的HTML和tail-wind CSS代码以准确再现给定的容器。请使用相同大小的纯灰色图像块替换原始截图中的图像，不需要识别图像中的文字信息。请注意所有组块在boundary box中的相对位置、排版、文字信息、颜色需要在用户额外条件的基础上与原始截图基本保持一致。以下是供填写的代码：

    <div>
    your code here
    </div>

    只需返回<div>和</div>标签内的代码"""
}

# English prompts for each region
# PROMPT_DICT = {
#     "sidebar": f"""This is a screenshot of a container. Here is the user's additional instruction: {user_instruction["sidebar"]}
#     Please fill in a complete HTML and Tailwind CSS code to accurately reproduce the given container.
#     Please ensure that all block layouts, icon styles, sizes, and text information are consistent with the original screenshot,
#     based on the user's additional conditions. Below is the code template to fill in:

#     <div>
#     your code here
#     </div>

#     Only return the code within the <div> and </div> tags.""",

#     "header": f"""This is a screenshot of a container. Here is the user's additional instruction: {user_instruction["header"]}
#     Please fill in a complete HTML and Tailwind CSS code to accurately reproduce the given container.
#     Please ensure that all blocks' relative positions, layout, text information, and colors within the bounding box
#     are consistent with the original screenshot, based on the user's additional conditions. Below is the code template to fill in:

#     <div>
#     your code here
#     </div>

#     Only return the code within the <div> and </div> tags.""",

#     "navigation": f"""This is a screenshot of a container. Here is the user's additional instruction: {user_instruction["navigation"]}
#     Please fill in a complete HTML and Tailwind CSS code to accurately reproduce the given container.
#     Please ensure that all blocks' relative positions, text layout, and colors within the bounding box
#     are consistent with the original screenshot, based on the user's additional conditions.
#     Please use the same icons as in the original screenshot. Below is the code template to fill in:

#     <div>
#     your code here
#     </div>

#     Only return the code within the <div> and </div> tags.""",

#     "main content": f"""This is a screenshot of a container. Here is the user's additional instruction: {user_instruction["main content"]}
#     Please fill in a complete HTML and Tailwind CSS code to accurately reproduce the given container.
#     Please replace the images in the original screenshot with solid gray blocks of the same size;
#     text inside the images does not need to be recognized.
#     Please ensure that all blocks' relative positions, layout, text information, and colors within the bounding box
#     are consistent with the original screenshot, based on the user's additional conditions. Below is the code template to fill in:

#     <div>
#     your code here
#     </div>

#     Only return the code within the <div> and </div> tags."""
# }

# Support refining the generated code.
# PROMPT_refinement = """Here is a prototype image of a webpage. I have an draft HTML file that contains most of the elements and their correct positions, but it has *inaccurate background*, and some missing or wrong elements. Please compare the draft and the prototype image, then revise the draft implementation. Return a single piece of accurate HTML+tail-wind CSS code to reproduce the website. Respond with the content of the HTML+tail-wind CSS code. The current implementation I have is: \n\n [CODE]"""

# Generate code for each component


def generate_code(bbox_tree, img_path, bot):
    """generate code for all the leaf nodes in the bounding box tree, return a dictionary: {'id': 'code'}"""
    img = Image.open(img_path)
    code_dict = {}

    def _generate_code(node):
        if node["children"] == []:
            bbox = node["bbox"]
            # bbox is already in pixel coordinates [x1, y1, x2, y2]
            cropped_img = img.crop(bbox)

            # Select prompt based on node type
            if "type" in node:
                if node["type"] == "sidebar":
                    prompt = PROMPT_DICT["sidebar"]
                elif node["type"] == "header":
                    prompt = PROMPT_DICT["header"]
                elif node["type"] == "navigation":
                    prompt = PROMPT_DICT["navigation"]
                elif node["type"] == "main content":
                    prompt = PROMPT_DICT["main content"]
                else:
                    print(f"Unknown component type: {node['type']}")
                    return
            else:
                print("Node type not found")
                return

            try:
                code = bot.ask(prompt, encode_image(cropped_img))
                code_dict[node["id"]] = code
            except Exception as e:
                print(
                    f"Error generating code for {node.get('type', 'unknown')}: {str(e)}")
                code_dict[node["id"]] = f"<!-- Error: {str(e)} -->"
        else:
            for child in node["children"]:
                _generate_code(child)

    _generate_code(bbox_tree)
    return code_dict

# Generate code for each component in parallel


def generate_code_parallel(bbox_tree, img_path, bot):
    """generate code for all the leaf nodes in the bounding box tree, return a dictionary: {'id': 'code'}"""
    code_dict = {}
    t_list = []

    def _generate_code_with_retry(node, max_retries=3, retry_delay=2):
        """Generate code with retry mechanism for rate limit errors"""
        try:
            # Create a new image instance for each thread
            with Image.open(img_path) as img:
                bbox = node["bbox"]
                cropped_img = img.crop(bbox)

                # Select prompt based on node type
                if "type" in node:
                    if node["type"] in PROMPT_DICT:
                        prompt = PROMPT_DICT[node["type"]]
                    else:
                        print(f"Unknown component type: {node['type']}")
                        code_dict[node["id"]
                                  ] = f"<!-- Unknown component type: {node['type']} -->"
                        return
                else:
                    print("Node type not found")
                    code_dict[node["id"]] = f"<!-- Node type not found -->"
                    return

                for attempt in range(max_retries):
                    try:
                        code = bot.ask(prompt, encode_image(cropped_img))
                        code_dict[node["id"]] = code
                        return
                    except Exception as e:
                        if "rate_limit" in str(e).lower() and attempt < max_retries - 1:
                            print(
                                f"Rate limit hit, retrying in {retry_delay} seconds... (Attempt {attempt + 1}/{max_retries})")
                            time.sleep(retry_delay)
                            retry_delay *= 2  # Exponential backoff
                        else:
                            print(
                                f"Error generating code for node {node['id']}: {str(e)}")
                            code_dict[node["id"]] = f"<!-- Error: {str(e)} -->"
                            return
        except Exception as e:
            print(f"Error processing image for node {node['id']}: {str(e)}")
            code_dict[node["id"]] = f"<!-- Error: {str(e)} -->"

    def _generate_code(node):
        if not node.get("children"):
            t = Thread(target=_generate_code_with_retry, args=(node,))
            t.start()
            t_list.append(t)
        else:
            for child in node["children"]:
                _generate_code(child)

    _generate_code(bbox_tree)

    # Wait for all threads to complete
    for t in t_list:
        t.join()

    return code_dict

# Generate HTML from the bounding box tree


def generate_html(bbox_tree, output_file="output.html", img_path="data/test1.png"):
    """
    Generates an HTML file with nested containers based on the bounding box tree.

    :param bbox_tree: Dictionary representing the bounding box tree.
    :param output_file: The name of the output HTML file.
    """
    # HTML and CSS templates
    # the container class is used to create grid and position the boxes
    # include the tailwind css in the head tag
    html_template_start = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Bounding Boxes Layout</title>
        <style>
            body, html {
                margin: 0;
                padding: 0;
                width: 100%;
                height: 100%;
            }
            .container { 
                position: relative;
                width: 100%;
                height: 100%;
                box-sizing: border-box;
            }
            .box {
                position: absolute;
                box-sizing: border-box;
                overflow: hidden;
            }
            .box > .container {
                display: grid;
                width: 100%;
                height: 100%;
            }
        </style>
        <link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
    </head>
    <body>
        <div class="container">
    """

    html_template_end = """
        </div>
    </body>
    </html>
    """

    # Function to recursively generate HTML
    def process_bbox(node, parent_width, parent_height, parent_left, parent_top, img):
        bbox = node['bbox']
        children = node.get('children', [])
        id = node['id']

        # Calculate relative positions and sizes
        left = (bbox[0] - parent_left) / parent_width * 100
        top = (bbox[1] - parent_top) / parent_height * 100
        width = (bbox[2] - bbox[0]) / parent_width * 100
        height = (bbox[3] - bbox[1]) / parent_height * 100

        # Start the box div
        html = f'''
            <div id="{id}" class="box" style="left: {left}%; top: {top}%; width: {width}%; height: {height}%;">
        '''

        if children:
            # If there are children, add a nested container
            html += '''
                <div class="container">
            '''
            # Get the current box's width and height in pixels for child calculations
            current_width = bbox[2] - bbox[0]
            current_height = bbox[3] - bbox[1]
            for child in children:
                html += process_bbox(child, current_width,
                                     current_height, bbox[0], bbox[1], img)
            html += '''
                </div>
            '''

        # Close the box div
        html += '''
            </div>
        '''
        return html

    root_bbox = bbox_tree['bbox']
    root_children = bbox_tree.get('children', [])
    root_width = root_bbox[2]
    root_height = root_bbox[3]
    root_x = root_bbox[0]
    root_y = root_bbox[1]

    html_content = html_template_start
    for child in root_children:
        html_content += process_bbox(child, root_width,
                                     root_height, root_x, root_y, img)
    html_content += html_template_end

    soup = bs4.BeautifulSoup(html_content, 'html.parser')
    html_content = soup.prettify()

    with open(output_file, 'w') as f:
        f.write(html_content)

# Substitute the code in the html file


def code_substitution(html_file, code_dict):
    """substitute the code in the html file"""
    with open(html_file, "r") as f:
        html = f.read()
    soup = bs4.BeautifulSoup(html, 'html.parser')
    for id, code in code_dict.items():
        code = code.replace("```html", "").replace("```", "")
        div = soup.find(id=id)
        # replace the inner html of the div
        if div:
            div.append(bs4.BeautifulSoup(code, 'html.parser'))
    with open(html_file, "w") as f:
        f.write(soup.prettify())

# def html_refinement(html_file, output_file, img_path, bot):
#     """refine the html file"""
#     try:
#         with open(html_file, "r") as f:
#             html_content = f.read()

#         img = Image.open(img_path)

#         prompt = PROMPT_refinement.replace("[CODE]", html_content)

#         refined_html = bot.ask(prompt, encode_image(img))
#         refined_html = refined_html.replace("```html", "").replace("```", "").strip()

#         with open(output_file, "w") as f:
#             f.write(refined_html)
#     except Exception as e:
#         print(f"An error occurred during HTML refinement: {e}")


# Main
if __name__ == "__main__":
    import json
    import time
    from PIL import Image

    # Load bboxes from block_parsing.py output
    boxes_data = json.load(open("data/tmp/test1_bboxes.json"))

    img_path = "data/input/test1.png"
    with Image.open(img_path) as img:
        width, height = img.size

    # Create root node with actual image dimensions
    root = {
        "bbox": [0, 0, width, height],  # Use actual image dimensions
        "children": []
    }

    # Add each region as a child with its type
    for component_name, norm_bbox in boxes_data.items():
        # The coordinates from block_parsor are normalized to 1000x1000
        # Convert normalized coordinates to pixel coordinates
        x1 = int(norm_bbox[0] * width / 1000)
        y1 = int(norm_bbox[1] * height / 1000)
        x2 = int(norm_bbox[2] * width / 1000)
        y2 = int(norm_bbox[3] * height / 1000)

        child = {
            "bbox": [x1, y1, x2, y2],
            "children": [],
            "type": component_name
        }
        root["children"].append(child)

    # Assign IDs to all nodes
    def assign_id(node, id):
        node["id"] = id
        for child in node.get("children", []):
            id = assign_id(child, id+1)
        return id

    assign_id(root, 0)

    # print(root)
    # Generate initial HTML layout
    generate_html(root, 'data/tmp/test1_layout.html')

    # Initialize the bot
    # Get Doubao API key from unified config
    doubao_api_key = get_api_key(ApiService.DOUBAO)
    bot = Doubao(doubao_api_key, model="doubao-1.5-thinking-vision-pro-250428")
    # You can switch model by changing the client and API key source
    # For example: Qwen(get_api_key(ApiService.QWEN)), GPT(get_api_key(ApiService.GPT)), Gemini(get_api_key(ApiService.GEMINI))
    # bot = Qwen("qwen_api.txt", model="qwen2.5-vl-72b-instruct")
    # bot = GPT("gpt_api.txt", model="gpt-4o")
    # bot = Gemini("gemini_api.txt", model="gemini-1.5-flash-latest")

    # Generate code for each component
    # code_dict = generate_code(root, img_path, bot)

    code_dict = generate_code_parallel(root, img_path, bot)

    # Substitute the generated code into the HTML
    code_substitution('data/tmp/test1_layout.html', code_dict)

    # Refine the html file
    # html_refinement('data/tmp/test1_layout.html', 'data/tmp/test1_layout_refined.html', img_path, bot)
