import configparser
import logging
import re
import tempfile
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any

import uvicorn
from PyPDF2 import PdfReader
from anthropic import Anthropic
from fastapi import BackgroundTasks, FastAPI  # Updated import for FastAPI
from pyzotero import zotero

# Load the configuration file
config = configparser.ConfigParser()  # Create a ConfigParser object
config.read('config.ini')  # Read the config.ini file

MODEL_NAME = config.get('general', 'model_name')
ZOTERO_API_KEY = config.get('zotero', 'api_key')
ZOTERO_USER_ID = config.getint('zotero', 'user_id')
ZOTERO_TODO_TAG_NAME = config.get('zotero', 'todo_tag_name')
ZOTERO_SUMMARIZED_TAG_NAME = config.get('zotero', 'summarized_tag_name')
ZOTERO_DENY_TAG_NAME = config.get('zotero', 'deny_tag_name')
ZOTERO_ERROR_TAG_NAME = config.get('zotero', 'error_tag_name')
FILE_BASE_PATH = config.get('zotero', 'file_path')
API_KEY = config.get('claude', 'api_key')

app = FastAPI()  # Create a FastAPI instance


def setup_logger():
    """
    Setup Logger

    This method sets up a logger for the "Clautero" application.

    :return: A logger instance configured with console and file handlers.
    """
    # create logger
    _logger = logging.getLogger("Clautero")
    _logger.setLevel(logging.DEBUG)  # set logger level

    # create console handler and set level to debug
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)

    # create file handler and set level to debug
    file_handler = logging.FileHandler("application.log")
    file_handler.setLevel(logging.DEBUG)

    # create formatter
    standard_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

    # add formatter to handlers
    console_handler.setFormatter(standard_formatter)
    file_handler.setFormatter(standard_formatter)

    # add handlers to logger
    _logger.addHandler(console_handler)
    _logger.addHandler(file_handler)

    return _logger


zot = zotero.Zotero(ZOTERO_USER_ID, "user", ZOTERO_API_KEY)
logger = setup_logger()


def unzip_pdf(zip_file_name):
    """
    Unzips a PDF file from the given zip file.

    :param zip_file_name: The name of the zip file containing the PDF.
    :return: The path of the extracted PDF file, stored as a temporary file.
    """
    # Open the zip file in read mode
    with zipfile.ZipFile(zip_file_name, 'r') as zip_ref:
        # Extract the name of the pdf file
        for name in zip_ref.namelist():
            if name.endswith('.pdf'):
                pdf_file_name = name
                break
        else:
            return None
        # Read the pdf file into memory
        pdf_file_data = zip_ref.read(pdf_file_name)
    # Write the pdf file data to a temporary file
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp:
        temp.write(pdf_file_data)
        temp_path = temp.name
    return temp_path


def get_file_path(attachment_key):
    """
    Get the file path for a given attachment.

    :param attachment_key: The key of the attachment.
    :return: The file path for the attachment.
    """
    return Path(f"zotero/{attachment_key}.zip")


def key_exists_and_not_none(dictionary: dict, dict_key: Any) -> bool:
    """
    Check if a key exists in a dictionary and its value is not None.

    :param dictionary: The dictionary to check.
    :param dict_key: The key to check in the dictionary.
    :return: True if the key exists and its value is not None, False otherwise.
    """
    return dictionary.get(dict_key) is not None


def write_note(parent_id: str, note_text: str) -> None:
    """
    Write a note to a Zotero item.

    :param parent_id: ID of the parent item to which the note should be attached.
    :param note_text: Text of the note to be added.
    :return: None
    """
    template = zot.item_template("note")
    template["tags"] = [{"tag": MODEL_NAME},
                        {"tag": ZOTERO_SUMMARIZED_TAG_NAME}]
    template["note"] = note_text.replace("\n", "<br>")
    zot.create_items([template], parent_id)


def set_error_tag(item_id: str, tag_name: str) -> None:
    """
    Set the error tag for a given item in Zotero.

    :param item_id: The ID of the item.
    :param tag_name: The name of the error tag to be set.
    :return: None
    """
    logger.info(f"Setting error tag for item {item_id}")
    item_to_update = zot.item(item_id)
    tags = item_to_update["data"]["tags"]
    tags.extend([{"tag": tag_name}])
    item_to_update["data"]["tags"] = tags
    zot.update_item(item_to_update)


def remove_todo_tag(item_id: str) -> None:
    """
    :param item_id: The unique identifier of the item to update.
    :return: None
    """
    logger.info(f"Updating tags for item {item_id}")
    item_to_update = zot.item(item_id)
    tags = item_to_update["data"]["tags"]
    if {"tag": ZOTERO_TODO_TAG_NAME} in tags:
        tags.remove({"tag": ZOTERO_TODO_TAG_NAME})
    elif {"tag": ZOTERO_TODO_TAG_NAME, "type": 1} in tags:
        tags.remove({"tag": ZOTERO_TODO_TAG_NAME, "type": 1})
    item_to_update["data"]["tags"] = tags
    zot.update_item(item_to_update)


def update_tags(item_id):
    """
    Update tags for the specified Zotero item.

    :param item_id: The ID of the item to update.
    """
    logger.info(f"Updating tags for item {item_id}")
    item_to_update = zot.item(item_id)
    tags = item_to_update["data"]["tags"]
    if {"tag": ZOTERO_TODO_TAG_NAME} in tags:
        tags.remove({"tag": ZOTERO_TODO_TAG_NAME})
    elif {"tag": ZOTERO_TODO_TAG_NAME, "type": 1} in tags:
        tags.remove({"tag": ZOTERO_TODO_TAG_NAME, "type": 1})
    tags.extend([{"tag": ZOTERO_SUMMARIZED_TAG_NAME}])
    item_to_update["data"]["tags"] = tags
    zot.update_item(item_to_update)


def add_todo_tag(item_id):
    """
    Add the TODO tag to the specified Zotero item.
    :param item_id: The ID of the item to update.
    """
    logger.info(f"Adding TODO tag for item {item_id}")
    item_to_update = zot.item(item_id)
    tags = item_to_update["data"]["tags"]
    tags.extend([{"tag": ZOTERO_TODO_TAG_NAME}])
    item_to_update["data"]["tags"] = tags
    zot.update_item(item_to_update)


def extract_text_from_pdf(pdf_data) -> str:
    """
    Extracts text from a byte-read PDF using PyPDF2.

    :param pdf_data: The byte-read PDF data.
    :return: The extracted text from the PDF.
    """
    try:
        # Create a BytesIO object from the PDF data
        pdf_buffer = BytesIO(pdf_data)

        # Create a PDF reader object
        pdf_reader = PdfReader(pdf_buffer)

        # Initialize an empty string to store the extracted text
        extracted_text = ""

        # Iterate over each page of the PDF
        for page in pdf_reader.pages:
            # Extract the text from the page
            page_text = page.extract_text()

            # Append the page text to the extracted text
            extracted_text += page_text

        return extracted_text
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
        return None


def get_summary_file(item_name, pdf_file_name):
    """
    :param item_name: The name of the item to be summarized.
    :param pdf_file_name: The name of the PDF file to be attached.
    :return: The summarized text of the item.
    """
    client = Anthropic(api_key=API_KEY)

    try:
        logger.info(f"Sending {item_name} to Claude for summarization")
        with open("prompt.txt", "r") as f:
            prompt = f.read()
        with open(pdf_file_name, "rb") as f:
            pdf_data = f.read()
        prompt = prompt.replace("{{PAPER}}", extract_text_from_pdf(pdf_data))
        message = client.messages.create(
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            model=MODEL_NAME,
        )
        assistant_response = message.content[0].text
        assistant_response = assistant_response.replace("•", "-")
        pattern = r'<summary>(.*?)</summary>'
        match = re.search(pattern, assistant_response, re.DOTALL)
        if match:
            extracted_text = match.group(1)
            return extracted_text
        else:
            raise Exception("No summary found inside <summary> tags.")
        # lines = assistant_response.splitlines()
        # for i, line in enumerate(lines):
        #     if line.startswith('-'):
        #         return '\n'.join(lines[i:])
    except Exception as e:
        logger.error(f"Error summarizing {item_name}: {e}")
        return None


def summarize_all_docs():
    """
    Summarize all documents in Zotero that have the TODO tag.
    """
    items = zot.top(tag=[ZOTERO_TODO_TAG_NAME, f"-{ZOTERO_ERROR_TAG_NAME}", f"-{ZOTERO_DENY_TAG_NAME}"], limit=50)
    logger.info(f"Found {len(items)} items to summarize")
    for item in items:
        key = item["data"]["key"]
        if not key_exists_and_not_none(item["data"], "title"):
            logger.warning(f"Skipping item {key} because it has no title")
            set_error_tag(key, ZOTERO_ERROR_TAG_NAME)
            continue
        logger.info(f"Searching attachments for {item['data']['title']} [{key}]")
        zot_children = zot.children(key)
        logger.info(f"Found {len(zot_children)} attachments for {item['data']['title']} [{key}]")
        if len(zot_children) == 0:
            logger.error(f"No attachments for {item['data']['title']} [{key}]")
            set_error_tag(key, ZOTERO_ERROR_TAG_NAME)
            continue
        pdf_items = [child for child in zot_children if child.get('data', {}).get('contentType') == 'application/pdf']
        first_pdf_item = pdf_items[0] if pdf_items else None
        if first_pdf_item is None:
            logger.error(f"No PDF attachment found for item {key}, skipping.")
            set_error_tag(key, ZOTERO_DENY_TAG_NAME)
            continue
        children_key = first_pdf_item["key"]
        pdf_temp_path = unzip_pdf(get_file_path(children_key))

        if pdf_temp_path is None:
            logger.error(f"Could not find a PDF for item {key} in the path, skipping.")
            set_error_tag(key, ZOTERO_ERROR_TAG_NAME)
            continue
        if not 5 <= len(PdfReader(pdf_temp_path).pages) <= 60:
            logger.error(f"PDF length is out of bounds, skipping.")
            set_error_tag(key, ZOTERO_DENY_TAG_NAME)
            remove_todo_tag(key)
            continue

        summary = get_summary_file(str(pdf_temp_path), pdf_temp_path)
        text = f"Summary\n\n{summary}"
        if summary is None:
            logger.error(f"Could not summarize item {key}, skipping.")
            set_error_tag(key, ZOTERO_ERROR_TAG_NAME)
            continue
        write_note(key, text)
        update_tags(key)


def add_missing_tags():
    """
    Add the TODO tag to all items that are missing it.
    """
    items = zot.top(tag=[f"-{ZOTERO_TODO_TAG_NAME}",
                         f"-{ZOTERO_SUMMARIZED_TAG_NAME}",
                         f"-{ZOTERO_ERROR_TAG_NAME}",
                         f"-{ZOTERO_DENY_TAG_NAME}"], limit=50)
    for item in items:
        add_todo_tag(item["data"]["key"])


@app.get('/ping/')
def ping():
    """Endpoint to check if the server is running."""
    return {"status": "Server is up and running!"}


@app.get('/add_missing_tags/')
def fastapi_add_missing_tags():
    """Endpoint to run add_missing_tags function."""
    try:
        add_missing_tags()
        return {"status": "Tags added successfully!"}
    except Exception as e:
        return {"status": "Error", "message": str(e)}


@app.get('/summarize/')
def summarize(background_tasks: BackgroundTasks):  # Added BackgroundTasks parameter
    """Endpoint to run summarize_all_docs function in the background."""
    background_tasks.add_task(summarize_all_docs)  # Run the function in the background
    return {"status": "started summary"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)  # Run the FastAPI app using uvicorn
