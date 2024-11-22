import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

SANITY_PROJECT_ID = os.getenv("SANITY_PROJECT_ID")
SANITY_DATASET = os.getenv("SANITY_DATASET", "production")
SANITY_WRITE_TOKEN = os.getenv("SANITY_WRITE_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

def fetch_recipe_from_openai():
    prompt = "Generate a unique smoothie recipe with a title, description, ingredients, steps, and an image prompt."
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
    return parse_recipe(content)

def parse_recipe(content):
    # Parse the recipe (you can adapt this based on the format of your OpenAI response)
    lines = content.split("\n")
    recipe = {
        "title": "Example Title",
        "description": "Example description",
        "ingredients": ["Ingredient 1", "Ingredient 2"],
        "steps": ["Step 1", "Step 2"],
        "image_prompt": "Example image prompt",
    }
    return recipe

def generate_image(prompt):
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "image-alpha-001",
        "prompt": prompt,
        "n": 1,
        "size": "1024x1024",
    }
    response = requests.post("https://api.openai.com/v1/images/generations", json=payload, headers=headers)
    response.raise_for_status()

    image_url = response.json()["data"][0]["url"]
    return image_url

def upload_to_sanity(recipe, image_url):
    # Step 1: Upload the recipe
    payload = {
        "mutations": [
            {
                "create": {
                    "_type": "smoothie",
                    "title": recipe["title"],
                    "description": recipe["description"],
                    "ingredients": recipe["ingredients"],
                    "steps": recipe["steps"],
                }
            }
        ]
    }

    url = f"https://{SANITY_PROJECT_ID}.api.sanity.io/v1/data/mutate/{SANITY_DATASET}"
    headers = {
        "Authorization": f"Bearer {SANITY_WRITE_TOKEN}",
        "Content-Type": "application/json",
    }

    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()

    # Get the created document ID
    document_id = response.json()["results"][0]["id"]

    # Step 2: Upload the image
    image_data = requests.get(image_url).content
    files = {"file": image_data}
    image_upload_url = f"https://{SANITY_PROJECT_ID}.api.sanity.io/v1/assets/images/{SANITY_DATASET}"
    image_response = requests.post(image_upload_url, files=files, headers={"Authorization": f"Bearer {SANITY_WRITE_TOKEN}"})
    image_response.raise_for_status()

    # Get the uploaded image asset ID
    asset_id = image_response.json()["document"]["_id"]

    # Step 3: Attach the image to the document
    patch_payload = {
        "mutations": [
            {
                "patch": {
                    "id": document_id,
                    "set": {
                        "image": {"_type": "image", "asset": {"_ref": asset_id}},
                    },
                }
            }
        ]
    }
    patch_response = requests.post(url, json=patch_payload, headers=headers)
    patch_response.raise_for_status()

if __name__ == "__main__":
    recipe = fetch_recipe_from_openai()
    image_url = generate_image(recipe["image_prompt"])
    upload_to_sanity(recipe, image_url)
