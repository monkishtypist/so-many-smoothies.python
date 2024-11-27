# generate_smoothie.py

import base64
import logging
import os
import random
import re
import requests
import uuid
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

SANITY_PROJECT_ID = os.getenv("SANITY_PROJECT_ID")
SANITY_DATASET = os.getenv("SANITY_DATASET", "production")
SANITY_WRITE_TOKEN = os.getenv("SANITY_WRITE_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Prompt defaults
IMAGE_PROMPT_TEMPLATE = """
"A photograph of [describe the smoothie and corresponding scene], captured with a [wide/smaller] aperture (f/[aperture value]) to [effect on focus].
The image features [lighting type], enhancing [specific details like textures or colors].
The shutter speed is set to [value] to ensure [sharpness/clarity, etc].
The composition draws the viewer's eye to [describe focal point] by making it the brightest spot in the frame.
The overall mood is [describe atmosphere], replicating natural light with [mention any tools like reflectors].
The image should not include any text or logos, focusing solely on the smoothie and its ingredients."
"""

REPEATED_PROMPT = f"""
Include the following sections in the response:
Title: A unique, SEO-friendly title for the smoothie recipe.
Description: A brief and appealing description of the smoothie.
Ingredients: An unordered list of ingredients (1 per line).
Steps: Step-by-step preparation instructions as an unordered list.
Tags: Relevant tags for the smoothie recipe based on the purpose or health benefits, as well as the ingredients, as a comma-separated list.
ImagePrompt: A creative and enticing image prompt to visually represent the smoothie using the following prompt template: {IMAGE_PROMPT_TEMPLATE}
Format the response using these exact section headers. Do not include any extra text.
"""

# Unique prompts for each day of the week
DAILY_PROMPTS = [
    "Generate a light and cleansing Detox smoothie recipe with hydrating fruits, anti-inflammatory ingredients, and natural detoxifiers.",
    "Generate a fun and creative Tropical smoothie recipe inspired by island flavors like mango, pineapple, coconut, and passion fruit.",
    "Generate a delicious Berry smoothie recipe using a variety of fresh and frozen berries.",
    "Generate a refreshing Green smoothie recipe packed with leafy greens, superfoods, and hydrating ingredients.",
    "Generate a unique smoothie recipe inspired by South Asian flavors like tamarind, cardamom, rosewater, or turmeric.",
    "Generate a rich and indulgent smoothie recipe inspired by desserts, focusing on flavors like chocolate, caramel, or hazelnut.",
    "Generate a vibrant and creative smoothie recipe inspired by diverse African flavors, such as Northern Africa, Central Africa, Southern Africa, coastal and inland, etc., incorporating ingredients like hibiscus or baobab."
]

def get_prompt(random_choice=False):
    """
    Returns the appropriate prompt based on the day of the week or random choice.
    """
    if random_choice:
        logger.info("Random prompt selected.")
        return random.choice(DAILY_PROMPTS) + REPEATED_PROMPT
    # Use the day of the week as the default index
    day_of_week = datetime.now().weekday()  # Monday = 0, Sunday = 6
    logger.info(f"Prompt for day {day_of_week} selected.")
    return DAILY_PROMPTS[day_of_week] + REPEATED_PROMPT

def fetch_recipe_from_openai(prompt):
    """
    Fetches a smoothie recipe from OpenAI based on the given prompt.
    """
    logger.info("Fetching recipe from OpenAI...")
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "gpt-4",
        "messages": [{"role": "user", "content": prompt}],
    }
    response = requests.post("https://api.openai.com/v1/chat/completions", json=payload, headers=headers)
    response.raise_for_status()

    content = response.json()["choices"][0]["message"]["content"]

    # Debugging: Print the full response
    logger.debug(f"Raw Response Content:\n{content}\n")

    return parse_recipe(content)

def generate_slug(title, existing_slugs):
    """
    Generates a unique slug from the given title.
    """
    import re
    import uuid

    # Normalize the title by replacing special characters and spaces
    slug = re.sub(r'[^a-zA-Z0-9]+', '-', title.lower()).strip('-')

    # Ensure uniqueness
    while slug in existing_slugs:
        slug = f"{slug}-{uuid.uuid4().hex[:6]}"
    return slug

def parse_recipe(content):
    """
    Parses the recipe content into a structured dictionary.
    """
    logger.info("Parsing recipe...")
    lines = content.strip().split("\n")
    recipe = {
        "title": None,
        "description": None,
        "ingredients": [],
        "steps": [],
        "tags": [],
        "image_prompt": None,
    }

    section = None
    buffer = []

    def is_ordered_list_item(line):
        return bool(re.match(r'^\d+[\.\)]\s+', line))

    def clean_list_item(line):
        return re.sub(r'^(-|\d+[\.\)])\s+', '', line).strip()

    def finalize_buffer_to_section():
        nonlocal section, buffer
        if section in ["ingredients", "steps"]:
            for line in buffer:
                if line.startswith("- ") or is_ordered_list_item(line):
                    cleaned_line = clean_list_item(line)
                    if section == "ingredients":
                        recipe["ingredients"].append(cleaned_line)
                        logger.debug(f"Added Ingredient: {cleaned_line}")
                    elif section == "steps":
                        recipe["steps"].append(cleaned_line)
                        logger.debug(f"Added Step: {cleaned_line}")
        elif section and buffer:
            content = " ".join(buffer).strip()
            if section == "title":
                recipe["title"] = content
                logger.debug(f"Parsed Title: {content}")
            elif section == "description":
                recipe["description"] = content
                logger.debug(f"Parsed Description: {content}")
            elif section == "tags":
                recipe["tags"] = [tag.strip() for tag in content.split(",") if tag.strip()]
                logger.debug(f"Parsed Tags: {recipe['tags']}")
            elif section == "image_prompt":
                recipe["image_prompt"] = content
                logger.debug(f"Parsed ImagePrompt: {content}")
        buffer = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Check for section headers
        if line.lower().startswith("title:"):
            finalize_buffer_to_section()
            section = "title"
            buffer = [line.split(":", 1)[1].strip()] if ":" in line else []
        elif line.lower().startswith("description:"):
            finalize_buffer_to_section()
            section = "description"
            buffer = [line.split(":", 1)[1].strip()] if ":" in line else []
        elif line.lower().startswith("ingredients:"):
            finalize_buffer_to_section()
            section = "ingredients"
            buffer = []
        elif line.lower().startswith("steps:"):
            finalize_buffer_to_section()
            section = "steps"
            buffer = []
        elif line.lower().startswith("tags:"):
            finalize_buffer_to_section()
            section = "tags"
            buffer = [line.split(":", 1)[1].strip()] if ":" in line else []
        elif line.lower().startswith("imageprompt:"):
            finalize_buffer_to_section()
            section = "image_prompt"
            buffer = [line.split(":", 1)[1].strip()] if ":" in line else []
        else:
            # Add line to the current section's buffer
            buffer.append(line)

    # Finalize the last buffered section
    finalize_buffer_to_section()

    # Ensure all required fields are present
    required_fields = ["title", "description", "ingredients", "steps", "image_prompt"]
    missing_fields = [key for key in required_fields if not recipe.get(key)]
    if missing_fields:
        logger.error(f"Missing required fields: {missing_fields}")
        raise ValueError("Incomplete recipe data")

    return recipe

def get_existing_recipes():
    """
    Fetches all existing smoothie recipes from Sanity.
    """
    logger.info("Fetching existing recipes...")
    url = f"https://{SANITY_PROJECT_ID}.api.sanity.io/v1/data/query/{SANITY_DATASET}"
    query = '*[_type == "smoothie"] { title, ingredients, "slug": slug.current }'
    headers = {"Authorization": f"Bearer {SANITY_WRITE_TOKEN}"}
    response = requests.get(f"{url}?query={query}", headers=headers)
    response.raise_for_status()
    return response.json().get("result", [])

def is_unique_recipe(title, ingredients, existing_recipes):
    """
    Checks if the recipe's title and ingredients are unique.
    """
    logger.info("Checking for uniqueness...")
    for recipe in existing_recipes:
        if recipe["title"] == title:
            if sorted(recipe["ingredients"]) == sorted(ingredients):
                return False, title  # Title and ingredients match
            else:
                count = 2
                new_title = f"{title} {count}"
                while any(r["title"] == new_title for r in existing_recipes):
                    count += 1
                    new_title = f"{title} {count}"
                return True, new_title
    return True, title

def generate_image(prompt):
    """
    Generates an image using OpenAI's Image Generation API and saves it locally.
    Returns the local filename of the saved image.
    """
    logger.info("Generating image...")
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "dall-e-3",
        "prompt": prompt,
        "n": 1,
        "size": "1024x1024",
        "response_format": "b64_json"
    }
    try:
        response = requests.post("https://api.openai.com/v1/images/generations", json=payload, headers=headers)
        logger.debug(f"OpenAI Response: {response.status_code}, {response.text}")
        response.raise_for_status()

        response_data = response.json()
        image_data = response_data["data"][0]["b64_json"]
        logger.info("Image data received from OpenAI.")

        # Decode the base64 image data
        image_content = base64.b64decode(image_data)

        # Save the image locally
        image_filename = "generated_image.png"
        with open(image_filename, 'wb') as f:
            f.write(image_content)
        logger.info(f"Image saved locally as: {image_filename}")

        return image_filename

    except requests.exceptions.HTTPError as http_err:
        error_message = response.json().get('error', {}).get('message', '')
        logger.error(f"HTTP error occurred: {http_err} - {error_message}")
        raise
    except Exception as e:
        logger.error(f"An error occurred during image generation: {e}")
        raise

def upload_recipe_to_sanity(recipe, recipe_prompt, image_prompt):
    """
    Uploads the recipe document to Sanity and returns the document ID.
    """
    payload = {
        "mutations": [
            {
                "create": {
                    "_type": "smoothie",
                    "title": recipe["title"],
                    "slug": {"_type": "slug", "current": recipe["slug"]},
                    "description": recipe["description"],
                    "ingredients": recipe["ingredients"],
                    "steps": recipe["steps"],
                    "tags": recipe["tags"],
                    "date": datetime.now().isoformat(),
                    "recipePrompt": recipe_prompt,
                    "imagePrompt": image_prompt,
                }
            }
        ]
    }

    mutation_url = f"https://{SANITY_PROJECT_ID}.api.sanity.io/v2021-06-07/data/mutate/{SANITY_DATASET}?returnIds=true"
    headers = {
        "Authorization": f"Bearer {SANITY_WRITE_TOKEN}",
        "Content-Type": "application/json",
    }

    response = requests.post(mutation_url, json=payload, headers=headers)
    logger.debug(f"Recipe Upload Response: {response.status_code}, {response.text}")
    response.raise_for_status()

    mutation_data = response.json()
    document_id = mutation_data["results"][0].get("id")
    logger.info(f"Recipe uploaded with ID: {document_id}")
    return document_id

def upload_image_asset(image_filename):
    """
    Uploads the local image file to Sanity's Assets API.
    Returns the image asset document.
    """
    try:
        logger.info(f"Uploading image '{image_filename}' to Sanity's Assets API...")

        # Read the image data from the file
        with open(image_filename, 'rb') as img_file:
            image_data = img_file.read()
        logger.info("Image read successfully.")

        # Determine the content type based on file extension
        filename = os.path.basename(image_filename)
        ext = os.path.splitext(filename)[1].lower()
        if ext == '.png':
            content_type = 'image/png'
        elif ext in ('.jpg', '.jpeg'):
            content_type = 'image/jpeg'
        else:
            raise ValueError("Unsupported image file extension. Please use .png or .jpg/.jpeg.")

        # Prepare the upload URL and headers
        image_upload_url = f"https://{SANITY_PROJECT_ID}.api.sanity.io/v2021-06-07/assets/images/{SANITY_DATASET}?filename={filename}"
        headers = {
            "Authorization": f"Bearer {SANITY_WRITE_TOKEN}",
            "Content-Type": content_type
        }

        # Upload the image to Sanity
        response = requests.post(image_upload_url, data=image_data, headers=headers)
        logger.debug(f"Sanity Response: {response.status_code}, {response.text}")
        response.raise_for_status()

        # Extract and return the asset document from the response
        image_asset = response.json()
        document = image_asset.get("document")
        asset_id = document.get("_id")
        logger.info(f"Image uploaded successfully with asset ID: {asset_id}")
        return document

    except requests.exceptions.HTTPError as http_err:
        error_message = response.json().get('error', {}).get('message', '')
        logger.error(f"HTTP error occurred: {http_err} - {error_message}")
        raise
    except Exception as e:
        logger.error(f"An error occurred during image upload: {e}")
        raise

def link_image_asset_to_recipe(document_id, asset_id):
    """
    Links the uploaded image asset to the specified recipe document.
    """
    try:
        logger.info("Linking image asset to recipe document...")
        patch_payload = {
            "mutations": [
                {
                    "patch": {
                        "id": document_id,
                        "set": {
                            "image": {
                                "_type": "image",
                                "asset": {"_ref": asset_id},
                            }
                        },
                    }
                }
            ]
        }
        mutation_url = f"https://{SANITY_PROJECT_ID}.api.sanity.io/v2021-06-07/data/mutate/{SANITY_DATASET}"
        headers = {
            "Authorization": f"Bearer {SANITY_WRITE_TOKEN}",
            "Content-Type": "application/json",
        }
        patch_response = requests.post(mutation_url, json=patch_payload, headers=headers)
        logger.debug(f"Patch Response: {patch_response.status_code}, {patch_response.text}")
        patch_response.raise_for_status()

        logger.info(f"Image successfully linked to the recipe with ID: {document_id}")

    except Exception as e:
        logger.error(f"An error occurred in link_image_asset_to_recipe: {e}")
        raise

def upload_to_sanity(recipe, image_filename, recipe_prompt, image_prompt):
    """
    Uploads the recipe and associated image to Sanity.
    """
    try:
        # Upload the recipe
        document_id = upload_recipe_to_sanity(recipe, recipe_prompt, image_prompt)

        # Upload the image asset
        image_asset = upload_image_asset(image_filename)
        asset_id = image_asset.get("_id")
        if not asset_id:
            raise ValueError("Asset ID missing in the image asset response.")

        # Link the image asset to the recipe
        link_image_asset_to_recipe(document_id, asset_id)

        # After successful upload
        os.remove(image_filename)
        logger.info(f"Temporary image file {image_filename} deleted.")

    except Exception as e:
        logger.error(f"Sanity upload failed: {e}")
        raise

def main(random_choice=False, dry_run=False):
    logger.info("Starting the script...")
    recipe_prompt = get_prompt(random_choice)
    logger.debug(f"Using Recipe Prompt:\n{recipe_prompt}")

    try:
        recipe = fetch_recipe_from_openai(recipe_prompt)
        logger.info("Recipe fetched successfully.")

        image_prompt = recipe["image_prompt"]
        image_filename = generate_image(image_prompt)
        logger.info(f"Image saved at: {image_filename}")

        if dry_run:
            logger.info("\n--- Dry Run Mode ---")
            logger.info("Parsed Recipe:")
            for key, value in recipe.items():
                logger.info(f"{key.capitalize()}: {value}")
            logger.info(f"Generated Image File: {image_filename}")
            return

        # Check for uniqueness
        existing_recipes = get_existing_recipes()
        existing_slugs = {recipe.get("slug", "") for recipe in existing_recipes}

        is_unique, unique_title = is_unique_recipe(recipe["title"], recipe["ingredients"], existing_recipes)
        if not is_unique:
            logger.info(f"Duplicate recipe found for title: {recipe['title']} with identical ingredients. Skipping.")
            return

        # Generate slug
        recipe["title"] = unique_title
        recipe["slug"] = generate_slug(unique_title, existing_slugs)


        # Upload to Sanity
        upload_to_sanity(recipe, image_filename, recipe_prompt, image_prompt)
        logger.info(f"Uploaded recipe: {recipe['title']}")

    except Exception as e:
        logger.error(f"An error occurred: {e}")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate a smoothie recipe.")
    parser.add_argument("--random", action="store_true", help="Use a random prompt.")
    parser.add_argument("--dry-run", action="store_true", help="Test without uploading to Sanity.")
    args = parser.parse_args()

    main(random_choice=args.random, dry_run=args.dry_run)
